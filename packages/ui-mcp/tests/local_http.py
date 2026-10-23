"""Run a real HTTP server and both client suites in one local process namespace."""
import os, secrets, subprocess, sys, time, urllib.request
from pathlib import Path
root=Path(__file__).resolve().parents[1]
out=Path(sys.argv[1]).resolve();out.mkdir(parents=True,exist_ok=True)
env={**os.environ,'PYTHONPATH':str(root),'UI_MCP_API_KEY':secrets.token_urlsafe(48),'MCP_TEST_URL':'http://127.0.0.1:8000/mcp','NO_PROXY':'127.0.0.1,localhost'}
with (out/'server.log').open('w') as log:
 p=subprocess.Popen([sys.executable,'-m','ui_core.http_server'],cwd=root,env=env,stdout=log,stderr=log)
 try:
  for _ in range(100):
   try:
    if urllib.request.build_opener(urllib.request.ProxyHandler({})).open('http://127.0.0.1:8000/health').status==200: break
   except OSError: time.sleep(.1)
  else: raise RuntimeError('Server failed to become ready')
  for script in ('sdk_smoke','sdk_v04','http_security'):
   with (out/(script+'.json')).open('w') as stdout, (out/(script+'.stderr')).open('w') as stderr:
    r=subprocess.run([sys.executable,str(root/'tests'/f'{script}.py')],env=env,stdout=stdout,stderr=stderr)
    print(script,r.returncode,flush=True)
    if r.returncode: raise RuntimeError(script+' failed; see stderr')
 finally:
  p.terminate();p.wait(timeout=10)
