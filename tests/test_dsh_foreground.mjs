// Mock native events and callbacks only: no DSH process, network or inference.
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { DshForegroundHost } from '../src/yohaku/dsh_foreground.mjs';

function fixture() {
  const listeners = new Map();
  const ctx = { on(name, fn) { listeners.set(name, fn); return () => listeners.delete(name); } };
  const scope = { ...ctx, tools: { guard(fn) { scope.guard = fn; return () => {}; } } };
  const agent = { session: { id: 'session', seq: 0 }, ctx: scope };
  let current = { logical_task_id: 'task', intent_revision: 0, execution_revision: 0,
    workspace: { revision: 0, stamp: 'baseline', paths: ['source'] } };
  const host = new DshForegroundHost(ctx, agent, { enabled: true, tools: ['read', 'edit', 'bash'],
    observeCurrent: async () => current, authorize: async () => true,
    retryPolicy: { maxRetries: 0 }, bashPolicy: { enableRunInBackground: false, promoteOnTimeout: false } });
  host.attach();
  function exec(id = 'call-1', name = 'read', turn = 1) {
    const args = { path: 'source' };
    const event = { type: 'tool/call', seq: agent.session.seq++, data: {
      turn, step: 1, callId: id, name, arguments: JSON.stringify(args) } };
    listeners.get('session/event')(agent.session, event);
    return { callId: id, rootCallId: id, name, arguments: args, agent,
      token: Symbol('native registry token'), signal: new AbortController().signal };
  }
  async function complete(e, status = 'success', terminalStatus = status) {
    const result = { content: [{ type: 'text', text: 'native finalizer output' }], isError: status === 'failure' };
    const message = { id: `message-${e.callId}`, role: 'tool', toolCallId: e.callId,
      source: { kind: 'tool', callId: e.callId }, content: result.content, isError: result.isError };
    await host.execute(e, async () => result);
    listeners.get('tools/result')(e, result);
    const event = { type: 'tool/result', seq: agent.session.seq++, sourceEventSeqs: [host.calls.get(e.callId).seq],
      data: { turn: host.calls.get(e.callId).turn, step: 1, message } };
    listeners.get('session/event')(agent.session, event);
    host.attestTerminal(e.callId, { executionComplete: true, status: terminalStatus, evidenceRef: 'owned-process-end' });
    host.observeInput({ sessionId: 'session', messages: [message] });
    current = { ...current, execution_revision: current.execution_revision + 1 };
    await host.incorporate(e.callId, { current, evidenceRef: 'actual task/result/effects' });
    return { result, message, event };
  }
  return { host, agent, scope, listeners, exec, complete,
    get current() { return current; }, set current(v) { current = v; } };
}

test('native call alone and handler return never prove quiescence', async () => {
  const f = fixture(), e = f.exec();
  assert.equal(f.host.quiescent, false);
  await f.host.prepare(e, async () => ({ kind: 'allow' }));
  assert.equal(f.scope.guard(e), undefined);
  await f.complete(e);
  assert.equal(f.host.quiescent, true);
});

test('failed test then distinct edit/retest work remains tracked', async () => {
  const f = fixture();
  for (const [id, name, status] of [['test', 'bash', 'failure'], ['fix', 'edit', 'success'], ['retest', 'bash', 'success']]) {
    const e = f.exec(id, name);
    await f.host.prepare(e, async () => ({ kind: 'allow' }));
    await f.complete(e, status);
  }
  assert.equal(f.host.records.get('test').status, 'failure');
  assert.equal(f.host.quiescent, true);
  assert.equal(f.host.records.size, 3);
});

for (const mode of ['missing permit', 'changed args', 'nested parent', 'foreign root', 'foreign agent', 'aborted', 'changed seq']) {
  test(`guard refuses ${mode} before execution`, async () => {
    const f = fixture(), e = f.exec();
    if (mode !== 'missing permit') await f.host.prepare(e, async () => ({ kind: 'allow' }));
    if (mode === 'changed args') e.arguments.path = 'other';
    if (mode === 'nested parent') e.parent = Symbol('native parent');
    if (mode === 'foreign root') e.rootCallId = 'other';
    if (mode === 'foreign agent') e.agent = { session: f.agent.session };
    if (mode === 'aborted') e.signal = AbortSignal.abort();
    if (mode === 'changed seq') f.agent.session.seq++;
    let effects = 0;
    assert.notEqual(f.scope.guard(e), undefined);
    await assert.rejects(f.host.execute(e, async () => { effects++; return {}; }));
    assert.equal(effects, 0);
  });
}

