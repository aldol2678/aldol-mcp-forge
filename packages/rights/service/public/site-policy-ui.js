/* External-site documents: mobile read-only verification workspace. No external writes. */
'use strict';
function sitePolicyWorkspace() {
  main.innerHTML=page('다른 웹사이트 정책 점검','공개 정책을 찾고, 제공한 문서를 기준으로 수정 권고를 만듭니다.')+
    `<section class="card"><h2>1. 공개 사이트 정책 찾기</h2>
      <p class="muted">공개 HTTPS 웹페이지만 제한적으로 읽습니다. 스캔이 비활성화된 경우 문서를 직접 입력할 수 있습니다.</p>
      <form id="external-site-scan">
      <label class="field"><span>웹사이트 HTTPS 주소</span><input type="url" name="url" placeholder="https://example.org" required maxlength="1600"></label>
      <div class="form-error"></div><button type="submit">공개 정책 탐색</button></form>
      <div id="external-scan-result" role="status"></div>
    </section>
    <section class="card"><h2>2. 개인정보처리방침·이용약관 점검</h2>
      <p class="muted">문서를 붙여넣거나 권한 있는 운영자가 검증한 정보를 입력하세요. 미확인 내용은 사실로 만들어내지 않습니다.</p>
      <form id="external-policy-audit">
      <label class="field"><span>문서 유형</span><select name="kind"><option value="privacy">개인정보처리방침</option><option value="terms">이용약관</option></select></label>
      <label class="field"><span>현재 문서 본문 (최대 30,000자)</span><textarea name="document_text" rows="8" maxlength="30000" required placeholder="정책 문서의 텍스트를 붙여넣으세요."></textarea></label>
      <details><summary>선택: 확인된 실제 운영 정보 (JSON)</summary>
      <p class="muted">예: {"processors":"실제 수탁업체 및 처리 목적"} 등 확인된 정보만 입력하세요.</p>
      <textarea name="verified_facts_json" rows="3" maxlength="10000" spellcheck="false">{}</textarea></details>
      <div class="form-error"></div><button class="primary" type="submit">누락 가능성 검사·수정 계획</button></form>
      <div id="external-audit-result" role="status"></div>
    </section>
    <section class="card"><h2>3. 수정 후 반영</h2>
      <p>보고서를 바탕으로 기존 문서와 변경안을 비교한 후, 사이트 소유자의 권한으로 코드 저장소에 변경안을 제출해야 합니다.</p>
      <div class="notice warn">이 화면에서는 다른 사이트에 글을 게시하거나 정책을 자동 교체하지 않습니다. 키워드 검사 결과는 준법 또는 위반 판정이 아닙니다.</div>
    </section>`;
  addGithubPRUI();
  const scan=$('#external-site-scan');
  scan.onsubmit=async e=>{e.preventDefault();busy(scan,true);$('.form-error',scan).innerHTML='';
    try {
      const result=await api('/site-policy/scan',{method:'POST',body:{url:scan.elements.url.value}});
      let content=Object.entries(result.found||{}).map(([kind,p])=>`<li><strong>${kind==='privacy'?'개인정보처리방침':'이용약관'}:</strong> ${esc(p.url||'')} · ${esc(p.status||'정적 HTML 확인')}</li>`).join('');
      $('#external-scan-result').innerHTML=`<div class="notice">${esc(result.warning)}</div><ul>${content||'<li>직접 확인된 정책 링크가 없습니다.</li>'}</ul>`;
    }catch(err){showFormError(scan,err)}finally{busy(scan,false)}};
  const audit=$('#external-policy-audit');
  audit.onsubmit=async e=>{e.preventDefault();busy(audit,true);$('.form-error',audit).innerHTML='';
    try {
      const data={kind:audit.elements.kind.value,document_text:audit.elements.document_text.value,
                  verified_facts_json:audit.elements.verified_facts_json.value||'{}',jurisdiction:'KR'};
      const result=await api('/site-policy/audit',{method:'POST',body:data});
      const gaps=result.plan.suggested_changes||[];
      $('#external-audit-result').innerHTML=`<div class="notice">표현 검출: ${result.audit.mentioned}/${result.audit.total}개 · 모든 항목 사람 검토 필요</div><h3>수정 검토 목록</h3>
        <ul>${gaps.map(f=>`<li><strong>${esc(f.section)}</strong> · ${f.status==='FACTS_REQUIRED'?'운영정보 확인 필요':'운영정보 제공됨, 조항 검토 필요'}</li>`).join('')||'<li>표면적 검사는 마쳤으나 추가 법적 검토가 필요합니다.</li>'}</ul>
        <button id="copy-audit">검토 계획 복사</button><p class="muted">검사 결과만으로 적법성을 증명할 수 없습니다.</p>`;
      $('#copy-audit').onclick=()=>GenUICopyWorkaround(JSON.stringify(result,null,2));
    }catch(err){showFormError(audit,err)}finally{busy(audit,false)}};
}
async function GenUICopyWorkaround(value){
  try{await navigator.clipboard.writeText(value);toast('검토 계획을 복사했습니다.')}
  catch{toast('이 브라우저에서는 복사가 제한될 수 있습니다.')}
}
