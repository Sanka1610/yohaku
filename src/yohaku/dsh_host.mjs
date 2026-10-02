import { AsyncLocalStorage } from 'node:async_hooks';
import { createHash, randomUUID } from 'node:crypto';

const RECEIPT_PROFILE = 'messages-plain-text-owner-no-retry';
const hash = text => createHash('sha256').update(text).digest('hex');
const freeze = value => {
  if (value && typeof value === 'object') {
    Object.values(value).forEach(freeze);
    Object.freeze(value);
  }
  return value;
};
const deferred = () => {
  const result = Promise.withResolvers();
  result.promise.catch(() => {}); // Cancellation can precede the owner's wait.
  return result;
};
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);

/** DSH-specific same-process service wiring for the fresh, no-tool owner.
 * Mount stock BasicCompaction auto:false before attaching. The embedding owner
 * serializes calls; no alternate writer, global freeze or restart is covered.
 * Transport to Python, if needed, belongs to that embedding host.
 */
export class DshNativeHost {
  constructor(ctx, agent, { version, createUserMessage }) {
    if (version !== '0.2.0-rc.2' || agent.session.seq !== 0) {
      throw new Error('DSH host requires the pinned fresh Session');
    }
    this.ctx = ctx;
    this.agent = agent;
    this.version = version;
    this.createUserMessage = createUserMessage;
    this.session_id = agent.id;
    this.events = [];
    this.workCount = this.requestCount = 0;
    this.stopped = false;
    this.disposers = [ctx.on('session/event', (session, event) => {
      if (session.id === this.session_id) {
        this.events.push(structuredClone({ sessionId: session.id, ...event }));
      }
    })];
  }

  async observe() {
    if (this.stopped) throw new Error('DSH owner stopped; no retry');
    await this.agent.whenIdle();
    const a = this.agent;
    return {
      sessionId: a.id, seq: a.session.seq, settled: true, status: a.status,
      nextTurn: a.inbox.nextTurn.map(x => x.id),
      nextStep: a.inbox.nextStep.map(x => x.id),
      lastTurnEnd: this.events.findLast(e => e.type === 'turn/end')?.data ?? {},
    };
  }

  async work(prompt) {
    const before = await this.observe();
    if (this.workCount || this.requestCount || before.status !== 'idle'
        || before.nextTurn.length || before.nextStep.length) {
      throw new Error('DSH profile allows one foreground turn');
    }
    this.workCount = 1;
    try {
      this.agent.followup(this.createUserMessage({
        content: [{ type: 'text', text: prompt }], source: { kind: 'user' },
      }));
      return await this.observe();
    } catch (error) {
      this.stopped = true;
      throw error;
    }
  }

  async compact(requestSeq, preSeq) {
    const before = await this.observe();
    if (this.requestCount || requestSeq !== 1 || this.workCount !== 1
        || preSeq !== before.seq || before.status !== 'idle'
        || before.nextTurn.length || before.nextStep.length) {
      throw new Error('DSH native request is stale, busy or already consumed');
    }
    this.requestCount = 1;
    try {
      // Native runMaintenance reserves the owned idle driver and queued input.
      const result = await this.ctx.compaction.compactNow(
        this.agent, new AbortController().signal);
      if (!result) throw new Error('DSH produced no native transition');
      const events = this.events.filter(e => e.seq >= preSeq && (
        e.type.startsWith('compaction/')
        || e.data?.source?.kind === 'compact-checkpoint'));
      await this.ctx.sessions.flush(this.agent.session);
      const handle = await this.ctx.sessionPersistence.open(this.session_id, 'read');
      let readback;
      try { readback = await handle.read(); }
      finally { await handle.close(); }
      return structuredClone({
        requestSeq, preSeq, result, events, flushed: true,
        readbackSessionId: this.session_id, readbackEvents: readback.events,
      });
    } catch (error) {
      this.stopped = true;
      throw error;
    }
  }

  async project() {
    const current = await this.observe();
    return structuredClone({ sessionId: current.sessionId, seq: current.seq,
      messages: this.agent.session.deriveMessages() });
  }