test('admission exception and late release retain closed owner', async () => {
  const f = fixture(), e = f.exec();
  f.host.authorize = async () => { throw new Error('host admission failed'); };
  await assert.rejects(f.host.prepare(e, async () => ({ kind: 'allow' })));
  assert.notEqual(f.scope.guard(e), undefined);
  assert.equal(f.host.stopped, true);
});

test('final outcome observer fault cannot be swallowed into success', async () => {
  const f = fixture(), e = f.exec();
  await f.host.prepare(e, async () => ({ kind: 'allow' }));
  await f.host.execute(e, async () => ({ content: [] }));
  f.listeners.get('tools/result')(e, { content: undefined });
  assert.equal(f.host.stopped, true);
  assert.equal(f.host.quiescent, false);
  assert.throws(() => f.host.dispose());
});

test('native error cannot be attested as successful physical work', async () => {
  const f = fixture(), e = f.exec();
  await f.host.prepare(e, async () => ({ kind: 'allow' }));
  await assert.rejects(f.complete(e, 'failure', 'success'));
  assert.equal(f.host.stopped, true);
  assert.equal(f.host.records.get(e.callId).terminal, false);
  assert.equal(f.host.quiescent, false);
});

test('missing native error discriminator cannot become a final successful outcome', async () => {
  const f = fixture(), e = f.exec();
  await f.host.prepare(e, async () => ({ kind: 'allow' }));
  await f.host.execute(e, async () => ({ content: [] }));
  f.listeners.get('tools/result')(e, { content: [] });
  assert.equal(f.host.stopped, true);
  assert.equal(f.host.records.get(e.callId).resultHash, null);
});

test('unknown timeout never detaches callbacks or declares physical end', async () => {
  const f = fixture(), e = f.exec();
  await f.host.prepare(e, async () => ({ kind: 'allow' }));
  await f.host.execute(e, async () => ({ content: [] }));
  assert.throws(() => f.host.attestTerminal(e.callId, { executionComplete: true,
    status: 'failure', uncertain: true, evidenceRef: 'timeout' }));
  assert.throws(() => f.host.dispose());
  assert(f.listeners.has('tools/execute'));
});

test('missing final result, duplicate commit or transformed input is refused', async () => {
  for (const mode of ['no observer', 'duplicate commit', 'wrong input']) {
    const f = fixture(), e = f.exec();
    await f.host.prepare(e, async () => ({ kind: 'allow' }));
    const { event, message } = await f.complete(e);
    if (mode === 'no observer') {
      const other = f.exec('call-2');
      await f.host.prepare(other, async () => ({ kind: 'allow' }));
      assert.throws(() => f.host.observeEvent({ ...event, seq: f.agent.session.seq,
        data: { turn: 1, step: 1, message: { ...message, toolCallId: 'call-2',
          source: { kind: 'tool', callId: 'call-2' } } } }));
    } else if (mode === 'duplicate commit') {
      f.listeners.get('session/event')(f.agent.session, event);
    } else {
      const record = f.host.records.get(e.callId);
      record.incorporated = false;
      assert.throws(() => f.host.observeInput({ sessionId: 'session', messages: [{ ...message, content: [] }] }));
    }
    assert.equal(f.host.stopped, true);
  }
});

test('parallel preparation or duplicate native IDs close admission', async () => {
  const f = fixture(), a = f.exec('one'), b = f.exec('two');
  await assert.rejects(f.host.prepare(a, async () => ({ kind: 'allow' })));
  assert.equal(f.host.stopped, true);
  const g = fixture(), e = g.exec();
  await g.host.prepare(e, async () => ({ kind: 'allow' }));
  await g.complete(e);
  g.exec();
  assert.equal(g.host.stopped, true);
});

