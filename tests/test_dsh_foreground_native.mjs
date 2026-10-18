// Offline native-shaped lifecycle/services only; no installed DSH or inference.
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { DshForegroundHost } from '../src/yohaku/dsh_foreground.mjs';
import { DshForegroundNativeOwner } from '../src/yohaku/dsh_foreground_native.mjs';
import { bindDshPiAiGateToOwnedAdapter, DshSseAttemptGate } from '../src/yohaku/dsh_pi_ai_gate.mjs';

function fixture({ sameCompactionId = false } = {}) {
  const listeners = new Map(), log = [];
  const on = (name, fn) => { const list = listeners.get(name) ?? []; list.push(fn); listeners.set(name, list);
    return () => { const i = list.indexOf(fn); if (i >= 0) list.splice(i, 1); }; };
  const emit = (name, ...args) => { for (const fn of [...(listeners.get(name) ?? [])]) fn(...args); };
  let calls = 0, flushed = false, flushCount = 0, opened = 0, closed = 0, idleFault = false;
  const agent = { id: 'session', session: { id: 'session', seq: 0, deriveMessages: () => [] },
    status: 'idle', options: { provider: 'openai-codex', model: 'same-model' },
    inbox: { nextTurn: [], nextStep: [] }, whenIdle: async () => { if (idleFault) throw new Error('idle fault'); },
    ctx: { on, tools: { guard: () => () => {} } } };
  const append = (type, data, sourceEventSeqs) => { const event = { seq: agent.session.seq++, type, data,
    ...(sourceEventSeqs === undefined ? {} : { sourceEventSeqs }) };
    log.push(event); emit('session/event', agent.session, event); return event; };
  const ctx = { on, sessions: { flush: async () => { flushed = true; flushCount++; } },
    sessionPersistence: { open: async (id, mode) => {
      assert.equal(id, agent.id); assert.equal(mode, 'read'); assert.equal(flushed, true); opened++;
      return { read: async () => ({ events: structuredClone(log) }), close: async () => { closed++; } };
    } }, compaction: { compactNow: async () => {
      calls++; flushed = false;
      const compactionId = `actual-fixture-id-${sameCompactionId ? 1 : calls}`;
      append('compaction/start', { compactionId, turn: null });
      const summary = append('compaction/summary', { compactionId, shadowedSeqs: [0] });
      append('user/message', { id: `replacement-${calls}`, source: { kind: 'compact-checkpoint', compactionId } });
      const end = append('compaction/end', { compactionId, turn: null });
      return { compactionId, startSeq: summary.seq - 1, summarySeq: summary.seq, endSeq: end.seq };
    } } };
  const work = new DshForegroundHost(ctx, agent, { enabled: true, tools: ['read'],
    observeCurrent: async () => ({}), authorize: async () => true,
    retryPolicy: { maxRetries: 0 }, bashPolicy: { enableRunInBackground: false, promoteOnTimeout: false } });
  work.attach();
  const owner = new DshForegroundNativeOwner(ctx, agent, { foreground: work, version: '0.2.0-rc.2',
    toolKinds: { read: 'read' }, effectScope: ['source'] });
  const frame = value => emit('agent/assistant-stream', { agent, frame: value });
  const complete = (turn = 1) => append('turn/end', { turn, reason: { kind: 'completed' } });
  return { agent, ctx, owner, work, emit, append, frame, complete,
    get counts() { return { calls, opened, closed }; }, get flushCount() { return flushCount; },
    set idleFault(v) { idleFault = v; } };
}

test('native frame owns binding; chunk/end carry no fabricated turn or step', async () => {
  const f = fixture(); f.agent.status = 'running';
  f.frame({ type: 'start', revision: 1, attemptId: 'session:actual', turn: 1, step: 1 });
  const message = { id: 'user-message', role: 'user', content: [{ type: 'text', text: 'input' }] };
  const options = Object.freeze({ sessionId: 'session', provider: 'openai-codex', model: 'same-model', messages: [message] });
  const observed = f.owner.observeRequest(options);
  assert.equal(observed.binding.attemptId, 'session:actual'); assert.equal(observed.binding.frameRevision, 1);
  f.owner.assertInputMember(message);
  f.frame({ type: 'chunk', revision: 2, attemptId: 'session:actual', index: 0 });
  assert.equal(f.owner.observe().attempt.turn, 1);
  f.frame({ type: 'end', revision: 3, attemptId: 'session:actual', index: 1 });
  assert.equal(f.owner.observe().attempt, null); assert.equal(f.owner.stopped, false);
  f.complete(); f.agent.status = 'idle';
  assert.equal(f.owner.observe().settled, false);
  assert.equal((await f.owner.settle()).settled, true);
});