  enableReceipt({ provider, adapter, DeepSeekAdapter, options, observeCurrent }) {
    if (this.receipt_profile || this.workCount || this.agent.session.seq !== 0
        || !(adapter instanceof DeepSeekAdapter) || options.retryPolicy?.maxRetries !== 0
        || typeof observeCurrent !== 'function' || !provider) {
      throw new Error('receipt requires a fresh official Messages owner with retry disabled');
    }
    this.receipt_profile = RECEIPT_PROFILE;
    this.receiptProvider = provider;
    this.receiptOptions = options;
    this.observeCurrent = observeCurrent;
    this.epoch = randomUUID(); // Host-local identity, never a native HTTP attempt ID.
    this.actualAttempts = this.nativeCalls = this.freshRevision = this.frameRevision = 0;
    this.nativeContext = new AsyncLocalStorage();
    this.gateReady = deferred();
    this.receiptDone = deferred();
    this.disposers.push(this.ctx.on('agent/assistant-stream', ({ agent, frame }) => {
      if (agent !== this.agent) return;
      if (frame.revision <= this.frameRevision
          || !frame.attemptId.startsWith(this.session_id + ':')
          || (frame.type !== 'start' && frame.attemptId !== this.latestStart?.attemptId)) {
        this.invalidate_receipt('late or foreign native observation');
        return;
      }
      this.frameRevision = frame.revision;
      if (frame.type === 'start') {
        if (this.candidate) this.invalidate_receipt('another native attempt');
        this.latestStart = structuredClone(frame);
      }
      if (frame.type === 'end' && this.candidate?.binding.nativeAttemptId === frame.attemptId) {
        this.invalidate_receipt('native attempt ended');
      }
    }));
    this.disposers.push(this.ctx.on('session/event', (session, event) => {
      if (session.id === this.session_id && this.delivery
          && (event.type.startsWith('llm/retry') || event.type === 'turn/end')) {
        this.invalidate_receipt(event.type);
      }
    }));
    this.disposers.push(this.ctx.on('agent/disposed', ({ agent }) => {
      if (agent === this.agent) this.invalidate_receipt('owner loss');
    }));
    const host = this;
    this.disposers.push(this.ctx.on('llm/stream', async function* (options, next) {
      if (!host.delivery) { yield* next(); return; }
      try {
        const d = host.delivery, start = host.latestStart;
        if (!host.receiptStarted || host.stopped || host.nativeCalls || !Object.isFrozen(options)
            || options.sessionId !== host.session_id || options.provider !== host.receiptProvider
            || options.purpose !== undefined || options.tools?.length || options.toolHistory?.length
            || options.messages.some(m => m.content.some(b => b.type !== 'text'))
            || !start || `${host.session_id}:${start.turn}` !== d.turnId || start.step !== 1) {
          throw new Error('request left the qualified one-attempt plain-text profile');
        }
        const members = options.messages.filter(m => m.id === d.messageId);
        if (members.length !== 1 || !same(members[0].content, host.handoffMessage.content)) {
          throw new Error('native handoff MessageId or exact payload mismatch');
        }
        const binding = { sessionId: host.session_id, messageId: d.messageId,
          handoffId: d.handoffId, turnId: d.turnId, turn: start.turn, step: start.step,
          nativeAttemptId: start.attemptId, nativeCall: ++host.nativeCalls,
          nativeSeq: host.agent.session.seq, handoffHash: d.handoffHash };
        const iterator = next()[Symbol.asyncIterator]();
        try {
          while (true) {
            const result = await host.nativeContext.run(binding, () => iterator.next());
            if (result.done) return;
            yield result.value;
          }
        } finally {
          if (iterator.return) await host.nativeContext.run(binding, () => iterator.return());
        }
      } catch (error) {
        host.invalidate_receipt(error.message);
        throw error;
      }
    }));
    this.disposers.push(this.ctx.deepseekLlmApiExtensions.register('yohaku_receipt_gate', {
      prepare: request => this._receiptGate(request),
    }));
  }

