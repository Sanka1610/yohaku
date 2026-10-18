// Offline transport injection only; never contacts a provider or loads authentication.
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { zstdCompressSync } from 'node:zlib';
import { bindDshPiAiGateToOwnedAdapter, createDshPiAiGateAdapter, DshSseAttemptGate } from '../src/yohaku/dsh_pi_ai_gate.mjs';

function fixture() {
  const binding = { sessionId: 'session', turn: 2, step: 1, attemptId: 'native-attempt',
    frameRevision: 3, provider: 'openai-codex', model: 'native-model' };
  const current = { logical_task_id: 'task', execution_revision: 1 };
  const state = { binding, current };
  let sends = 0, received;
  const signal = new AbortController();
  const gate = new DshSseAttemptGate({ binding, current, signal: signal.signal,
    url: 'https://provider.invalid/responses', observe: async () => state,
    validatePayload: async body => body.input?.[0]?.content === 'handoff',
    authorize: async () => true,
    fetch: async (url, options) => { sends++; received = options; return { status: 200 }; } });
  const model = { provider: binding.provider, id: binding.model };
  const body = { model: model.id, input: [{ role: 'user', content: 'handoff' }] };
  async function prepared(compressed = false) {
    const payload = await gate.callbacks.onPayload(body, model);
    const bytes = JSON.stringify(payload);
    return { method: 'POST', body: compressed ? new Uint8Array(zstdCompressSync(bytes)) : bytes,
      headers: compressed ? { 'content-encoding': 'zstd' } : {}, signal: signal.signal };
  }
  async function accepted(options) {
    const response = await gate.callbacks.fetch('https://provider.invalid/responses', options);
    await gate.callbacks.onResponse(response, model);
    return gate.requireAccepted();
  }
  return { gate, state, signal, model, body, prepared, accepted,
    get sends() { return sends; }, get received() { return received; } };
}

for (const compressed of [false, true]) {
  test(`exact ${compressed ? 'zstd' : 'JSON'} bytes pass once without rewriting`, async () => {
    const f = fixture(), options = await f.prepared(compressed);
    assert.equal(f.gate.evidence, null);
    const proof = await f.accepted(options);
    assert.equal(proof.result, 'http-accepted');
    assert.equal(proof.encoding, compressed ? 'zstd' : 'identity');
    assert.equal(f.received, options);
    assert.equal(f.sends, 1);
    assert(!JSON.stringify(proof).includes('handoff'));
    await assert.rejects(f.gate.callbacks.fetch('https://provider.invalid/responses', options));
    assert.equal(f.sends, 1);
  });
}

for (const mode of ['wrong body', 'foreign URL', 'wrong encoding', 'abort', 'changed native attempt', 'owner task changed']) {
  test(`${mode} prevents provider effect`, async () => {
    const f = fixture(), options = await f.prepared();
    if (mode === 'wrong body') options.body = JSON.stringify({ ...f.body, input: [] });
    if (mode === 'wrong encoding') options.headers['content-encoding'] = 'gzip';
    if (mode === 'abort') f.signal.abort();
    if (mode === 'changed native attempt') f.state.binding = { ...f.state.binding, attemptId: 'foreign' };
    if (mode === 'owner task changed') f.state.current = { ...f.state.current, execution_revision: 2 };
    await assert.rejects(f.gate.callbacks.fetch(mode === 'foreign URL' ? 'https://other.invalid/'
      : 'https://provider.invalid/responses', options));
    assert.equal(f.sends, 0);
    assert.throws(() => f.gate.requireAccepted());
  });
}

test('payload validation/authorization faults are caught before transport', async () => {
  for (const fault of ['validation', 'authorization']) {
    const f = fixture();
    if (fault === 'validation') f.gate.validatePayload = async () => { throw new Error('fault'); };
    else f.gate.authorize = async () => false;
    await assert.rejects(f.prepared());
    assert.equal(f.sends, 0);
    assert(f.gate.stopped);
  }
});

test('mutation during final fresh read cannot bypass wire equality', async () => {
  const f = fixture(), options = await f.prepared();
  let calls = 0;
  f.gate.observe = async () => { if (++calls === 2) options.body += ' '; return f.state; };
  await assert.rejects(f.gate.callbacks.fetch('https://provider.invalid/responses', options));
  assert.equal(f.sends, 0);
});