test('foreign or duplicated request cannot replace source-owned binding', () => {
  for (const mode of ['provider', 'duplicate', 'changed input']) {
    const f = fixture(); f.frame({ type: 'start', revision: 1, attemptId: 'session:attempt', turn: 1, step: 1 });
    const message = { id: 'm', role: 'user', content: [{ type: 'text', text: 'owned' }] };
    const options = Object.freeze({ sessionId: 'session', provider: 'openai-codex', model: 'same-model', messages: [message] });
    if (mode === 'provider') assert.throws(() => f.owner.observeRequest(Object.freeze({ ...options, provider: 'foreign' })));
    else {
      f.owner.observeRequest(options);
      if (mode === 'duplicate') assert.throws(() => f.owner.observeRequest(options));
      else { message.content[0].text = 'changed'; assert.throws(() => f.owner.assertInputMember(message)); }
    }
    assert.equal(f.work.stopped, true);
  }
});

test('closed settled gate compact flushes then independently reads exactly once', async () => {
  const f = fixture(); f.complete(); await f.owner.settle(); f.owner.closeGate();
  const before = f.owner.observe(); const result = await f.owner.compact(1, before.seq);
  assert.equal(result.events.length, 4); assert.equal(result.flushed, true);
  assert.equal(result.readbackSessionId, 'session'); assert.equal(result.readbackEvents.length, 5);
  assert.deepEqual(f.counts, { calls: 1, opened: 1, closed: 1 });
  assert.equal(f.work.barrier, true);
  await assert.rejects(f.owner.compact(1, f.agent.session.seq));
  assert.equal(f.counts.calls, 1);
});

test('open, stale or unacknowledged native boundary never dispatches compact', async () => {
  for (const mode of ['open', 'stale', 'not settled', 'inbox']) {
    const f = fixture(); f.complete();
    if (mode !== 'not settled') await f.owner.settle();
    if (mode !== 'open') f.owner.closeGate();
    if (mode === 'inbox') f.agent.inbox.nextTurn.push({ id: 'pending' });
    await assert.rejects(f.owner.compact(1, f.agent.session.seq + (mode === 'stale' ? 1 : 0)));
    assert.equal(f.counts.calls, 0); assert.equal(f.work.stopped, true);
  }
});

test('independent readback fault consumes compact and retains native callbacks', async () => {
  const f = fixture(); f.complete(); await f.owner.settle(); f.owner.closeGate();
  f.ctx.sessionPersistence.open = async () => { throw new Error('readback fault'); };
  await assert.rejects(f.owner.compact(1, f.agent.session.seq));
  assert.equal(f.owner.requestConsumed, true); assert.equal(f.work.stopped, true);
  await assert.rejects(f.owner.compact(1, f.agent.session.seq));
  assert.equal(f.counts.calls, 1); assert.throws(() => f.owner.dispose());
  assert(f.work.disposers.length > 0);
});

test('native idle acknowledgement failure cannot become settled observation', async () => {
  const f = fixture(); f.complete(); f.idleFault = true;
  await assert.rejects(f.owner.settle());
  assert.equal(f.owner.stopped, true); assert.equal(f.work.stopped, true);
});

test('late native frame or native retry latches stop even if emit catches errors', () => {
  const late = fixture(); late.frame({ type: 'end', revision: 1, attemptId: 'session:foreign', index: 0 });
  assert.equal(late.owner.stopped, true);
  const retry = fixture(); retry.append('llm/retry/start', {});
  assert.equal(retry.owner.stopped, true); assert.equal(retry.work.stopped, true);
});