  async prepareExtensions(request) {
    // Wire this method ONLY to the official adapter's prepareExtensions option.
    const prepared = await this.ctx.deepseekLlmApiExtensions.prepare(request);
    if (Object.keys(prepared.fields).length) {
      this.invalidate_receipt('additional extension fields');
      throw new Error('receipt profile requires empty extension fields');
    }
    if (!this.delivery) return prepared;
    const c = this.candidate;
    if (!this._currentCandidate(c) || !c.authorized) throw new Error('invalid receipt release');
    return { fields: prepared.fields, accept: async () => {
      // Official adapter invokes this after HTTP success, before translating SSE.
      // No assistant content or model acknowledgment is receipt proof.
      if (!this._currentCandidate(c) || !c.authorized || c.accepted) {
        throw new Error('late or duplicate HTTP acceptance');
      }
      await prepared.accept();
      if (!this._currentCandidate(c)) throw new Error('receipt invalidated during acceptance');
      c.accepted = true;
      this.receiptEvidence = freeze({ profile: RECEIPT_PROFILE,
        binding: structuredClone(c.binding), freshRevision: c.fresh.revision,
        authorization: 'one-shot', result: 'http-accepted' });
      this.receiptDone.resolve(this.receiptEvidence);
    } };
  }

  async reserve_receipt() {
    const native = await this.observe();
    if (!this.receipt_profile || this.delivery || this.receiptTarget || this.requestCount !== 1
        || native.status !== 'idle' || native.nextTurn.length || native.nextStep.length
        || !Number.isSafeInteger(native.lastTurnEnd.turn)) throw new Error('receipt target unavailable');
    const turn = native.lastTurnEnd.turn + 1;
    this.receiptTarget = { sessionId: this.session_id, turnId: `${this.session_id}:${turn}`, turn };
    // Expected next turn from the public lifecycle; actual start must confirm it.
    return structuredClone(this.receiptTarget);
  }

  async _directRead() {
    const seq = this.agent.session.seq;
    await this.ctx.sessions.flush(this.agent.session);
    const handle = await this.ctx.sessionPersistence.open(this.session_id, 'read');
    let log;
    try { log = await handle.read(); } finally { await handle.close(); }
    const current = structuredClone(await this.observeCurrent());
    if (this.stopped || this.agent.id !== this.session_id || this.agent.session.id !== this.session_id
        || seq !== this.agent.session.seq || log.events.length !== seq) {
      throw new Error('fresh direct Session read changed');
    }
    return { sessionId: this.session_id, seq, status: this.agent.status,
      settled: this.agent.status === 'idle', current, readbackEvents: log.events };
  }

  async deliver_handoff(handoffId, turnId, text) {
    const native = await this.observe();
    if (!this.receiptTarget || this.delivery || turnId !== this.receiptTarget.turnId
        || !handoffId || typeof text !== 'string' || !text.includes(handoffId)
        || native.status !== 'idle' || native.nextTurn.length || native.nextStep.length) {
      throw new Error('one reserved same-Session handoff required');
    }
    const message = this.createUserMessage({ source: { kind: 'user' },
      content: [{ type: 'text', text }] });
    this.handoffMessage = freeze(message);
    // Consume the delivery slot BEFORE I/O. No re-injection after uncertain flush.
    this.delivery = { sessionId: this.session_id, handoffId, turnId,
      messageId: message.id, handoffHash: hash(text) };
    try {
      this.agent.inject(message);
      const fresh = await this._directRead();
      const inserted = fresh.readbackEvents.filter(e => e.type === 'agent/inbox/spliced')
        .flatMap(e => e.data.inserted ?? []).filter(m => m.id === message.id);
      if (!same(inserted, [message]) || this.agent.status !== 'idle'
          || this.agent.inbox.nextTurn.length || !same(this.agent.inbox.nextStep.map(m => m.id), [message.id])
          || this.agent.session.deriveMessages().some(m => m.id === message.id)) {
        throw new Error('non-waking durable inbox delivery mismatch');
      }
      return { ...this.delivery, nonWaking: true, durable: true, seq: fresh.seq };
    } catch (error) { this.invalidate_receipt(error.message); throw error; }
  }

  async start_receipt_request() {
    if (!this.delivery || this.receiptStarted || this.stopped) throw new Error('receipt request unavailable');
    this.receiptStarted = true;
    this.agent.followup(this.createUserMessage({ source: { kind: 'user' }, content: [{ type: 'text',
      text: 'Receipt inspection only. Do not continue the task or execute recovered actions.' }] }));
    return this.gateReady.promise;
  }

