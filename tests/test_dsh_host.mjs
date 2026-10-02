/** Local gate regressions; stock-DSH transport acceptance is recorded separately. */
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createHash } from 'node:crypto';
import { DshNativeHost } from '../src/yohaku/dsh_host.mjs';
const hash = s => createHash('sha256').update(s).digest('hex');
async function fixture(extraFields = {}) {
  const listeners = new Map();
  let gate;
  const ctx = {
    on(name, fn) { listeners.set(name, [...(listeners.get(name) ?? []), fn]); return () => {}; },
    deepseekLlmApiExtensions: {
      register(name, provider) { gate = provider; return () => {}; },
      async prepare(request) { await gate.prepare(request); return { fields: extraFields, accept: async () => {} }; },
    },
    sessions: { flush: async () => {} },
    sessionPersistence: { open: async () => ({ read: async () => ({ events: log }), close: async () => {} }) },
  };
  const text = 'historical handoff h-1';
  const message = { id: 'm-1', content: [{ type: 'text', text }] };
  const log = [{ type: 'user/message', seq: 0, data: message }];
  const agent = { id: 's-1', session: { id: 's-1', seq: 0 }, status: 'running', cancel() {} };
  class OfficialAdapter {}
  const host = new DshNativeHost(ctx, agent, { version: '0.2.0-rc.2' });
  const current = { logical_task_id: 'task', intent_revision: 0, execution_revision: 1,
    workspace: { revision: 1, stamp: 'task-hash', paths: ['task.json'] } };
  host.enableReceipt({ provider: 'messages', adapter: new OfficialAdapter(), DeepSeekAdapter: OfficialAdapter,
    options: { retryPolicy: { maxRetries: 0 } }, observeCurrent: async () => current });
  agent.session.seq = 1;
  host.delivery = { sessionId: 's-1', messageId: 'm-1', handoffId: 'h-1', turnId: 's-1:2' };
  host.handoffMessage = message;
  host.latestStart = { attemptId: 's-1:2' };
  const binding = { ...host.delivery, nativeAttemptId: 's-1:2', nativeCall: 1,
    turn: 2, step: 1, nativeSeq: 1, handoffHash: hash(text) };
  const signal = new AbortController();
  const request = { sessionId: 's-1', signal: signal.signal,
    body: { messages: [{ role: 'user', content: [{ type: 'text', text }] }] } };
  const prepared = host.nativeContext.run(binding, () => host.prepareExtensions(request));
  prepared.catch(() => {});
  const claims = await host.gateReady.promise;
  const fresh = await host.fresh_receipt();
  return { host, signal, prepared, claims, fresh, current, listeners, agent, log, message };
}

test('authorization precedes HTTP acceptance; receipt uses no model output', async () => {
  const f = await fixture();
  assert.equal(f.host.receiptEvidence, undefined);
  const receipt = f.host.authorize_receipt(f.claims, f.fresh);
  const prepared = await f.prepared;
  assert.equal(f.host.receiptEvidence, undefined);
  assert.deepEqual(prepared.fields, {});
  await prepared.accept();
  const proof = await receipt;
  assert.deepEqual(proof.binding, f.claims);
  assert.equal(proof.result, 'http-accepted');
  await assert.rejects(prepared.accept(), /duplicate/);
  await assert.rejects(f.host.authorize_receipt(f.claims, f.fresh), /duplicate/);
  await f.host.dispose();
});

for (const [name, field] of [ ['wrong Session', 'sessionId'], ['wrong MessageId', 'messageId'],
  ['payload hash mismatch', 'handoffHash'], ['body hash mismatch', 'bodyHash'],
  ['old host attempt', 'hostAttempt'], ['wrong native attempt', 'nativeAttemptId'],
  ['wrong turn', 'turn'], ['wrong step', 'step'], ['wrong native call', 'nativeCall'] ]) {
  test(name + ' invalidates candidate and rejects late authorization', async () => {
    const f = await fixture();
    await assert.rejects(f.host.authorize_receipt({ ...f.claims, [field]: 'foreign' }, f.fresh));
    assert(f.host.candidate.invalid);
    await assert.rejects(f.prepared);
    await assert.rejects(f.host.authorize_receipt(f.claims, f.fresh));
    assert.equal(f.host.receiptEvidence, undefined);
    await f.host.dispose();
  });
}

