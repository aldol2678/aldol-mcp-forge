from pathlib import Path
import re,json
root=Path(__file__).resolve().parents[1]
parts=[]
for filename in ['core.js','assets.js','contract.js','generator.js','store.js','page.js','index.js']:
 text=(root/'worker'/filename).read_text()
 text=re.sub(r'^import .*?;\n','',text,flags=re.M)
 text=re.sub(r'^export \{.*?\};\n','',text,flags=re.M)
 text=re.sub(r'\bexport (?=(?:const|function|async function)\b)','',text)
 if filename == 'contract.js':
  # Bundle private compiler helpers in their own lexical scope. Preserve only
  # declared public functions for the adjoining modules; avoid collisions with core.
  exports='parseContract,previewContract,contractInputSchema,renderContractServer,contractReadme'
  text="const {"+exports+"}=(()=>{\n"+text+"\nreturn {"+exports+"};\n})();"
 parts.append('// MODULE '+filename+'\n'+text)
out=root/'dist'/'server';out.mkdir(parents=True,exist_ok=True);(out/'index.js').write_text('\n'.join(parts))
