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
  return { host, signal, prepared, claims, fresh, current, listeners, agent };
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
