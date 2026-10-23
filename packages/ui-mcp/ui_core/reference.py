"""Bounded static reference inventory. Never fetches, renders or evaluates input.

Replica recon-map inspired evidence/inference separation; independently implemented.
Source text, form values, script bodies and URLs are deliberately not returned.
"""
from __future__ import annotations

from collections import Counter
from html.parser import HTMLParser
import json
import re
from typing import Any

import tinycss2
from . import bonsae_bridge, core

MAX_BYTES, MAX_NODES, MAX_DEPTH, MAX_COMPONENTS = 200_000, 3000, 64, 200
VOID = set('area base br col embed hr img input link meta param source track wbr'.split())
REGIONS = {'header': 'header', 'nav': 'navigation', 'aside': 'sidebar',
           'main': 'content', 'article': 'card', 'button': 'button',
           'dialog': 'modal', 'form': 'form', 'footer': 'footer'}
ROLES = {'banner': 'header', 'navigation': 'navigation', 'complementary': 'sidebar',
         'main': 'content', 'button': 'button', 'dialog': 'modal', 'form': 'form',
         'contentinfo': 'footer', 'tab': 'tab', 'tablist': 'tabs'}
CLASS_ROLES = {'card': 'card', 'panel': 'panel', 'modal': 'modal', 'popup': 'modal',
               'sidebar': 'sidebar', 'content': 'content', 'tabs': 'tabs'}
SAFE_VALUE = re.compile(r'(?:#[0-9a-fA-F]{3,8}|-?\d+(?:\.\d+)?(?:px|rem|em|%|vh|vw)|0)\Z')


def _bounded(text: str, label: str) -> None:
    if not isinstance(text, str) or len(text.encode('utf-8')) > MAX_BYTES:
        raise ValueError(label + ' exceeds the 200000-byte text limit')


def _nesting(text: str) -> None:
    # Preflight protects recursive JSON/CSS parsers, including escaped strings.
    depth, quote, escaped = 0, None, False
    for ch in text:
        if quote:
            if escaped:
                escaped = False
            elif ch == '\\':
                escaped = True
            elif ch == quote:
                quote = None
        elif ch in ('"', "'"):
            quote = ch
        elif ch in '[{(':
            depth += 1
            if depth > MAX_DEPTH:
                raise ValueError('Source nesting exceeds 64')
        elif ch in ']})':
            depth = max(0, depth - 1)