  async _receiptGate(request) {
    if (!this.delivery) return undefined;
    try {
      const native = this.nativeContext.getStore();
      const text = this.handoffMessage.content[0].text;
      if (!native || this.stopped || this.candidate || this.actualAttempts
          || request.sessionId !== this.session_id || request.purpose !== undefined
          || this.receiptOptions.retryPolicy?.maxRetries !== 0
          || request.body.tools?.length || request.body.messages.some(m =>
            m.content.some(b => b.type !== 'text'))) throw new Error('unqualified serialized gate');
      freeze(request.body);
      const texts = request.body.messages.flatMap(m => m.content.map(b => b.text));
      if (texts.filter(t => t === text).length !== 1 || hash(text) !== native.handoffHash) {
        throw new Error('serialized exact handoff incorporation mismatch');
      }
      const binding = freeze({ ...native, profile: RECEIPT_PROFILE,
        hostEpoch: this.epoch, hostAttempt: ++this.actualAttempts,
        bodyHash: hash(JSON.stringify({ ...request.body })) });
      const c = { binding, body: request.body, signal: request.signal, release: deferred(),
        invalid: false, authorized: false, accepted: false };
      this.candidate = c;
      const onAbort = () => this.invalidate_receipt('abort');
      request.signal.addEventListener('abort', onAbort, { once: true });
      this.disposers.push(() => request.signal.removeEventListener('abort', onAbort));
      if (request.signal.aborted) onAbort();
      if (!this._currentCandidate(c)) throw new Error('gate aborted before observation');
      this.gateReady.resolve(structuredClone(binding));
      await c.release.promise;
      if (!this._currentCandidate(c) || !c.authorized) throw new Error('late authorization rejected');
      return undefined; // Gate contributes no extra DeepSeek field.
    } catch (error) { this.invalidate_receipt(error.message); throw error; }
  }

  _currentCandidate(c) {
    return c && c === this.candidate && !this.stopped && !c.invalid && !c.signal.aborted
      && this.agent.id === c.binding.sessionId && this.agent.session.id === c.binding.sessionId
      && this.latestStart?.attemptId === c.binding.nativeAttemptId
      && this.receiptOptions.retryPolicy?.maxRetries === 0
      && hash(this.handoffMessage.content[0].text) === c.binding.handoffHash
      && hash(JSON.stringify({ ...c.body })) === c.binding.bodyHash;
  }

  async fresh_receipt() {
    const c = this.candidate;
    if (!this._currentCandidate(c) || c.authorized) throw new Error('fresh receipt candidate unavailable');
    try {
      const fresh = await this._directRead();
      const members = fresh.readbackEvents.filter(e => e.type === 'user/message'
        && e.data.id === c.binding.messageId);
      if (!this._currentCandidate(c) || fresh.status !== 'running'
          || fresh.seq < c.binding.nativeSeq || members.length !== 1
          || !same(members[0].data.content, this.handoffMessage.content)) {
        throw new Error('gate direct read is stale or has wrong MessageId');
      }
      delete fresh.readbackEvents; // Keep the durable native log in DSH, not receipt metadata.
      fresh.revision = `${this.epoch}:${++this.freshRevision}`; // Host observation revision.
      c.fresh = freeze(fresh);
      return structuredClone(fresh);
    } catch (error) { this.invalidate_receipt(error.message); throw error; }
  }

  async authorize_receipt(binding, fresh) {
    const c = this.candidate;
    if (!this._currentCandidate(c) || c.authorized || !same(binding, c.binding)
        || !c.fresh || !same(fresh, c.fresh)) {
      this.invalidate_receipt('wrong or duplicate receipt authorization');
      throw new Error('wrong or duplicate receipt authorization');
    }
    const current = await this.observeCurrent();
    if (!this._currentCandidate(c) || c.authorized || this.agent.session.seq !== fresh.seq
        || !same(current, fresh.current)) {
      this.invalidate_receipt('state changed before authorization');
      throw new Error('stale receipt authorization');
    }
    c.authorized = true;
    c.release.resolve();
    return this.receiptDone.promise;
  }

  invalidate_receipt(reason) {
    if (this.candidate) {
      this.candidate.invalid = true;
      this.candidate.release.reject(new Error(reason));
    }
    this.stopped = true;
    this.gateReady?.reject(new Error(reason));
    this.receiptDone?.reject(new Error(reason));
    if (this.delivery) this.agent.cancel({ kind: 'hook', reason }, { keepInbox: true });
  }

  async dispose() {
    this.invalidate_receipt('host disposal');
    for (const dispose of this.disposers.splice(0)) await dispose();
  }
}
