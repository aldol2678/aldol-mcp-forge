import itertools,json,tempfile,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
import forge
from openapi_forge import parse_openapi
cases=[]
for size in range(1,4):
 for selected in itertools.permutations(forge.TEMPLATE_INFO,size):
  with tempfile.TemporaryDirectory() as d:
   target=Path(d);forge._write_project(target,'test-project','HTML 텍스트 JSON 검사',list(selected))
   files={p.name:p.read_text() for p in target.iterdir()};files.pop('manifest.json')
   cases.append({'name':'curated-'+','.join(selected),'args':{'project_name':'test-project','description':'HTML 텍스트 JSON 검사'},'selected':list(selected),'files':files})
for description in ['\u001cHTML 검사\u0085','\ufeffHTML 검사\ufeff','HTML $$ 검사 🐈']:
 with tempfile.TemporaryDirectory() as d:
  target=Path(d);forge._write_project(target,'test-edge',description.strip(),['html_audit'])
  files={p.name:p.read_text() for p in target.iterdir()};files.pop('manifest.json')
  cases.append({'name':'strip-'+repr(description),'args':{'project_name':'test-edge','description':description},'files':files})
for summary in ['Read pets',"A 'quoted' summary",'a"b\'c\\d\nnext\tline','한글 😺','\u2028\x00\u00a0']:
 spec=json.dumps({'openapi':'3.1.0','info':{'title':'Pets'},'paths':{'/pets/{id}':{'get':{'operationId':'readPet','summary':summary,'parameters':[{'name':'verbose','in':'query','schema':{'type':'boolean'}},{'name':'id','in':'path','required':True,'schema':{'type':'string'}}]}},'/pets':{'get':{'operationId':'listPets','parameters':[{'name':'limit','in':'query','schema':{'type':'integer'}}]},'post':{}}}},ensure_ascii=False)
 with tempfile.TemporaryDirectory() as d:
  target=Path(d);forge._write_openapi_project(target,'pets-api',parse_openapi(spec),spec)
  files={p.name:p.read_text() for p in target.iterdir()};files.pop('manifest.json')
  cases.append({'name':'openapi-'+repr(summary),'args':{'project_name':'pets-api','spec_json':spec},'files':files})
print(json.dumps(cases,ensure_ascii=False))
