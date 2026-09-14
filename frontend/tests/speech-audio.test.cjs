const { test } = require('node:test');
const assert = require('node:assert/strict');
const ts = require('typescript');
const fs = require('node:fs');
const vm = require('node:vm');
function load(fetch) {
  const exports = {};
  const source = fs.readFileSync('lib/speech-audio.ts', 'utf8');
  vm.runInNewContext(ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } }).outputText,
    { exports, process: { env: {} }, fetch, Blob });
  return exports.getSpeechAudio;
}
test('concurrent and repeat requests reuse identical audio; language and account remain separate', async () => {
  let calls = 0;
  const blob = new Blob(['original audio']);
  const get = load(async () => { calls++; return { ok: true, blob: async () => blob }; });
  const [a, b] = await Promise.all([get('user1', 'hello', 'en'), get('user1', 'hello', 'en')]);
  assert.equal(a, blob); assert.equal(b, blob); assert.equal(calls, 1);
  assert.equal(await get('user1', 'hello', 'en'), blob); assert.equal(calls, 1);
  await get('user1', 'hello', 'hi'); assert.equal(calls, 2);
  await get('user2', 'hello', 'en'); assert.equal(calls, 3);
});
test('quota failures retain retry time and are not cached', async () => {
  let calls = 0;
  const get = load(async () => { calls++; return { ok: false, json: async () => ({ detail: 'ZeroGPU quota exceeded. Try again in 23:47:21.' }) }; });
  await assert.rejects(get('user', 'hello', 'en'), /23:47:21/);
  await assert.rejects(get('user', 'hello', 'en'), /quota/);
  assert.equal(calls, 2);
});
test('cache evicts old entries and rejects unauthenticated calls', async () => {
  let calls = 0;
  const get = load(async () => { calls++; return { ok: true, blob: async () => new Blob(['audio']) }; });
  await assert.rejects(get(null, 'hello', 'en'), /sign in/);
  assert.equal(calls, 0);
  for (let i = 0; i < 21; i++) await get('user', String(i), 'en');
  await get('user', '0', 'en'); assert.equal(calls, 22);
});
