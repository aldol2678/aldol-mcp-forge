"""Run current example without overwriting projects or existing ZIP files."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import forge
from templates import html_audit

if __name__ == '__main__':
    name = 'aldol-game-html-audit'
    test = forge._test({'project_name': name, 'isolation': 'strict'})
    sample = '<html><body><canvas id="game"></canvas><img src="http://example.org/a.png"></body></html>'
    report = {
        'forge_version': '0.2.0',
        'source_project': name,
        'tools': forge._validated(name)[2],
        'smoke_test': test,
        'example_html_audit': html_audit({'content': sample}),
        'installed_sdk': test['sdk_available_locally'],
        'external_deployment': False,
    }
    dest = ROOT / 'examples' / 'verification.json'
    dest.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'passed': test['passed'], 'tools': report['tools'],
                      'isolation': test['isolation'], 'sdk_status': test['official_sdk']}, ensure_ascii=False))
