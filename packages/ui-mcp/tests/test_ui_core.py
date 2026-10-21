import json
import unittest
from pathlib import Path
from ui_core import core

EXAMPLE = Path(__file__).resolve().parents[1] / 'examples' / 'expedition-hud.json'

class UICoreTests(unittest.TestCase):
    def setUp(self):
        self.doc = json.loads(EXAMPLE.read_text(encoding='utf-8'))
        self.src = json.dumps(self.doc, ensure_ascii=False)

    def test_example(self):
        self.assertTrue(core.validate(self.src)['valid'])

    def test_two_targets(self):
        for target in ("web-html", "game-hud-html"):
            out = core.render(self.src, target)
            self.assertIn('군단 체력', out['html'])
            self.assertIn('alui:action', out['javascript'])
            self.assertIn('data-alui-id="tactics"', out['html'])

    def test_demo_stage_only_in_game(self):
        g = core.render(self.src, 'game-hud-html')
        w = core.render(self.src)
        self.assertIn('ILLUSTRATIVE BATTLEFIELD', g['preview_html'])
        self.assertNotIn('ILLUSTRATIVE BATTLEFIELD', w['preview_html'])
        self.assertNotIn('alui-demo-stage', g['html'])
        self.assertIn('pointer-events:none', g['css'])

    def test_actions_are_declarative(self):
        r = core.render(self.src)
        self.assertIn('data-alui-action="toggle"', r['html'])
        self.assertIn('data-alui-action="emit"', r['html'])
        self.assertIn('aria-expanded="false"', r['html'])
        self.assertIn('aria-controls="alui-panel-tactics"', r['html'])
        self.assertIn('id="alui-panel-tactics"', r['html'])
        self.assertNotIn('onclick=', r['html'])

    def test_mobile_44px_touch_minimum(self):
        css = core.render(self.src)['css']
        self.assertIn('min-height:48px',css)
        self.assertIn('repeat(2,minmax(0,1fr))', css)
        self.assertIn('prefers-reduced-motion',css)

    def test_audit(self):
        a = core.audit(self.src)
        self.assertEqual(a['button_count'], 3)
        self.assertEqual(a['toggle_count'], 2)
        self.assertEqual(a['emit_count'], 1)
        self.assertGreaterEqual(a['contrast_ratio'],4.5)

    def test_injection_text(self):
        self.doc['root']['children'][0]['children'][1]['text'] = '<script>alert(1)</script>'
        out=core.render(json.dumps(self.doc))
        self.assertNotIn('<script>alert(1)',out['preview_html'])
        self.assertIn('&lt;script&gt;',out['preview_html'])

    def test_injection_panel_label(self):
        self.doc['root']['children'][0]['label'] = 'foo" onclick="evil()'
        out=core.render(json.dumps(self.doc))
        self.assertNotIn(' onclick="evil()"',out['html'])
        self.assertIn('&quot;',out['html'])

    def test_invalid_theme(self):
        self.doc['theme']['primary'] = 'red;body{color:red}'
        self.assertFalse(core.validate(json.dumps(self.doc))['valid'])

    def test_invalid_type(self):
        self.doc['root']['type'] = 'html'
        self.assertFalse(core.validate(json.dumps(self.doc))['valid'])

    def test_unknown_props(self):
        self.doc['root']['onclick'] = 'bad'
        self.assertFalse(core.validate(json.dumps(self.doc))['valid'])

    def test_unknown_doc_props(self):
        self.doc['script'] = 'bad'
        self.assertFalse(core.validate(json.dumps(self.doc))['valid'])

    def test_unknown_target(self):
        with self.assertRaises(ValueError): core.render(self.src,'unity')

    def test_bad_progress(self):
        progress = self.doc['root']['children'][0]['children'][2]
        progress['value'] = 101
        self.assertFalse(core.validate(json.dumps(self.doc))['valid'])

    def test_bad_nonfinite(self):
        self.doc['root']['children'][0]['children'][2]['value'] = float('nan')
        self.assertFalse(core.validate(json.dumps(self.doc))['valid'])

    def test_unsupported_action(self):
        self.doc['root']['children'][1]['children'][1]['children'][0]['action'] = {'type':'eval','code':'evil()'}
        self.assertFalse(core.validate(json.dumps(self.doc))['valid'])

    def test_unknown_target_action(self):
        self.doc['root']['children'][1]['children'][1]['children'][0]['action']['target']='missing'
        self.assertFalse(core.validate(json.dumps(self.doc))['valid'])

    def test_duplicate_panel_ids(self):
        self.doc['root']['children'][1]['children'][3]['id'] = 'tactics'
        self.assertFalse(core.validate(json.dumps(self.doc))['valid'])

    def test_invalid_event_name(self):
        self.doc['root']['children'][1]['children'][2]['children'][2]['action']['name']='";alert(1)'
        self.assertFalse(core.validate(json.dumps(self.doc))['valid'])

    def test_invalid_hidden_type(self):
        self.doc['root']['children'][1]['children'][2]['hidden']='false'
        self.assertFalse(core.validate(json.dumps(self.doc))['valid'])

    def test_invalid_variant(self):
        self.doc['root']['children'][1]['children'][1]['children'][0]['variant']='javascript'
        self.assertFalse(core.validate(json.dumps(self.doc))['valid'])

    def test_excessive_depth(self):
        n={'type':'text','text':'leaf'}
        for _ in range(12): n={'type':'stack','children':[n]}
        self.doc['root']=n
        self.assertFalse(core.validate(json.dumps(self.doc))['valid'])

    def test_large_source(self):
        self.assertFalse(core.validate(' '*30001)['valid'])

    def test_contrast_warning(self):
        self.doc['theme'].update({'foreground':'#000000','background':'#000000'})
        self.assertEqual(core.audit(json.dumps(self.doc))['contrast_ratio'],1)

    def test_legacy_01(self):
        data = json.dumps({'version':'0.1','title':'old',
            'theme': {'primary':'#346EEA','background':'#121A2B','foreground':'#F7F9FF'},
            'root':{'type':'stack','children':[{'type':'button','label':'go'},
                                                  {'type':'progress','label':'hp','value':1,'max':2}]}})
        self.assertTrue(core.validate(data)['valid'])
        self.assertIn('html',core.render(data))

    def test_catalog(self):
        c=core.catalog()
        self.assertIn('0.1',c['accepts_versions'])
        self.assertEqual(len(c['components']),12)

if __name__=='__main__': unittest.main()
