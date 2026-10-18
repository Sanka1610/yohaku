// Version-local compatibility shim for DSH 0.2.0-rc.2, not a public SDK extension.
import { createHash } from 'node:crypto';
import * as zlib from 'node:zlib';
import { valueHash } from './dsh_foreground.mjs';
const hash = value => createHash('sha256').update(value).digest('hex');
const freeze = value => {
  if (value && typeof value === 'object') {
    for (const item of Object.values(value)) freeze(item);
    Object.freeze(value);
  }
  return value;
};

/** One observed native attempt. Owner callbacks and the actual transport are injected.
 * Receipt is HTTP acceptance of these exact bytes, not model understanding or terminal
 * task completion. No IDs are invented, no auth fields are retained, no retry is allowed.
 */
export class DshSseAttemptGate {
  constructor({ binding, current, observe, validatePayload, authorize, fetch, url,
      signal, maxBytes = 2 * 1024 * 1024 }) {
    if (!binding || typeof binding.sessionId !== 'string' || !binding.sessionId.trim()
        || typeof binding.attemptId !== 'string' || !binding.attemptId.trim()
        || typeof binding.model !== 'string' || !binding.model.trim()
        || binding.provider !== 'openai-codex' || !Number.isSafeInteger(binding.turn) || binding.turn < 1
        || !Number.isSafeInteger(binding.step) || binding.step < 1
        || !Number.isSafeInteger(binding.frameRevision) || binding.frameRevision < 1
        || ![observe, validatePayload, authorize, fetch].every(f => typeof f === 'function')
        || typeof url !== 'string' || !signal || signal.aborted
        || !Number.isSafeInteger(maxBytes) || maxBytes < 1 || maxBytes > 4 * 1024 * 1024) {
      throw new Error('owned native attempt and exact SSE transport required');
    }
    new URL(url);
    this.binding = freeze(structuredClone(binding)); this.current = freeze(structuredClone(current));
    this.observe = observe; this.validatePayload = validatePayload; this.authorize = authorize;
    this.transport = fetch; this.url = url; this.signal = signal; this.maxBytes = maxBytes;
    this.phase = 'new'; this.sendCount = 0; this.stopped = false; this.evidence = null;
    this.callbacks = { onPayload: (body, model) => this.onPayload(body, model),
      fetch: (url, options) => this.send(url, options),
      onResponse: (response, model) => this.onResponse(response, model), transport: 'sse', maxRetries: 0 };
  }
  stop() { this.stopped = true; }
  fail(reason) { this.stop(); throw new Error(reason); }
  async fresh() {
    if (this.stopped || this.signal.aborted) this.fail('attempt stopped or aborted');
    const actual = await this.observe();
    if (this.stopped || this.signal.aborted || valueHash(actual.binding) !== valueHash(this.binding)
        || valueHash(actual.current) !== valueHash(this.current)) this.fail('native attempt or task changed');
  }
  modelMatches(model) {
    if (model?.provider !== this.binding.provider || model.id !== this.binding.model) this.fail('foreign native model');
  }
  async onPayload(body, model) {
    try {
      this.modelMatches(model); await this.fresh();
      if (this.phase !== 'new') this.fail('duplicate payload callback');
      this.phase = 'preparing';
      if (await this.validatePayload(body, this.binding) !== true) this.fail('actual transformed input rejected');
      // Preserve the native property order and JSON semantic value. No arguments are filled in.
      const json = JSON.stringify(body);
      if (typeof json !== 'string' || Buffer.byteLength(json) > this.maxBytes) this.fail('payload exceeds bound');
      valueHash(body); // Reject lossy/unsupported JSON values, including NaN and undefined.
      this.payloadHash = hash(json);
      const detached = freeze(structuredClone(body));
      if (await this.authorize({ binding: this.binding, payloadHash: this.payloadHash }) !== true) {
        this.fail('current one-shot authorization refused');
      }
      await this.fresh(); this.phase = 'prepared';
      return detached;
    } catch (error) { this.stop(); throw error; }
  }
  wireBytes(options) {
    const body = options.body;
    if (typeof body !== 'string' && !ArrayBuffer.isView(body)) this.fail('unknown native request body');
    const wire = typeof body === 'string' ? Buffer.from(body) : Buffer.from(body.buffer, body.byteOffset, body.byteLength);
    if (wire.length > this.maxBytes) this.fail('wire body exceeds bound');
    const encoding = new Headers(options.headers).get('content-encoding');
    if (encoding === 'zstd' && typeof zlib.zstdDecompressSync !== 'function') this.fail('zstd observation unavailable');
    const plain = encoding === 'zstd' ? zlib.zstdDecompressSync(wire, { maxOutputLength: this.maxBytes }) : wire;
    if (encoding !== null && encoding !== 'zstd') this.fail('unmeasured native encoding');
    if (plain.length > this.maxBytes || hash(plain) !== this.payloadHash) this.fail('serialized body changed after payload gate');
    return { wireHash: hash(wire), encoding: encoding ?? 'identity' };
  }
  async send(url, options) {
    try {
      await this.fresh();
      if (this.phase !== 'prepared' || this.sendCount || String(url) !== this.url
          || options?.method !== 'POST' || options.signal?.aborted !== false) this.fail('foreign/duplicate native send');
      const wire = this.wireBytes(options);
      await this.fresh();
      if (this.phase !== 'prepared' || this.sendCount || options.signal.aborted
          || this.wireBytes(options).wireHash !== wire.wireHash) this.fail('late or changed native send');
      // Consume before I/O. Forward the original request body/options without reserialization.
      this.phase = 'sent'; this.sendCount = 1; this.wire = wire;
      const response = await this.transport(url, options);
      if (this.stopped || this.signal.aborted || options.signal.aborted
          || !Number.isInteger(response?.status)) this.fail('response outcome unconfirmed');
      this.status = response.status;
      return response;
    } catch (error) { this.stop(); throw error; }
  }
  async onResponse(response, model) {
    try {
      this.modelMatches(model); await this.fresh();
      if (this.phase !== 'sent' || this.sendCount !== 1 || response?.status !== this.status
          || this.status < 200 || this.status >= 300) this.fail('HTTP acceptance unconfirmed');
      this.phase = 'accepted';
      this.evidence = freeze({ binding: this.binding, payloadHash: this.payloadHash,
        wireHash: this.wire.wireHash, encoding: this.wire.encoding, result: 'http-accepted', sends: 1 });
      return this.evidence;
    } catch (error) { this.stop(); throw error; }
  }
  requireAccepted() {
    if (this.stopped || this.phase !== 'accepted' || !this.evidence) this.fail('native callbacks/acceptance missing');
    return this.evidence;
  }
}

