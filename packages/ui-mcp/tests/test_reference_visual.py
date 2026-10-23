import base64
from io import BytesIO
import json
from pathlib import Path
import struct
import sys
import unittest
import zlib
from unittest.mock import patch
import jsonschema

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PIL import Image, ImageDraw, PngImagePlugin
from ui_core import reference, visual, core, bonsae_bridge


def encoded(size=(160, 120), box=(20, 20, 80, 80), color='black', fmt='PNG'):
    im = Image.new('RGB', size, 'white')
    if box:
        ImageDraw.Draw(im).rectangle(box, fill=color)
    out = BytesIO(); im.save(out, format=fmt)
    return base64.b64encode(out.getvalue()).decode()


class ReferenceTests(unittest.TestCase):
    def test_published_output_contracts(self):
        root=Path(__file__).resolve().parents[1]/'schemas'
        for name, results in [
            ('ui_reference_analyze',[reference.analyze(''),reference.analyze('<main><button>B</button></main>')]),
            ('ui_visual_compare',[visual.compare(encoded(),encoded()),visual.compare(encoded(),encoded(size=(161,120)))])]:
            schema=json.loads((root/(name+'.output.schema.json')).read_text())
            for result in results: jsonschema.validate(result,schema)

    def test_regions_and_interactions(self):
        r = reference.analyze('''<header></header><nav><a href='/next'>Go</a></nav>
        <aside></aside><main><article></article><button role='tab'>Tab</button>
        <dialog hidden></dialog><form><input type='submit'></form><details><summary>More</summary></details></main><footer></footer>''')
        self.assertTrue({'header','navigation','sidebar','content','card','tab','modal','form','footer'} <= {c['role'] for c in r['components']})
        self.assertTrue({'navigation','tab_selection','popup','form_submission','expand_collapse'} <= {c['kind'] for c in r['interaction_candidates']})
        self.assertTrue(all(not c['behavior_verified'] for c in r['interaction_candidates']))

    def test_responsive_and_tokens(self):
        r = reference.analyze('<meta name="viewport" content="width=device-width, initial-scale=1"><button style="position:fixed">B</button>', css='@media(max-width:390px){.card{overflow:auto;gap:12px;color:#112233}}')
        self.assertTrue(r['responsive_evidence'][0]['observed'])
        self.assertTrue({'media_rule','position','overflow'} <= {e['kind'] for e in r['responsive_evidence']})
        self.assertIn('#112233', [e['value'] for e in r['tokens']])

    def test_empty(self):
        r = reference.analyze('')
        self.assertEqual(r['status'], 'INSUFFICIENT_EVIDENCE')
        self.assertIsNone(r['ui_spec_draft'])

    def test_invalid_json(self):
        for s in ('{', '[]', 'null', '{"root":{}}'):
            with self.subTest(s=s), self.assertRaises(ValueError): reference.analyze(s, 'ui-json')

    def test_deep_json(self):
        with self.assertRaises(ValueError): reference.analyze('[' * 1000 + '0' + ']' * 1000, 'ui-json')

    def test_deep_html(self):
        with self.assertRaises(ValueError): reference.analyze('<div>' * 65)

    def test_many_elements(self):
        with self.assertRaises(ValueError): reference.analyze('<input>' * 3001)

    def test_deep_css(self):
        with self.assertRaises(ValueError): reference.analyze('<button>B</button>', css='@media all{' * 65 + '}' * 65)

    def test_size_limit(self):
        with self.assertRaises(ValueError): reference.analyze('가' * 70000)

    def test_combined_limit(self):
        with self.assertRaises(ValueError): reference.analyze('x' * 110000, css=' ' * 100000)

    def test_no_execution_fetch_or_sensitive_echo(self):
        secret = 'PRIVATE_SENTINEL_123'
        source = '<script>fetch("https://invalid/' + secret + '")</script><input value="' + secret + '"><button onclick="' + secret + '"> ' + secret + '</button><a href="https://invalid/' + secret + '">go</a>'
        with patch('socket.socket', side_effect=AssertionError('network prohibited')):
            r = reference.analyze(source)
        self.assertNotIn(secret, json.dumps(r))
        self.assertTrue(any('ignored' in s for s in r['unknowns']))

    def test_template_is_inert(self):
        r = reference.analyze('<template><button>hidden</button></template><button>real</button>')
        self.assertEqual(len(r['components']), 1)

    def test_repetition_and_missing_region(self):
        r = reference.analyze('<button>A</button><button>B</button>')
        self.assertEqual(r['repeated_components'][0]['count'], 2)
        self.assertNotIn('header', [c['role'] for c in r['layout_regions']])

    def test_malformed_html(self):
        r = reference.analyze('<main><button></main>')
        self.assertTrue(any('Malformed' in x for x in r['unknowns']))

    def test_draft_handoff_generate_audit(self):
        r = reference.analyze('<main><button>Save</button></main>')
        imported = bonsae_bridge.import_bonsae(json.dumps(r['bonsae_spec_draft']))
        spec = imported['ui_spec_json']
        self.assertEqual(json.loads(spec), r['ui_spec_draft'])
        self.assertTrue(core.validate(spec)['valid'])
        for target in core.ALLOWED_TARGETS: self.assertTrue(core.render(spec, target))
        self.assertTrue(core.audit(spec)); self.assertTrue(core.review(spec))
        self.assertFalse(r['release_authorized'])

    def test_all_legacy_examples(self):
        for name in ('web-dashboard','expedition-hud-v03','expedition-hud'):
            s = (Path(__file__).resolve().parents[1] / 'examples' / (name + '.json')).read_text()
            with self.subTest(name=name):
                r = reference.analyze(s, 'ui-json')
                self.assertTrue(r['components'])
                self.assertTrue(core.validate(json.dumps(r['ui_spec_draft']))['valid'])

    def test_draft_and_inventory_caps_disclosed(self):
        r = reference.analyze('<button>B</button>' * 210)
        self.assertEqual(len(r['components']), 200)
        self.assertEqual(len(r['bonsae_spec_draft']['components']), 20)
        self.assertTrue(any('omitted' in x for x in r['unmapped_features']))
        self.assertTrue(any('capped' in x for x in r['unknowns']))


