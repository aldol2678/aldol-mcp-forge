"""Transparent, contextual anti-AI-slop heuristics, not an aesthetic classifier.

No model calls, network access, automatic content rewriting, or arbitrary scoring.
Findings are advisory unless caller explicitly opts into enforcement. A game
can intentionally be playful; explicit, reasoned exceptions remain auditable.
"""
from __future__ import annotations

from collections import Counter
import re
from typing import Any
from . import anti_slop_ext

RULES = {
    "generic-headline": "의미 없는 홍보성 문구보다 화면의 실제 목적을 제목으로 표시하세요.",
    "ornamental-glyph": "장식용 특수문자 대신 의미 있는 텍스트나 일관된 아이콘 자산을 사용하세요.",
    "repeated-metric-cards": "동일한 카드 반복을 줄이고 데이터의 우선순위에 맞게 표·행·요약 구조를 선택하세요.",
    "badge-overuse": "상태 변화나 경고가 아닌 정보는 배지 대신 일반 텍스트로 나타내세요.",
    "no-data-provenance": "데모 수치와 외부 데이터 연동을 구분해 명시하세요.",
    "unclear-button": "버튼에 수행할 구체적인 동작을 적으세요.",
    "inactive-button": "동작 없는 버튼을 만들지 말고 명시적으로 비활성 상태를 구현하세요.",
    "primary-action-overload": "강조 버튼은 주요 행동에 집중하세요.",
    "excessive-nesting": "중첩된 패널과 카드를 줄이고 정보의 구조를 단순화하세요.",
    "missing-brand-direction": "프로젝트 고유의 디자인 방향을 짧게 명시하세요.",
    "decorative-accent-rail": "근거 없는 왼쪽 세로 강조선을 반복하지 말고 정보 구조와 상태 표기로 구분하세요.",
    "sloganized-declarative-headline": "추상적인 선언형 슬로건 대신 화면에서 할 수 있는 구체적인 작업을 제목에 적으세요.",
}
_HEADLINE = re.compile(r"(한곳에서\s*모든|새로운\s*경험|혁신적인\s*경험|당신을\s*위한\s*완벽|한\s*차원\s*높은|seamless experience|unlock (the )?power|next.level experience)", re.I)
_GLYPH = re.compile(r"^[\s✦✧✨⭐◆◈●⚔🚀🔥💎🎯]+")
_VAGUE = {"시작하기", "자세히", "더 보기", "더 알아보기", "확인", "클릭", "계속", "go", "learn more", "get started"}


def review(spec: dict[str, Any]) -> dict[str, Any]:
    design = spec.get("design", {})
    context = design.get("context", "game" if spec.get("preset") == "forest" else "product")
    exceptions = {e["rule"]: e["reason"] for e in design.get("exceptions", [])}
    findings, waived = [], []
    counts: Counter[str] = Counter()
    panels_nested = []
    metric_cards = []
    primary_buttons = []
    def flag(rule: str, path: str, evidence: str, severity: str = "medium") -> None:
        finding = {"rule":rule, "severity":severity, "path":path, "evidence":evidence[:160], "suggestion":RULES[rule]}
        if rule in exceptions:
            waived.append({**finding, "waiver_reason": exceptions[rule]})
        else:
            findings.append(finding)
    def walk(n: dict[str, Any], path: str, nested: int = 0) -> None:
        kind = n["type"]
        counts[kind] += 1
        if kind in ("panel", "card"):
            nested += 1
            if nested >= 3:
                panels_nested.append(path)
        if kind == "card":
            children = n.get("children", [])
            if len(children) <= 2 and sum(child["type"] == "metric" for child in children) == 1:
                metric_cards.append(path)
        if kind == "button":
            if "action" not in n:
                flag("inactive-button", path, n["label"], "high")
            if n["label"].strip().lower() in _VAGUE:
                flag("unclear-button", path, n["label"])
            if n.get("variant", "primary") == "primary":
                primary_buttons.append(path)
        if kind in ("button", "badge", "text"):
            value = n.get("label") if kind == "button" else n.get("text", "")
            if kind == "text" and n.get("variant") == "heading" and _HEADLINE.search(value):
                flag("generic-headline", path, value, "high")
            if _GLYPH.match(value) and (kind != "text" or n.get("variant") in ("heading", "eyebrow")):
                flag("ornamental-glyph", path, value)
        for index, child in enumerate(n.get("children", [])):
            walk(child, f"{path}.children[{index}]", nested)
    walk(spec["root"], "root")
    if len(metric_cards) >= 4:
        flag("repeated-metric-cards", "root", f"유사한 지표 카드 {len(metric_cards)}개")
    if counts["badge"] >= 4:
        flag("badge-overuse", "root", f"배지 {counts['badge']}개")
    if len(primary_buttons) >= 3:
        flag("primary-action-overload", "root", f"강조 버튼 {len(primary_buttons)}개")
    if panels_nested:
        flag("excessive-nesting", panels_nested[0], f"3단계 이상 패널/카드 중첩 {len(panels_nested)}곳")
    if (counts["metric"] or counts["progress"]) and "data_mode" not in spec:
        flag("no-data-provenance", "root", "숫자 데이터의 출처 구분 없음", "high")
    if design and not design.get("brand_note"):
        flag("missing-brand-direction", "design.brand_note", "고유한 브랜드 방향이 지정되지 않음")
    # Alpha 0.3.2: evaluate additional declarative headline heuristics on the
    # original JSON AST; rendered CSS/HTML can be scanned with ui_review_markup.
    extension = anti_slop_ext.scan_document(spec)
    findings.extend(extension["findings"])
    for item in extension["waived"]:
        waived.append({**{k: v for k, v in item.items() if k != "reason"}, "waiver_reason": item.get("reason", "")})
    return {
        "status": "review" if findings else "clear",
        "context": context,
        "findings": findings,
        "waived": waived,
        "counts": dict(sorted(counts.items())),
        "high_severity_count": sum(f["severity"] == "high" for f in findings),
        "human_review_required": True,
        "note": "정적 패턴 점검만 수행. 디자인 완성도, 브랜드 적합성, 접근성 인증이 아닙니다.",
    }