/** Base is the pinned native PiAiAdapter. Instance-local copies avoid modifying the
 * mounted adapter, its shared Models collection, global fetch or any installed file.
 * Each owner constructs a fresh adapter; streamWithSnapshot is a PRIVATE pin seam.
 */
export function createDshPiAiGateAdapter(Base, config, { enabled = false, retryPolicy, gateFor }) {
  if (enabled !== true || retryPolicy?.maxRetries !== 0 || typeof gateFor !== 'function'
      || typeof Base?.prototype?.streamWithSnapshot !== 'function') {
    throw new Error('pinned private adapter seam requires explicit no-retry opt-in');
  }
  return new (class extends Base {
    async *streamWithSnapshot(options, snapshot) {
      yield* gatedSnapshotStream(options, snapshot, gateFor, (o, s) => super.streamWithSnapshot(o, s));
    }
  })(config);
}

async function* gatedSnapshotStream(options, snapshot, gateFor, dispatch) {
  if (options.provider !== 'openai-codex') throw new Error('unqualified provider route');
  const gate = gateFor(options);
  if (!(gate instanceof DshSseAttemptGate) || options.sessionId !== gate.binding.sessionId
      || options.model !== gate.binding.model) throw new Error('owned native attempt gate required');
  let wrapped = false;
  const models = new Proxy(snapshot.models, {
    get(target, key) {
      if (key === 'streamSimple') return (model, context, lowOptions) => {
        if (wrapped || ['onPayload', 'onResponse', 'fetch'].some(k => lowOptions?.[k] !== undefined)) {
          gate.fail('duplicate stream or unknown native callbacks');
        }
        wrapped = true; gate.modelMatches(model);
        return target.streamSimple(model, context, { ...lowOptions, ...gate.callbacks });
      };
      const value = Reflect.get(target, key, target);
      return typeof value === 'function' ? value.bind(target) : value;
    },
  });
  try {
    for await (const chunk of dispatch(options, { ...snapshot, models })) {
      gate.requireAccepted(); yield chunk;
    }
    gate.requireAccepted();
  } catch (error) { gate.stop(); throw error; }
}

