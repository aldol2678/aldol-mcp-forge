/* Draft GitHub PR workflow. No direct website publish, merge or deployment. */
'use strict';
function addGithubPRUI() {
  main.insertAdjacentHTML('beforeend',`
  <section class="card" id="github-pr-workbench">
    <h2>4. 내 사이트의 GitHub 약관 수정 PR</h2>
    <p class="muted">승인된 GitHub App 설치와 사이트·저장소·파일 매핑이 있는 경우에만 사용할 수 있습니다. 공개 URL만으로 수정 권한이 부여되지는 않습니다.</p>
    <form id="github-policy-form">
      <label class="field"><span>사이트 주소 (승인된 HTTPS 루트)</span><input name="site_url" type="url" placeholder="https://example.org" required maxlength="300"></label>
      <label class="field"><span>GitHub 저장소</span><input name="repository" placeholder="owner/repository" required maxlength="130"></label>
      <label class="field"><span>등록된 정책 파일 경로</span><input name="document_path" placeholder="docs/privacy.md" required maxlength="220"></label>
      <label class="field"><span>새 문서 전문 (20~30000자)</span><textarea name="proposed_text" minlength="20" maxlength="30000" rows="10" required></textarea></label>
      <div class="form-error"></div>
      <button class="primary" type="submit">GitHub 파일 확인·변경사항 미리보기</button>
    </form>
    <div id="github-pr-preview" role="status"></div>
  </section>`);
  const form=$('#github-policy-form');
  let preview=null;
  const $input=(key)=>form.elements[key].value;
  const payload=()=>({site_url:$input('site_url'),repository:$input('repository'),
                     document_path:$input('document_path'),proposed_text:$input('proposed_text')});
  for(const el of form.querySelectorAll('input,textarea'))el.oninput=()=>{
    if(preview){preview=null;$('#github-pr-preview').innerHTML='<p class="notice warn">입력이 변경되었습니다. 변경사항 미리보기를 다시 확인해야 합니다.</p>'}
  };
  form.onsubmit=async e=>{
    e.preventDefault();busy(form,true);$('.form-error',form).innerHTML='';preview=null;
    $('#github-pr-preview').innerHTML='<p role="status">저장소 권한과 문서 버전을 확인 중입니다…</p>';
    try {
      const sent=payload();
      const plan=await api('/site-policy/github/prepare',{method:'POST',body:sent});
      preview={digest:plan.preview_digest,payload:sent};
      $('#github-pr-preview').innerHTML=`
      <div class="notice">소유자 권한 매핑 및 원본 파일 확인에 성공했습니다. 이 단계에서는 저장소가 변경되지 않았습니다.</div>
      <h3>변경 검토</h3>
      <p><small>저장소: ${esc(plan.repository)} · 파일: ${esc(plan.document_path)} · 기준: ${esc(plan.base_branch)}</small></p>
      <pre class="legal-content policy-diff">${esc(plan.diff)}</pre>
      <p class="muted">${esc(plan.warning)}</p>
      <label class="check"><input id="github-pr-confirm" type="checkbox"> 위 변경 내용을 검토했으며 GitHub에 <strong>Draft PR을 생성</strong>하는 데 동의합니다.</label>
      <button id="github-pr-create" class="primary" type="button">Draft PR 생성 (병합·배포 안 함)</button>
      <div class="form-error"></div>`;
      $('#github-pr-create').onclick=async()=>{
        if(!preview||!$('#github-pr-confirm').checked){toast('미리보기 검토와 PR 생성 확인이 필요합니다.');return}
        const btn=$('#github-pr-create');btn.disabled=true;
        try{
          const result=await api('/site-policy/github/submit',{method:'POST',body:{
            ...preview.payload,expected_preview_digest:preview.digest,confirmed:true
          }});
          preview=null;
          const checkedUrl=typeof result.url==='string'&&result.url.startsWith('https://github.com/')?result.url:null;
          $('#github-pr-preview').innerHTML=`<div class="notice"><strong>Draft PR 생성·재조회 검증 완료</strong>
            <p>저장소: ${esc(result.repository)} · 브랜치: ${esc(result.branch)} · PR #${esc(result.number)}</p>
            ${checkedUrl?`<a target="_blank" rel="noopener noreferrer" href="${esc(checkedUrl)}">GitHub에서 검토하기</a>`:''}
            <p>병합과 운영 배포는 별도 승인·검증이 필요합니다.</p></div>`;
        }catch(err){const box=$('.form-error',$('#github-pr-preview'));if(box)box.innerHTML=errorBox(err.message);else toast(err.message);}
        finally{btn.disabled=false}
      };
    }catch(err){$('#github-pr-preview').innerHTML='';showFormError(form,err)}
    finally{busy(form,false)}
  };
}