test('abort before authorization settles gate and rejects late release', async () => {
  const f = await fixture();
  f.signal.abort();
  await assert.rejects(f.prepared);
  await assert.rejects(f.host.authorize_receipt(f.claims, f.fresh));
  assert(f.host.candidate.invalid);
  await f.host.dispose();
});

test('retry start invalidates candidate without creating another attempt', async () => {
  const f = await fixture();
  for (const fn of f.listeners.get('session/event')) fn(f.agent.session, { type: 'llm/retry-started' });
  await assert.rejects(f.prepared);
  assert(f.host.candidate.invalid);
  assert.equal(f.host.actualAttempts, 1);
  await assert.rejects(f.host.authorize_receipt(f.claims, f.fresh));
  await f.host.dispose();
});

test('fresh task change refuses authorization', async () => {
  const f = await fixture();
  f.current.execution_revision++;
  await assert.rejects(f.host.authorize_receipt(f.claims, f.fresh), /stale/);
  await assert.rejects(f.prepared);
  await f.host.dispose();
});

test('host disposal and owner loss settle held gates', async () => {
  for (const disposal of [true, false]) {
    const f = await fixture();
    if (disposal) await f.host.dispose();
    else for (const fn of f.listeners.get('agent/disposed')) fn({ agent: f.agent });
    await assert.rejects(f.prepared);
    await assert.rejects(f.host.authorize_receipt(f.claims, f.fresh));
    assert.equal(f.host.receiptEvidence, undefined);
    await f.host.dispose();
  }
});

test('late native observation invalidates a held candidate', async () => {
  const f = await fixture();
  for (const fn of f.listeners.get('agent/assistant-stream')) {
    fn({ agent: f.agent, frame: { type: 'start', revision: 0, attemptId: 's-1:1' } });
  }
  await assert.rejects(f.prepared);
  assert(f.host.candidate.invalid);
  await f.host.dispose();
});

test('extra extension fields stop release before official dispatch', async () => {
  const f = await fixture({ extra: 1 });
  const receipt = f.host.authorize_receipt(f.claims, f.fresh);
  await assert.rejects(f.prepared, /empty extension/);
  await assert.rejects(receipt);
  assert(f.host.candidate.invalid);
  await f.host.dispose();
});

test('body and payload divergence invalidate the held candidate', async () => {
  for (const bodyChanged of [true, false]) {
    const f = await fixture();
    if (bodyChanged) f.host.candidate.body = { messages: [] };
    else f.host.handoffMessage = { ...f.host.handoffMessage, content: [{ type: 'text', text: 'foreign' }] };
    await assert.rejects(f.host.authorize_receipt(f.claims, f.fresh));
    assert(f.host.candidate.invalid);
    await assert.rejects(f.prepared);
    await f.host.dispose();
  }
});

async function acceptedIdle() {
  const f = await fixture();
  const receipt = f.host.authorize_receipt(f.claims, f.fresh);
  await (await f.prepared).accept();
  await receipt;
  f.signal.abort(); // Stock owner releases the native request signal on settle.
  f.host.receiptTarget = { turn: 2 };
  const end = { type: 'turn/end', seq: 1, data: { turn: 2, reason: { kind: 'completed' } } };
  f.log.push(end);
  f.agent.session.seq = 2;
  f.agent.session.deriveMessages = () => [f.message];
  f.agent.inbox = { nextTurn: [], nextStep: [] };
  f.agent.whenIdle = async () => { f.agent.status = 'idle'; };
  for (const fn of f.listeners.get('agent/assistant-stream')) {
    fn({ agent: f.agent, frame: { type: 'end', revision: 1, attemptId: 's-1:2' } });
  }
  for (const fn of f.listeners.get('session/event')) fn(f.agent.session, end);
  return f;
}

test('accepted receipt settles before new current/projection/readback observations', async () => {
  const f = await acceptedIdle();
  assert.equal(f.host.stopped, false);
  const post = await f.host.post_receipt();
  assert.equal(post.phase, 'post-receipt-idle');
  assert.equal(post.status, 'idle');
  assert.equal(post.terminalSeq, 1);
  assert.notEqual(post.revision, f.fresh.revision);
  assert.deepEqual(post.messages, [f.message]);
  assert.deepEqual(post.current, f.current);
  assert.equal(f.host.actualAttempts, 1);
  await f.host.dispose();
});

