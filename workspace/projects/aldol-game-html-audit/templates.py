"""Curated safe read-only starter tools. No network or shell execution."""
import json
import re
from html.parser import HTMLParser
from mcp_runtime import Tool, str_schema

TEMPLATE_INFO = {
    'html_audit': 'HTML의 기본 문서 구조, 모바일 viewport, 이미지 대체 텍스트를 정적 검사',
    'json_audit': 'JSON 구문, 최상위 구조, 키 수 검사',
    'text_stats': '텍스트 길이, 단어 수, 줄 수 계산',
}


class HTMLAuditParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tags = {}
        self.title = False
        self.viewport = False
        self.images_without_alt = 0
        self.canvas_count = 0
        self.insecure_urls = 0
        self.lang = False
        self.duplicate_id = set()
        self.ids = set()

    def handle_starttag(self, tag, attrs):
        self.tags[tag] = self.tags.get(tag, 0) + 1
        attr = dict(attrs)
        if tag == 'html':
            self.lang = bool(attr.get('lang'))
        if tag == 'title':
            self.title = True
        if tag == 'meta' and (attr.get('name') or '').lower() == 'viewport':
            self.viewport = True
        if tag == 'img' and not (attr.get('alt') is not None):
            self.images_without_alt += 1
        if tag == 'canvas':
            self.canvas_count += 1
        if 'id' in attr:
            if attr['id'] in self.ids:
                self.duplicate_id.add(attr['id'])
            self.ids.add(attr['id'])
        for k in ('src', 'href'):
            if (attr.get(k) or '').lower().startswith('http://'):
                self.insecure_urls += 1


def html_audit(arguments):
    source = arguments['content']
    if len(source) > 220_000:
        raise ValueError('HTML input exceeds limit')
    p = HTMLAuditParser()
    p.feed(source)
    issues = []
    def issue(severity, code, message):
        issues.append({'severity': severity, 'code': code, 'message': message})
    if not p.tags.get('html'):
        issue('warning', 'missing-html', 'html element not detected')
    if not p.tags.get('head'):
        issue('warning', 'missing-head', 'head element not detected')
    if not p.tags.get('body'):
        issue('warning', 'missing-body', 'body element not detected')
    if not p.title:
        issue('warning', 'missing-title', 'title element not detected')
    if not p.viewport:
        issue('warning', 'missing-viewport', 'mobile viewport meta element not detected')
    if not p.lang:
        issue('info', 'missing-lang', 'html lang attribute not detected')
    if p.images_without_alt:
        issue('warning', 'missing-alt', f'{p.images_without_alt} image(s) without alt attribute')
    if p.insecure_urls:
        issue('warning', 'http-resource', f'{p.insecure_urls} HTTP asset link(s) detected')
    if p.duplicate_id:
        issue('warning', 'duplicate-id', f'{len(p.duplicate_id)} duplicate HTML id value(s) detected')
    return {
        'type': 'static_html_audit',
        'checks': {'canvas_count': p.canvas_count, 'image_alt_missing': p.images_without_alt, 'viewport_declared': p.viewport},
        'issue_count': len(issues),
        'issues': issues,
        'limitations': 'Static syntax/markup heuristics only. No rendering, gameplay, JavaScript execution or device QA.',
    }


def json_audit(arguments):
    source = arguments['content']
    try:
        data = json.loads(source)
    except json.JSONDecodeError as e:
        return {'valid': False, 'error': e.msg, 'line': e.lineno, 'column': e.colno}
    typ = type(data).__name__
    if isinstance(data, dict):
        size = len(data)
    elif isinstance(data, list):
        size = len(data)
    else:
        size = None
    return {'valid': True, 'top_level_type': typ, 'top_level_items': size}


def text_stats(arguments):
    content = arguments['content']
    return {'characters': len(content), 'words': len(re.findall(r'\S+', content)), 'lines': len(content.splitlines())}


def get_tool(template):
    mapping = {'html_audit': html_audit, 'json_audit': json_audit, 'text_stats': text_stats}
    if template not in TEMPLATE_INFO:
        raise ValueError('Unsupported template: ' + str(template))
    return Tool(template, TEMPLATE_INFO[template], str_schema('content'), mapping[template], read_only=True)


def select_template(description):
    desc = description.casefold()
    if any(word in desc for word in ('html', '웹게임', '웹 게임', 'web game', 'webpage', '웹페이지')):
        return 'html_audit'
    if any(word in desc for word in ('json', '제이슨')):
        return 'json_audit'
    if any(word in desc for word in ('텍스트', '문장', '단어', 'text', 'word', '글자')):
        return 'text_stats'
    return None  # Do not silently implement an unrelated user request.