function request(generation, id = `core-request-${generation}`) {
  return { request_id: id, thread_id: 'session', rollover_generation: generation, origin: 'controller',
    transition_id: `transition-${generation}`, boundary_id: `boundary-${generation}`,
    checkpoint_id: `checkpoint-${generation}`, lease_id: `lease-${generation}` };
}
async function closed(f, turn = 1) {
  f.complete(turn); await f.owner.settle(); f.owner.closeGate();
  return f.agent.session.seq;
}
async function actionBoundary(f) {
  f.frame({ type: 'start', revision: 1, attemptId: 'session:task', turn: 3, step: 1 });
  const binding = f.owner.observe().attempt;
  f.owner.closeGate(); f.owner.openTask('fresh', binding, 'durable-task-binding', ['read']);
  f.frame({ type: 'end', revision: 2, attemptId: 'session:task', index: 0 });
  f.frame({ type: 'start', revision: 3, attemptId: 'session:task-next', turn: 3, step: 2 });
  f.owner.observeRequest(Object.freeze({ sessionId: 'session', provider: 'openai-codex', model: 'same-model', messages: [] }));
  f.owner.openTask('action', binding, 'durable-read-incorporated', ['read']);
  f.frame({ type: 'end', revision: 4, attemptId: 'session:task-next', index: 0 });
  await closed(f, 3); return binding;
}

test('same task next request can release actions using the saved first-step anchor', () => {
  const f = fixture();
  f.frame({ type: 'start', revision: 1, attemptId: 'session:first-step', turn: 3, step: 1 });
  const binding = f.owner.observe().attempt;
  f.owner.closeGate(); f.owner.openTask('fresh', binding, 'durable-task-binding', ['read']);
  f.frame({ type: 'end', revision: 2, attemptId: 'session:first-step', index: 0 });
  f.frame({ type: 'start', revision: 3, attemptId: 'session:next-step', turn: 3, step: 2 });
  // Read/input/effects evidence is supplied separately by the trusted coordinator.
  f.owner.observeRequest(Object.freeze({ sessionId: 'session', provider: 'openai-codex', model: 'same-model', messages: [] }));
  assert.equal(f.owner.openTask('action', binding, 'durable-incorporated-read', ['read']), true);
  assert.deepEqual(f.owner.taskAnchor, binding); assert.equal(f.work.boundTurn, 3);
});

test('fresh read commit enters the next observed request before effects can release actions', async () => {
  const f = fixture(); let bodyCalls = 0;
  let current = { logical_task_id: 'task', intent_revision: 0, execution_revision: 0, workspace: { revision: 0 } };
  f.work.observeCurrent = async () => current;
  f.frame({ type: 'start', revision: 1, attemptId: 'session:read-step', turn: 3, step: 1 });
  const anchor = f.owner.observe().attempt;
  f.owner.closeGate(); f.owner.openTask('fresh', anchor, 'saved-task', ['read']);
  f.owner.observeRequest(Object.freeze({ sessionId: 'session', provider: 'openai-codex', model: 'same-model', messages: [] }));
  f.frame({ type: 'end', revision: 2, attemptId: 'session:read-step', index: 0 });
  const call = f.append('tool/call', { turn: 3, step: 1, callId: 'read-call', name: 'read', arguments: '{}' });
  const exec = { callId: 'read-call', rootCallId: 'read-call', name: 'read', arguments: {}, agent: f.agent,
    token: Symbol('fixture native token'), signal: new AbortController().signal };
  await f.work.prepare(exec, async () => ({ kind: 'allow' }));
  const result = await f.work.execute(exec, async () => { bodyCalls++; return { content: [{ type: 'text', text: 'read content' }], isError: false }; });
  f.emit('tools/result', exec, result);
  const message = { id: 'committed-read', role: 'tool', toolCallId: exec.callId,
    source: { kind: 'tool', callId: exec.callId }, content: result.content, isError: false };
  f.append('tool/result', { turn: 3, step: 1, message }, [call.seq]);
  f.work.attestTerminal(exec.callId, { executionComplete: true, status: 'success', evidenceRef: 'owned-sync-end' });
  assert.equal(f.work.quiescent, false);
  f.frame({ type: 'start', revision: 3, attemptId: 'session:result-step', turn: 3, step: 2 });
  f.owner.observeRequest(Object.freeze({ sessionId: 'session', provider: 'openai-codex', model: 'same-model', messages: [message] }));
  f.owner.assertInputMember(message);
  assert.equal(f.work.records.get(exec.callId).inputSeen, true); assert.equal(f.work.quiescent, false);
  current = { ...current, execution_revision: 1 };
  await f.work.incorporate(exec.callId, { current, evidenceRef: 'current-result-and-effects' });
  assert.equal(f.owner.openTask('action', anchor, 'saved-fresh-read', ['read']), true);
  assert.equal(bodyCalls, 1); assert.deepEqual(f.owner.taskAnchor, anchor);
});

