import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';

const source = readFileSync(new URL('../../majung-studio/worker/runtime.mjs', import.meta.url), 'utf8');
const start = source.indexOf('function backend(env){');
const end = source.indexOf('\nasync function rpc(', start);
if (start < 0 || end < 0) throw Error('Backend validator missing');
const code = source.slice(start, end);
const backend = runInNewContext(code + '\nbackend', { URL, Error });

test('Railway stays allowed without explicit host (unchanged default)', () => {
  assert.equal(backend({MCP_BACKEND_URL:'https://example.up.railway.app/mcp',MCP_BACKEND_TOKEN:'server-only'}), 'https://example.up.railway.app/mcp');
});
test('Cloudflare requires operator-pinned exact hostname', () => {
  const env={MCP_BACKEND_URL:'https://aldol-majung.example.workers.dev/mcp',MCP_BACKEND_TOKEN:'server-only',
      MCP_BACKEND_ALLOWED_HOST:'aldol-majung.example.workers.dev'};
  assert.equal(backend(env),env.MCP_BACKEND_URL);
  assert.throws(()=>backend({...env,MCP_BACKEND_URL:'https://attacker.example.workers.dev/mcp'}));
  assert.throws(()=>backend({...env,MCP_BACKEND_ALLOWED_HOST:'*.workers.dev'}));
  assert.throws(()=>backend({...env,MCP_BACKEND_ALLOWED_HOST:'worker.example.workers.dev'}));
});
test('Bad schemes, credentials, ports, path, query and fragment are rejected', () => {
  const env={MCP_BACKEND_TOKEN:'server-only', MCP_BACKEND_ALLOWED_HOST:'candidate.example.workers.dev'};
  for (const url of ['http://candidate.example.workers.dev/mcp',
    'https://user:pass@candidate.example.workers.dev/mcp',
    'https://candidate.example.workers.dev:8443/mcp',
    'https://candidate.example.workers.dev/status',
    'https://candidate.example.workers.dev/mcp?key=1',
    'https://candidate.example.workers.dev/mcp#f']) {
    assert.throws(()=>backend({...env,MCP_BACKEND_URL:url}),url);
  }
});
test('No backend secret or URL means no connection', () => {
 assert.equal(backend({}),null);
 assert.equal(backend({MCP_BACKEND_URL:'https://candidate.example.workers.dev/mcp'}),null);
});
