// Opt-in native owner callbacks; no launcher, transport or inferred task success.
import { DshForegroundHost, valueHash } from './dsh_foreground.mjs';

export class DshForegroundNativeOwner {
  constructor(ctx, agent, { foreground, version, toolKinds, effectScope } = {}) {
    if (version !== '0.2.0-rc.2' || !(foreground instanceof DshForegroundHost)
        || foreground.agent !== agent || agent?.session?.seq !== 0 || agent.status !== 'idle'
        || agent.id !== agent.session.id || !foreground.quiescent || foreground.disposers.length === 0
        || agent.inbox.nextTurn.length || agent.inbox.nextStep.length
        || typeof ctx.compaction?.compactNow !== 'function' || typeof ctx.sessions?.flush !== 'function'
        || typeof ctx.sessionPersistence?.open !== 'function' || typeof agent.whenIdle !== 'function') {
      throw new Error('fresh pinned native Agent and attached foreground/services required');
    }
    this.ctx = ctx; this.agent = agent; this.work = foreground;
    this.taxonomy = structuredClone({ toolKinds, effectScope });
    this.events = []; this.latestStart = null; this.frameRevision = 0;
    this.taskAnchor = null; this.seenAttempts = new Set();
    this.activeAttempt = false; this.requestInput = null; this.requestConsumed = false;
    this.compactMode = null; this.requestSeq = 0; this.requestGeneration = 0;
    this.consumedRequestIds = new Set(); this.compactionIds = new Set();
    this.busy = false; this.stopped = false; this.settledSeq = 0;
    this.disposers = [ctx.on('session/event', (session, event) => {
      if (session !== this.agent.session) return;
      try {
        if (event.type.startsWith('llm/retry')) this.fail('native retry outside foreground owner');
        this.events.push(structuredClone({ sessionId: session.id, ...event }));
      } catch { this.stop(); }
    }), ctx.on('agent/assistant-stream', ({ agent: subject, frame }) => {
      if (subject !== this.agent) return;
      try {
        if (!Number.isSafeInteger(frame.revision) || frame.revision <= this.frameRevision
            || typeof frame.attemptId !== 'string' || !frame.attemptId.startsWith(this.agent.id + ':')
            || !['start', 'chunk', 'end'].includes(frame.type)
            || (frame.type === 'start' && (!Number.isSafeInteger(frame.turn) || frame.turn < 1
              || frame.turn <= this.work.returnedTurnFloor || this.seenAttempts.has(frame.attemptId)
              || !Number.isSafeInteger(frame.step) || frame.step < 1
              || (this.latestStart && (frame.turn < this.latestStart.turn
                || (frame.turn === this.latestStart.turn && frame.step <= this.latestStart.step)))))
            || (frame.type !== 'start' && (!this.activeAttempt || frame.attemptId !== this.latestStart?.attemptId))) {
          this.fail('late or foreign native frame');
        }
        this.frameRevision = frame.revision;
        if (frame.type === 'start') {
          if (this.activeAttempt) this.fail('overlapping native attempt');
          this.seenAttempts.add(frame.attemptId);
          this.latestStart = structuredClone(frame); this.activeAttempt = true; this.requestInput = null;
        } else if (frame.type === 'end') this.activeAttempt = false;
      } catch { this.stop(); }
    }), ctx.on('agent/disposed', ({ agent: subject }) => {
      if (subject === this.agent) this.stop();
    })];
  }
  stop() { this.stopped = true; this.work.stop(); }
  fail(reason) { this.stop(); throw new Error(reason); }
  ready() { if (this.stopped || this.work.stopped) this.fail('native foreground owner stopped'); }
  observe() {
    this.ready(); const a = this.agent, start = this.activeAttempt ? this.latestStart : null;
    return structuredClone({ sessionId: a.id, seq: a.session.seq, status: a.status,
      settled: !this.busy && !this.activeAttempt && a.status === 'idle' && a.session.seq === this.settledSeq,
      nextTurn: a.inbox.nextTurn.map(x => x.id), nextStep: a.inbox.nextStep.map(x => x.id),
      lastTurnEnd: this.events.findLast(e => e.type === 'turn/end')?.data ?? {},
      attempt: start ? { sessionId: a.id, turn: start.turn, step: start.step,
        attemptId: start.attemptId, frameRevision: start.revision,
        provider: a.options.provider, model: a.options.model } : null });
  }
  async settle() {
    this.ready();
    try { await this.agent.whenIdle(); } catch (error) { this.stop(); throw error; }
    this.ready();
    if (this.busy || this.activeAttempt || this.agent.status !== 'idle' || !this.work.quiescent
        || this.agent.inbox.nextTurn.length || this.agent.inbox.nextStep.length) {
      this.fail('whole native foreground activity not settled');
    }
    this.settledSeq = this.agent.session.seq;
    return this.observe();
  }
  observeRequest(options, { incorporatedResults = true } = {}) {
    this.ready(); const before = this.observe(), binding = before.attempt;
    if (!binding || this.requestInput || options?.sessionId !== before.sessionId
        || options.provider !== binding.provider || options.model !== binding.model
        || options.purpose !== undefined || !Object.isFrozen(options) || !Array.isArray(options.messages)) {
      this.fail('actual owned one-shot AgentLoop request required');
    }
    const messageHash = valueHash(options.messages);
    if (incorporatedResults) this.work.observeInput(options);
    if (valueHash(this.observe()) !== valueHash(before)) this.fail('native request changed during observation');
    this.requestInput = { binding, messageHash };
    this.requestMessages = options.messages;
    return structuredClone(this.requestInput);
  }
  assertInputMember(message) {
    this.ready();
    // Membership must be checked against the actual frozen request, not toolHistory.
    if (!this.activeAttempt || !this.requestMessages || !this.requestInput
        || valueHash(this.requestMessages) !== this.requestInput.messageHash
        || this.requestMessages.filter(m => m.id === message.id).length !== 1
        || valueHash(this.requestMessages.find(m => m.id === message.id)) !== valueHash(message)) {
      this.fail('native input membership missing or changed');
    }
  }
  closeGate() { this.ready(); return this.work.closeAdmission(); }
  openTask(mode, binding, bindingRecord, readTools) {
    this.ready(); const native = this.observe();
    try {
      if (mode !== 'fresh' && (!this.taskAnchor || valueHash(binding) !== valueHash(this.taskAnchor))) {
        this.fail('saved native task anchor required');
      }
      if (mode === 'work') {
        if (!native.settled || native.status !== 'idle' || native.attempt !== null
            || native.nextTurn.length || native.nextStep.length || !this.work.barrier
            || native.lastTurnEnd.reason?.kind !== 'completed' || native.lastTurnEnd.turn !== binding?.turn
            || binding?.provider !== this.agent.options.provider || binding?.model !== this.agent.options.model
            || !this.work.quiescent) {
          this.fail('closed settled completed previous native task required for work');
        }
      } else if (mode === 'action') {
        // The saved proof anchors the task; result incorporation uses a later observed request.
        const current = native.attempt;
        if (!current || !this.work.quiescent
            || ['sessionId', 'turn', 'provider', 'model'].some(key => current[key] !== this.taskAnchor[key])
            || current.step <= this.taskAnchor.step || current.frameRevision <= this.taskAnchor.frameRevision
            || current.attemptId === this.taskAnchor.attemptId
            || !this.requestInput || valueHash(this.requestInput.binding) !== valueHash(current)
            || !this.requestMessages || valueHash(this.requestMessages) !== this.requestInput.messageHash) {
          this.fail('unchanged observed later request in the anchored native task required');
        }
      } else if (this.taskAnchor || valueHash(native.attempt) !== valueHash(binding) || !this.work.quiescent) {
        this.fail('foreign/stale actual native task binding');
      }
      if (this.work.openBoundTask(mode, binding, { readTools, bindingRecord }) !== true) {
        this.fail('native task gate acknowledgement unknown');
      }
      if (mode === 'fresh') this.taskAnchor = structuredClone(binding);
      else if (mode === 'work') this.taskAnchor = null;
      return true;
    } catch (error) { this.stop(); throw error; }
  }
  history() { this.ready(); return this.work.observations(this.taxonomy); }
  project() {
    const native = this.observe();
    return structuredClone({ sessionId: native.sessionId, seq: native.seq,
      messages: this.agent.session.deriveMessages() });
  }
  async compact(requestSeq, preSeq, coreRequest) {
    this.ready(); const before = this.observe(), mode = coreRequest === undefined ? 'legacy' : 'core';
    if (this.compactMode !== null && this.compactMode !== mode) this.fail('mixed native compact modes');
    // Existing codec omits default origin; asdict keeps it. Both use the existing Request schema.
    if (mode === 'legacy') {
      if (requestSeq !== 1 || this.requestConsumed) this.fail('one legacy native compact required');
    } else if (!coreRequest || Object.getPrototypeOf(coreRequest) !== Object.prototype
        || (Object.hasOwn(coreRequest, 'origin') && coreRequest.origin !== 'controller')
        || coreRequest.thread_id !== before.sessionId
        || !['request_id', 'thread_id', 'transition_id', 'boundary_id', 'checkpoint_id', 'lease_id']
          .every(key => typeof coreRequest[key] === 'string' && coreRequest[key].trim())
        || !Number.isSafeInteger(coreRequest.rollover_generation) || coreRequest.rollover_generation < 1
        || coreRequest.rollover_generation <= this.requestGeneration
        || !Number.isSafeInteger(requestSeq) || requestSeq !== this.requestSeq + 1
        || this.consumedRequestIds.has(coreRequest.request_id)) {
      this.fail('fresh request-bound native compact required');
    }
    if (this.busy || !this.work.barrier || !this.work.quiescent
        || !before.settled || before.seq !== preSeq || before.nextTurn.length || before.nextStep.length
        || before.lastTurnEnd.reason?.kind !== 'completed') {
      this.fail('one current closed/settled native compact required');
    }
    // Consume existing Core authority before dispatch, including an unknown native outcome.
    this.compactMode = mode; this.requestConsumed = true; this.requestSeq = requestSeq;
    if (mode === 'core') {
      this.consumedRequestIds.add(coreRequest.request_id);
      this.requestGeneration = coreRequest.rollover_generation;
    }
    this.busy = true;
    try {
      const result = await this.ctx.compaction.compactNow(this.agent, new AbortController().signal);
      this.ready();
      if (!result || typeof result.compactionId !== 'string' || !result.compactionId.trim()
          || this.compactionIds.has(result.compactionId)) this.fail('missing or reused native compaction ID');
      this.compactionIds.add(result.compactionId);
      const events = this.events.filter(e => e.seq >= preSeq
        && (e.type.startsWith('compaction/') || e.data?.source?.kind === 'compact-checkpoint'));
      await this.ctx.sessions.flush(this.agent.session); this.ready();
      const handle = await this.ctx.sessionPersistence.open(this.agent.id, 'read');
      let readback;
      try { readback = await handle.read(); } finally { await handle.close(); }
      this.ready(); this.busy = false;
      const after = await this.settle();
      if (after.seq <= result.endSeq || !this.work.barrier) this.fail('native post-compact boundary changed');
      return structuredClone({ requestSeq, preSeq, result, events, flushed: true,
        readbackSessionId: this.agent.id, readbackEvents: readback.events });
    } catch (error) { this.busy = false; this.stop(); throw error; }
  }
  dispose() {
    this.ready();
    const observed = this.observe();
    if (this.busy || this.activeAttempt || !observed.settled || !this.work.quiescent
        || observed.nextTurn.length || observed.nextStep.length) {
      this.fail('native owner not settled for callback disposal');
    }
    this.work.dispose();
    for (const dispose of this.disposers.splice(0).reverse()) dispose();
    this.stopped = true;
  }
}
