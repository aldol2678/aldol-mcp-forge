"""Create an offline OpenAPI MCP example without overwriting existing projects."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import forge


if __name__ == '__main__':
    name = 'aldol-openapi-pets'
    spec_json = (ROOT / 'examples' / 'pets_openapi.json').read_text(encoding='utf-8')
    existing = forge.PROJECTS / name
    if not existing.exists():
        forge._import_openapi({'project_name': name, 'spec_json': spec_json, 'isolation': 'auto'})
    check = forge._test({'project_name': name, 'isolation': 'auto'})
    pkg = forge.PACKAGES / (name + '-v0.3.0.zip')
    if not pkg.exists():
        forge._package({'project_name': name, 'isolation': 'auto'})
    report = {'forge_version': '0.3.0', 'project_name': name,
              'preview': forge._preview_openapi({'spec_json': spec_json}),
              'verification': check, 'official_sdk_real_tested': check['official_sdk'] == 'passed',
              'external_deployment': False}
    dest = ROOT / 'examples' / 'verification_v03.json'
    dest.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'passed': check['passed'], 'checks': len(check['checks']),
                      'official_sdk': check['official_sdk'], 'isolation': check['isolation']}))