test('failed/foreign HTTP response consumes send and permits no blind retry', async () => {
  for (const status of [403, 500]) {
    const f = fixture(), options = await f.prepared();
    f.gate.transport = async () => ({ status });
    const response = await f.gate.callbacks.fetch('https://provider.invalid/responses', options);
    await assert.rejects(f.gate.callbacks.onResponse(response, f.model));
    assert.equal(f.gate.sendCount, 1);
    assert.throws(() => f.gate.requireAccepted());
    await assert.rejects(f.gate.callbacks.fetch('https://provider.invalid/responses', options));
  }
});

test('missing or duplicate callback never provides a new acceptance', async () => {
  const f = fixture();
  await assert.rejects(f.gate.callbacks.fetch('https://provider.invalid/responses', {
    method: 'POST', body: '{}', signal: f.signal.signal }));
  assert.equal(f.sends, 0);
  const g = fixture(), options = await g.prepared();
  await g.accepted(options);
  const evidence = g.gate.evidence;
  await assert.rejects(g.gate.callbacks.onResponse({ status: 200 }, g.model));
  assert.equal(g.gate.evidence, evidence); // Historical receipt retained, not re-issued.
});

test('bounded decompression and lossy payloads fail closed', async () => {
  const f = fixture(), options = await f.prepared(true);
  f.gate.maxBytes = 8;
  await assert.rejects(f.gate.callbacks.fetch('https://provider.invalid/responses', options));
  assert.equal(f.sends, 0);
  const g = fixture();
  g.body.unobserved = undefined;
  await assert.rejects(g.prepared());
  assert.equal(g.sends, 0);
});

class MockNativeAdapter {
  constructor(config) { this.config = config; }
  async *streamWithSnapshot(options, snapshot) {
    for await (const chunk of snapshot.models.streamSimple({ provider: options.provider, id: options.model }, {}, {})) {
      yield chunk;
    }
  }
}

test('shim preserves original snapshot/models and injects no model/provider change', async () => {
  const f = fixture();
  const models = { async *streamSimple(model, context, options) {
    assert.equal(options.transport, 'sse'); assert.equal(options.maxRetries, 0);
    const payload = await options.onPayload(f.body, model);
    const response = await options.fetch('https://provider.invalid/responses', {
      method: 'POST', body: JSON.stringify(payload), signal: f.signal.signal });
    await options.onResponse(response, model);
    yield { kind: 'native-output' };
  } };
  const original = models.streamSimple, snapshot = Object.freeze({ models, other: 'preserved' });
  const adapter = createDshPiAiGateAdapter(MockNativeAdapter, { private: 'native-config' }, {
    enabled: true, retryPolicy: { maxRetries: 0 }, gateFor: () => f.gate });
  const chunks = [];
  for await (const chunk of adapter.streamWithSnapshot({ sessionId: 'session', provider: 'openai-codex',
    model: 'native-model' }, snapshot)) chunks.push(chunk);
  assert.deepEqual(chunks, [{ kind: 'native-output' }]);
  assert.equal(models.streamSimple, original);
  assert.equal(snapshot.models, models);
  assert.equal(f.sends, 1);
});

test('shim refuses missing callbacks/acceptance before yielding model output', async () => {
  const f = fixture();
  const adapter = createDshPiAiGateAdapter(MockNativeAdapter, {}, {
    enabled: true, retryPolicy: { maxRetries: 0 }, gateFor: () => f.gate });
  let chunks = 0;
  await assert.rejects(async () => {
    for await (const chunk of adapter.streamWithSnapshot({ sessionId: 'session', provider: 'openai-codex',
      model: 'native-model' }, { models: { async *streamSimple() { yield 'unqualified'; } } })) chunks++;
  });
  assert.equal(chunks, 0); assert.equal(f.sends, 0);
});

test('shim cannot silently use a different engine or retry policy', () => {
  assert.throws(() => createDshPiAiGateAdapter(MockNativeAdapter, {}, {
    enabled: true, retryPolicy: { maxRetries: 1 }, gateFor() {} }));
});

