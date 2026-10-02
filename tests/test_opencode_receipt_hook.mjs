// Direct checks of the shipped callback; no Runtime/provider fixture involved.
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import plugin from '../src/yohaku/opencode_receipt_hook.mjs';

const digest = value => createHash('sha256').update(value).digest('hex');
async function run(mutate) {
  const calls = [];
  const hooks = {};
  const event = { sessionID: 'ses_test', agent: 'build', kind: 'primary', model: {id:'local'},
    request: new Request('http://127.0.0.1/v1/chat/completions', {
      method: 'POST', body: '{"messages":[{"role":"user","content":"exact handoff"}]}'
    }) };
  const original = event.request;
  globalThis.fetch = async (url, options) => {
    const data = JSON.parse(options.body);
    const path = new URL(url).pathname;
    calls.push({path, data});
    if (path === '/hello') return Response.json({epoch:'host-epoch'});
    if (path === '/observe') {
      if (mutate) event.request = new Request(event.request, {body:'changed after authorization'});
      return Response.json({id:data.id, action:'allow', gated:true});
    }
    return Response.json({id:data.id, action:'allow'});
  };
  await plugin.setup({options:{origin:'http://127.0.0.1',token:'fixture'}, location:{directory:'/owned'},
    session:{hook:async (name, callback) => { hooks[name] = callback; }}});
  if (mutate) {
    await assert.rejects(hooks['http.request'](event), /Terminal request changed/);
    assert.equal(calls.filter(c => c.path === '/seal').length, 0);
    assert.equal(calls.filter(c => c.path === '/invalidate').length, 1);
  } else {
    await hooks['http.request'](event);
    assert.notEqual(event.request, original);
    const observed = calls.find(c => c.path === '/observe').data;
    assert.equal(observed.id, 'host-epoch:1');
    assert.equal(digest(Buffer.from(observed.body_base64, 'base64')), observed.body_sha256);
    assert.equal(digest(Buffer.from(await event.request.clone().arrayBuffer())), observed.body_sha256);
    assert.equal(calls.filter(c => c.path === '/seal').length, 1);
  }
  await assert.rejects(hooks.retry({sessionID:'ses_test'}), /does not allow retry/);
}
await run(false);
await run(true);
console.log('PASS: body copy/hash, post-authorization mutation deny, retry stop');