/** Bind only a fresh, exclusively owned, unregistered pinned adapter (or its native Proxy).
 * Keep the outer stream/prepareCall wrapper, config, auth closures and receiver intact.
 * isQuiescent must observe the whole owner: preparation, driver, queues and physical work;
 * it is a trusted embedding contract, not producer authentication. Stop the owner on error.
 * No original seam may have been exposed to earlier consumers; this cannot revoke such references.
 * Retirement closes this inner model-stream port, not earlier outer/auth/network activity.
 */
export function bindDshPiAiGateToOwnedAdapter(adapter, {
  enabled = false, exclusive = false, retryPolicy, gateFor, isQuiescent,
} = {}) {
  if (enabled !== true || exclusive !== true || retryPolicy?.maxRetries !== 0
      || typeof gateFor !== 'function' || typeof isQuiescent !== 'function'
      || !adapter || typeof adapter !== 'object') {
    throw new Error('exclusive owned adapter binding requires explicit no-retry opt-in and owner observation');
  }
  const assertFreshSlot = () => {
    if (Object.hasOwn(adapter, 'streamWithSnapshot')) throw new Error('existing private adapter hook cannot be replaced');
    if (!Object.isExtensible(adapter)) throw new Error('owned adapter cannot accept a private hook');
  };
  assertFreshSlot();
  if (isQuiescent() !== true) throw new Error('owned adapter is not quiescent');
  const nativeStream = adapter.streamWithSnapshot;
  if (typeof nativeStream !== 'function') throw new Error('pinned private adapter seam missing');
  let active = false, retired = false;
  const gates = new Set();
  const ownedGateFor = options => {
    const gate = gateFor(options);
    if (gate instanceof DshSseAttemptGate) gates.add(gate);
    return gate;
  };
  async function* port(options, snapshot) {
    if (retired) throw new Error('owned adapter binding retired');
    if (active) throw new Error('overlapping owned adapter stream');
    active = true;
    try {
      yield* gatedSnapshotStream(options, snapshot, ownedGateFor, (o, s) => nativeStream.call(adapter, o, s));
    } finally { active = false; }
  }
  // Getter access is compatible with the native Proxy that binds returned functions.
  // A non-writable data slot would violate that Proxy's get invariant instead.
  const idle = isQuiescent();
  if (active || idle !== true) throw new Error('owned adapter is not quiescent');
  assertFreshSlot();
  Object.defineProperty(adapter, 'streamWithSnapshot', {
    get: () => port, configurable: false, enumerable: false,
  });
  return Object.freeze({ retire() {
    if (retired) return;
    if (active) throw new Error('owned adapter stream still active');
    const idle = isQuiescent();
    if (active || idle !== true) throw new Error('owned adapter is not quiescent');
    retired = true; // Never restore an ungated method; retained/lazy callbacks stay closed.
    for (const gate of gates) gate.stop();
    gates.clear();
  } });
}
