const button=document.getElementById('scan');
const state=document.getElementById('state');
const output=document.getElementById('output');
button.addEventListener('click',async()=>{
  const token=document.getElementById('token').value;
  const subpath=document.getElementById('path').value;
  const tool=document.getElementById('tool').value;
  if(!token){state.textContent='토큰이 필요합니다';return}
  button.disabled=true;state.textContent='검사 중';output.textContent='';
  try{
    const response=await fetch('/api/scan',{method:'POST',headers:{'Authorization':'Bearer '+token,'Content-Type':'application/json'},body:JSON.stringify({subpath,tool}),cache:'no-store'});
    const data=await response.json();
    state.textContent=response.ok?(data.overall||data.status||'완료'):'오류 '+response.status;
    output.textContent=JSON.stringify(data,null,2);
  }catch(_){state.textContent='연결 실패';output.textContent='서버 연결 상태를 확인하세요'}
  finally{button.disabled=false}
});