test('bound fresh read settles before the same native task opens action work', async () => {
  const f = fixture(), binding = { sessionId: 'session', turn: 3, step: 1 };
  assert.equal(f.host.closeAdmission(), true);
  assert.equal(f.host.openBoundTask('fresh', binding, { readTools: ['read'], bindingRecord: 'saved-claim-binding' }), true);
  const read = f.exec('fresh-read', 'read', 3);
  await f.host.prepare(read, async () => ({ kind: 'allow' }));
  await f.complete(read);
  assert.equal(f.host.openBoundTask('action', binding, { readTools: ['read'], bindingRecord: 'saved-read-effects' }), true);
  const edit = f.exec('after-read-edit', 'edit', 3);
  await f.host.prepare(edit, async () => ({ kind: 'allow' }));
  await f.complete(edit);
  assert.equal(f.host.quiescent, true);
});

test('binding cannot release actions before fresh read or into another native turn', async () => {
  for (const mode of ['early edit', 'foreign turn']) {
    const f = fixture(), binding = { sessionId: 'session', turn: 3, step: 1 };
    f.host.closeAdmission();
    f.host.openBoundTask('fresh', binding, { readTools: ['read'], bindingRecord: 'saved-binding' });
    const e = f.exec('denied-call', mode === 'early edit' ? 'edit' : 'read', mode === 'foreign turn' ? 4 : 3);
    await assert.rejects(f.host.prepare(e, async () => ({ kind: 'allow' })));
    assert.equal(f.host.stopped, true);
    assert.equal(f.host.records.size, 0);
  }
});

test('settled native work exports only detached existing WorkRecord metadata', async () => {
  const f = fixture(), e = f.exec('native-id', 'read', 3);
  await f.host.prepare(e, async () => ({ kind: 'allow' }));
  await f.complete(e);
  f.host.closeAdmission();
  const config = { toolKinds: { read: 'read', edit: 'edit', bash: 'shell' }, effectScope: ['source'] };
  const rows = f.host.observations(config);
  assert.deepEqual(rows[0].identity, { runtime: 'dsh', session_id: 'session', operation_id: 'native-id', native_scope: ['3'] });
  assert.equal(rows[0].execution, 'terminal'); assert.equal(rows[0].incorporation, 'incorporated');
  assert.equal(rows[0].kind, 'read'); assert.equal(rows[0].result_status, 'success');
  assert.equal(rows[0].incorporation_evidence, 'actual task/result/effects');
  assert.equal(Object.keys(rows[0]).length, 9);
  rows[0].effect_scope.push('foreign'); rows[0].identity.operation_id = 'changed';
  assert.deepEqual(f.host.observations(config)[0].effect_scope, ['source']);
  assert.equal(f.host.observations(config)[0].identity.operation_id, 'native-id');
  assert(!JSON.stringify(rows).includes('native finalizer output'));
});

test('work export refuses pending execution and retains failed partial effects', async () => {
  const config = { toolKinds: { read: 'read', edit: 'edit', bash: 'shell' }, effectScope: ['source'] };
  const pending = fixture(); pending.exec();
  assert.throws(() => pending.host.observations(config));
  const failed = fixture(), e = failed.exec('failed-test', 'bash');
  await failed.host.prepare(e, async () => ({ kind: 'allow' }));
  await failed.complete(e, 'failure');
  assert.equal(failed.host.observations(config)[0].result_status, 'failure');
});

test('work export cannot silently classify unknown taxonomy as success', async () => {
  const f = fixture(), e = f.exec();
  await f.host.prepare(e, async () => ({ kind: 'allow' })); await f.complete(e);
  assert.throws(() => f.host.observations({ toolKinds: { read: 'test' }, effectScope: ['source'] }));
  assert.equal(f.host.stopped, true);
});

async function actionWork(f, turn = 3) {
  const binding = { sessionId: 'session', turn, step: 1 };
  f.host.closeAdmission();
  f.host.openBoundTask('fresh', binding, { readTools: ['read'], bindingRecord: `saved-binding-${turn}` });
  const read = f.exec(`read-${turn}`, 'read', turn);
  await f.host.prepare(read, async () => ({ kind: 'allow' })); await f.complete(read);
  f.host.openBoundTask('action', binding, { readTools: ['read'], bindingRecord: `saved-read-${turn}` });
  const edit = f.exec(`edit-${turn}`, 'edit', turn);
  await f.host.prepare(edit, async () => ({ kind: 'allow' })); await f.complete(edit);
  return binding;
}

