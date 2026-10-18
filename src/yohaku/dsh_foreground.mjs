// Opt-in, owner-local DSH gate. Native lifecycle/Core/recovery wiring is NOT qualified.
import { createHash } from 'node:crypto';

export function valueHash(value) {
  const encode = v => {
    if (v === null || typeof v === 'string' || typeof v === 'boolean') return v;
    if (typeof v === 'number' && Number.isFinite(v)) return v;
    if (Array.isArray(v)) return v.map(encode);
    if (v && Object.getPrototypeOf(v) === Object.prototype) {
      return Object.fromEntries(Object.keys(v).sort().map(k => [k, encode(v[k])]));
    }
    throw new Error('lossless JSON observation required');
  };
  return createHash('sha256').update(JSON.stringify(encode(value))).digest('hex');
}

/** Gate callbacks supply actual current task facts, never native IDs synthesized from time.
 * Every tools/result callback catches its own fault and latches stop: native emit catches
 * observer failures. No return/result/message alone proves physical execution completion.
 */
export class DshForegroundHost {
  constructor(ctx, agent, { enabled = false, tools, observeCurrent, authorize,
      retryPolicy, bashPolicy } = {}) {
    if (!agent?.session || agent.session.seq !== 0 || !Array.isArray(tools) || !tools.length
        || new Set(tools).size !== tools.length || tools.some(n => typeof n !== 'string' || !n.trim()
          || ['run_code', 'subagent', 'job_wait', 'job_kill'].includes(n))
        || typeof observeCurrent !== 'function' || typeof authorize !== 'function'
        || retryPolicy?.maxRetries !== 0 || bashPolicy?.enableRunInBackground !== false
        || bashPolicy?.promoteOnTimeout !== false) {
      throw new Error('fresh owner, declared tools and foreground/no-retry policies required');
    }
    this.ctx = ctx; this.agent = agent; this.enabled = enabled === true;
    this.names = new Set(tools); this.observeCurrent = observeCurrent; this.authorize = authorize;
    this.stopped = false; this.barrier = false; this.preparing = false;
    this.recoveryMode = null; this.boundTurn = null; this.readNames = new Set(); this.returnedTurnFloor = 0;
    this.calls = new Map(); this.records = new Map(); this.seen = new Set(); this.disposers = [];
  }
  stop() { this.stopped = true; this.barrier = true; }
  fail(reason) { this.stop(); throw new Error(reason); }
  ready() {
    if (!this.enabled || this.stopped || this.barrier) this.fail('foreground owner closed');
  }
  attach() {
    this.ready();
    if (this.disposers.length) this.fail('foreground gate already attached');
    const scope = this.agent.ctx;
    if (!scope?.tools?.guard || typeof scope.on !== 'function') this.fail('native agent-scoped gate unavailable');
    try {
      this.disposers.push(scope.tools.guard(exec => {
        try { this.guard(exec); return undefined; }
        catch { this.stop(); return 'Yohaku foreground admission unavailable'; }
      }));
      this.disposers.push(scope.on('tools/pre-execute', (exec, next) => this.prepare(exec, next)));
      this.disposers.push(scope.on('tools/execute', (exec, next) => this.execute(exec, next)));
      this.disposers.push(scope.on('tools/result', (exec, result) => {
        try { this.finalResult(exec, result); } catch { this.stop(); }
      }));
      this.disposers.push(this.ctx.on('session/event', (session, event) => {
        if (session !== this.agent.session) return;
        try { this.observeEvent(event); } catch { this.stop(); }
      }));
    } catch (error) { this.stop(); throw error; }
  }
  observeEvent(event) {
    if (!['tool/call', 'tool/result'].includes(event.type)) return;
    this.ready();
    if (event.type === 'tool/call') {
      const d = event.data;
      if (!Number.isSafeInteger(event.seq) || !Number.isSafeInteger(d?.turn) || d.turn < 1
          || d.turn <= this.returnedTurnFloor || !Number.isSafeInteger(d.step) || d.step < 1 || typeof d.callId !== 'string'
          || !d.callId.trim() || this.calls.has(d.callId) || this.calls.size >= 256) {
        this.fail('missing/duplicate native tool call');
      }
      const args = typeof d.arguments === 'string' ? JSON.parse(d.arguments || '{}') : d.arguments;
      this.calls.set(d.callId, { seq: event.seq, turn: d.turn, step: d.step,
        name: d.name, argsHash: valueHash(args) });
    } else if (event.type === 'tool/result') {
      const message = event.data?.message, record = this.records.get(message?.toolCallId);
      if (!record || !record.resultHash || record.committedHash || !Number.isSafeInteger(event.seq)
          || event.seq <= record.call.seq || event.data.turn !== record.call.turn
          || event.data.step !== record.call.step || message.role !== 'tool'
          || message.source?.kind !== 'tool' || message.source.callId !== message.toolCallId
          || typeof message.id !== 'string' || !message.id.trim()
          || valueHash(event.sourceEventSeqs) !== valueHash([record.call.seq])
          || valueHash({ content: message.content, isError: message.isError === true }) !== record.resultHash) {
        this.fail('native final result/commit provenance missing or changed');
      }
      record.committedHash = valueHash(message); record.messageId = message.id;
    }
  }
  matching(exec) {
    this.ready();
    const call = this.calls.get(exec?.callId);
    if (exec?.agent !== this.agent || exec.parent !== undefined || exec.rootCallId !== exec.callId
        || typeof exec.token !== 'symbol'
        || !this.names.has(exec.name) || !call || call.name !== exec.name || call.turn <= this.returnedTurnFloor
        || call.argsHash !== valueHash(exec.arguments) || exec.signal?.aborted !== false
        || exec.arguments?.run_in_background === true || exec.arguments?.background === true) {
      this.fail('foreign/missing/nested native foreground execution');
    }
    if (this.boundTurn !== null && (call.turn !== this.boundTurn
        || (this.recoveryMode === 'fresh' && !this.readNames.has(exec.name)))) {
      this.fail('work before bound continuation or incorporated fresh read');
    }
    return call;
  }
  async prepare(exec, next) {
    const call = this.matching(exec);
    if (this.preparing || this.seen.has(exec.callId)
        || [...this.records.values()].some(r => !r.incorporated)
        || [...this.calls.keys()].some(id => id !== exec.callId && !this.records.get(id)?.incorporated)) {
      this.fail('parallel/duplicate/pending work');
    }
    this.preparing = true;
    try {
      const decision = await next();
      this.matching(exec);
      if (decision?.kind !== 'allow') this.fail('native admission denied');
      const current = await this.observeCurrent();
      if (typeof current?.logical_task_id !== 'string' || !current.logical_task_id.trim()
          || !Number.isSafeInteger(current.intent_revision) || current.intent_revision < 0
          || !Number.isSafeInteger(current.execution_revision) || current.execution_revision < 0
          || !Number.isSafeInteger(current.workspace?.revision) || current.workspace.revision < 0) {
        this.fail('current task observation is incomplete');
      }
      if (await this.authorize(exec, structuredClone(current)) !== true) this.fail('trusted admission denied');
      this.matching(exec);
      if (valueHash(await this.observeCurrent()) !== valueHash(current)) this.fail('task changed during admission');
      this.seen.add(exec.callId);
      this.records.set(exec.callId, { token: exec.token, call, nativeSeq: this.agent.session.seq,
        current: structuredClone(current),
        phase: 'admitted', resultHash: null, committedHash: null, terminal: false,
        incorporated: false, inputSeen: false });
      return decision;
    } catch (error) { this.stop(); throw error; }
    finally { this.preparing = false; }
  }
  guard(exec) {
    this.matching(exec);
    const record = this.records.get(exec.callId);
    if (!record || record.token !== exec.token || record.phase !== 'admitted'
        || record.nativeSeq !== this.agent.session.seq) this.fail('no current one-shot permit');
  }
  async execute(exec, next) {
    this.guard(exec);
    const record = this.records.get(exec.callId);
    record.phase = 'executing';
    try {
      const result = await next();
      this.ready(); record.phase = 'returned';
      return result; // Provisional: finalizers may still change native content.
    } catch (error) { this.stop(); throw error; }
  }
  finalResult(exec, result) {
    this.matching(exec);
    const record = this.records.get(exec.callId);
    if (!record || record.token !== exec.token || record.phase !== 'returned' || record.resultHash) {
      this.fail('missing/duplicate final native outcome');
    }
    if (!Array.isArray(result?.content) || typeof result.isError !== 'boolean') {
      this.fail('actual final native outcome is incomplete');
    }
    record.isError = result.isError;
    record.resultHash = valueHash({ content: result.content, isError: result.isError });
  }
  observeInput(options) {
    this.ready();
    if (options.sessionId !== this.agent.session.id || !Array.isArray(options.messages)) this.fail('foreign native input');
    for (const [callId, record] of this.records) {
      if (record.incorporated) continue;
      const matches = options.messages.filter(m => m.role === 'tool' && m.toolCallId === callId);
      if (!record.messageId || matches.length !== 1 || valueHash(matches[0]) !== record.committedHash) {
        this.fail('final committed result missing or changed in next native input');
      }
      record.inputSeen = true;
    }
  }
  attestTerminal(callId, { executionComplete, status, uncertain = false, evidenceRef } = {}) {
    this.ready(); const record = this.records.get(callId);
    if (!record?.resultHash || !record.committedHash || record.terminal
        || executionComplete !== true || uncertain !== false
        || !['success', 'failure', 'declined'].includes(status)
        || (status === 'success' && record.isError !== false)
        || typeof evidenceRef !== 'string' || !evidenceRef.trim()) {
      this.fail('physical terminal execution is not proven');
    }
    record.terminal = true; record.status = status; record.terminalRef = evidenceRef;
  }
  async incorporate(callId, { current, evidenceRef } = {}) {
    this.ready(); const record = this.records.get(callId);
    if (!record?.terminal || !record.inputSeen || record.incorporated
        || typeof evidenceRef !== 'string' || !evidenceRef.trim()
        || current?.logical_task_id !== record.current.logical_task_id
        || !Number.isSafeInteger(current.execution_revision)
        || current.execution_revision <= record.current.execution_revision
        || current.intent_revision < record.current.intent_revision
        || !Number.isSafeInteger(current.workspace?.revision)
        || current.workspace.revision < record.current.workspace.revision
        || (valueHash(current.workspace) !== valueHash(record.current.workspace)
          && current.workspace.revision <= record.current.workspace.revision)) {
      this.fail('result and partial effects incorporation is unproven');
    }
    if (valueHash(await this.observeCurrent()) !== valueHash(current)) this.fail('stale effects observation');
    this.ready(); record.incorporated = true; record.current = structuredClone(current);
    record.incorporationRef = evidenceRef;
  }
  get quiescent() {
    return this.enabled && !this.stopped && !this.preparing
      && [...this.calls.keys()].every(id => this.records.get(id)?.incorporated === true);
  }
  observations({ toolKinds, effectScope } = {}) {
    // Owner-local metadata in the existing WorkRecord field layout; no native notifications.
    const kinds = new Set(['read', 'search', 'edit', 'shell', 'build', 'test', 'other']);
    if (!this.quiescent || !this.disposers.length || !toolKinds
        || !Array.isArray(effectScope) || !effectScope.length
        || effectScope.some(s => typeof s !== 'string' || !s.trim() || s.length > 160)
        || [...this.names].some(name => !kinds.has(toolKinds[name]))) {
      this.fail('settled native owner and declared work taxonomy/effects required');
    }
    const rows = [];
    for (const [callId, record] of this.records) {
      if (!record.terminal || !record.incorporated || !record.inputSeen || !record.committedHash
          || !record.resultHash || !record.terminalRef || !record.incorporationRef) {
        this.fail('unsettled native work cannot become Core history');
      }
      rows.push({ identity: { runtime: 'dsh', session_id: this.agent.session.id,
        operation_id: callId, native_scope: [String(record.call.turn)] },
        kind: toolKinds[record.call.name], effect_scope: [...effectScope],
        execution: 'terminal', incorporation: 'incorporated', result_status: record.status,
        result_ref: record.resultHash, terminal_evidence: record.terminalRef,
        incorporation_evidence: record.incorporationRef });
    }
    return structuredClone(rows); // Never expose Symbols, args, raw results or live records.
  }
  closeAdmission() {
    this.barrier = true;
    return this.disposers.length > 0; // Ack only an attached native gate.
  }
  openBoundTask(mode, binding, { readTools, bindingRecord } = {}) {
    if (!this.enabled || this.stopped || !this.quiescent || !bindingRecord
        || !Array.isArray(readTools) || !readTools.length || readTools.some(n => !this.names.has(n))
        || binding?.sessionId !== this.agent.session.id || !Number.isSafeInteger(binding.turn)
        || binding.turn < 1 || binding.turn <= this.returnedTurnFloor || binding.step !== 1
        || !['fresh', 'action', 'work'].includes(mode)
        || (mode === 'fresh' && (!this.barrier || this.boundTurn !== null))
        || (mode === 'action' && (this.recoveryMode !== 'fresh' || this.boundTurn !== binding.turn))
        || (mode === 'work' && (!this.barrier || this.recoveryMode !== 'action' || this.boundTurn !== binding.turn))) {
      this.fail('current durable DSH binding/fresh-read gate required');
    }
    if (mode === 'work') {
      this.returnedTurnFloor = binding.turn;
      this.boundTurn = null; this.readNames = new Set(); this.recoveryMode = null;
    } else {
      this.boundTurn = binding.turn; this.readNames = new Set(readTools); this.recoveryMode = mode;
    }
    this.barrier = false;
    return true;
  }
  dispose() {
    // Unknown physical execution retains its exact callbacks; detaching is not cleanup proof.
    if ([...this.records.values()].some(r => !r.terminal)) this.fail('native execution still unconfirmed');
    this.stop(); for (const dispose of this.disposers.splice(0).reverse()) dispose();
  }
}
