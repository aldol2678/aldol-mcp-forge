// Exercises the shipped mobile.js click handler via real loopback HTTP requests.
// Simulated DOM only. NOT a real Android device or full browser rendering test.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const base = process.env.ALDOL_TEST_HTTP_ORIGIN;
const token = process.env.ALDOL_TEST_HTTP_TOKEN;
assert.match(base || '', /^http:\/\/127\.0\.0\.1:\d+$/);
assert.ok(token?.startsWith('LOCAL_TEST_ONLY_'));
const elements = {
  scan: {
    disabled: false,
    addEventListener(event, cb) {
      assert.equal(event, 'click');
      this.click = cb;
    },
  },
  token: { value: token },
  path: { value: '.' },
  tool: { value: 'guardian' },
  state: { textContent: '' },
  output: { textContent: '' },
};
const source = fs.readFileSync(path.join(import.meta.dirname, '..', 'mobile.js'), 'utf8');
const sandbox = {
  document: { getElementById: (id) => elements[id] },
  fetch: async (uri, options) => {
    assert.equal(uri, '/api/scan');
    assert.equal(options.method, 'POST');
    assert.equal(options.cache, 'no-store');
    assert.equal(JSON.parse(options.body).tool, 'guardian');
    const fullUrl = new URL(uri, base);
    assert.equal(fullUrl.origin, base);
    return globalThis.fetch(fullUrl, options);
  },
};
vm.runInNewContext(source, sandbox, { filename: 'mobile.js' });
assert.equal(typeof elements.scan.click, 'function');
await elements.scan.click();
assert.equal(elements.scan.disabled, false);
assert.ok(['INVENTORIED', 'FINDINGS', 'FINDINGS_WITH_GAPS'].includes(elements.state.textContent));
const data = JSON.parse(elements.output.textContent);
assert.equal(data.module, 'Secret Guardian');
assert.equal(data.credential_count, 2);
assert.doesNotMatch(elements.output.textContent, /FAKE_ONLY_NEVER_A_REAL_SECRET_123456|OPENAI_API_KEY|test_prod_token/);
elements.token.value = 'incorrect';
await elements.scan.click();
assert.equal(elements.state.textContent, '오류 401');
assert.equal(elements.scan.disabled, false);
elements.token.value = '';
await elements.scan.click();
assert.equal(elements.state.textContent, '토큰이 필요합니다');
console.log('mobile.js simulated DOM -> localhost HTTP: PASS (success, denied, missing token)');
