"""Portable, non-destructive ALDOL UI anti-slop extension (v0.3.2 candidate).

This module does NOT overwrite the existing ui_core/anti_slop.py. It can be
called after v0.3.1 renderer output is generated. No extra Python dependency.
"""
from __future__ import annotations

from html.parser import HTMLParser
import re
from typing import Any

RAIL_ID = "decorative-accent-rail"
HEADLINE_ID = "sloganized-declarative-headline"

# Catch marketing-like poetic / self-congratulatory predicates only in headings.
# Normal declarative Korean in body text remains completely unaffected.
PROMO_ENDINGS = (
    "말한다", "이야기한다", "바꾼다", "깨운다", "혁신한다", "완성한다",
    "담는다", "열어준다", "열어간다", "이어준다", "연결한다", "시작된다",
    "만든다", "선사한다", "그린다", "이끈다", "디자인한다", "진화한다",
)
ABSTRACT = (
    "미래", "가능성", "경험", "새로운", "진정한", "본질", "마음", "세상",
    "디자인", "아이콘", "이야기", "기술", "공간", "순간", "일상", "변화",
    "혁신", "가치", "감성", "상태", "당신", "우리", "더 나은",
)


def _findings(headlines: list[tuple[str, str]], css: str, inline_styles: list[tuple[str, str]]) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for location, raw in headlines:
        s = re.sub(r"\s+", " ", raw).strip()
        if not s or len(s) < 7 or len(s) > 55:
            continue
        if re.search(r"\d|[%/:]|\b(?:v\d|Alpha|Beta|HTTP|CSS|HTML|API|JSON)\b", s, re.I):
            continue  # Concrete technical / measured heading: no guessing based on particles.
        if not re.search(r"[가-힣](?:은|는|이|가)\s+.{2,35}(?:다|이다)[.!?]?$", s):
            continue
        predicate = s.rstrip(".!? ")
        poetic = any(predicate.endswith(e) for e in PROMO_ENDINGS)
        abstract = any(word in s for word in ABSTRACT)
        generic_copula = predicate.endswith(('이다', '입니다')) and abstract
        if poetic and abstract or generic_copula:
            found.append({
                "rule": HEADLINE_ID, "severity": "high" if poetic else "medium",
                "path": location, "evidence": s,
                "problem": "짧고 추상적인 '~은/는 ~다' 선언형 슬로건이 기능 설명 대신 사용됨",
                "suggestion": "무엇을 확인하거나 할 수 있는지 구체적 작업명으로 제목을 작성 (예: '5개 아이콘 동작 테스트')",
            })

    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    rail_selectors: list[tuple[str, str]] = []
    # CSS after brace tokenizer is enough for a simple standalone CSS and nested @media
    # (not a CSS conformance parser; see documented scanner limits).
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", css):
        selector, props = m.group(1).strip(), m.group(2)
        # Don't match `border-left-color` and similar subproperties alone.
        if re.search(r"(?:^|;)\s*(?:border-left|border-inline-start)\s*:\s*[^;]*\bsolid\b", props, re.I):
            rail_selectors.append((selector.split('}')[-1].strip(), re.search(r"(?:border-left|border-inline-start)\s*:\s*([^;]+)", props, re.I).group(1).strip()))
    for location, style in inline_styles:
        if re.search(r"(?:^|;)\s*(?:border-left|border-inline-start)\s*:\s*[^;]*\bsolid\b", style, re.I):
            rail_selectors.append((location, style[:130]))
    # Return one review finding per visual selector; two+ on same page is a repeated motif.
    for selector, evidence in rail_selectors:
        found.append({
            "rule": RAIL_ID,
            "severity": "high" if len(rail_selectors) >= 2 else "medium",
            "path": f"css:{selector}" if not selector.startswith('html:') else selector,
            "evidence": f"{selector}: {evidence}",
            "problem": "카드/알림 옆 세로 강조선은 반복될 때 템플릿 장식으로 보이기 쉬움",
            "suggestion": "강조선을 제거하고 내용, 아이콘, 시맨틱 상태, 간결한 레이블로 구분. 단계 표시 등 의미가 있으면 근거 있는 예외 등록",
        })
    return found


class _Markup(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tags: list[str] = []
        self.heading: tuple[str, list[str]] | None = None
        self.headings: list[tuple[str, str]] = []
        self.css: list[str] = []
        self.inlines: list[tuple[str, str]] = []
        self.style_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append(tag)
        attrib = dict(attrs)
        if tag == 'style':
            self.style_depth += 1
        if tag in ('h1', 'h2', 'h3'):
            self.heading = (f"html:{tag}#{attrib.get('id', '')}".rstrip('#'), [])
        if attrib.get('style'):
            self.inlines.append((f"html:{tag}#{attrib.get('id', '')}".rstrip('#'), attrib['style']))

    def handle_endtag(self, tag: str) -> None:
        if tag == 'style' and self.style_depth:
            self.style_depth -= 1
        if tag in ('h1', 'h2', 'h3') and self.heading:
            self.headings.append((self.heading[0], ''.join(self.heading[1])))
            self.heading = None
        if tag in self.tags:
            idx = len(self.tags) - 1 - self.tags[::-1].index(tag)
            self.tags = self.tags[:idx]

    def handle_data(self, data: str) -> None:
        if self.style_depth:
            self.css.append(data)
        elif self.heading is not None:
            self.heading[1].append(data)


def apply_exceptions(findings: list[dict[str, Any]], exceptions: list[dict[str, str]] | None = None) -> dict[str, Any]:
    exceptions = exceptions or []
    allowed = {x.get('rule'): x.get('reason', '').strip() for x in exceptions if isinstance(x, dict) and len(x.get('reason', '').strip()) >= 10}
    waived, active = [], []
    for f in findings:
        if f['rule'] in allowed:
            waived.append({**f, 'reason': allowed[f['rule']]})
        else:
            active.append(f)
    high = sum(f['severity'] == 'high' for f in active)
    return {'status': 'blocked' if high else 'clear' if not active else 'warning',
            'findings': active, 'waived': waived, 'high_severity_count': high,
            'reviewed_rules': [HEADLINE_ID, RAIL_ID]}


def scan_html(html: str, exceptions: list[dict[str, str]] | None = None) -> dict[str, Any]:
    parser = _Markup()
    parser.feed(html)
    return apply_exceptions(_findings(parser.headings, '\n'.join(parser.css), parser.inlines), exceptions)


def scan_document(document: dict[str, Any]) -> dict[str, Any]:
    """Analyze 0.3/0.3.1 style JSON `root` text headings.

    Decorative CSS rails must be checked on rendered HTML using scan_html().
    This does not claim to know existing renderer internals.
    """
    titles: list[tuple[str,str]] = []
    def walk(node: Any, path: str) -> None:
        if isinstance(node, dict):
            if node.get('type') == 'text' and node.get('variant') in ('heading', 'title'):
                titles.append((path + '.text', str(node.get('text', ''))))
            for k, val in node.items():
                if isinstance(val, (dict,list)):
                    walk(val, path + '.' + str(k))
        elif isinstance(node, list):
            for i, val in enumerate(node):
                walk(val, path + f'[{i}]')
    walk(document.get('root', {}), 'root')
    design = document.get('design', {})
    return apply_exceptions(_findings(titles, '', []), design.get('exceptions', []) if isinstance(design, dict) else None)