class Inventory(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.nodes, self.styles = [], [], []
        self.viewport = False
        self.ignored, self.external, self.malformed = 0, 0, False

    def handle_starttag(self, tag, attrs):
        if len(self.nodes) >= MAX_NODES or len(self.stack) >= MAX_DEPTH:
            raise ValueError('HTML exceeds 3000 elements or depth 64')
        a = dict(attrs)
        node = {'tag': tag, 'attrs': a, 'line': self.getpos()[0],
                'index': len(self.nodes), 'parent': self.stack[-1][1] if self.stack else None,
                'inert': any(t in ('script', 'style', 'template') for t, _ in self.stack)}
        self.nodes.append(node)
        if tag == 'meta' and str(a.get('name', '')).lower() == 'viewport':
            self.viewport = 'width=device-width' in str(a.get('content', '')).replace(' ', '').lower()
        if tag in ('script', 'iframe', 'object', 'embed'):
            self.ignored += 1
        if (tag == 'link' and 'stylesheet' in str(a.get('rel', ''))) or (tag == 'script' and a.get('src')):
            self.external += 1
        if tag not in VOID:
            self.stack.append((tag, node['index']))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                if i != len(self.stack) - 1:
                    self.malformed = True
                del self.stack[i:]
                return
        if tag not in VOID:
            self.malformed = True

    def handle_data(self, data):
        if self.stack and self.stack[-1][0] == 'style':
            self.styles.append(data)


def _css_evidence(styles: list[str]):
    responsive, tokens, unknowns = [], [], []
    for sheet_index, css in enumerate(styles):
        _nesting(css)
        rules = tinycss2.parse_stylesheet(css, skip_comments=True, skip_whitespace=True)
        todo = list(rules)
        scanned = 0
        while todo:
            rule = todo.pop()
            scanned += 1
            if scanned > 6000:
                raise ValueError('CSS exceeds 6000 rules')
            loc = {'sheet': sheet_index, 'line': rule.source_line}
            if rule.type == 'error':
                unknowns.append('CSS syntax error; declarations may be incomplete')
            elif rule.type == 'at-rule':
                if rule.lower_at_keyword in ('media', 'container'):
                    query = tinycss2.serialize(rule.prelude)
                    breakpoints = [{'feature': m[0], 'value': m[1]} for m in re.findall(
                        r'((?:min-|max-)?(?:width|height))\s*:\s*(\d+(?:\.\d+)?(?:px|em|rem))', query)]
                    responsive.append({'kind': rule.lower_at_keyword + '_rule', 'observed': True,
                                       'breakpoints': breakpoints[:16], **loc})
                if rule.lower_at_keyword == 'import':
                    unknowns.append('External CSS imports were not fetched')
                if rule.content:
                    todo.extend(tinycss2.parse_rule_list(rule.content, skip_comments=True, skip_whitespace=True))
            elif rule.type == 'qualified-rule':
                for d in tinycss2.parse_declaration_list(rule.content, skip_comments=True, skip_whitespace=True):
                    if d.type != 'declaration':
                        continue
                    val = tinycss2.serialize(d.value).strip()
                    name = d.lower_name
                    if (name == 'position' and val in ('fixed', 'sticky')) or (name.startswith('overflow') and val in ('auto', 'scroll', 'hidden', 'clip')):
                        responsive.append({'kind': name, 'value': val, 'observed': True, **loc})
                    if (name.startswith('--') or name in ('color', 'background-color', 'gap', 'padding', 'border-radius', 'font-size', 'width', 'max-width')) and SAFE_VALUE.fullmatch(val):
                        tokens.append({'property': 'custom-property' if name.startswith('--') else name,
                                       'value': val, 'observed': True, **loc})
    return responsive[:200], tokens[:100], sorted(set(unknowns)), len(responsive) > 200 or len(tokens) > 100


def analyze(source: str, source_format: str = 'html', css: str = '') -> dict[str, Any]:
    _bounded(source, 'source')
    _bounded(css, 'css')
    if len(source.encode('utf-8')) + len(css.encode('utf-8')) > MAX_BYTES:
        raise ValueError('Combined source and CSS exceed 200000 bytes')
    if source_format not in ('html', 'ui-json'):
        raise ValueError('source_format must be html or ui-json')
    components, interactions, evidence, unknowns = [], [], [], []
    styles = [css] if css else []
    viewport, script_count, external, malformed = False, 0, 0, False
    if source_format == 'ui-json':
        _nesting(source)
        validity = core.validate(source)
        if not validity.get('valid'):
            raise ValueError('Invalid UI JSON reference; use ui_validate for schema diagnostics')
        doc = json.loads(source)
        todo = [(doc['root'], '$.root')]
        while todo:
            node, path = todo.pop()
            eid = 'e' + str(len(evidence) + 1)
            evidence.append({'id': eid, 'path': path, 'observed': True, 'kind': node['type']})
            components.append({'id': 'c' + str(len(components) + 1), 'role': node['type'],
                               'basis': 'declared_ui_component', 'evidence': eid, 'confidence': 'high'})
            if node.get('action'):
                interactions.append({'component': components[-1]['id'], 'kind': 'declarative_action',
                                     'evidence': eid, 'behavior_verified': False})
            todo.extend((child, path + '.children[' + str(i) + ']') for i, child in enumerate(node.get('children', [])))
        unknowns.append('UI JSON declarations were validated, not rendered or executed')
    else:
        parser = Inventory()
        try:
            parser.feed(source)
            parser.close()
        except RecursionError as exc:
            raise ValueError('HTML nesting limit exceeded') from exc
        styles.extend(parser.styles)
        viewport, script_count, external = parser.viewport, parser.ignored, parser.external
        malformed = parser.malformed or bool(parser.stack)
        for n in parser.nodes:
            if n['inert'] or n['tag'] in ('script', 'style', 'template', 'iframe', 'object', 'embed'):
                continue
            a, tag = n['attrs'], n['tag']
            role = ROLES.get(a.get('role')) or REGIONS.get(tag)
            basis = 'semantic_tag_or_role'
            if not role:
                parts = set(re.split(r'[^a-z]+', str(a.get('class', '')).lower()))
                role = next((v for k, v in CLASS_ROLES.items() if k in parts), None)
                basis = 'class_name_heuristic'
            if not role and tag in ('input', 'select', 'textarea', 'details', 'summary', 'a'):
                role = {'details': 'disclosure', 'summary': 'disclosure_control', 'a': 'link'}.get(tag, 'form_control')
            if not role:
                continue
            eid, cid = 'e' + str(len(evidence) + 1), 'c' + str(len(components) + 1)
            evidence.append({'id': eid, 'element_index': n['index'], 'line': n['line'], 'tag': tag, 'observed': True})
            components.append({'id': cid, 'role': role, 'basis': basis, 'evidence': eid,
                               'confidence': 'medium' if basis == 'class_name_heuristic' else 'high',
                               'hidden_attribute': 'hidden' in a, 'disabled_attribute': 'disabled' in a})
            kinds = []
            if role in ('button', 'tab', 'tabs', 'modal'):
                kinds.append({'button': 'activation', 'tab': 'tab_selection', 'tabs': 'tab_selection', 'modal': 'popup'}[role])
            if tag in ('details', 'summary') or 'aria-expanded' in a:
                kinds.append('expand_collapse')
            if tag == 'a' and a.get('href'):
                kinds.append('navigation')
            if tag == 'form' or (tag in ('button', 'input') and a.get('type') == 'submit'):
                kinds.append('form_submission')
            if any(k.startswith('on') for k in a) or any(k.startswith('data-alui-') for k in a):
                kinds.append('handler_or_declarative_binding')
            for kind in kinds:
                interactions.append({'component': cid, 'kind': kind, 'evidence': eid, 'behavior_verified': False})
        styles.extend('x{' + n['attrs']['style'] + '}' for n in parser.nodes if n['attrs'].get('style') and not n['inert'])
    responsive, tokens, css_unknowns, css_truncated = _css_evidence(styles)
    unknowns.extend(css_unknowns)
    if source_format == 'html':
        responsive.insert(0, {'kind': 'device_width_viewport', 'observed': viewport})
    unknowns.extend(['Computed geometry, overflow, visibility and cascade require browser QA',
                     'Interactions and state transitions are candidates, not verified behavior',
                     'No screenshot understanding adapter is connected'])
    if script_count:
        unknowns.append('Executable/embed content ignored: ' + str(script_count))
    if external:
        unknowns.append('External resource references not fetched: ' + str(external))
    if malformed:
        unknowns.append('Malformed or unclosed HTML; static inventory may be incomplete')
    if not components:
        unknowns.append('No recognized UI components or regions')
    count = len(components)
    truncated = count > MAX_COMPONENTS
    components, evidence = components[:MAX_COMPONENTS], evidence[:MAX_COMPONENTS]
    ids = {c['id'] for c in components}
    interactions = [i for i in interactions if i['component'] in ids][:400]
    repeats = Counter(c['role'] for c in components)
    bonsae = None
    draft = None
    unmapped = ['Arbitrary CSS layout and runtime logic are not translated into UI JSON',
                'Draft components are review placeholders; source copy, links and actions are not transferred']
    if components:
        selected = components[:20]
        bonsae = {'goal': 'Static reference structure review', 'device': 'unspecified', 'tokens': {},
                  'components': [{'name': c['id'] + ' ' + c['role'], 'role': c['role'],
                                  'states': ['unverified'], 'mobile_behavior': 'Requires viewport QA',
                                  'interaction': 'Not implemented; see interaction_candidates'} for c in selected]}
        handoff = bonsae_bridge.import_bonsae(json.dumps(bonsae))
        draft = json.loads(handoff['ui_spec_json'])
        if count > 20:
            unmapped.append(str(count - 20) + ' components omitted from the 20-component BONSAE draft limit')
    if truncated or css_truncated:
        unknowns.append('Inventory/evidence output capped; omitted entries are not negative evidence')
    return {'analysis_version': '0.4', 'status': 'DRAFT_REVIEW_REQUIRED' if components else 'INSUFFICIENT_EVIDENCE',
            'screens': [{'id': 's1', 'basis': 'single supplied static document', 'routes_verified': False}],
            'components': components, 'layout_regions': [c for c in components if c['role'] in set(REGIONS.values()) | {'panel'}],
            'repeated_components': [{'role': role, 'count': n, 'basis': 'same semantic role; not proven reusable component'} for role, n in sorted(repeats.items()) if n > 1],
            'interaction_candidates': interactions, 'responsive_evidence': responsive,
            'tokens': tokens, 'source_evidence': evidence,
            'confidence': {'structure': 'medium' if components else 'low', 'runtime': 'unknown', 'geometry': 'unknown'},
            'unknowns': sorted(set(unknowns)), 'unmapped_features': unmapped,
            'ui_spec_draft': draft, 'bonsae_spec_draft': bonsae,
            'counts': {'recognized_components': count, 'returned_components': len(components)},
            'functional_ui_complete': False, 'release_authorized': False}
