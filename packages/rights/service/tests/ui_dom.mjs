// DOM interaction checks with synthetic fetch responses. Not a real browser/device.
// RIGHTS_JSDOM_PATH=/absolute/node_modules/jsdom/lib/api.js node ui_dom.mjs
import {readFileSync} from 'node:fs';
import {randomUUID} from 'node:crypto';
import assert from 'node:assert/strict';
const {JSDOM}=await import(process.env.RIGHTS_JSDOM_PATH||'jsdom');
const root=new URL('../public/',import.meta.url);
const dom=new JSDOM(readFileSync(new URL('index.html',root),'utf8'),{url:'https://rights.aldol.app',runScripts:'outside-only',pretendToBeVisual:true});
const w=dom.window,d=w.document;const id=randomUUID();let records=[];let calls=[];let failedRegister=false;
const asset={asset_id:id,title:'<img src=x onerror=alert(1)> 긴 자산 '+('제목'.repeat(100)),kind:'image',license_id:'CC-BY-4.0',creator:'저작자',source_url:'https://example.org/'+('a'.repeat(400)),project:'테스트',revision:1,usage:{attribution_planned:true},created_at:new Date().toISOString()};
w.matchMedia=()=>({matches:false});w.scrollTo=()=>{};w.HTMLElement.prototype.scrollIntoView=()=>{};w.Headers=Headers;w.crypto.randomUUID=randomUUID;let downloads=0;w.URL.createObjectURL=()=>{downloads++;return 'blob:test'};w.URL.revokeObjectURL=()=>{};w.HTMLAnchorElement.prototype.click=function(){};
const response=(obj,status=200)=>({ok:status<400,status,headers:new Headers({'content-type':'application/json'}),json:async()=>obj});
w.fetch=async(url,opts={})=>{calls.push([url,opts]);if(url==='/api/licenses')return response({licenses:{UNKNOWN:{},'CC-BY-4.0':{}},labels:{SUITABLE:'조건상 적합',REVIEW:'추가 검토 필요'}});if(url==='/api/session')return response({id:'fixture',email:'qa@example.invalid'});if(url==='/api/assets'&&opts.method==='POST'){if(failedRegister){failedRegister=false;throw Error('offline')}const a=JSON.parse(opts.body);records.push({...a,revision:1});return response(records.at(-1))}if(url==='/api/assets')return response({assets:records});if(url==='/api/history')return response({items:[]});if(url.startsWith('/api/assets/')&&url.endsWith('/check'))return response({check_id:'x'});if(url.startsWith('/api/assets/'))return response({asset:records.find(a=>url.includes(a.asset_id))||asset,history:[]});if(url.startsWith('/api/report'))return response({count:1,counts:{SUITABLE:1},credits:{credits:'test credits'},review_needed:[],items:[],disclaimer:'승인 아님'});if(url==='/api/keys')return response({keys:[]});return response({})};
w.eval(readFileSync(new URL('app.js',root),'utf8'));
const flush=async()=>{for(let i=0;i<8;i++)await new Promise(r=>setImmediate(r))};
const hash=async h=>{w.location.hash=h;await new Promise(r=>setTimeout(r,5));await flush()};
await flush();assert.match(d.querySelector('h1').textContent,/권리 현황/);assert.equal(d.querySelector('#nav').hidden,false);console.log('dashboard DOM PASS');
records=[asset];await hash('#assets');assert.match(d.querySelector('#asset-list').textContent,/<img src=x/);assert.equal(d.querySelector('#asset-list img'),null);console.log('untrusted title escaped PASS');
d.querySelector('#search').value='없는것';d.querySelector('#search').dispatchEvent(new w.Event('input'));assert.match(d.querySelector('#asset-list').textContent,/아직 자산이 없습니다/);console.log('search/filter DOM PASS');
await hash('#new');const f=d.querySelector('#asset-form');f.elements.title.value='모바일 흐름 테스트';f.elements.creator.value='author';f.elements.source_url.value='https://example.org/source';f.elements.evidence_url.value='https://example.org/license';failedRegister=true;f.dispatchEvent(new w.Event('submit',{cancelable:true}));await flush();assert.match(d.querySelector('.form-error').textContent,/네트워크/);assert.equal(f.elements.title.value,'모바일 흐름 테스트');console.log('network failure preserves form PASS');
f.dispatchEvent(new w.Event('submit',{cancelable:true}));await flush();await new Promise(r=>setTimeout(r,10));await flush();assert(calls.some(([u])=>u.endsWith('/check')));assert(w.location.hash.startsWith('#asset/'));console.log('register then check flow DOM PASS');
await hash('#reports');d.querySelector('#generate').click();await flush();d.querySelector('#download-json').click();assert.equal(downloads,1);console.log('report download DOM PASS');
await hash('#settings');assert.match(d.querySelector('h1').textContent,/ChatGPT 연결/);console.log('settings DOM PASS');
d.querySelector('#theme').click();assert.equal(d.documentElement.dataset.theme,'dark');assert.equal(w.localStorage.getItem('rights-theme'),'dark');console.log('dark mode DOM PASS');
dom.window.close();
