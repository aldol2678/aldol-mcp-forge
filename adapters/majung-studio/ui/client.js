'use strict';
(() => {
  const company = document.body.dataset.company;
  const historyKey = `aldol-${company}-studio-history-v1`;
  const names = {analyze_design:'디자인 분석',generate_design_spec:'디자인 명세',review_visual:'시각 검수',research_market:'시장조사',analyze_competitors:'경쟁사 분석',evaluate_opportunity:'사업성 평가',asset_audit:'에셋 메타데이터 검수'};
  const labels = {findings:'검사 결과',improvements:'수정 제안',specification:'디자인 명세',constraints:'제약 및 인계 조건',verdict:'판정',evidence:'근거 자료',uncertainties:'불확실성',competitors:'경쟁 제품',differentiation:'차별화 분석',recommendation:'자문 판단',risks:'가정·계산·위험',issues:'발견한 문제',severity:'중요도',code:'문제 코드',location:'위치',suggestion:'수정 제안',sources:'출처',title:'제목',url:'출처 URL',source_url:'출처 URL',observed_at:'관측일',fetched_at:'수집 시점',checked_at:'확인 시점',published_at:'발행일',claim:'확인 내용',method:'수집 방법',reliability:'신뢰 수준',price:'가격',currency:'통화',name:'이름',scope:'검사 범위',html:'HTML',css:'CSS',components:'컴포넌트',tokens:'디자인 토큰',states:'상태',mobile_behavior:'모바일 동작',viewport:'뷰포트',visual_inspection_performed:'실제 시각 검사',source_content_verified:'출처 내용 확인',unverified_claims:'미검증 주장',unit_contribution:'고객당 공헌이익',acquisition_cost:'고객획득비용',variable_cost:'변동비',expected_customers:'예상 고객 수',decision_is_advisory:'자문 결과',launch_authorized:'출시 승인',warnings:'주의·확인할 사항',provider:'수집 제공자',status:'상태',reason:'이유',error:'오류',type:'유형',details:'상세',inspected:'검사 여부',limitations:'검증 한계',scenarios:'시나리오',baseline:'기준',optimistic:'낙관',pessimistic:'비관',fixed_cost:'고정비',break_even_customers:'손익분기 고객 수',experiments:'초기 실험',report_id:'보고서 ID'};
  const htmlExample = '<!doctype html>\n<html lang="ko"><head><meta name="viewport" content="width=device-width, initial-scale=1"><title>예제 — 신청 폼</title></head><body><main><h1>소식 받기</h1><form><label for="email">이메일</label><input id="email" type="email" required><button type="submit">신청</button></form></main></body></html>';
  const examples = {
    analyze: {html:htmlExample,css:':root { --color-text:#203c39; --color-background:#ffffff; --space:16px; }\nbody { color:var(--color-text); background:var(--color-background); margin:0; padding:var(--space); }\ninput, button { min-height:44px; max-width:100%; }\nbutton:focus-visible { outline:3px solid #87571f; }\n@media (max-width:600px) { form { display:grid; gap:16px; } }'},
    system: {brief:JSON.stringify({goal:'예제 — 모바일에서 소식받기 신청을 완료한다',components:[{name:'SignupForm',role:'이메일을 입력하고 신청한다',states:['default','focus','loading','empty','error','disabled','success'],mobile_behavior:'390px에서 입력창과 버튼을 한 열에 배치하고 모든 안내 문구를 보존한다'}],tokens:{'color.text':'#203c39','color.background':'#ffffff','space.base':'16px','touch.minimum':'44px'},device:'390px / 820px / desktop'},null,2)},
    visual: {artifact:JSON.stringify({artifact_id:'example-signup-form',html:htmlExample,css:'body { font-family:sans-serif; padding:20px; } input,button { min-height:44px; max-width:100%; }',viewport:'390x844',viewports:[390,820,1280]},null,2)},
    research: {question:'게임 에셋 제작 도구의 무료·유료 요금제와 주요 고객',region:'KR'},
    competitors: {product:JSON.stringify({name:'예제 — 2D 게임 에셋 팩',price:10,currency:'USD',period:'one_time',competitors:[],live:true},null,2)},
    opportunity: {price:10000,variable_cost:2000,acquisition_cost:1000,expected_customers:100,fixed_cost:300000,opportunity_name:'예제 — 디자인 에셋 팩'}
  };
  function el(tag,text,className) { const n=document.createElement(tag); if(text!==undefined)n.textContent=String(text); if(className)n.className=className; return n; }
  function readHistory(){try{const a=JSON.parse(localStorage.getItem(historyKey)||'[]');return Array.isArray(a)?a.slice(0,30):[];}catch{return [];}}
  function saveHistory(entry){const a=[entry,...readHistory()].slice(0,30);try{localStorage.setItem(historyKey,JSON.stringify(a));}catch{ /* Private mode or quota does not invalidate the server result. */ }renderHistory();}
  function safeUrl(value){try{const u=new URL(value);return ['https:','http:'].includes(u.protocol)?u.href:null;}catch{return null;}}
  function parseValue(v){if(typeof v==='string'){try{return JSON.parse(v);}catch{return v;}}return v;}
  function badge(value){const n=el('span',value,'badge');n.dataset.level=/FAIL|NO.GO|HIGH|CRITICAL/i.test(value)?'fail':/HOLD|UNKNOWN|UNINSPECTED|NOT.RUN|MEDIUM/i.test(value)?'hold':/^PASS|^OK|^SUCCESS/i.test(value)?'pass':'';return n;}
  function cellValue(value){const v=parseValue(value);if(v===null||v===undefined)return el('span','확인 정보 없음','muted');if(typeof v==='boolean')return el('span',v?'예':'아니요');if(typeof v==='object')return el('span',JSON.stringify(v));const url=typeof v==='string'?safeUrl(v):null;if(url){const a=el('a',v);a.href=url;a.target='_blank';a.rel='noopener noreferrer';return a;}return el('span',v);}
  function renderValue(raw,depth=0){
    const value=parseValue(raw);
    if(value===null||value===undefined)return el('span','확인 정보 없음','muted');
    if(depth>7)return el('pre',JSON.stringify(value,null,2));
    if(Array.isArray(value)){
      if(!value.length)return el('p','항목 없음','muted');
      const objects=value.every(v=>v&&typeof v==='object'&&!Array.isArray(v));
      const keys=objects?[...new Set(value.flatMap(v=>Object.keys(v)))]:[];
      const compact=objects&&value.length>1&&keys.length<=9&&value.every(v=>Object.values(v).every(x=>x===null||typeof x!=='object'));
      if(compact){const wrap=el('div',undefined,'table-wrap');wrap.tabIndex=0;wrap.setAttribute('role','region');wrap.setAttribute('aria-label','분석 결과 표 · 가로로 스크롤할 수 있습니다');const t=el('table');const head=el('thead'),tr=el('tr');keys.forEach(k=>{const th=el('th',labels[k]||k);th.scope='col';tr.append(th);});head.append(tr);t.append(head);const body=el('tbody');value.forEach(v=>{const row=el('tr');keys.forEach(k=>{const td=el('td');td.append(cellValue(v[k]));row.append(td);});body.append(row);});t.append(body);wrap.append(t);return wrap;}
      const list=el('ol',undefined,'data-list');value.forEach(v=>{const li=el('li');li.append(renderValue(v,depth+1));list.append(li);});return list;
    }
    if(typeof value==='object'){
      const grid=el('div',undefined,'object-grid');Object.entries(value).forEach(([k,v])=>{const pair=el('div',undefined,'data-pair');pair.append(el('span',labels[k]||k,'data-key'));if(['verdict','severity','recommendation','status'].includes(k)&&typeof v==='string')pair.append(badge(v));else pair.append(renderValue(v,depth+1));grid.append(pair);});return grid;
    }
    const p=el('p',undefined,'data-value');p.append(cellValue(value));return p;
  }
  function showResult(container,result,title,at=new Date().toISOString()){
    container.replaceChildren();const header=el('div',undefined,'result-header'),text=el('div');text.append(el('h2',title));const time=el('p',`실행 시점 · ${new Date(at).toLocaleString('ko-KR')}`,'result-meta');text.append(time);header.append(text);const copy=el('button','JSON 복사');copy.type='button';copy.dataset.copy='true';copy.addEventListener('click',async()=>{try{await navigator.clipboard.writeText(JSON.stringify(result,null,2));copy.textContent='복사됨';}catch{copy.textContent='아래 원문에서 복사하세요';}});header.append(copy);container.append(header);
    const data=result&&typeof result==='object'?result:{result};Object.entries(data).forEach(([k,v])=>{const section=el('section',undefined,'result-section');section.append(el('h3',labels[k]||k));if(['verdict','recommendation'].includes(k)&&typeof v==='string')section.append(badge(v));else section.append(renderValue(v));container.append(section);});const details=el('details'),summary=el('summary','원본 JSON 보기');details.append(summary,el('pre',JSON.stringify(result,null,2)));container.append(details);
  }
  async function request(path,payload){
    const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),120000);
    try{const response=await fetch(path,{method:payload?'POST':'GET',headers:payload?{'content-type':'application/json'}:undefined,body:payload?JSON.stringify(payload):undefined,credentials:'same-origin',signal:controller.signal});let body;try{body=await response.json();}catch{throw Error(response.status===401?'인증이 필요합니다. 페이지를 새로 열어 로그인한 뒤 다시 실행하세요.':'서버 응답을 읽지 못했습니다.');}if(!response.ok||body.error){throw Error(typeof body.error==='string'?body.error:body.error?.message||`요청에 실패했습니다 (${response.status}).`);}return body;}catch(e){if(e.name==='AbortError')throw Error('요청 시간이 초과되었습니다. 실행 결과를 확인한 뒤 다시 시도하세요.');throw e;}finally{clearTimeout(timer);}
  }
  function formMessage(form,text,error=false){const p=form.querySelector('.form-message');p.textContent=text;p.classList.toggle('error',error);}
  function setBusy(form,busy){form.setAttribute('aria-busy',String(busy));form.querySelectorAll('button[type=submit]').forEach(b=>{b.disabled=busy;if(!b.dataset.text)b.dataset.text=b.textContent;b.textContent=busy?'실행 중…':b.dataset.text;});}
  function getArguments(form){
    const data=Object.fromEntries(new FormData(form));
    form.querySelectorAll('[data-json=true]').forEach(input=>{if(input.value.trim())JSON.parse(input.value);});
    if(form.id==='opportunity-form'){
      const brief={name:data.opportunity_name,currency:data.currency,price:Number(data.price),variable_cost:Number(data.variable_cost),acquisition_cost:Number(data.acquisition_cost),expected_customers:Number(data.expected_customers),fixed_cost:Number(data.fixed_cost),evidence_urls:data.evidence_urls.split(/\s+/).filter(Boolean)};
      if(data.scenarios?.trim())brief.scenarios=JSON.parse(data.scenarios);return {brief:JSON.stringify(brief)};
    }
    return data;
  }
  document.querySelectorAll('form[data-tool]').forEach(form=>form.addEventListener('submit',async event=>{
    event.preventDefault();if(form.getAttribute('aria-busy')==='true')return;let args;try{args=getArguments(form);}catch{formMessage(form,'JSON 형식을 확인하세요. 따옴표와 쉼표가 올바른지 확인할 수 있습니다.',true);return;}
    setBusy(form,true);formMessage(form,'서버에서 실행하고 있습니다. 결과가 도착할 때까지 기다려 주세요.');const name=form.dataset.tool;
    try{const response=await request('/api/call',{name,arguments:args});const result=response.result??response;showResult(form.nextElementSibling,result,names[name]);const at=new Date().toISOString();saveHistory({name,title:names[name],at,result});formMessage(form,'실행 결과를 받았습니다. 판정과 미검증 항목을 함께 확인하세요.');}
    catch(e){formMessage(form,e.message,true);}finally{setBusy(form,false);}
  }));
  document.getElementById('assets-form')?.addEventListener('submit',async event=>{
    event.preventDefault();const form=event.currentTarget;if(form.getAttribute('aria-busy')==='true')return;let manifest;try{manifest=JSON.parse(form.elements.manifest.value);}catch{formMessage(form,'에셋 메타데이터의 JSON 형식을 확인하세요.',true);return;}setBusy(form,true);formMessage(form,'에셋 검사 인터페이스에 요청하고 있습니다.');try{const response=await request('/api/assets',{manifest});const result=response.result??response;showResult(form.nextElementSibling,result,names.asset_audit);saveHistory({name:'asset_audit',title:names.asset_audit,at:new Date().toISOString(),result});formMessage(form,'검사 결과를 받았습니다. 검사 범위를 확인하세요.');}catch(e){formMessage(form,e.message,true);}finally{setBusy(form,false);}
  });
  document.querySelectorAll('[data-example]').forEach(button=>button.addEventListener('click',()=>{
    const example=examples[button.dataset.example];Object.entries(example).forEach(([id,value])=>{const input=document.getElementById(id);if(input)input.value=value;});const form=button.closest('form');if(form)formMessage(form,'예제 입력입니다. 실제 자료와 구분해 사용하세요.');
  }));
  document.querySelectorAll('[data-file-target]').forEach(input=>input.addEventListener('change',async()=>{const f=input.files?.[0];if(!f)return;const form=input.closest('form');if(f.size>131072){formMessage(form,'HTML 파일은 128KiB 이하로 선택하세요.',true);return;}document.getElementById(input.dataset.fileTarget).value=await f.text();formMessage(form,`${f.name} 파일을 입력했습니다. 실행 버튼을 눌러 분석하세요.`);}));
  document.getElementById('visual-file')?.addEventListener('change',async event=>{
    const f=event.target.files?.[0];if(!f)return;const form=event.target.closest('form');if(f.size>131072){formMessage(form,'검사 자료는 128KiB 이하로 선택하세요.',true);return;}
    try{let data;if(f.type==='text/html'||/\.html?$/i.test(f.name)){data={artifact_id:f.name,html:await f.text(),css:'',viewport:'390x844',viewports:[390,820,1280]};}else if(['image/png','image/jpeg'].includes(f.type)){const base64=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result).split(',')[1]);reader.onerror=reject;reader.readAsDataURL(f);});data={artifact_id:f.name,image_base64:base64,viewport:'390x844',viewports:[390,820,1280]};}else{throw Error('HTML, PNG, JPEG 파일을 선택하세요.');}document.getElementById('artifact').value=JSON.stringify(data,null,2);formMessage(form,`${f.name} 파일을 읽었습니다. 실행하면 자료가 서버로 전달됩니다.`);}catch(e){formMessage(form,e.message||'파일을 읽지 못했습니다.',true);}
  });
  function renderHistory(){const target=document.getElementById('history-list');if(!target)return;target.replaceChildren();const history=readHistory();if(!history.length){target.append(el('p','이 브라우저에 저장된 실행 기록이 없습니다.','empty'));return;}history.forEach(item=>{const article=el('article',undefined,'history-item');article.append(el('time',new Date(item.at).toLocaleString('ko-KR')),el('h2',item.title));const details=el('details'),summary=el('summary','결과 열기'),output=el('div');details.append(summary,output);details.addEventListener('toggle',()=>{if(details.open&&!output.childElementCount)showResult(output,item.result,item.title,item.at);});article.append(details);target.append(article);});}
  function download(name,content){const a=document.createElement('a');const url=URL.createObjectURL(new Blob([content],{type:'application/json'}));a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
  document.getElementById('export-history')?.addEventListener('click',()=>download(`ALDOL_${company.toUpperCase()}_history_${new Date().toISOString().slice(0,10)}.json`,JSON.stringify({company,exported_at:new Date().toISOString(),storage:'this browser only',records:readHistory()},null,2)));
  document.getElementById('clear-history')?.addEventListener('click',()=>{if(confirm('이 브라우저에 저장된 검수·조사 기록을 지울까요? 서버 기록에는 영향을 주지 않습니다.')){try{localStorage.removeItem(historyKey);renderHistory();}catch{alert('브라우저 기록을 지우지 못했습니다.');}}});
  const menuButton=document.querySelector('.menu-toggle'),nav=document.getElementById('navigation');menuButton?.addEventListener('click',()=>{const open=nav.classList.toggle('open');menuButton.setAttribute('aria-expanded',String(open));});
  function route(){const requested=location.hash.slice(1)||'dashboard';const active=document.getElementById(requested)?.classList.contains('view')?requested:'dashboard';document.querySelectorAll('.view').forEach(v=>{v.hidden=v.id!==active;});nav.querySelectorAll('a').forEach(a=>{if(a.hash==='#'+active)a.setAttribute('aria-current','page');else a.removeAttribute('aria-current');});nav.classList.remove('open');menuButton?.setAttribute('aria-expanded','false');document.title=`${document.getElementById(active).querySelector('h1').textContent} · ALDOL ${company.toUpperCase()}`;}
  window.addEventListener('hashchange',route);route();renderHistory();
  async function refreshStatus(){const target=document.getElementById('status-result'),summary=document.querySelector('.connection-summary'),dot=document.querySelector('.status-dot'),button=document.getElementById('refresh-status');button.disabled=true;try{const status=await request('/api/status');showResult(target,status,'현재 연결 상태');const unavailable=status.connected===false||/BLOCKED|UNAVAILABLE|NOT_CONFIGURED|ERROR/i.test(JSON.stringify(status));summary.textContent=unavailable?'일부 연결을 사용할 수 없습니다. 설정에서 상세 상태를 확인하세요.':'연결 상태 응답을 받았습니다. 설정에서 기능별 범위를 확인하세요.';dot.dataset.status=unavailable?'error':'ok';}catch(e){summary.textContent=e.message;dot.dataset.status='error';target.replaceChildren(el('p',e.message,'empty'));}finally{button.disabled=false;}}
  document.getElementById('refresh-status')?.addEventListener('click',refreshStatus);refreshStatus();
})();