// Source-shaped subset of subscription 2.5.3's callback order, not a native plugin test.
// Preferences surround the caller hook; image detail can be added after that hook.
async function subscriptionShapedPayload(onPayload, body, model, detail = 'auto') {
  const preferred = { ...body, text: { ...body.text, verbosity: 'low' }, service_tier: 'default' };
  const next = await onPayload(preferred, model);
  const detailed = detail === 'auto' ? next : { ...next, input: next.input.map(item => {
    const field = Array.isArray(item.content) ? 'content'
      : ['function_call_output', 'custom_tool_call_output'].includes(item.type) && Array.isArray(item.output) ? 'output' : undefined;
    return field === undefined ? item : { ...item, [field]: item[field].map(part =>
      part.type === 'input_image' ? { ...part, detail } : part) };
  }) };
  return { ...detailed, text: { ...detailed.text, verbosity: 'low' }, service_tier: 'default' };
}

for (const compressed of [false, true]) {
  for (const shape of ['text', 'already-detailed-image', 'changed-input-image', 'changed-tool-image']) {
    test(`source-shaped post-hook ${shape}, ${compressed ? 'zstd' : 'JSON'}: exact bytes only`, async () => {
      const f = fixture(), initial = structuredClone(f.body);
      if (shape !== 'text') {
        const image = { type: 'input_image', image_url: 'https://image.invalid/fixture' };
        if (shape === 'already-detailed-image') image.detail = 'high';
        f.body.input.push(shape === 'changed-tool-image'
          ? { type: 'function_call_output', call_id: 'fixture-call', output: [image] }
          : { type: 'message', role: 'user', content: [image] });
      }
      const sourceBody = structuredClone(f.body);
      let wireOptions;
      const models = { async *streamSimple(model, context, options) {
        assert.equal(options.transport, 'sse'); assert.equal(options.maxRetries, 0);
        const payload = await subscriptionShapedPayload(options.onPayload, f.body, model, shape === 'text' ? 'auto' : 'high');
        const json = JSON.stringify(payload);
        wireOptions = { method: 'POST', body: compressed ? new Uint8Array(zstdCompressSync(json)) : json,
          headers: compressed ? { 'content-encoding': 'zstd' } : {}, signal: f.signal.signal };
        const response = await options.fetch('https://provider.invalid/responses', wireOptions);
        await options.onResponse(response, model);
        yield 'source-shaped-output';
      } };
      const original = models.streamSimple;
      const adapter = createDshPiAiGateAdapter(MockNativeAdapter, {}, {
        enabled: true, retryPolicy: { maxRetries: 0 }, gateFor: () => f.gate });
      const chunks = [];
      const run = async () => {
        for await (const chunk of adapter.streamWithSnapshot({ sessionId: 'session', provider: 'openai-codex',
          model: 'native-model' }, Object.freeze({ models }))) chunks.push(chunk);
      };
      if (shape.startsWith('changed-')) {
        await assert.rejects(run, /serialized body changed after payload gate/);
        assert.equal(f.sends, 0); assert.equal(f.gate.evidence, null); assert(f.gate.stopped);
        assert.deepEqual(chunks, []);
      } else {
        await run(); assert.equal(f.sends, 1); assert.equal(f.received, wireOptions);
        assert.equal(f.gate.requireAccepted().encoding, compressed ? 'zstd' : 'identity');
        assert.deepEqual(chunks, ['source-shaped-output']);
      }
      assert.deepEqual(f.body, sourceBody); assert.equal(models.streamSimple, original);
      assert.deepEqual(f.body.input[0], initial.input[0]);
    });
  }
}