test('action release rejects stale anchors, scope drift and unobserved or changed requests', () => {
  for (const mode of ['anchor', 'turn', 'provider', 'model', 'same step', 'reused attempt', 'old frame',
      'unobserved', 'old request', 'changed input', 'ended request', 'unknown ack', 'pending work']) {
    const f = fixture();
    f.frame({ type: 'start', revision: 1, attemptId: 'session:first-step', turn: 3, step: 1 });
    const binding = f.owner.observe().attempt;
    f.owner.closeGate(); f.owner.openTask('fresh', binding, 'saved-anchor', ['read']);
    const input = [{ id: 'current-message', role: 'user', content: [{ type: 'text', text: 'current' }] }];
    const options = () => Object.freeze({ sessionId: 'session', provider: f.agent.options.provider,
      model: f.agent.options.model, messages: input });
    if (mode === 'old request') f.owner.observeRequest(options());
    f.frame({ type: 'end', revision: 2, attemptId: 'session:first-step', index: 0 });
    if (mode === 'provider' || mode === 'model') f.agent.options[mode] = 'different-scope';
    f.frame({ type: 'start', revision: mode === 'old frame' ? 1 : 3,
      attemptId: mode === 'reused attempt' ? 'session:first-step' : 'session:next-step',
      turn: mode === 'turn' ? 4 : 3, step: mode === 'same step' ? 1 : 2 });
    if (!f.owner.stopped && !['unobserved', 'old request'].includes(mode)) f.owner.observeRequest(options());
    if (mode === 'changed input') input[0].content[0].text = 'not the observed input';
    if (mode === 'ended request') f.frame({ type: 'end', revision: 4, attemptId: 'session:next-step', index: 0 });
    if (mode === 'unknown ack') f.work.openBoundTask = () => undefined;
    if (mode === 'pending work') f.work.preparing = true;
    assert.throws(() => f.owner.openTask('action', mode === 'anchor' ? { ...binding, frameRevision: 99 } : binding,
      'saved-read-proof', ['read']), mode);
    assert.equal(f.work.recoveryMode, 'fresh', mode); assert.equal(f.work.barrier, true, mode);
    assert.equal(f.owner.stopped, true, mode); assert(f.owner.disposers.length > 0);
    assert.deepEqual(f.owner.taskAnchor, binding);
  }
});

test('source frame history rejects old steps and reused attempts after a later request', () => {
  for (const mode of ['old step', 'reused attempt']) {
    const f = fixture();
    f.frame({ type: 'start', revision: 1, attemptId: 'session:step-one', turn: 3, step: 1 });
    f.frame({ type: 'end', revision: 2, attemptId: 'session:step-one', index: 0 });
    f.frame({ type: 'start', revision: 3, attemptId: 'session:step-two', turn: 3, step: 2 });
    f.frame({ type: 'end', revision: 4, attemptId: 'session:step-two', index: 0 });
    f.frame({ type: 'start', revision: 5, attemptId: mode === 'reused attempt' ? 'session:step-one' : 'session:fresh-id',
      turn: 3, step: mode === 'old step' ? 1 : 3 });
    assert.equal(f.owner.stopped, true); assert.equal(f.work.barrier, true);
    assert.equal(f.owner.seenAttempts.size, 2); assert(f.owner.disposers.length > 0);
  }
});

test('two Core-bound compacts consume before dispatch and independently flush/read each', async () => {
  const f = fixture(), native = f.ctx.compaction.compactNow;
  f.ctx.compaction.compactNow = async (...args) => {
    assert.equal(f.owner.requestConsumed, true);
    assert(f.owner.consumedRequestIds.has(`core-request-${f.owner.requestGeneration}`));
    assert.equal(f.owner.requestSeq, f.counts.calls + 1);
    return native(...args);
  };
  const first = await f.owner.compact(1, await closed(f), request(2));
  const second = await f.owner.compact(2, await closed(f, 2), request(5));
  assert.notEqual(first.result.compactionId, second.result.compactionId);
  assert.equal(first.events.length, 4); assert.equal(second.events.length, 4);
  assert(second.readbackEvents.length > first.readbackEvents.length);
  assert.deepEqual(f.counts, { calls: 2, opened: 2, closed: 2 }); assert.equal(f.flushCount, 2);
  assert.equal(f.owner.compactMode, 'core'); assert.equal(f.owner.requestGeneration, 5);
  assert.equal(f.owner.consumedRequestIds.size, 2); assert.equal(f.owner.compactionIds.size, 2);
});