test('work reset preserves all histories and admits normal later work across two task cycles', async () => {
  const f = fixture(), first = await actionWork(f);
  const { calls, records, seen } = f.host;
  const oldCalls = [...calls], oldRecords = [...records], oldSeen = [...seen];
  f.host.closeAdmission();
  assert.equal(f.host.openBoundTask('work', first, { readTools: ['read'], bindingRecord: 'durable-return-1' }), true);
  assert.equal(f.host.boundTurn, null); assert.equal(f.host.recoveryMode, null); assert.equal(f.host.readNames.size, 0);
  assert.equal(f.host.returnedTurnFloor, 3); assert.equal(f.host.barrier, false);
  assert.equal(f.host.calls, calls); assert.equal(f.host.records, records); assert.equal(f.host.seen, seen);
  assert.deepEqual([...calls], oldCalls); assert.deepEqual([...records], oldRecords); assert.deepEqual([...seen], oldSeen);
  const normal = f.exec('normal-edit', 'edit', 4);
  await f.host.prepare(normal, async () => ({ kind: 'allow' })); await f.complete(normal);
  const second = await actionWork(f, 6);
  f.host.closeAdmission(); f.host.openBoundTask('work', second, { readTools: ['read'], bindingRecord: 'durable-return-2' });
  assert.equal(f.host.returnedTurnFloor, 6); assert.equal(f.host.calls.size, 5); assert.equal(f.host.records.size, 5);
  assert.equal(f.host.seen.size, 5); assert.equal(f.host.quiescent, true);
});

test('returned native binding and tool turn cannot replay after reset', async () => {
  for (const mode of ['fresh', 'action', 'work', 'tool turn', 'seen ID', 'old permit']) {
    const f = fixture(), binding = await actionWork(f);
    const prior = f.host.records.get('edit-3');
    f.host.closeAdmission(); f.host.openBoundTask('work', binding, { readTools: ['read'], bindingRecord: 'saved-return' });
    if (['fresh', 'action', 'work'].includes(mode)) {
      f.host.closeAdmission();
      assert.throws(() => f.host.openBoundTask(mode, binding, { readTools: ['read'], bindingRecord: 'replayed-binding' }));
    } else if (mode === 'old permit') {
      assert.throws(() => f.host.guard({ callId: 'edit-3', rootCallId: 'edit-3', name: 'edit', arguments: { path: 'source' },
        agent: f.agent, token: prior.token, signal: new AbortController().signal }));
    } else {
      f.exec(mode === 'seen ID' ? 'read-3' : 'new-ID-old-turn', 'read', mode === 'seen ID' ? 4 : 3);
      assert.equal(f.host.calls.size, 2);
    }
    assert.equal(f.host.stopped, true); assert.equal(f.host.records.size, 2); assert.equal(f.host.seen.size, 2);
    assert(f.host.disposers.length > 0); assert.equal(f.host.returnedTurnFloor, 3);
  }
});

test('work reset requires closed same action binding and wholly incorporated work', async () => {
  for (const mode of ['open gate', 'fresh mode', 'wrong bound turn', 'pending call']) {
    const f = fixture(), binding = await actionWork(f);
    if (mode === 'pending call') f.exec('pending', 'read', 3);
    if (mode !== 'open gate') f.host.closeAdmission();
    if (mode === 'fresh mode') f.host.recoveryMode = 'fresh';
    if (mode === 'wrong bound turn') f.host.boundTurn = 4;
    assert.throws(() => f.host.openBoundTask('work', binding, { readTools: ['read'], bindingRecord: 'saved-return' }));
    assert.equal(f.host.stopped, true); assert.equal(f.host.returnedTurnFloor, 0);
    assert(f.host.disposers.length > 0);
  }
});

test('foreground settings are deployment preconditions, not guessed from commands', () => {
  const f = fixture();
  assert.throws(() => new DshForegroundHost({}, f.agent, { enabled: true, tools: ['bash'],
    observeCurrent: async () => ({}), authorize: async () => true, retryPolicy: { maxRetries: 1 },
    bashPolicy: { enableRunInBackground: false, promoteOnTimeout: false } }));
});