test('post-receipt read cannot use a held unaccepted gate', async () => {
  const f = await fixture();
  await assert.rejects(f.host.post_receipt(), /accepted receipt/);
  await f.host.dispose();
  await assert.rejects(f.prepared);
});

for (const mode of ['duplicate terminal', 'aborted terminal', 'pending inbox', 'foreign Session',
    'wrong projection', 'another attempt', 'retry after receipt']) {
  test(mode + ' cannot authorize post-receipt continuation', async () => {
    const f = await acceptedIdle();
    if (mode === 'duplicate terminal') f.log.push({ ...f.log[1], seq: 2 });
    if (mode === 'aborted terminal') f.log[1].data.reason = { kind: 'aborted' };
    if (mode === 'pending inbox') f.agent.inbox.nextStep.push({ id: 'pending' });
    if (mode === 'foreign Session') f.agent.session.id = 'foreign';
    if (mode === 'wrong projection') f.agent.session.deriveMessages = () => [];
    if (mode === 'another attempt') {
      for (const fn of f.listeners.get('agent/assistant-stream')) {
        fn({ agent: f.agent, frame: { type: 'start', revision: 2, attemptId: 's-1:3' } });
      }
    }
    if (mode === 'retry after receipt') {
      for (const fn of f.listeners.get('session/event')) fn(f.agent.session, { type: 'llm/retry-started' });
    }
    await assert.rejects(f.host.post_receipt());
    assert.equal(f.host.actualAttempts, 1);
    await f.host.dispose();
  });
}

async function taskHeld() {
  const f = await acceptedIdle();
  f.host.nativeCalls = 1;
  f.host.delivery.handoffHash = hash(f.message.content[0].text);
  f.host.receiptStarted = true;
  f.host.createUserMessage = data => ({ id: 'task-input', ...data });
  f.agent.session.deriveMessages = () => f.log.filter(e => ['user/message', 'assistant/message'].includes(e.type))
    .map(e => e.type === 'assistant/message' ? e.data.message : e.data);
  f.dispatches = 0;
  f.agent.followup = message => {
    f.agent.status = 'running';
    f.log.push({ type: 'turn/start', seq: f.log.length, data: { turn: 3 } });
    f.log.push({ type: 'user/message', seq: f.log.length, data: message });
    f.agent.session.seq = f.log.length;
    for (const fn of f.listeners.get('agent/assistant-stream')) {
      fn({ agent: f.agent, frame: { type: 'start', revision: 2, attemptId: 's-1:3', turn: 3, step: 1 } });
    }
    const signal = new AbortController();
    f.taskSignal = signal;
    const options = Object.freeze({ sessionId: 's-1', provider: 'messages',
      messages: f.agent.session.deriveMessages() });
    const next = async function* () {
      const prepared = await f.host.prepareExtensions({ sessionId: 's-1', signal: signal.signal,
        body: { messages: options.messages.map(m => ({ role: 'user', content: m.content })) } });
      f.dispatches++;
      await prepared.accept();
    };
    f.execution = (async () => {
      for await (const item of f.listeners.get('llm/stream')[0](options, next)) void item;
      f.log.push({ type: 'assistant/message', seq: f.log.length, data: { turn: 3, step: 1,
        message: { id: 'task-output', role: 'assistant', content: [{ type: 'text', text: 'FINALIZED' }] } } });
      const end = { type: 'turn/end', seq: f.log.length, data: { turn: 3, reason: { kind: 'completed' } } };
      f.log.push(end);
      f.agent.session.seq = f.log.length;
      for (const fn of f.listeners.get('session/event')) fn(f.agent.session, end);
      f.agent.status = 'idle';
      signal.abort();
    })();
    f.execution.catch(() => {});
    f.agent.whenIdle = async () => { await f.execution; };
  };
  const post = await f.host.post_receipt();
  f.taskClaims = await f.host.start_task_interaction('task-claim', 'h-1', 'FINALIZE', post);
  f.taskFresh = await f.host.fresh_task();
  f.bound = { claimId: 'task-claim', handoffId: 'h-1', turnId: 's-1:3',
    bindingRecord: 'local-fixture-bound-record', controlRevision: 20 };
  return f;
}