test('existing encoded Core Request may omit the default controller origin', async () => {
  const f = fixture(), encoded = request(3); delete encoded.origin;
  await f.owner.compact(1, await closed(f), encoded);
  assert.equal(f.owner.compactMode, 'core'); assert.equal(f.owner.requestGeneration, 3);
  assert(f.owner.consumedRequestIds.has(encoded.request_id));
  assert.deepEqual(f.counts, { calls: 1, opened: 1, closed: 1 });
});

test('Core request duplicate/old generation/wrong sequence/origin/session never redispatches', async () => {
  const cases = [
    [2, request(2, 'core-request-1')], [2, request(1, 'different-old-request')],
    [1, request(2)], [3, request(2)], [2.5, request(2)],
    [2, { ...request(2), rollover_generation: 0 }],
    [2, { ...request(2), rollover_generation: Number.MAX_SAFE_INTEGER + 1 }],
    [2, { ...request(2), origin: 'native_auto' }],
    [2, { ...request(2), origin: null }], [2, { ...request(2), origin: undefined }],
    [2, { ...request(2), thread_id: 'foreign-session' }],
    [2, { ...request(2), checkpoint_id: '' }],
  ];
  for (const [seq, binding] of cases) {
    const f = fixture(); await f.owner.compact(1, await closed(f), request(1));
    await assert.rejects(f.owner.compact(seq, await closed(f, 2), binding));
    assert.equal(f.counts.calls, 1); assert.equal(f.owner.stopped, true);
    assert.deepEqual([...f.owner.consumedRequestIds], ['core-request-1']);
  }
  const f = fixture(); await assert.rejects(f.owner.compact(2, await closed(f), request(1)));
  assert.equal(f.counts.calls, 0);
});

test('legacy and Core compact modes cannot be mixed in either direction', async () => {
  for (const firstMode of ['core', 'legacy']) {
    const f = fixture(), seq = await closed(f);
    await f.owner.compact(1, seq, firstMode === 'core' ? request(1) : undefined);
    await assert.rejects(f.owner.compact(2, await closed(f, 2), firstMode === 'legacy' ? request(2) : undefined));
    assert.equal(f.counts.calls, 1); assert.equal(f.owner.compactMode, firstMode);
  }
});

test('different next Core request still needs a fresh closed whole-native boundary', async () => {
  for (const mode of ['open', 'stale', 'not settled', 'inbox', 'active attempt']) {
    const f = fixture(); await f.owner.compact(1, await closed(f), request(1));
    f.complete(2);
    if (mode !== 'not settled') await f.owner.settle();
    if (mode === 'open') f.work.barrier = false;
    if (mode === 'inbox') f.agent.inbox.nextStep.push({ id: 'queued' });
    if (mode === 'active attempt') f.frame({ type: 'start', revision: 1, attemptId: 'session:new', turn: 3, step: 1 });
    await assert.rejects(f.owner.compact(2, f.agent.session.seq + (mode === 'stale' ? 1 : 0), request(2)));
    assert.equal(f.counts.calls, 1); assert.equal(f.owner.consumedRequestIds.size, 1);
    assert.equal(f.owner.stopped, true);
  }
});

test('unknown Core readback retains consumed request/native ID and all guards without retry', async () => {
  const f = fixture(), open = f.ctx.sessionPersistence.open;
  f.ctx.sessionPersistence.open = async (...args) => {
    const handle = await open(...args);
    return { read: async () => { throw new Error('unknown native readback'); }, close: handle.close };
  };
  await assert.rejects(f.owner.compact(1, await closed(f), request(1)));
  assert.equal(f.owner.requestConsumed, true); assert.equal(f.owner.requestSeq, 1);
  assert(f.owner.consumedRequestIds.has('core-request-1')); assert.equal(f.owner.compactionIds.size, 1);
  assert.deepEqual(f.counts, { calls: 1, opened: 1, closed: 1 });
  assert(f.owner.disposers.length > 0); assert(f.work.disposers.length > 0);
  await assert.rejects(f.owner.compact(2, f.agent.session.seq, request(2)));
  assert.equal(f.counts.calls, 1); assert.throws(() => f.owner.dispose());
});