class VisualTests(unittest.TestCase):
    def test_identical_all_modes(self):
        im = encoded()
        for mode in ('layout','pixel','region'):
            with self.subTest(mode=mode):
                r = visual.compare(im, im, mode)
                self.assertEqual(r['layout_similarity'], 1)
                self.assertEqual(r['pixel_difference']['ratio'], 0)
                self.assertFalse(r['changed_regions'])
                self.assertEqual(r['status'], 'COMPARED')

    def test_shift_inside_same_tile_detected(self):
        r = visual.compare(encoded(box=(22,22,25,25)), encoded(box=(27,22,30,25)))
        self.assertLess(r['layout_similarity'], 1)
        self.assertTrue(r['changed_regions'])

    def test_recolor_layout_vs_pixel(self):
        a, b = encoded(color='black'), encoded(color='red')
        r = visual.compare(a,b)
        self.assertEqual(r['layout_similarity'], 1)
        self.assertGreater(r['pixel_difference']['ratio'], 0)
        self.assertFalse(r['changed_regions'])

    def test_missing_panel(self):
        r = visual.compare(encoded(), encoded(box=None))
        self.assertEqual(r['layout_similarity'], 0)
        self.assertTrue(r['changed_regions'])

    def test_dimension_mismatch(self):
        r = visual.compare(encoded(), encoded(size=(160,121)))
        self.assertTrue(r['dimension_mismatch'])
        self.assertEqual(r['status'], 'INCOMPARABLE')
        self.assertIsNone(r['layout_similarity']); self.assertIsNone(r['pixel_difference'])

    def test_blank_no_structure(self):
        r = visual.compare(encoded(box=None), encoded(box=None))
        self.assertIsNone(r['layout_similarity'])

    def test_last_column_and_nondivisible_width(self):
        r = visual.compare(encoded(size=(163,119),box=None), encoded(size=(163,119),box=(162,0,162,118)), 'pixel')
        self.assertTrue(any(x['x'] + x['width'] == 163 for x in r['changed_regions']))

    def test_corrupt_inputs(self):
        for s in ('', 'not base64!', base64.b64encode(b'\x89PNG\r\n\x1a\nxxx').decode(), base64.b64encode(b'\xff\xd8\xffbroken').decode()):
            with self.subTest(s=s), self.assertRaises(ValueError): visual.compare(s, encoded())

    def test_urls_and_svg_rejected(self):
        for s in ('https://example.com/screen.png','/etc/passwd','data:image/png;base64,' + encoded(),base64.b64encode(b'<svg/>').decode()):
            with self.assertRaises(ValueError): visual.compare(s, encoded())

    def test_byte_limit(self):
        with self.assertRaises(ValueError): visual.compare('A' * 240004, encoded())

    def test_pixel_and_side_limits(self):
        for size in ((4097,1),(1500,1500)):
            with self.subTest(size=size), self.assertRaises(ValueError): visual.compare(encoded(size=size,box=None), encoded())

    def test_decompression_bomb_header(self):
        def chunk(k,d): return struct.pack('>I',len(d))+k+d+struct.pack('>I',zlib.crc32(k+d)&0xffffffff)
        raw = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR',struct.pack('>IIBBBBB',100000,100000,8,2,0,0,0)) + chunk(b'IEND',b'')
        with self.assertRaises(ValueError): visual.compare(base64.b64encode(raw).decode(),encoded())

    def test_compressed_metadata_rejected(self):
        info = PngImagePlugin.PngInfo(); info.add_text('note','x' * 10000,zip=True)
        out=BytesIO(); Image.new('RGB',(10,10)).save(out,format='PNG',pnginfo=info)
        with self.assertRaises(ValueError): visual.compare(base64.b64encode(out.getvalue()).decode(),encoded())

    def test_jpeg(self):
        a=encoded(fmt='JPEG'); self.assertEqual(visual.compare(a,a)['pixel_difference']['ratio'],0)

    def test_alpha_white_compositing(self):
        out=BytesIO(); Image.new('RGBA',(160,120),(255,0,0,0)).save(out,format='PNG')
        self.assertEqual(visual.compare(base64.b64encode(out.getvalue()).decode(),encoded(box=None))['pixel_difference']['ratio'],0)

    def test_parameters(self):
        for kw in ({'comparison_mode':'shell'},{'viewport':'phone'},{'tolerance':65},{'tolerance':True},{'same_state':'yes'}):
            with self.assertRaises(ValueError): visual.compare(encoded(),encoded(),**kw)

    def test_state_warning(self):
        self.assertEqual(visual.compare(encoded(),encoded())['evidence']['state_match'],'unverified')
        self.assertEqual(visual.compare(encoded(),encoded(),same_state=True)['evidence']['state_match'],'caller_asserted')

    def test_concurrency_gate(self):
        visual._SLOT.acquire()
        try:
            with self.assertRaises(ValueError): visual.compare(encoded(),encoded())
        finally: visual._SLOT.release()

    def test_mask_and_transport_budget(self):
        r=visual.compare(encoded(),encoded(box=None),'region')
        artifact=r['diff_artifact']
        mask=Image.open(BytesIO(base64.b64decode(artifact['data'])))
        self.assertEqual(mask.mode,'1'); self.assertFalse(artifact['stored'])
        envelope={'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':'ui_visual_compare','arguments':{'reference_image':'A'*240000,'candidate_image':'A'*240000}}}
        self.assertLess(len(json.dumps(envelope)),512000)


if __name__ == '__main__': unittest.main()
