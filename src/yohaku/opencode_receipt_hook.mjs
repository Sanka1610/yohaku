// Only the attested terminal http.request position on OpenCode 2.0.21 is supported.
import { createHash } from 'node:crypto';
const hash = bytes => createHash('sha256').update(bytes).digest('hex');

export default {
  id: 'yohaku.opencode.receipt',
  async setup(ctx) {
    const { origin, token } = ctx.options;
    const call = async (path, data) => {
      const response = await fetch(origin + path, {
        method: 'POST', headers: { 'content-type': 'application/json', authorization: `Bearer ${token}` },
        body: JSON.stringify(data), signal: AbortSignal.timeout(60000)
      });
      if (!response.ok) throw new Error('OpenCode receipt host denied/unavailable');
      return response.json();
    };
    const { epoch } = await call('/hello', { directory: ctx.location.directory });
    let counter = 0;
    await ctx.session.hook('http.request', async event => {
      // This is a host-local epoch/counter, never a Runtime-native HTTP ID.
      const id = `${epoch}:${++counter}`;
      const bytes = Buffer.from(await event.request.clone().arrayBuffer());
      const bodyHash = hash(bytes);
      const observedRequest = event.request;
      const data = { id, sessionID: event.sessionID, agent: event.agent, model: event.model,
        kind: event.kind, url: event.request.url, method: event.request.method,
        body_base64: bytes.toString('base64'), body_sha256: bodyHash };
      try {
        const answer = await call('/observe', data);
        if (answer.id !== id || answer.action !== 'allow') throw new Error('Receipt attempt denied');
        // Authorization cannot release bytes changed while the callback was held.
        if (event.request !== observedRequest ||
            hash(Buffer.from(await event.request.clone().arrayBuffer())) !== bodyHash) {
          throw new Error('Terminal request changed after observation');
        }
        // Detach all earlier Request/body references before the final host check.
        const frozen = new Request(observedRequest, { body: Buffer.from(bytes) });
        event.request = frozen;
        if (answer.gated) {
          const seal = await call('/seal', { id, body_sha256: bodyHash });
          if (seal.id !== id || seal.action !== 'allow') throw new Error('Receipt seal denied');
        }
        if (event.request !== frozen ||
            hash(Buffer.from(await frozen.clone().arrayBuffer())) !== bodyHash) {
          throw new Error('Terminal body changed after authorization');
        }
        // The fixed native wrapper copies these bytes to its dispatch handler.
      } catch (error) {
        try { await call('/invalidate', { id }); } catch { /* host failure remains deny */ }
        throw error;
      }
    });
    await ctx.session.hook('retry', async event => {
      await call('/retry', { sessionID: event.sessionID });
      throw new Error('OpenCode production receipt profile does not allow retry');
    });
  }
};