test('task uses observed native turn and waits for saved binding before dispatch', async () => {
  const f = await taskHeld();
  assert.equal(f.taskClaims.turnId, 's-1:3');
  assert.equal(f.taskClaims.nativeAttemptId, 's-1:3');
  assert.equal(f.taskClaims.taskMessageId, 'task-input');
  assert.equal(f.dispatches, 0);
  await assert.rejects(f.host.authorize_receipt(f.taskClaims, f.taskFresh), /cannot release a task/);
  await f.host.authorize_task(f.taskClaims, f.taskFresh, f.bound);
  const post = await f.host.post_task();
  assert.equal(post.lastTurnEnd.turn, 3);
  assert.equal(post.phase, 'post-task-idle');
  assert.equal(f.dispatches, 1);
  await assert.rejects(f.host.start_task_interaction('another', 'h-1', 'FINALIZE', post));
  await assert.rejects(f.host.authorize_task(f.taskClaims, f.taskFresh, f.bound));
  assert.equal(f.dispatches, 1);
  await f.host.dispose();
});

for (const mode of ['missing binding', 'foreign turn', 'stale task', 'owner loss', 'send abort']) {
  test('task gate refuses ' + mode + ' and late release', async () => {
    const f = await taskHeld();
    if (mode === 'missing binding') f.bound.bindingRecord = '';
    if (mode === 'foreign turn') f.bound.turnId = 'other:3';
    if (mode === 'stale task') f.current.execution_revision++;
    if (mode === 'owner loss') f.agent.session.id = 'foreign';
    if (mode === 'send abort') f.taskSignal.abort();
    await assert.rejects(f.host.authorize_task(f.taskClaims, f.taskFresh, f.bound));
    await assert.rejects(f.execution);
    await assert.rejects(f.host.authorize_task(f.taskClaims, f.taskFresh, f.bound));
    assert.equal(f.dispatches, 0);
    await f.host.dispose();
  });
}

test('duplicate task terminal is not a completed new continuation', async () => {
  const f = await taskHeld();
  await f.host.authorize_task(f.taskClaims, f.taskFresh, f.bound);
  await f.execution;
  f.log.push({ ...f.log.at(-1), seq: f.log.length });
  f.agent.session.seq = f.log.length;
  await assert.rejects(f.host.post_task(), /terminal/);
  assert.equal(f.dispatches, 1);
  await f.host.dispose();
});


test('final evidence derives bound output and counts from independent readback', async () => {
  const f = await taskHeld();
  await f.host.authorize_task(f.taskClaims, f.taskFresh, f.bound);
  const final = await f.host.final_task();
  assert.equal(final.completion.readbackSessionId, 's-1');
  assert.equal(final.completion.taskRequests, 1);
  assert.equal(final.completion.finalizedCount, 1);
  assert.deepEqual(final.completion.outputContent, [{ type: 'text', text: 'FINALIZED' }]);
  const reread = await f.host.final_task();
  assert.notEqual(final.revision, reread.revision);
  assert.deepEqual({ ...final, revision: null }, { ...reread, revision: null });
  await f.host.dispose();
});

for (const mode of ['readback failure', 'missing output', 'foreign output turn', 'projection mismatch',
  'duplicate turn', 'failed terminal', 'duplicate request', 'uncertain candidate']) {
  test('final evidence refuses ' + mode, async () => {
    const f = await taskHeld();
    await f.host.authorize_task(f.taskClaims, f.taskFresh, f.bound);
    await f.execution;
    const output = f.log.find(e => e.type === 'assistant/message');
    if (mode === 'readback failure') f.host.ctx.sessionPersistence.open = async () => { throw new Error('unavailable'); };
    if (mode === 'missing output') f.log.splice(f.log.indexOf(output), 1);
    if (mode === 'foreign output turn') output.data.turn = 2;
    if (mode === 'projection mismatch') f.agent.session.deriveMessages = () =>
      f.log.filter(e => e.type === 'user/message').map(e => e.data);
    if (mode === 'duplicate turn') f.log.push({ type: 'turn/start', seq: f.log.length, data: { turn: 4 } });
    if (mode === 'failed terminal') f.log.findLast(e => e.type === 'turn/end').data.reason.kind = 'error';
    if (mode === 'duplicate request') f.host.actualAttempts++;
    if (mode === 'uncertain candidate') f.host.candidate.invalid = true;
    await assert.rejects(f.host.final_task());
    await f.host.dispose();
  });
}
