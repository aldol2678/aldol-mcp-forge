// Declarative contract preview and generator. No evaluation, network or implementation.
const IDENT=/^[a-z][a-z0-9_]{1,63}$/;
const KEYWORDS=new Set("False None True and as assert async await break class continue def del elif else except finally for from global if import in is lambda nonlocal not or pass raise return try while with yield".split(" "));
const RESERVED=new Set(["app","sys","Any","MCPServer","ToolError","Tool","serve","TOOLS","not_implemented"]);
const TYPES={string:"str",integer:"int",number:"float",boolean:"bool"};
const own=(obj,key)=>Object.hasOwn(obj,key);
const obj=x=>x!==null&&typeof x==="object"&&!Array.isArray(x);
const fail=message=>{throw Error(message);};
const identical=(obj,keys)=>obj&&obj.size===undefined&&Object.keys(obj).length===keys.length&&keys.every(k=>own(obj,k));
const ident=x=>typeof x==="string"&&IDENT.test(x)&&!KEYWORDS.has(x)&&!RESERVED.has(x);
const bounded=(x)=>typeof x==="string"&&[...x].length<=300;
function scalar(field,context){
 if(!obj(field)||Object.keys(field).some(k=>!["type","description"].includes(k)))fail(context+": unsupported JSON Schema keywords");
 if(!own(TYPES,field.type))fail(context+": only scalar types are supported");
 if(own(field,"description")&&!bounded(field.description))fail(context+": invalid field description");
}
// Reject duplicate object keys, even if the second value would overwrite a forbidden field.
// JSON.parse validates syntax; this scanner handles quoted strings and braces only.
function rejectDuplicateKeys(raw){
 const stack=[];let i=0;
 while(i<raw.length){
  const c=raw[i];
  if(c==='"'){
   const start=i++;
   while(i<raw.length){
    if(raw[i]==='\\'){i+=2;continue;}
    if(raw[i]==='"'){i++;break;}
    i++;
   }
   let j=i;while(/\s/.test(raw[j]||'')&&j<raw.length)j++;
   if(raw[j]===':'&&stack.at(-1)?.kind==='object'){
    const key=JSON.parse(raw.slice(start,i)),current=stack.at(-1).seen;
    if(current.has(key))fail("Duplicate JSON key: "+key);
    current.add(key);
   }
   continue;
  }
  if(c==='{')stack.push({kind:'object',seen:new Set()});
  if(c==='[')stack.push({kind:'array'});
  if(c==='}'||c===']')stack.pop();
  i++;
 }
}
export function parseContract(raw){
 if(typeof raw!=="string"||[...raw].length<2||[...raw].length>120000)fail("contract_json must be 2..120000 characters");
 let doc;try{doc=JSON.parse(raw);}catch{fail("contract_json must be valid JSON");}
 rejectDuplicateKeys(raw);
 if(!obj(doc)||!identical(doc,["tools"]))fail("Contract requires only a tools array");
 if(!Array.isArray(doc.tools)||doc.tools.length<1||doc.tools.length>12)fail("Contract requires 1..12 tools");
 const seen=new Set();
 for(const tool of doc.tools){
  if(!obj(tool)||!identical(tool,["name","description","inputs","output_schema"]))fail("Tool requires name, description, inputs and output_schema");
  if(!ident(tool.name)||seen.has(tool.name))fail("Unsafe or duplicate tool name");
  seen.add(tool.name);
  if(typeof tool.description!=="string"||![...tool.description.trim()].length||[...tool.description.trim()].length>500)fail("Tool description must be 1..500 characters");
  if(!Array.isArray(tool.inputs)||tool.inputs.length>12)fail("Tool inputs must be an array of at most 12 fields");
  const inputNames=new Set();
  for(const field of tool.inputs){
   if(!obj(field)||Object.keys(field).some(k=>!["name","type","required","description"].includes(k)))fail("Invalid input field keys");
   if(!ident(field.name)||inputNames.has(field.name))fail("Unsafe or duplicate input name");
   inputNames.add(field.name);
   scalar({type:field.type,...(own(field,"description")?{description:field.description}:{})},field.name);
   if(typeof field.required!=="boolean")fail("Input required must be boolean");
  }
  const out=tool.output_schema;
  if(!obj(out)||!identical(out,["type","properties","required","additionalProperties"])||out.type!=="object"||out.additionalProperties!==false)fail("Output must be a closed object JSON Schema");
  if(!obj(out.properties)||Object.keys(out.properties).length<1||Object.keys(out.properties).length>20)fail("Output requires 1..20 scalar properties");
  if(!Array.isArray(out.required)||new Set(out.required).size!==out.required.length||out.required.some(n=>typeof n!=="string"||!own(out.properties,n)))fail("Output required must list existing property names");
  for(const [key,field] of Object.entries(out.properties)){
   if(!ident(key))fail("Unsafe output property name");
   scalar(field,key);
  }
 }
 return {tools:doc.tools};
}
export function previewContract({contract_json}){
 const doc=parseContract(contract_json);
 return {supported:true,tools:doc.tools.map(t=>t.name),count:doc.tools.length,kind:"declarative-scaffold",
         handlers_implemented:false,network_access:false,
         note:"Scaffold only. All handlers reject calls with NOT_IMPLEMENTED."};
}
export function contractInputSchema(tool){
 return {type:"object",properties:Object.fromEntries(tool.inputs.map(f=>[f.name,
  {type:f.type,...(f.type==="string"?{maxLength:4096}:{}),...(own(f,"description")?{description:f.description}:{})}])),
  required:tool.inputs.filter(f=>f.required).map(f=>f.name),additionalProperties:false};
}
export function renderContractServer(name,tools,pyrepr){
 const lines=[
  '"""Generated scaffold by ALDOL MCP Forge v0.4. No handlers are implemented."""',
  "import sys","from typing import Any","",
  "def not_implemented(tool_name: str) -> dict[str, Any]:",
  '    raise ValueError("NOT_IMPLEMENTED: " + tool_name)',"",
  'if __name__ == "__main__" and "--compat-smoke-test" in sys.argv:',
  "    from mcp_runtime import Tool, serve","    tools = []",
 ];
 for(const t of tools){
  lines.push("    tools.append(Tool("+pyrepr(t.name)+", "+pyrepr(t.description)+", "+
   pyrepr(contractInputSchema(t))+", lambda args, n="+pyrepr(t.name)+": not_implemented(n)))");
 }
 lines.push("    serve("+pyrepr(name)+", '0.4.0', tools)","else:",
    "    from mcp.server import MCPServer",
    "    from mcp.server.mcpserver.exceptions import ToolError",
    "    app = MCPServer("+pyrepr(name)+")");
 for(const t of tools){
  const sorted=[...t.inputs].sort((a,b)=>Number(b.required)-Number(a.required));
  const params=sorted.map(f=>f.name+": "+TYPES[f.type]+(f.required?"":" | None = None")).join(", ");
  lines.push("","    @app.tool()","    def "+t.name+"("+params+") -> dict[str, Any]:",
    "        "+pyrepr(t.description),"        raise ToolError("+pyrepr("NOT_IMPLEMENTED: "+t.name)+")");
 }
 lines.push("","    if __name__ == \"__main__\":","        app.run()","");
 return lines.join("\n");
}
export function contractReadme(name,tools){
 const listing=tools.map(t=>"- "+t.name+": "+t.description).join("\n");
 return "# "+name+"\n\nALDOL MCP Forge v0.4 declarative scaffold.\n\nTools:\n"+listing+
 "\n\nPython 3.11+. Install mcp>=2,<3 then run python server.py.\n\n"+
 "IMPORTANT: every tool raises NOT_IMPLEMENTED. The saved contract.json\n"+
 "contains the proposed input/output shapes; the output schema is NOT\n"+
 "enforced by the SDK until a developer implements and tests handlers.\n"+
 "No API calls, filesystem edits, credentials, or deployment are generated.\n"+
 "The --compat-smoke-test mode is not an official SDK test.\n"+
 "Do not trust edited server.py until reviewed and tested independently.\n";
}