test('a reused actual native compaction ID stops after consuming the next Core request', async () => {
  const f = fixture({ sameCompactionId: true });
  await f.owner.compact(1, await closed(f), request(1));
  await assert.rejects(f.owner.compact(2, await closed(f, 2), request(2)));
  assert.equal(f.counts.calls, 2); assert.equal(f.owner.consumedRequestIds.size, 2);
  assert.equal(f.owner.compactionIds.size, 1); assert.equal(f.flushCount, 1);
  assert(f.owner.disposers.length > 0); assert.equal(f.work.stopped, true);
});

test('work mode resets only after an actual completed settled prior action turn', async () => {
  const f = fixture(), binding = await actionBoundary(f);
  assert.equal(f.owner.openTask('work', binding, 'durable-return-to-work', ['read']), true);
  assert.equal(f.work.barrier, false); assert.equal(f.work.boundTurn, null);
  assert.equal(f.work.recoveryMode, null); assert.equal(f.work.returnedTurnFloor, 3);
  assert.equal(f.owner.taskAnchor, null); assert.equal(f.owner.seenAttempts.size, 2);
  // Even a newer source frame revision cannot resurrect a returned native task turn.
  f.frame({ type: 'start', revision: 5, attemptId: 'session:old-turn', turn: 3, step: 1 });
  assert.equal(f.owner.stopped, true); assert(f.work.disposers.length > 0);
});

test('stale/unknown work reset acknowledgement stops and retains callbacks', async () => {
  for (const mode of ['binding', 'provider', 'model', 'gate open', 'not settled', 'inbox', 'active attempt', 'end turn', 'end reason', 'fresh mode', 'unknown ack']) {
    const f = fixture(), binding = await actionBoundary(f);
    if (mode === 'provider' || mode === 'model') f.agent.options[mode] = 'changed-after-verified-turn';
    if (mode === 'gate open') f.work.barrier = false;
    if (mode === 'not settled') f.agent.session.seq++;
    if (mode === 'inbox') f.agent.inbox.nextTurn.push({ id: 'queued' });
    if (mode === 'active attempt') f.frame({ type: 'start', revision: 5, attemptId: 'session:pending', turn: 4, step: 1 });
    if (mode === 'end turn') { f.complete(4); await f.owner.settle(); }
    if (mode === 'end reason') { f.append('turn/end', { turn: 3, reason: { kind: 'failed' } }); await f.owner.settle(); }
    if (mode === 'fresh mode') f.work.recoveryMode = 'fresh';
    if (mode === 'unknown ack') f.work.openBoundTask = () => undefined;
    assert.throws(() => f.owner.openTask('work', mode === 'binding' ? { ...binding, turn: 2 } : binding, 'saved-return', ['read']));
    assert.equal(f.owner.stopped, true); assert.equal(f.work.stopped, true);
    assert(f.owner.disposers.length > 0); assert(f.work.disposers.length > 0);
  }
});

function ownerBoundTransportFixture() {
  const f = fixture(), current = { logical_task_id: 'task', execution_revision: 0 };
  let sends = 0, bodies = 0, gate;
  const models = { async *streamSimple(model, context, options) {
    const payload = await options.onPayload({ model: model.id, input: ['fixture'] }, model);
    const response = await options.fetch('https://provider.invalid/responses', {
      method: 'POST', body: JSON.stringify(payload), signal: options.signal });
    await options.onResponse(response, model);
    yield 'fixture-output';
  } };
  class Adapter {
    prepareCall() { return { stream: options => this.streamWithSnapshot(options, { models }) }; }
    async *streamWithSnapshot(options, snapshot) {
      bodies++;
      yield* snapshot.models.streamSimple({ provider: options.provider, id: options.model }, {}, { signal: options.signal });
    }
  }
  const adapter = new Adapter();
  const binding = bindDshPiAiGateToOwnedAdapter(adapter, {
    enabled: true, exclusive: true, retryPolicy: { maxRetries: 0 },
    isQuiescent: () => {
      const observed = f.owner.observe();
      return observed.settled && f.work.quiescent && !observed.nextTurn.length && !observed.nextStep.length;
    },
    gateFor: options => {
      const observed = f.owner.observeRequest(options, { incorporatedResults: false });
      gate = new DshSseAttemptGate({ binding: observed.binding, current,
        observe: async () => ({ binding: f.owner.observe().attempt, current }),
        validatePayload: async body => body.input[0] === 'fixture', authorize: async () => true,
        fetch: async () => { sends++; return { status: 200 }; },
        url: 'https://provider.invalid/responses', signal: options.signal });
      return gate;
    },
  });
  const options = Object.freeze({ sessionId: f.agent.id, ...f.agent.options,
    messages: [], signal: new AbortController().signal });
  return { f, adapter, binding, options, get gate() { return gate; },
    get sends() { return sends; }, get bodies() { return bodies; } };
}

