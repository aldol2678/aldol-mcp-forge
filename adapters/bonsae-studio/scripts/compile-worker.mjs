import fs from 'node:fs';
const q=JSON.stringify;
const company="bonsae";
const prefix='const COMPANY='+q(company)+';\nconst TOOLS='+fs.readFileSync('worker/tools.json','utf8')+';\nconst PAGE='+q(fs.readFileSync('ui/page.html','utf8'))+';\nconst CLIENT='+q(fs.readFileSync('ui/client.js','utf8'))+';\nconst CSS='+q(fs.readFileSync('ui/style.css','utf8'))+';\n';
fs.writeFileSync('worker/index.js',prefix+fs.readFileSync('worker/runtime.mjs','utf8'));