function ownedFixture() {
  const f = fixture(), owner = { idle: true }, trace = [];
  const models = { async *streamSimple(model, context, options) {
    const payload = await options.onPayload(f.body, model);
    const response = await options.fetch('https://provider.invalid/responses', {
      method: 'POST', body: JSON.stringify(payload), signal: f.signal.signal });
    await options.onResponse(response, model);
    yield 'owned-output';
  } };
  class Native extends MockNativeAdapter {
    stream(options) { return this.streamWithSnapshot(options, this.config.snapshot); }
    async prepareCall() {
      return { model: 'preserved-metadata', stream: options => this.streamWithSnapshot(options, this.config.snapshot) };
    }
    async *streamWithSnapshot(options, snapshot) {
      trace.push('inner');
      assert.equal(snapshot.other, 'preserved');
      yield* super.streamWithSnapshot(options, snapshot);
    }
  }
  const config = { snapshot: Object.freeze({ models, other: 'preserved' }), auth: () => { throw new Error('auth not in scope'); } };
  const inner = new Native(config);
  const wrap = factory => (async function* () {
    trace.push('outer-start');
    try { yield* factory(); } finally { trace.push('outer-end'); }
  })();
  // Same method binding/prepareCall shape as the installed compaction Proxy; no plugin import.
  const outer = new Proxy(inner, { get(target, key) {
    if (key === 'stream') return options => wrap(() => target.stream(options));
    if (key === 'prepareCall') return async () => {
      const call = await target.prepareCall();
      return { ...call, stream: options => wrap(() => call.stream(options)) };
    };
    const value = Reflect.get(target, key, target);
    return typeof value === 'function' ? value.bind(target) : value;
  } });
  const options = { sessionId: 'session', provider: 'openai-codex', model: 'native-model' };
  const policy = { enabled: true, exclusive: true, retryPolicy: { maxRetries: 0 },
    isQuiescent: () => owner.idle, gateFor: () => f.gate };
  return { f, owner, trace, config, inner, outer, models, options, policy,
    bind: overrides => bindDshPiAiGateToOwnedAdapter(outer, { ...policy, ...overrides }) };
}

for (const prepared of [false, true]) {
  test(`owned binding preserves outer Proxy and ${prepared ? 'prepared' : 'direct'} dispatch`, async () => {
    const o = ownedFixture(), originalModels = o.models.streamSimple;
    const binding = o.bind();
    const call = prepared ? await o.outer.prepareCall() : o.outer;
    if (prepared) assert.equal(call.model, 'preserved-metadata');
    assert.deepEqual(await Array.fromAsync(call.stream(o.options)), ['owned-output']);
    assert.deepEqual(o.trace, ['outer-start', 'inner', 'outer-end']);
    assert.equal(o.outer.config, o.config); assert.equal(o.inner.config.auth, o.config.auth);
    assert.equal(o.models.streamSimple, originalModels); assert.equal(o.f.sends, 1);
    binding.retire(); binding.retire();
    await assert.rejects(Array.fromAsync(o.outer.stream(o.options)), /retired/);
    assert.equal(o.f.sends, 1);
  });
}

test('retire closes retained prepared calls, bound callbacks and unstarted iterators', async () => {
  const o = ownedFixture(), binding = o.bind();
  const prepared = await o.outer.prepareCall();
  const heldPort = o.outer.streamWithSnapshot;
  const delayed = heldPort(o.options, o.config.snapshot);
  binding.retire();
  await assert.rejects(Array.fromAsync(prepared.stream(o.options)), /retired/);
  await assert.rejects(Array.fromAsync(heldPort(o.options, o.config.snapshot)), /retired/);
  await assert.rejects(delayed.next(), /retired/);
  assert(!o.trace.includes('inner')); assert.equal(o.f.sends, 0);
});

test('retire invalidates held attempt callbacks without deleting historical evidence', async () => {
  const o = ownedFixture(), binding = o.bind();
  await Array.fromAsync(o.outer.stream(o.options));
  const proof = o.f.gate.requireAccepted(), callbacks = o.f.gate.callbacks;
  binding.retire();
  assert.equal(o.f.gate.evidence, proof);
  assert.throws(() => o.f.gate.requireAccepted());
  await assert.rejects(callbacks.onPayload(o.f.body, o.f.model));
  await assert.rejects(callbacks.fetch('https://provider.invalid/responses', {
    method: 'POST', body: JSON.stringify(o.f.body), signal: o.f.signal.signal }));
  await assert.rejects(callbacks.onResponse({ status: 200 }, o.f.model));
  assert.equal(o.f.sends, 1);
});

test('binding permanently reserves the private slot without violating Proxy method binding', async () => {
  const o = ownedFixture(), binding = o.bind();
  const descriptor = Object.getOwnPropertyDescriptor(o.inner, 'streamWithSnapshot');
  assert.equal(typeof descriptor.get, 'function'); assert.equal(descriptor.set, undefined);
  assert.equal(descriptor.configurable, false);
  assert.equal(typeof o.outer.streamWithSnapshot, 'function');
  assert.equal(Reflect.set(o.outer, 'streamWithSnapshot', async function* () {}), false);
  assert.equal(Reflect.deleteProperty(o.outer, 'streamWithSnapshot'), false);
  assert.throws(() => Object.defineProperty(o.outer, 'streamWithSnapshot', { value() {} }), TypeError);
  assert.throws(() => o.bind(), /existing.*hook/);
  binding.retire();
  assert.throws(() => o.bind(), /existing.*hook/);
  await assert.rejects(Array.fromAsync(o.inner.stream(o.options)), /retired/);
  assert.equal(o.f.sends, 0);
});