test('offline owner observation fences preparation, queue and work before binding retirement', async () => {
  const o = ownerBoundTransportFixture(), { f } = o;
  await f.owner.settle();
  f.agent.status = 'running'; // Preparation before the first assistant frame.
  assert.equal(f.owner.activeAttempt, false);
  assert.throws(() => o.binding.retire(), /quiescent/);
  const prepared = o.adapter.prepareCall();
  f.frame({ type: 'start', revision: 1, attemptId: 'session:bound-step', turn: 1, step: 1 });
  assert.deepEqual(await Array.fromAsync(prepared.stream(o.options)), ['fixture-output']);
  assert.equal(o.sends, 1); assert.equal(o.bodies, 1);
  assert.throws(() => o.binding.retire(), /quiescent/);
  f.frame({ type: 'end', revision: 2, attemptId: 'session:bound-step' });
  f.complete(); f.agent.status = 'idle';
  assert.throws(() => o.binding.retire(), /quiescent/); // Seq not settled yet.
  await f.owner.settle();
  for (const queue of [f.agent.inbox.nextTurn, f.agent.inbox.nextStep]) {
    queue.push({ id: 'pending' });
    assert.equal(f.owner.observe().settled, true);
    assert.throws(() => o.binding.retire(), /quiescent/);
    queue.pop();
  }
  f.work.preparing = true; // Mock reservation, not physical execution evidence.
  assert.equal(f.owner.observe().settled, true);
  assert.throws(() => o.binding.retire(), /quiescent/);
  f.work.preparing = false;
  o.binding.retire();
  assert.throws(() => o.gate.requireAccepted());
  await assert.rejects(Array.fromAsync(prepared.stream(o.options)), /retired/);
  assert.equal(o.sends, 1); assert.equal(o.bodies, 1);
});

test('stopped owner refuses retirement observation and blocks stale dispatch before the body', async () => {
  const o = ownerBoundTransportFixture(), prepared = o.adapter.prepareCall();
  o.f.owner.stop();
  assert.throws(() => o.binding.retire(), /owner stopped/);
  await assert.rejects(Array.fromAsync(prepared.stream(o.options)), /owner stopped/);
  assert.equal(o.sends, 0); assert.equal(o.bodies, 0);
  assert(o.f.owner.disposers.length > 0); assert(o.f.work.disposers.length > 0);
});

test('native owner disposal removes callbacks only at an empty settled boundary', async () => {
  const f = fixture();
  await f.owner.settle();
  f.owner.dispose();
  assert.equal(f.owner.stopped, true); assert.equal(f.work.stopped, true);
  assert.equal(f.owner.disposers.length, 0); assert.equal(f.work.disposers.length, 0);
});

for (const queue of ['nextTurn', 'nextStep']) {
  test(`native owner disposal retains guards when ${queue} remains queued after settle`, async () => {
    const f = fixture();
    await f.owner.settle();
    const ownerCallbacks = f.owner.disposers.length, workCallbacks = f.work.disposers.length;
    f.agent.inbox[queue].push({ id: 'queued-before-disposal' });
    assert.equal(f.owner.observe().settled, true);
    assert.equal(f.work.quiescent, true);
    assert.throws(() => f.owner.dispose(), /not settled/);
    assert.equal(f.owner.stopped, true); assert.equal(f.work.stopped, true);
    assert.equal(f.owner.disposers.length, ownerCallbacks);
    assert.equal(f.work.disposers.length, workCallbacks);
    assert.equal(f.agent.inbox[queue].length, 1);
  });
}
