import assert from 'node:assert/strict';
import test from 'node:test';
import {spawnSync} from 'node:child_process';
import { generate,verifyProject,zipFiles } from '../worker/generator.js';
const result=spawnSync('python3',[new URL('./generation_reference.py',import.meta.url).pathname],{encoding:'utf8',maxBuffer:8e6});assert.equal(result.status,0,result.stderr);
for(const c of JSON.parse(result.stdout))test('byte parity with original Python: '+c.name,async()=>{const p=await generate(c.args,c.selected);for(const[f,content]of Object.entries(c.files))assert.equal(p.files[f],content,f);});
test('ZIP read by independent Python zipfile; CRC, hashes and generated Python syntax',async()=>{const p=await generate({project_name:'html-test',description:'HTML 검사'});const b=zipFiles(p.files);const r=spawnSync('python3',['-c',`import sys,io,zipfile,hashlib,json,ast
z=zipfile.ZipFile(io.BytesIO(sys.stdin.buffer.read()));assert z.testzip() is None
m=json.loads(z.read('manifest.json'))
for n,h in m['files_sha256'].items():assert hashlib.sha256(z.read(n)).hexdigest()==h
for n in z.namelist():
 if n.endswith('.py'):ast.parse(z.read(n).decode())
print('independent ZIP CRC/SHA256/AST PASS')`],{input:Buffer.from(b),encoding:'utf8'});assert.equal(r.status,0,r.stderr);});
test('tampered source fails integrity check',async()=>{const p=await generate({project_name:'text-test',description:'text stats'});p.files['server.py']+='\n# modified';assert.equal((await verifyProject(p)).integrity.status,'FAIL');});
