"""Run the existing Vercel ASGI mounts locally; never changes deployment secrets."""
import asyncio
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT.parents[1]
out=Path(sys.argv[1]).resolve();out.mkdir(parents=True,exist_ok=True)
env={**os.environ,'PYTHONPATH':str(ROOT),'ALDOL_DESIGN_MCP_KEY':secrets.token_urlsafe(48),
     'MCP_TEST_URL':'http://127.0.0.1:8012/ui/mcp','MCP_BODY_LIMIT':'3000000'}
env['UI_MCP_API_KEY']=env['ALDOL_DESIGN_MCP_KEY']
with (out/'server.log').open('w') as log:
 p=subprocess.Popen([sys.executable,'-m','uvicorn','app:app','--port','8012','--no-access-log'],cwd=REPO,env=env,stdout=log,stderr=log)
 try:
  for _ in range(100):
   try:
    if urllib.request.build_opener(urllib.request.ProxyHandler({})).open('http://127.0.0.1:8012/health').status==200: break
   except OSError: time.sleep(.1)
  else: raise RuntimeError('ASGI mounts failed to start')
  for script in ('sdk_smoke','sdk_v04','http_security'):
   with (out/(script+'.json')).open('w') as stdout,(out/(script+'.stderr')).open('w') as stderr:
    r=subprocess.run([sys.executable,str(ROOT/'tests'/f'{script}.py')],env=env,stdout=stdout,stderr=stderr)
    assert r.returncode==0,script+' failed'
  os.environ.update({k:env[k] for k in ('UI_MCP_API_KEY',)})
  os.environ['MCP_TEST_URL']='http://127.0.0.1:8012/bonsae/mcp'
  from sdk_smoke import connection,data
  async def bonsae_check():
   async with connection() as session:
    assert {t.name for t in (await session.list_tools()).tools}=={'analyze_design','generate_design_spec','review_visual'}
    r=await session.call_tool('analyze_design',{'reference':'<main><button>Save</button></main>'})
    assert not r.is_error
    return {'discovery':3,'actual_call':'analyze_design','status':'PASS'}
  result=asyncio.run(bonsae_check());(out/'bonsae.json').write_text(json.dumps(result,indent=2))
  print('Vercel ASGI UI/BONSAE mounts: PASS')
 finally:
  p.terminate();p.wait(timeout=10)
