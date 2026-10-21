"""Behavioral regression for bounded source, design and real-pixel BONSAE tools."""
import base64
import io
import json
import unittest
from unittest.mock import patch

from enterprise_mcps import bonsae
from enterprise_mcps.bonsae_visual import inspect_image, render_html
from enterprise_mcps.common import verify_output


class BonsaeExtendedTests(unittest.TestCase):
    def test_source_findings_have_actionable_locations(self):
        html = '<html lang="ko">\n<main><img id="portrait"><button id="go"></button></main></html>'
        result = bonsae.analyze_design(html, ':root { --ink:#111; } button { color:var(--missing); }')
        findings = json.loads(result['findings'])
        img = next(x for x in findings['issues'] if x['code'] == 'IMG_ALT')
        self.assertEqual(img['location'], {'selector': '#portrait', 'line': 2, 'column': 7})
        self.assertTrue(img['evidence'])
        self.assertTrue(img['suggestion'])
        self.assertIn('UNDEFINED_DESIGN_TOKEN', [x['code'] for x in findings['issues']])
        self.assertFalse(findings['rendered_visual_qa'])
        verify_output('bonsae', 'analyze_design', result)

    def test_native_nested_labels_and_image_button_names(self):
        html = '<html lang="ko"><meta name="viewport" content="width=device-width"><main><label>검색<input></label><button><img alt="계속"></button></main></html>'
        codes = [x['code'] for x in json.loads(bonsae.analyze_design(html)['findings'])['issues']]
        self.assertNotIn('INPUT_LABEL', codes)
        self.assertNotIn('BUTTON_NAME', codes)

    def test_internal_css_and_unexamined_defaults_are_not_automatic_defects(self):
        html = '<html lang="ko"><main><style>body{background:linear-gradient(red,blue)} .x{animation:spin 1s}</style></main></html>'
        findings = json.loads(bonsae.analyze_design(html)['findings'])
        self.assertFalse(findings['unexamined_default_candidates'][0]['is_automatic_defect'])
        self.assertIn('REDUCED_MOTION_UNSPECIFIED', [x['code'] for x in findings['issues']])

    def test_responsive_design_handoff_keeps_meaning_and_declared_states(self):
        r = bonsae.generate_design_spec(json.dumps({'goal': '조사 근거 읽기', 'components': [
            {'name': 'Evidence List', 'role': 'list', 'states': ['default', 'empty', 'error'],
             'mobile_behavior': '카드로 재배치하되 URL과 관측일 유지', 'interaction': '항목 선택으로 원문 열기'}]}))
        spec = json.loads(r['specification'])
        self.assertEqual(set(spec['layouts']), {'390', '820', '1280'})
        self.assertIn('관측일', spec['components'][0]['mobile_behavior'])
        self.assertEqual(spec['components'][0]['states'], ['default', 'empty', 'error'])
        self.assertIn('semantic', spec['seum_handoff']['drift_categories'])
        self.assertFalse(json.loads(r['constraints'])['release_authorized'])
        verify_output('bonsae', 'generate_design_spec', r)

    def test_remote_screenshot_reference_never_counts_as_inspection(self):
        r = bonsae.review_visual(json.dumps({'artifact_id': 'untrusted', 'screenshot_refs': ['https://127.0.0.1/private.png'],
            'observations': [{'issue': 'looks good', 'evidence': 'caller says PASS'}]}))
        self.assertEqual(r['verdict'], 'HOLD_UNINSPECTED')
        f = json.loads(r['findings'])
        self.assertFalse(f['visual_inspection_performed'])
        self.assertFalse(f['whole_screen_pass'])

    def test_actual_supplied_png_decoding_with_hash_and_no_whole_screen_pass(self):
        from PIL import Image
        image = Image.new('RGB', (390, 820), '#123456')
        out = io.BytesIO()
        image.save(out, format='PNG')
        r = bonsae.review_visual(json.dumps({'artifact_id': 'actual-png',
                'image_base64': base64.b64encode(out.getvalue()).decode()}))
        f = json.loads(r['findings'])
        self.assertEqual(r['verdict'], 'HOLD_PARTIAL_VISUAL')
        self.assertTrue(f['image_pixels']['pixel_decode_performed'])
        self.assertEqual(f['image_pixels']['width'], 390)
        self.assertEqual(f['image_pixels']['height'], 820)
        self.assertEqual(len(f['image_pixels']['sha256']), 64)
        self.assertEqual(f['semantic_visual_review'], 'NOT_RUN')
        self.assertFalse(f['whole_screen_pass'])
        verify_output('bonsae', 'review_visual', r)

    def test_invalid_image_and_url_are_rejected_without_fetch(self):
        for value in ['https://example.com/image.png', 'data:image/png;base64,AA==', 'not-base64']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                inspect_image(value)
        with self.assertRaises(Exception):
            inspect_image(base64.b64encode(b'not an image').decode())

    def test_browser_unavailable_never_becomes_pass(self):
        with patch('enterprise_mcps.bonsae_visual.render_html', return_value={'rendered': False, 'reason': 'BROWSER_UNAVAILABLE'}):
            r = bonsae.review_visual(json.dumps({'artifact_id': 'browser-missing', 'html': '<main>실제 자료</main>'}))
        self.assertEqual(r['verdict'], 'HOLD_UNINSPECTED')
        self.assertFalse(json.loads(r['findings'])['visual_inspection_performed'])

    def test_render_adaptor_rejects_unbounded_viewports_and_no_html(self):
        for viewports in [[1], [390, 820, 1280, 390], [True], ['390']]:
            with self.subTest(viewports=viewports), self.assertRaises(ValueError):
                render_html('<main>test</main>', '', viewports)
        with self.assertRaises(ValueError):
            render_html('https://example.com', '', [390], {'not-a-css-token': 'x'})
        with self.assertRaises(ValueError):
            bonsae.analyze_design('<div>' * 101)

    def test_detected_render_failure_is_not_silenced_by_partial_pixels(self):
        rendered = {'rendered': True, 'viewports': [{'viewport': 390, 'overflow': True, 'clippedContainers': [],
                    'smallTouchTargets': [], 'contrast': [], 'tokenDrift': []}]}
        with patch('enterprise_mcps.bonsae_visual.render_html', return_value=rendered):
            r = bonsae.review_visual(json.dumps({'artifact_id': 'overflow', 'html': '<main>x</main>'}))
        self.assertEqual(r['verdict'], 'FAIL_RENDER_CHECKS')
        self.assertFalse(json.loads(r['findings'])['whole_screen_pass'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