test('owner-wide quiescence fences preparation and is not just inner active count', () => {
  const o = ownedFixture(), binding = o.bind();
  o.owner.idle = false; // SDK request preparation / outer wrapper / inbox / work pending.
  assert.throws(() => binding.retire(), /quiescent/);
  assert.equal(o.f.sends, 0);
  o.owner.idle = true;
  binding.retire();
});

test('outer prepared-call activity blocks retire before the inner seam starts', async () => {
  const o = ownedFixture(), prepare = o.inner.prepareCall.bind(o.inner);
  let enter, release;
  const entered = new Promise(resolve => { enter = resolve; });
  const ready = new Promise(resolve => { release = resolve; });
  o.inner.prepareCall = async () => { o.owner.idle = false; enter(); await ready; return prepare(); };
  const binding = o.bind(), pending = o.outer.prepareCall();
  await entered;
  assert(!o.trace.includes('inner')); assert.equal(o.f.sends, 0);
  assert.throws(() => binding.retire(), /quiescent/);
  release(); const prepared = await pending;
  assert.deepEqual(await Array.fromAsync(prepared.stream(o.options)), ['owned-output']);
  o.owner.idle = true; binding.retire();
  assert.equal(o.f.sends, 1);
});

test('binding rechecks owner idleness and slot conflicts immediately before installation', () => {
  const o = ownedFixture(); let checks = 0;
  assert.throws(() => o.bind({ isQuiescent: () => ++checks === 1 }), /quiescent/);
  assert.equal(Object.hasOwn(o.inner, 'streamWithSnapshot'), false);
  const p = ownedFixture(), foreign = async function* () {}; let calls = 0;
  assert.throws(() => p.bind({ isQuiescent: () => {
    if (++calls === 2) Object.defineProperty(p.inner, 'streamWithSnapshot', { value: foreign, configurable: true });
    return true;
  } }), /existing.*hook/);
  assert.equal(p.inner.streamWithSnapshot, foreign); assert.equal(p.f.sends, 0);
});

test('busy stream rejects retirement and overlapping dispatch until the iterator closes', async () => {
  const o = ownedFixture();
  let enter, release;
  const entered = new Promise(resolve => { enter = resolve; });
  const ready = new Promise(resolve => { release = resolve; });
  const original = o.models.streamSimple;
  o.models.streamSimple = async function* (...args) { enter(); await ready; yield* original(...args); };
  const binding = o.bind(), iterator = o.outer.stream(o.options);
  const first = iterator.next(); await entered;
  assert.throws(() => binding.retire(), /active/);
  await assert.rejects(o.outer.stream(o.options).next(), /overlapping/);
  assert.equal(o.f.sends, 0);
  release(); assert.equal((await first).value, 'owned-output');
  assert.throws(() => binding.retire(), /active/); // Paused after yielding still owns the scope.
  await iterator.return();
  binding.retire(); assert.equal(o.f.sends, 1);
});

test('binding refuses missing opt-in, callbacks, idle proof, and pre-existing seams', () => {
  for (const change of [{ enabled: false }, { exclusive: false }, { retryPolicy: { maxRetries: 1 } },
    { gateFor: undefined }, { isQuiescent: undefined }, { isQuiescent: () => false },
    { isQuiescent: () => 1 }, { isQuiescent: () => { throw new Error('unknown owner'); } }]) {
    const o = ownedFixture(); assert.throws(() => o.bind(change));
    assert.equal(Object.hasOwn(o.inner, 'streamWithSnapshot'), false); assert.equal(o.f.sends, 0);
  }
  const o = ownedFixture(), foreign = async function* () {};
  Object.defineProperty(o.inner, 'streamWithSnapshot', { value: foreign, configurable: true });
  assert.throws(() => o.bind(), /existing.*hook/);
  assert.equal(o.inner.streamWithSnapshot, foreign);
  const frozen = ownedFixture(); Object.preventExtensions(frozen.inner);
  assert.throws(() => frozen.bind());
  assert.equal(Object.hasOwn(frozen.inner, 'streamWithSnapshot'), false);
});
