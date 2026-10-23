const button=document.getElementById('scan');
const state=document.getElementById('state');
const output=document.getElementById('output');
button.addEventListener('click',async()=>{
  if(button.disabled)return;
  const token=document.getElementById('token').value;
  const subpath=document.getElementById('path').value;
  const tool=document.getElementById('tool').value;
  if(!token){state.textContent='토큰이 필요합니다';return}
  button.disabled=true;state.textContent='검사 중';output.textContent='';
  try{
    const response=await fetch('/api/scan',{method:'POST',headers:{'Authorization':'Bearer '+token,'Content-Type':'application/json'},body:JSON.stringify({subpath,tool}),cache:'no-store'});
    if(!response.ok){
      state.textContent=response.status===401?'인증 실패 (401)':'오류 '+response.status;
      output.textContent=response.status===401?'접근 토큰을 확인하세요':'요청을 처리하지 못했습니다';
      return;
    }
    let data;
    try{data=await response.json()}catch(_){state.textContent='응답 형식 오류';return}
    if(!data||typeof data!=='object'||Array.isArray(data)){state.textContent='응답 형식 오류';return}
    const status=data.overall||data.status||'UNKNOWN';
    const gaps=['UNKNOWN','INCOMPLETE','BLOCKED','FINDINGS_WITH_GAPS'].includes(status);
    state.textContent=status+(gaps?' · 검증 누락 — 안전 판정 아님':'');
    output.textContent=JSON.stringify(data,null,2);
  }catch(_){state.textContent='연결 실패';output.textContent='서버 연결 상태를 확인하세요'}
  finally{button.disabled=false}
});
