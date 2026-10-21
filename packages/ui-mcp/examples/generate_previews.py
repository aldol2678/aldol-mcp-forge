from pathlib import Path
import sys
import json
base = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(base))
from ui_core import core
source=(base/'examples/expedition-hud.json').read_text(encoding='utf-8')
for target, filename in [('game-hud-html','game-hud-preview.html'),('web-html','web-preview.html')]:
    output=core.render(source,target)
    (base/'examples'/filename).write_text(output['preview_html'],encoding='utf-8')
print(json.dumps({'version':core.catalog()['schema_version'], 'validation':core.validate(source),
                  'audit':core.audit(source)},ensure_ascii=False,indent=2))
