/* ALDOL RIGHTS policy notices, owner-only editor and data-subject controls. */
'use strict';
async function legalPublic(kind) {
  const docs=await api('/legal/documents'), d=docs[kind];
  const name=kind==='privacy'?'개인정보처리방침':'이용약관';
  const status=d ? `v${d.version} · 시행일 ${esc(d.effective_on)} · 게시 ${esc(date(d.published_at))}`:'현재 게시된 공식 문서가 없습니다.';
  main.innerHTML=page(name,status)+`<section class="card legal-document">${d?`<pre class="legal-content">${esc(d.content)}</pre>`:'<p class="notice warn">공식 문서 게시 준비 중입니다. 아직 게시 전인 초안은 약관이나 처리방침으로 표시하지 않습니다.</p>'}</section><p><a href="#dashboard">작업 공간으로 돌아가기</a></p>`;
  window.scrollTo(0,0);
}
async function legalAcceptanceGate(info) {
  main.innerHTML=page('서비스 이용약관 확인','새로운 약관 버전이 게시됐습니다.')+
    `<section class="card"><div class="notice">동의하기 전에도 개인정보 열람 및 권리 행사 요청은 사용할 수 있습니다. 개인정보처리방침의 공개는 그 자체로 별도 개인정보 처리 동의를 의미하지 않습니다.</div>
    <p>현재 이용약관: ${info.terms?'v'+esc(info.terms.version):'미게시'}</p>
    <p><a href="#terms">이용약관 전문 읽기</a> · <a href="#privacy">개인정보처리방침</a></p>
    <label class="check"><input type="checkbox" id="terms-agree">위 이용약관을 확인하고 동의합니다.</label>
    <div class="actions"><button class="primary" id="accept-terms" ${info.terms?'':'disabled'}>동의하고 계속</button><a class="button" href="#privacy-center">개인정보 권리 행사</a></div>
    <div class="form-error"></div></section>`;
  $('#accept-terms').onclick=async()=>{
    if(!$('#terms-agree').checked){toast('약관을 읽고 동의 여부를 선택하세요.');return}
    const btn=$('#accept-terms');btn.disabled=true;
    try{await api('/legal/acceptance',{method:'POST',body:{terms_id:info.terms.doc_id,accepted:true}});toast('약관 동의 기록이 저장됐습니다.');await route()}
    catch(e){$('.form-error').innerHTML=errorBox(e.message);btn.disabled=false}
  };
}
async function privacyCenter(){
  const [requests,account]=await Promise.all([api('/legal/privacy-requests'),api('/session')]);
  main.innerHTML=page('개인정보 관리','개인정보 열람·정정·삭제 및 처리정지 요청')+`
  <section class="card"><h2>내 계정</h2><p>${esc(account.email)}</p>
    <p class="muted">열람 파일은 등록 자산·연결 키·최근 검사 기록의 메타데이터를 담습니다. 원본 파일 또는 전체 기간 기록이 필요하면 별도 요청하세요.</p>
    <button id="my-data">내 정보 일부 내려받기 (JSON)</button></section>
  <section class="card"><h2>정보주체 권리 행사</h2>
    <p class="muted">요청 접수만으로 데이터가 삭제되거나 정정되지는 않습니다. 공유 인증계정 등 다른 ARAM 서비스에 미칠 영향을 확인한 후 처리합니다.</p>
    <form id="privacy-request"><label class="field"><span>요청 유형</span><select name="request_type">
      <option value="access">개인정보 열람</option><option value="rectification">개인정보 정정</option>
      <option value="erasure">개인정보 삭제</option><option value="restriction">처리정지</option>
    </select></label><div class="form-error"></div><button class="primary" type="submit">요청 접수</button></form>
  </section>
  <section class="card"><h2>요청 내역</h2>
    ${requests.requests.map(r=>`<div class="asset">${esc(r.request_type)} · ${esc(r.status)} · ${esc(date(r.created_at))}</div>`).join('')||'<p class="muted">요청 내역이 없습니다.</p>'}</section>`;
  $('#my-data').onclick=async()=>{try{
    const data=await api('/legal/my-data');
    saveFile(JSON.stringify(data,null,2),'aldol-rights-personal-metadata.json','application/json');
  }catch(e){toast(e.message)}};
  const form=$('#privacy-request');
  form.onsubmit=async e=>{e.preventDefault();busy(form,true);try{
    await api('/legal/privacy-requests',{method:'POST',body:{request_type:form.elements.request_type.value}});
    toast('개인정보 권리 행사 요청을 접수했습니다.');await privacyCenter();
  }catch(err){showFormError(form,err)}finally{busy(form,false)}};
}
async function adminPolicies(){
  const data=await api('/legal/admin');
  const docs=data.documents;
  const latest=(kind)=>docs.filter(d=>d.kind===kind).sort((a,b)=>b.version-a.version)[0];
  const show=(kind)=>{const d=latest(kind);return `<section class="card">
    <h2>${kind==='privacy'?'개인정보처리방침':'이용약관'}</h2>
    <p class="muted">${d?'최신 v'+d.version+' · '+(d.status==='draft'?'미게시 초안':'게시됨'):'작성 이력 없음'}</p>
    <div class="actions"><button class="new-doc" data-kind="${kind}">새 버전 초안</button></div>
    ${docs.filter(d=>d.kind===kind).map(d=>`<div class="asset"><div class="row between"><div class="grow">v${d.version} · ${esc(d.status)} · ${esc(d.effective_on)}</div>${d.status==='draft'?`<button class="edit-doc" data-id="${esc(d.doc_id)}">편집</button>`:''}</div></div>`).join('')}</section>`};
  main.innerHTML=page('정책 관리자','게시된 버전은 수정하지 않고 새 버전을 발행합니다.')+
    `<div class="notice warn">관리자 역할은 RIGHTS 전용 허가 목록으로 제한됩니다. 초안 게시 전 운영자·연락처·보존기간·국외이전/처리위탁의 실제 상태를 확인하세요.</div>
    <div class="two">${show('privacy')}${show('terms')}</div><section class="card" id="editor"><p>문서를 선택해 편집하세요. 사용자에게는 게시된 문서만 공개됩니다.</p></section>
    <section class="card"><h2>권리 행사 요청 <small>최근 100건</small></h2>${data.privacy_requests.map(r=>`<p>${esc(r.request_type)} · ${esc(r.status)} · ${esc(date(r.created_at))} · ID ${esc(r.request_id)}</p>`).join('')||'<p class="muted">접수된 요청이 없습니다.</p>'}</section>`;
  async function editor(d,chosenKind) {
    const isNew=!d;let text=d?.content||'',kind=d?.kind||chosenKind||'privacy';
    if(isNew) {
      const source=latest(kind);
      if(source)text=source.content;
      else {try{const r=await fetch('/static/legal-'+kind+'-template.txt');if(r.ok)text=await r.text()}catch{}}
    }
    $('#editor').innerHTML=`<h2>${d?'v'+d.version+' 초안 편집':'새 버전 초안'}</h2><form id="legal-editor">
      <input type="hidden" name="kind" value="${esc(kind)}"><label class="field"><span>시행일</span>
      <input name="effective_on" type="date" required value="${esc(d?.effective_on||new Date().toISOString().slice(0,10))}"></label>
      <label class="field"><span>본문 (일반 텍스트, 400~30000자)</span>
      <textarea name="content" rows="18" minlength="400" maxlength="30000" required></textarea></label>
      <div class="form-error"></div><div class="actions"><button class="primary" type="submit">초안 저장</button>
      ${d?'<button type="button" id="publish">검토 후 게시</button>':''}</div></form>${d?`<div class="notice"><strong>게시 전 필수 확인 (개별 확인)</strong><label class="check"><input type="checkbox" id="verify-operator">운영자 정보·연락처 확인</label><label class="check"><input type="checkbox" id="verify-retention">보존기간·파기 절차 확인</label><label class="check"><input type="checkbox" id="verify-vendors">위탁 및 국외이전 사실 확인</label><label class="check"><input type="checkbox" id="verify-human">문안 및 법적 검토 완료</label></div>`:""}`;
    const form=$('#legal-editor');form.elements.content.value=text;
    form.onsubmit=async e=>{e.preventDefault();busy(form,true);try{
      const body={content:form.elements.content.value,effective_on:form.elements.effective_on.value};
      if(d){body.revision=d.revision;await api('/legal/admin/'+d.doc_id,{method:'PATCH',body})}
      else{body.kind=kind;await api('/legal/admin',{method:'POST',body})}
      toast('미게시 초안이 저장됐습니다.');await adminPolicies();
    }catch(err){showFormError(form,err)}finally{busy(form,false)}};
    if(d)$('#publish').onclick=async()=>{
      if(!['verify-operator','verify-retention','verify-vendors','verify-human'].every(id=>$('#'+id).checked)){toast('네 가지 검토 항목을 각각 확인해야 게시할 수 있습니다.');return}
      if(!confirm('게시된 문서는 수정할 수 없습니다. 공식 문서로 게시하시겠습니까?'))return;
      try {
        const body={revision:d.revision,verified_operator_contact:true,verified_retention_disposal:true,
          verified_vendors_transfers:true,reviewed_by_human:true};
        await api('/legal/admin/'+d.doc_id+'/publish',{method:'POST',body});
        toast('새 공식 정책 버전이 게시됐습니다.');await adminPolicies();
      }catch(err){showFormError(form,err)}
    };
    $('#editor').scrollIntoView({block:'nearest'});
  }
  for(const btn of document.querySelectorAll('.edit-doc')) btn.onclick=()=>editor(docs.find(d=>d.doc_id===btn.dataset.id));
  for(const btn of document.querySelectorAll('.new-doc')) btn.onclick=()=>editor(null,btn.dataset.kind);
}
