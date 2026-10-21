"""Alpha 0.3 reusable components, versioning and strict data-binding checks."""
import json
import unittest
from pathlib import Path
from ui_core import core

BASE=Path(__file__).resolve().parents[1]

class UI03Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec=json.loads((BASE/'examples/web-dashboard.json').read_text(encoding='utf-8'))
        cls.source=json.dumps(cls.spec,ensure_ascii=False)

    def mutated(self, update):
        s=json.loads(json.dumps(self.spec));update(s);return json.dumps(s,ensure_ascii=False)

    def test_03_documents(self):
        self.assertEqual(core.validate(self.source)['schema_version'],'0.3')
        self.assertTrue(core.validate((BASE/'examples/expedition-hud-v03.json').read_text())['valid'])

    def test_new_components_gallery(self):
        html=core.render(self.source)['html']
        for cls in ('alui-card','alui-grid','alui-metric','alui-divider','alui-notice','alui-progress'):
            self.assertIn(cls,html)
        self.assertIn('data-alui-bind="project-count"',html)
        self.assertIn('data-alui-bind="work-progress"',html)

    def test_three_themes(self):
        for name, palette in core.PRESETS.items():
            s=self.mutated(lambda d: d.update(preset=name))
            self.assertIn('--alui-primary:'+palette['primary'],core.render(s)['css'])

    def test_tokens_impact_css(self):
        s=self.mutated(lambda d: d.update(tokens=dict(font='mono',radius='sharp',density='compact')))
        css=core.render(s)['css']
        self.assertIn('--alui-radius:8px',css)
        self.assertIn('--alui-spacing:8px',css)
        self.assertIn('ui-monospace',css)

    def test_primary_button_contrast(self):
        a=core.audit(self.source)
        self.assertGreaterEqual(a['contrast_ratio'],4.5)
        self.assertGreaterEqual(a['primary_button_contrast_ratio'],4.5)

    def test_bind_security(self):
        source=self.mutated(lambda d: d['root']['children'][3]['children'][0]['children'][0].update(bind='" onload="alert(1)'))
        self.assertFalse(core.validate(source)['valid'])

    def test_malformed_preset_type_is_validation_error(self):
        self.assertFalse(core.validate(self.mutated(lambda d: d.update(preset=[])))['valid'])

    def test_malformed_token_type_is_validation_error(self):
        self.assertFalse(core.validate(self.mutated(lambda d: d.update(tokens={'font':[]})))['valid'])

    def test_malformed_component_type_is_validation_error(self):
        self.assertFalse(core.validate(self.mutated(lambda d: d['root'].update(type=[])))['valid'])

    def test_invalid_preset(self):
        self.assertFalse(core.validate(self.mutated(lambda d: d.update(preset='url(https://example.com)')))['valid'])

    def test_invalid_token(self):
        self.assertFalse(core.validate(self.mutated(lambda d: d.update(tokens={'font':'url(http://x)'})))['valid'])

    def test_invalid_grid(self):
        self.assertFalse(core.validate(self.mutated(lambda d: d['root']['children'][3].update(columns=99)))['valid'])

    def test_v02_version_lock(self):
        self.assertFalse(core.validate(self.mutated(lambda d: d.update(version='0.2')))['valid'])

    def test_dynamic_text_no_html_injection(self):
        source=self.mutated(lambda d: d['root']['children'][1].update(text='<svg/onload=alert(1)>',bind='title'))
        html=core.render(source)['html']
        self.assertNotIn('<svg/',html)
        self.assertIn('&lt;svg/',html)
        self.assertIn('textContent',core.RUNTIME_JS)

    def test_react_export(self):
        r=core.render(self.source,'react-tsx')
        self.assertIn('component_tsx',r)
        self.assertIn('React.useState',r['component_tsx'])
        self.assertIn('aria-expanded',r['component_tsx'])
        self.assertNotIn('dangerouslySetInnerHTML',r['component_tsx'])
        self.assertIn('.alui-hud-overlay',r['css'])

    def test_react_source_escape(self):
        source=self.mutated(lambda d: d['root']['children'][1].update(text='"; console.log(5); //'))
        tsx=core.render(source,'react-tsx')['component_tsx']
        self.assertIn('\\"; console.log(5); //',tsx)

if __name__=='__main__': unittest.main()
