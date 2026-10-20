"""Independent original Forge validators and real SDK clients for JS-generated files."""
import ast,json,os,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
import forge
output=[]
spec=(ROOT/'examples/pets_openapi.json').read_text()
requests=[{'project_name':'studio-html','description':'HTML game audit'},{'project_name':'studio-text','description':'text statistics'},{'project_name':'studio-json','description':'JSON audit'},{'project_name':'studio-api','spec_json':spec}]
script="import {generate} from './adapters/sites/worker/generator.js'; let s=''; for await (const c of process.stdin) s+=c;console.log(JSON.stringify(await generate(JSON.parse(s))));"
with tempfile.TemporaryDirectory() as tmp:
 forge.PROJECTS=Path(tmp)
 for args in requests:
  p=json.loads(subprocess.check_output(['node','--input-type=module','-e',script],input=json.dumps(args),text=True,cwd=ROOT));folder=Path(tmp)/p['project_name'];folder.mkdir()
  for name,content in p['files'].items():
   (folder/name).write_text(content)
   if name.endswith('.py'):ast.parse(content)
  if p['kind']=='curated':forge._validated(p['project_name'])
  else:forge._validated_openapi(p['project_name'])
  item={'name':p['project_name'],'original_validator':'PASS','ast':'PASS'}
  if '--official-sdk' in sys.argv:
   env={**os.environ,'ALDOL_API_BASE_URL':'','ALDOL_API_ALLOWED_HOST':''}
   run=subprocess.run([sys.executable,str(ROOT/'verify_sdk.py'),str(folder),'--mode','both'],capture_output=True,text=True,env=env,timeout=90)
   report=json.loads(run.stdout);assert run.returncode==0 and report['passed'] and report['official_sdk'],(run.stdout,run.stderr)
   item['official_sdk']=report
  else:item['official_sdk']='SKIP'
  output.append(item)
report={'passed':True,'projects':output,'scope':'JS-generated files; local Python execution, not Sites Python runtime'}
print(json.dumps(report,ensure_ascii=False,indent=2))
