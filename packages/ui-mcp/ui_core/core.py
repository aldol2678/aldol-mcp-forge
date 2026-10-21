"""ALDOL UI Core 0.3: safe declarative UI for web pages and browser-game HUDs.

No user-provided HTML/CSS/JS is executed. Buttons can declare deterministic
show/hide actions or send CustomEvents to a game/web host. Preview's forest
battlefield is illustrative only: the host supplies a real game scene.
"""
from __future__ import annotations

from html import escape
import json
import math
import re
from typing import Any
from . import anti_slop, anti_slop_ext

COMPONENTS: dict[str, dict[str, Any]] = {
    "stack": {"required": ["children"], "optional": []},
    "row": {"required": ["children"], "optional": []},
    "panel": {"required": ["children"], "optional": ["label", "id", "hidden"]},
    "text": {"required": ["text"], "optional": ["variant", "bind"]},
    "button": {"required": ["label"], "optional": ["action", "variant"]},
    "badge": {"required": ["text"], "optional": ["tone", "bind"]},
    "progress": {"required": ["label", "value", "max"], "optional": ["bind"]},
    "card": {"required": ["children"], "optional": ["label"]},
    "grid": {"required": ["children"], "optional": ["columns"]},
    "metric": {"required": ["label", "value"], "optional": ["tone", "bind"]},
    "notice": {"required": ["text"], "optional": ["tone"]},
    "divider": {"required": [], "optional": []},
}
THEME_DEFAULTS = {"primary": "#E9B35E", "background": "#172638", "foreground": "#F7F9FF"}
PRESETS = {
    "forest": {"primary": "#E9B35E", "background": "#172638", "foreground": "#F7F9FF"},
    "studio": {"primary": "#98B7FF", "background": "#131D32", "foreground": "#F7F9FF"},
    "slate": {"primary": "#83D2BC", "background": "#21333A", "foreground": "#F3F9F7"},
}
FONTS = {"system": 'system-ui,-apple-system,"Noto Sans KR",sans-serif',
         "rounded": '"Arial Rounded MT Bold",system-ui,"Noto Sans KR",sans-serif',
         "mono": 'ui-monospace,monospace'}
DENSITIES = {"cozy": ("12px", "24px"), "compact": ("8px", "16px")}
RADII = {"soft": "12px", "sharp": "8px"}
ALLOWED_TARGETS = ("web-html", "game-hud-html", "react-tsx")
MAX_NODES, MAX_DEPTH, MAX_SOURCE_LENGTH = 120, 10, 30000
COLOR = re.compile(r"#[0-9a-fA-F]{6}\Z")
ID = re.compile(r"[a-z][a-z0-9-]{0,39}\Z")
EVENT = re.compile(r"[a-z][a-z0-9:_-]{0,59}\Z")


def catalog() -> dict[str, Any]:
    return {
        "schema_version": "0.3", "quality_patch": "0.3.2", "accepts_versions": ["0.1", "0.2", "0.3"],
        "targets": list(ALLOWED_TARGETS), "components": COMPONENTS,
        "anti_slop": {"tool":"ui_review", "quality_modes":["advisory","enforce"], "rules": list(anti_slop.RULES), "not_a_design_score": True, "markup_tool": "ui_review_markup"},
        "theme_keys": sorted(THEME_DEFAULTS),
        "presets": PRESETS, "fonts": list(FONTS),
        "densities": list(DENSITIES), "radii": list(RADII),
        "bindings": "bind slugs on text/badge/metric/progress; host uses ALDOLUI.setState",
        "actions": {"toggle": {"target": "existing panel id"},
                    "emit": {"name": "custom event name"}},
        "limits": {"max_nodes": MAX_NODES, "max_depth": MAX_DEPTH,
                   "max_spec_characters": MAX_SOURCE_LENGTH},
        "limitations": ["HTML DOM overlay only; no engine scene generation",
                        "only toggle works standalone; emit requires host handler",
                        "React TSX code-only export; no bundled React runtime",
                        "no native/engine render adapters", "not an MCP Apps UI resource"],
    }


def _parse(source: str) -> dict[str, Any]:
    if not isinstance(source, str) or len(source) > MAX_SOURCE_LENGTH:
        raise ValueError("spec_json must be a string of at most 30000 characters")
    try:
        spec = json.loads(source, parse_constant=lambda x: (_ for _ in ()).throw(ValueError("nonfinite number")))
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"invalid JSON: {exc}") from exc
    if not isinstance(spec, dict):
        raise ValueError("root document must be an object")
    if set(spec) - {"version", "title", "theme", "root", "preset", "tokens", "design", "data_mode"}:
        raise ValueError("unknown document properties")
    if spec.get("version") not in ("0.1", "0.2", "0.3"):
        raise ValueError("version must be 0.1, 0.2 or 0.3")
    if not isinstance(spec.get("title"), str) or not 1 <= len(spec["title"]) <= 100:
        raise ValueError("title must be 1..100 characters")
    if spec["version"] != "0.3" and ("preset" in spec or "tokens" in spec):
        raise ValueError("presets and tokens require version 0.3")
    if not isinstance(spec.get("preset", "forest"), str) or spec.get("preset", "forest") not in PRESETS:
        raise ValueError("invalid theme preset")
    tokens = spec.get("tokens", {})
    if not isinstance(tokens, dict) or set(tokens) - {"font", "density", "radius"}:
        raise ValueError("invalid design tokens")
    for key, allowed in (("font", FONTS), ("density", DENSITIES), ("radius", RADII)):
        if key in tokens and (not isinstance(tokens[key], str) or tokens[key] not in allowed):
            raise ValueError(f"invalid tokens.{key}")
    theme = spec.get("theme", {})
    if not isinstance(theme, dict) or set(theme) - set(THEME_DEFAULTS):
        raise ValueError("invalid theme properties")
    for k, v in theme.items():
        if not isinstance(v, str) or not COLOR.fullmatch(v):
            raise ValueError(f"theme.{k} must be a six-digit hex color")
    if "design" in spec or "data_mode" in spec:
        if spec["version"] != "0.3":
            raise ValueError("design and data_mode require version 0.3")
    if "data_mode" in spec and spec["data_mode"] not in ("demo", "external"):
        raise ValueError("data_mode must be demo or external")
    if "design" in spec:
        design = spec["design"]
        if not isinstance(design, dict) or set(design) - {"context", "brand_note", "exceptions"}:
            raise ValueError("invalid design contract")
        if design.get("context", "product") not in ("product", "editorial", "game"):
            raise ValueError("design.context must be product, editorial, or game")
        if "brand_note" in design and (not isinstance(design["brand_note"], str) or not 8 <= len(design["brand_note"]) <= 200):
            raise ValueError("design.brand_note must be 8..200 characters")
        exceptions = design.get("exceptions", [])
        if not isinstance(exceptions, list) or len(exceptions) > 6:
            raise ValueError("design.exceptions must be a list of at most 6 entries")
        seen = set()
        for entry in exceptions:
            if not isinstance(entry, dict) or set(entry) != {"rule", "reason"} or entry.get("rule") not in anti_slop.RULES or entry["rule"] in seen or not isinstance(entry.get("reason"), str) or not 12 <= len(entry["reason"]) <= 160:
                raise ValueError("design exception requires unique known rule and 12..160-character reason")
            seen.add(entry["rule"])
    counter = [0]
    ids: set[str] = set()
    toggle_targets: list[str] = []

    def node(value: Any, depth: int) -> None:
        if depth > MAX_DEPTH:
            raise ValueError("tree depth limit exceeded")
        if not isinstance(value, dict) or not isinstance(value.get("type"), str) or value.get("type") not in COMPONENTS:
            raise ValueError("invalid component node type")
        kind = value["type"]
        if spec["version"] != "0.3" and kind in ("card", "grid", "metric", "notice", "divider"):
            raise ValueError("new components require version 0.3")
        meta = COMPONENTS[kind]
        if set(value) - {"type", *meta["required"], *meta["optional"]} or set(meta["required"]) - set(value):
            raise ValueError(f"invalid or missing properties for {kind}")
        counter[0] += 1
        if counter[0] > MAX_NODES:
            raise ValueError("node count limit exceeded")
        for field in ("label", "text"):
            if field in value and (not isinstance(value[field], str) or
                                    not 1 <= len(value[field]) <= 250):
                raise ValueError(f"{kind}.{field} must be 1..250 characters")
        if "children" in value:
            children = value["children"]
            if not isinstance(children, list) or not 1 <= len(children) <= MAX_NODES:
                raise ValueError("children must be a nonempty list")
            for child in children:
                node(child, depth + 1)
        if "bind" in value:
            if spec["version"] != "0.3":
                raise ValueError("data bindings require version 0.3")
            binding = value["bind"]
            if not isinstance(binding, str) or not ID.fullmatch(binding):
                raise ValueError("bind must be lowercase slug")
        if kind == "grid":
            if isinstance(value.get("columns", 2), bool) or value.get("columns", 2) not in (2, 3, 4):
                raise ValueError("grid columns must be 2, 3 or 4")
        if kind == "metric":
            if isinstance(value["value"], bool) or not isinstance(value["value"], (str, int, float)) or (
                isinstance(value["value"], float) and not math.isfinite(value["value"])) or not 1 <= len(str(value["value"])) <= 50:
                raise ValueError("metric.value must be short text or finite number")
        if kind == "progress":
            v, mx = value["value"], value["max"]
            if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x)
                   for x in (v, mx)) or mx <= 0 or not 0 <= v <= mx:
                raise ValueError("progress requires finite 0 <= value <= max, max > 0")
        if kind == "panel":
            if "hidden" in value and not isinstance(value["hidden"], bool):
                raise ValueError("panel.hidden must be boolean")
            if "id" in value:
                n_id = value["id"]
                if not isinstance(n_id, str) or not ID.fullmatch(n_id) or n_id in ids:
                    raise ValueError("panel.id must be unique lowercase slug")
                ids.add(n_id)
        if kind == "button":
            if value.get("variant", "primary") not in ("primary", "secondary", "subtle"):
                raise ValueError("button.variant must be primary, secondary or subtle")
            if "action" in value:
                action = value["action"]
                if not isinstance(action, dict) or action.get("type") not in ("toggle", "emit"):
                    raise ValueError("button.action requires supported type")
                if action["type"] == "toggle":
                    if set(action) != {"type", "target"} or not isinstance(action.get("target"), str) or not ID.fullmatch(action["target"]):
                        raise ValueError("toggle action requires valid target id")
                    toggle_targets.append(action["target"])
                elif set(action) != {"type", "name"} or not isinstance(action.get("name"), str) or not EVENT.fullmatch(action["name"]):
                    raise ValueError("emit action requires valid event name")
        if kind in ("badge", "metric", "notice") and value.get("tone", "neutral") not in ("neutral", "success", "warning", "danger"):
            raise ValueError("badge.tone must be neutral, success, warning, danger")
        if kind == "text" and value.get("variant", "normal") not in ("normal", "muted", "heading", "eyebrow"):
            raise ValueError("text.variant must be normal, muted, heading, eyebrow")

    node(spec.get("root"), 0)
    for target in toggle_targets:
        if target not in ids:
            raise ValueError(f"toggle action target not found: {target}")
    return spec


def validate(spec_json: str) -> dict[str, Any]:
    try:
        spec = _parse(spec_json)
        return {"valid": True, "schema_version": spec["version"], "title": spec["title"]}
    except ValueError as exc:
        return {"valid": False, "errors": [str(exc)]}


def _luminance(hexcolor: str) -> float:
    values = [int(hexcolor[i:i+2], 16) / 255 for i in (1, 3, 5)]
    channels = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in values]
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def _contrast(a: str, b: str) -> float:
    hi, lo = sorted((_luminance(a), _luminance(b)), reverse=True)
    return round((hi + 0.05) / (lo + 0.05), 2)


def review(spec_json: str) -> dict[str, Any]:
    """Explainable, contextual anti-slop findings; no arbitrary aesthetics score."""
    return anti_slop.review(_parse(spec_json))


def review_markup(html_source: str, exceptions_json: str = "[]") -> dict[str, Any]:
    """Review standalone HTML/CSS, including decorative rails in generated UI.

    No JavaScript execution or network access. HTML parsing is heuristic and
    does not include linked stylesheets. Does not modify the source document.
    """
    if not isinstance(html_source, str) or len(html_source) > 120_000:
        raise ValueError("html_source must be a string at most 120000 characters")
    if not isinstance(exceptions_json, str) or len(exceptions_json) > 6000:
        raise ValueError("exceptions_json must be a JSON string at most 6000 characters")
    try:
        exceptions = json.loads(exceptions_json)
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError("invalid exceptions_json") from exc
    if not isinstance(exceptions, list) or len(exceptions) > 6:
        raise ValueError("exceptions must be a list of at most 6 entries")
    seen = set()
    for entry in exceptions:
        if (not isinstance(entry, dict) or set(entry) != {"rule", "reason"}
                or entry.get("rule") not in anti_slop.RULES or entry["rule"] in seen
                or not isinstance(entry.get("reason"), str)
                or not 12 <= len(entry["reason"]) <= 160):
            raise ValueError("markup exception requires unique known rule and 12..160-character reason")
        seen.add(entry["rule"])
    report = anti_slop_ext.scan_html(html_source, exceptions)
    return {
        "status": "review" if report["findings"] else "clear",
        "context": "markup",
        "findings": report["findings"],
        "waived": [{**{k:v for k,v in f.items() if k != "reason"},
                    "waiver_reason": f.get("reason", "")} for f in report["waived"]],
        "high_severity_count": report["high_severity_count"],
        "human_review_required": True,
        "note": "정적 HTML 및 내장 CSS 휴리스틱. 외부 CSS·렌더링 결과는 분석하지 않습니다.",
    }


def audit(spec_json: str) -> dict[str, Any]:
    spec = _parse(spec_json)
    theme = {**PRESETS[spec.get("preset", "forest")], **spec.get("theme", {})}
    ratio = _contrast(theme["foreground"], theme["background"])
    primary_text = max(("#000000", "#FFFFFF"), key=lambda c: _contrast(c, theme["primary"]))
    primary_ratio = _contrast(primary_text, theme["primary"])
    warnings = []
    if ratio < 4.5:
        warnings.append("foreground/background contrast below WCAG AA normal-text 4.5:1")
    buttons, toggles, emits, inactive = 0, 0, 0, 0
    def walk(n: dict[str, Any]) -> None:
        nonlocal buttons, toggles, emits, inactive
        if n["type"] == "button":
            buttons += 1
            if "action" not in n: inactive += 1
            elif n["action"]["type"] == "toggle": toggles += 1
            else: emits += 1
        for child in n.get("children", []):
            walk(child)
    walk(spec["root"])
    if inactive: warnings.append(f"{inactive} buttons are static: bind actions in the host application")
    if emits: warnings.append(f"{emits} emit actions require a host event listener; demo only shows feedback")
    return {"valid": True, "contrast_ratio": ratio, "primary_button_contrast_ratio": primary_ratio, "button_count": buttons,
            "toggle_count": toggles, "emit_count": emits, "warnings": warnings,
            "anti_slop": anti_slop.review(spec),
            "note": "preflight checks only; screenshot/browser accessibility testing is still required"}


# Host runtime is library-controlled. The UI spec cannot inject executable code.
RUNTIME_JS = r'''(() => {
  const roots = document.querySelectorAll('.alui-app, .alui-hud-overlay');
  const normalize = (value) => typeof value === 'string' || typeof value === 'number' ? String(value) : null;
  function setState(root, updates) {
    if (typeof root === 'string') root = document.querySelector(root);
    if (!root || typeof updates !== 'object' || updates === null || Array.isArray(updates)) return 0;
    let updated = 0;
    root.querySelectorAll('[data-alui-bind]').forEach(el => {
      const key = el.getAttribute('data-alui-bind');
      if (!Object.prototype.hasOwnProperty.call(updates, key)) return;
      const val = updates[key];
      if (el.getAttribute('role') === 'progressbar') {
        if (typeof val !== 'number' || !Number.isFinite(val)) return;
        const mx = Number(el.getAttribute('aria-valuemax'));
        if (!Number.isFinite(mx) || mx <= 0) return;
        const clamped = Math.max(0, Math.min(mx, val));
        el.setAttribute('aria-valuenow', String(clamped));
        const fill = el.querySelector('.alui-progress-fill');
        if (fill) fill.style.width = ((clamped / mx) * 100).toFixed(2) + '%';
      } else {
        const text = normalize(val);
        if (text === null || text.length > 250) return;
        const target = el.querySelector('[data-alui-bind-text]') || el;
        target.textContent = text;
      }
      updated += 1;
    });
    return updated;
  }
  roots.forEach(root => {
    if (root.dataset.aluiBound) return;
    root.dataset.aluiBound = 'true';
    root.addEventListener('click', event => {
      const btn = event.target.closest('button[data-alui-action]');
      if (!btn || !root.contains(btn)) return;
      const kind = btn.dataset.aluiAction;
      const value = btn.dataset.aluiValue;
      if (kind === 'toggle') {
        const panel = root.querySelector('[data-alui-id="' + value + '"]');
        if (!panel) return;
        panel.hidden = !panel.hidden;
        btn.setAttribute('aria-expanded', String(!panel.hidden));
        if (!panel.hidden) {
          root.querySelectorAll('[data-alui-id]').forEach(other => {
            if (other !== panel && other.dataset.aluiDisclosure === 'true') other.hidden = true;
          });
          root.querySelectorAll('button[data-alui-action="toggle"]').forEach(other => {
            if (other !== btn) other.setAttribute('aria-expanded', 'false');
          });
        }
      }
      root.dispatchEvent(new CustomEvent('alui:action', { bubbles: true,
        detail: { type: kind, name: value, sourceLabel: btn.textContent.trim() } }));
    });
    root.addEventListener('keydown', event => {
      if (event.key !== 'Escape') return;
      root.querySelectorAll('[data-alui-disclosure="true"]').forEach(panel => panel.hidden = true);
      root.querySelectorAll('button[data-alui-action="toggle"]').forEach(btn => btn.setAttribute('aria-expanded', 'false'));
    });
  });
  window.ALDOLUI = Object.freeze({setState});
})();'''


def _demo_stage() -> str:
    # Decorative mock battlefield only. Do not confuse with an actual game canvas.
    return '''<div class="alui-demo-stage" aria-label="전장 장식 미리보기 (게임 플레이 아님)">
      <div class="alui-demo-sun"></div><div class="alui-demo-hills"></div>
      <div class="alui-demo-ground"></div>
      <div class="alui-demo-scene-label">FOREST PATH <span>02 / 05</span></div>
      <div class="alui-demo-team" aria-hidden="true"><div class="alui-demo-unit"><span>🛡️</span><small>방패병</small></div><div class="alui-demo-unit"><span>🏹</span><small>궁수</small></div><div class="alui-demo-unit"><span>🧙</span><small>마법사</small></div></div>
      <div class="alui-demo-versus" aria-hidden="true">⚔</div>
      <div class="alui-demo-foes" aria-hidden="true"><div class="alui-demo-unit foe"><span>🐺</span><small>늑대</small></div><div class="alui-demo-unit foe"><span>👹</span><small>정예</small></div></div>
      <div class="alui-demo-watermark" aria-hidden="true">ILLUSTRATIVE BATTLEFIELD · UI TEST</div>
    </div>'''


def _css(container: str, theme: dict[str,str], button_text: str, game: bool, tokens: dict[str,str] | None = None, design: dict[str,Any] | None = None) -> str:
    tokens = tokens or {}
    design = design or {}
    font = FONTS[tokens.get("font", "system")]
    density = tokens.get("density", "cozy")
    radius = RADII[tokens.get("radius", "soft")]
    palette = (";".join(f"--alui-{k}:{v}" for k, v in theme.items()) +
               f";--alui-button-text:{button_text};--alui-radius:{radius};" +
               f"--alui-font:{font};--alui-spacing:{DENSITIES[density][0]};--alui-context:{design.get('context','product')}")
    # Keep CSS scoped to the root class so generated fragments can coexist with hosts.
    root = ".alui-hud-overlay" if game else ".alui-app"
    css = f'''
{root}{{{palette};color:var(--alui-foreground);font-family:var(--alui-font);
 box-sizing:border-box;width:100%;max-width:{'none' if game else '1100px'};padding:clamp(12px,3vw,24px);}}
{root}, {root} *{{box-sizing:border-box}}
{root} [hidden]{{display:none!important}}
{root} .alui-stack{{display:flex;flex-direction:column;gap:var(--alui-spacing)}}
{root} .alui-row{{display:flex;flex-flow:row wrap;align-items:center;gap:10px 12px}}
{root} .alui-panel{{min-width:0;padding:clamp(16px,3.5vw,24px);border-radius:var(--alui-radius);
 background:color-mix(in srgb,var(--alui-background) 95%,#fff 5%);border:1px solid #ffffff20;
 box-shadow:none}}
{root} .alui-text{{margin:0;line-height:1.5;overflow-wrap:break-word;letter-spacing:-.02em}}
{root} .alui-text--heading{{font-weight:750;font-size:clamp(20px,3vw,28px);letter-spacing:-.03em}}
{root} .alui-text--muted{{color:#c5d0d9;font-size:14px}}
{root} .alui-text--eyebrow{{color:color-mix(in srgb,var(--alui-foreground) 76%,transparent);letter-spacing:.06em;font-size:12px;font-weight:700}}
{root} .alui-badge{{display:inline-flex;align-items:center;gap:7px;min-height:26px;padding:4px 12px;
 border-radius:5px;background:#ffffff12;color:#f2f6fb;font-size:12px;font-weight:700;white-space:nowrap}}
{root} .alui-badge--success{{background:#3ebd8650;color:#abf5d2}}
{root} .alui-badge--warning{{background:#e9b35e2e;color:#ffe1a1}}
{root} .alui-badge--danger{{background:#f47d7740;color:#ffb8b2}}
{root} .alui-button{{appearance:none;display:inline-flex;justify-content:center;align-items:center;
 border:1px solid transparent;background:var(--alui-primary);color:var(--alui-button-text);
 border-radius:8px;min-height:48px;min-width:48px;padding:12px 20px;font:inherit;font-size:15px;
 font-weight:750;line-height:1.2;white-space:normal;text-align:center;cursor:pointer;
 touch-action:manipulation;transition:transform .16s ease,background-color .16s ease}}
{root} .alui-button--secondary{{background:#ffffff20;color:var(--alui-foreground);border-color:#ffffff2b}}
{root} .alui-button--subtle{{background:transparent;color:var(--alui-foreground);border-color:#ffffff44}}
{root} .alui-button:active{{transform:scale(.975)}}
{root} .alui-button:focus-visible{{outline:3px solid #fff;outline-offset:3px}}
{root} .alui-grid{{display:grid;grid-template-columns:repeat(var(--alui-cols,2),minmax(0,1fr));gap:var(--alui-spacing)}}
{root} .alui-card{{padding:18px;border:1px solid #ffffff21;border-radius:var(--alui-radius);
 background:color-mix(in srgb,var(--alui-background) 91%,#ffffff 9%);min-width:0}}
{root} .alui-metric{{min-width:0;display:flex;flex-direction:column;gap:7px}}
{root} .alui-metric-label{{font-size:12px;color:color-mix(in srgb,var(--alui-foreground) 72%, transparent);font-weight:650}}
{root} .alui-metric-value{{font-size:clamp(21px,3vw,30px);font-weight:750;letter-spacing:-.035em;overflow-wrap:anywhere}}
{root} .alui-metric--success .alui-metric-value{{color:#9cf2c5}}
{root} .alui-metric--warning .alui-metric-value{{color:#ffe1a1}}
{root} .alui-metric--danger .alui-metric-value{{color:#ffc1bc}}
{root} .alui-divider{{height:1px;width:100%;background:#ffffff29;border:0;margin:2px 0}}
{root} .alui-notice{{padding:12px 14px;border-radius:6px;background:#ffffff0f;border:1px solid #ffffff32;
 font-size:13px;line-height:1.6;overflow-wrap:break-word}}
{root} .alui-notice--success{{border-color:#83d9b4}}
{root} .alui-notice--warning{{border-color:#e9b35e}}
{root} .alui-notice--danger{{border-color:#fa8f87}}
{root} .alui-progress{{width:100%;min-width:0;display:grid;gap:7px}}
{root} .alui-progress-track{{display:block;background:#ffffff26;border-radius:3px;height:9px;overflow:hidden}}
{root} .alui-progress-fill{{display:block;height:100%;border-radius:3px;background:var(--alui-primary);}}
@media(max-width:480px){{{root}{{padding:12px}}{root} .alui-grid{{grid-template-columns:repeat(2,minmax(0,1fr))}}{root} .alui-panel{{padding:16px;border-radius:12px}}
 {root} .alui-row--actions{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr))}}
 {root} .alui-row--actions .alui-button{{width:100%;min-width:0;padding:12px 8px;font-size:13px}}}}
@media(prefers-reduced-motion:reduce){{{root} *{{animation:none!important;transition:none!important;scroll-behavior:auto!important}}}}
'''
    if game:
        css += '''
.alui-hud-overlay{position:absolute;inset:0;z-index:10;pointer-events:none;display:flex;flex-direction:column;
 max-height:100%;overflow-x:hidden;overflow-y:auto;scrollbar-width:thin}
.alui-hud-overlay>.alui-stack{flex:1;min-height:100%;justify-content:space-between;align-items:stretch}
.alui-hud-overlay>.alui-stack>.alui-panel{max-width:560px;width:100%;margin-inline:auto;
 pointer-events:auto}
.alui-hud-overlay>.alui-stack>.alui-panel:first-child{background:#142437f5}
.alui-hud-overlay>.alui-stack>.alui-panel:last-child{background:#142437f7}
@media(max-width:480px){.alui-hud-overlay>.alui-stack>.alui-panel{margin-inline:0}
.alui-hud-overlay>.alui-stack{gap:20px}}
'''
    else:
        css += '''
.alui-app{background:var(--alui-background);border-radius:12px;min-height:320px;
 border:1px solid #ffffff18;margin-block:12px}
@media(max-width:600px){.alui-app .alui-grid--2{grid-template-columns:1fr}}
@media(max-width:480px){.alui-app{border-radius:0;margin:0;min-height:100dvh}}
'''
    return css.strip()

DEMO_CSS = '''
html,body{margin:0;min-width:280px;min-height:100%;background:#101e2c}
.alui-demo-shell{position:relative;isolation:isolate;min-height:100vh;min-height:100dvh;
 background:#182f38;overflow:hidden}
.alui-demo-stage{position:absolute;inset:0;overflow:hidden;background:
 radial-gradient(ellipse at 73% 14%,#7bb6a363,transparent 35%),
 linear-gradient(160deg,#375e5d 0%,#517c77 39%,#526f61 55%,#243e35 78%,#182f32 100%)}
.alui-demo-sun{position:absolute;top:25%;left:71%;width:90px;height:90px;border-radius:50%;
 background:#ffe0a37a;box-shadow:0 0 85px 45px #ffd58c4a;filter:blur(1px)}
.alui-demo-hills{position:absolute;inset:24% -20% 12%;background:
 radial-gradient(ellipse at 8% 40%,#294f55 0 24%,transparent 24.5%),
 radial-gradient(ellipse at 63% 50%,#315b50 0 26%,transparent 26.5%),
 radial-gradient(ellipse at 108% 55%,#315c52 0 26%,transparent 26.5%)}
.alui-demo-ground{position:absolute;bottom:0;height:52%;width:100%;background:
 radial-gradient(ellipse at 60% 0%,#9fa5774d,transparent 43%),
 repeating-linear-gradient(145deg,transparent 0 45px,#263f3420 46px 48px),
 linear-gradient(180deg,#466657,#2d4e41 45%,#18372f);clip-path:polygon(0 31%,48% 6%,100% 24%,100% 100%,0 100%)}
.alui-demo-scene-label{position:absolute;top:34%;left:6%;color:#e3f8e8b0;font:800 12px system-ui;
 letter-spacing:.18em}
.alui-demo-scene-label span{opacity:.6;margin-left:8px}
.alui-demo-team,.alui-demo-foes{position:absolute;top:52%;display:flex;gap:clamp(8px,2vw,25px);align-items:flex-end;
 transform:translateY(-50%)}
.alui-demo-team{left:max(4%,calc(50% - 340px))}.alui-demo-foes{right:max(4%,calc(50% - 340px))}
.alui-demo-unit{position:relative;display:flex;flex-direction:column;align-items:center;gap:6px;filter:drop-shadow(0 9px 4px #071f2480)}
.alui-demo-unit>span{width:clamp(52px,10vw,98px);height:clamp(58px,11vw,100px);border:2px solid #ffffff3d;
 border-radius:25px 25px 19px 19px;display:grid;place-items:center;font-size:clamp(28px,6vw,52px);
 background:linear-gradient(135deg,#aec6a8dd,#59766fdc);box-shadow:inset 0 -10px 17px #124a4533}
.alui-demo-unit.foe>span{background:linear-gradient(135deg,#e19c84e0,#965c5ddc)}
.alui-demo-unit small{color:#fff;font:700 12px system-ui;text-shadow:0 1px 7px #000}
.alui-demo-versus{position:absolute;top:48%;left:50%;transform:translate(-50%,-50%);
 color:#ffdda8a8;font-size:clamp(35px,7vw,75px);text-shadow:0 5px 30px #ffd27988}
.alui-demo-watermark{position:absolute;bottom:38%;left:50%;transform:translateX(-50%);
 color:#ffffff74;font:700 10px system-ui;white-space:nowrap;letter-spacing:.12em}
.alui-demo-toast{position:fixed;left:50%;bottom:calc(25% + 20px);transform:translateX(-50%);z-index:25;
 max-width:calc(100% - 24px);pointer-events:none;padding:11px 17px;border-radius:999px;background:#101f2ced;
 border:1px solid #ffffff44;box-shadow:0 12px 30px #0005;color:#fff;font:600 13px system-ui}
.alui-demo-toast[hidden]{display:none}
@media(max-width:600px){.alui-demo-team,.alui-demo-foes{top:49%;gap:6px}
.alui-demo-team{left:3%}.alui-demo-foes{right:3%}
.alui-demo-unit>span{width:49px;height:61px;font-size:29px;border-radius:14px}
.alui-demo-unit small{font-size:10px}.alui-demo-watermark{bottom:31%}
.alui-demo-versus{top:46%;font-size:27px}.alui-demo-scene-label{top:31%}}
@media(prefers-reduced-motion:reduce){.alui-demo-stage *{animation:none!important;transition:none!important}}
'''

# Only demonstration notification: it does not pretend to mutate game state.
DEMO_JS = r'''(() => {
  const toast = document.querySelector('.alui-demo-toast');
  if (!toast) return;
  const root = document.querySelector('.alui-hud-overlay, .alui-app');
  if (!root) return;
  let toastTimer;
  root.addEventListener('alui:action', event => {
    const {type, name} = event.detail;
    toast.textContent = type === 'emit'
      ? '테스트 이벤트: ' + name + ' (호스트 연동 필요)'
      : '패널 ' + (root.querySelector('[data-alui-id="' + name + '"]')?.hidden ? '닫힘' : '열림');
    toast.hidden = false;
    window.clearTimeout(toastTimer);
    toastTimer = window.setTimeout(() => { toast.hidden = true; }, 1600);
  });
})();'''


def render(spec_json: str, target: str = "web-html", quality_mode: str = "advisory") -> dict[str, Any]:
    if quality_mode not in ("advisory", "enforce"):
        raise ValueError("quality_mode must be advisory or enforce")
    spec = _parse(spec_json)
    quality = anti_slop.review(spec)
    if quality_mode == "enforce" and quality["high_severity_count"]:
        raise ValueError("anti-slop quality gate: " + ", ".join(f["rule"] for f in quality["findings"] if f["severity"] == "high"))
    if target == "react-tsx":
        from .react_adapter import export
        return export(spec_json)
    if target not in ALLOWED_TARGETS:
        raise ValueError("unsupported rendering target")
    theme = {**PRESETS[spec.get("preset", "forest")], **spec.get("theme", {})}
    tokens = spec.get("tokens", {})
    button_text = max(("#000000", "#FFFFFF"), key=lambda c: _contrast(c, theme["primary"]))
    game = target == "game-hud-html"
    container = "alui-hud-overlay" if game else "alui-app"

    def node(n: dict[str, Any]) -> str:
        k = n["type"]
        if k in {"stack", "row", "panel", "card", "grid"}:
            inner = "".join(node(c) for c in n["children"])
            label = f' aria-label="{escape(n["label"], quote=True)}"' if "label" in n else ""
            attrs = ""
            if "id" in n: attrs += f' data-alui-id="{n["id"]}" data-alui-disclosure="true"'
            if n.get("hidden", False): attrs += " hidden"
            # Action rows get a mobile-friendly two-column grid.
            cls = f"alui-{k}"
            if k == "row" and all(c["type"] == "button" for c in n["children"]): cls += " alui-row--actions"
            if k == "grid":
                cls += f' alui-grid--{n.get("columns", 2)}'
                attrs += f' style="--alui-cols:{n.get("columns", 2)}"' 
            tag = "section" if k in ("panel", "card") else "div"
            return f'<{tag} class="{cls}"{label}{attrs}>{inner}</{tag}>'
        if k == "button":
            action = n.get("action")
            attrs = ""
            if action:
                kind, value = action["type"], action.get("target", action.get("name"))
                attrs = f' data-alui-action="{kind}" data-alui-value="{value}"'
                if kind == "toggle":
                    attrs += f' aria-controls="alui-panel-{value}" aria-expanded="false"'
            variant = n.get("variant", "primary")
            return f'<button type="button" class="alui-button alui-button--{variant}"{attrs}>{escape(n["label"])}</button>'
        if k == "divider":
            return '<hr class="alui-divider">'
        if k == "metric":
            tone = n.get("tone", "neutral")
            bind = f' data-alui-bind="{n["bind"]}"' if "bind" in n else ""
            return (f'<div class="alui-metric alui-metric--{tone}"{bind}>'
                    f'<span class="alui-metric-label">{escape(n["label"])}</span>'
                    f'<strong class="alui-metric-value" data-alui-bind-text>{escape(str(n["value"]))}</strong></div>')
        if k == "notice":
            tone = n.get("tone", "neutral")
            return f'<div class="alui-notice alui-notice--{tone}" role="note">{escape(n["text"])}</div>'
        if k == "text":
            bind = f' data-alui-bind="{n["bind"]}"' if "bind" in n else ""
            variant = n.get("variant", "normal")
            return f'<p class="alui-text alui-text--{variant}"{bind}>{escape(n["text"])}</p>'
        if k == "badge":
            tone = n.get("tone", "neutral")
            bind = f' data-alui-bind="{n["bind"]}"' if "bind" in n else ""
            return f'<span class="alui-badge alui-badge--{tone}"{bind}>{escape(n["text"])}</span>' 
        percentage = 100 * n["value"] / n["max"]
        bind = f' data-alui-bind="{n["bind"]}"' if "bind" in n else ""
        return (f'<div class="alui-progress" role="progressbar"{bind} ' 
                f'aria-label="{escape(n["label"], quote=True)}" '
                f'aria-valuemin="0" aria-valuemax="{n["max"]}" aria-valuenow="{n["value"]}">'
                f'<span class="alui-progress-track"><span class="alui-progress-fill" '
                f'style="width:{percentage:.2f}%"></span></span></div>')

    # Panel id's are validated slug: include native `id` for ARIA linkage.
    import re as _re
    inner = node(spec["root"])
    inner = _re.sub(r'data-alui-id="([a-z0-9-]+)"',
                    lambda m: f'id="alui-panel-{m.group(1)}" data-alui-id="{m.group(1)}"', inner)
    data_mode = f' data-alui-data-mode="{spec["data_mode"]}"' if "data_mode" in spec else ""
    html = f'<main class="{container}"{data_mode} aria-label="{escape(spec["title"], quote=True)}">{inner}</main>' 
    css = _css(container, theme, button_text, game, tokens, spec.get("design"))
    if game:
        preview_body = (f'<div class="alui-demo-shell">{_demo_stage()}{html}'
                        '<div class="alui-demo-toast" role="status" aria-live="polite" hidden></div></div>')
        preview_css = css + "\n" + DEMO_CSS
        preview_js = RUNTIME_JS + "\n" + DEMO_JS
    else:
        preview_body = html + '<div class="alui-demo-toast" role="status" aria-live="polite" hidden></div>'
        preview_css = css + '\n' + DEMO_CSS + '\nhtml,body{margin:0;background:#e8ecf0}body{display:flex;justify-content:center;padding-top:20px}@media(max-width:480px){body{padding-top:0;background:#131D32}}'
        preview_js = RUNTIME_JS + '\n' + DEMO_JS
    preview = ('<!doctype html><html lang="ko"><head><meta charset="utf-8">'
               '<meta name="viewport" content="width=device-width,initial-scale=1">'
               f'<title>{escape(spec["title"])}</title><style>{preview_css}</style></head>'
               f'<body>{preview_body}<script>{preview_js}</script></body></html>')
    return {
        "target": target, "html": html, "css": css, "javascript": RUNTIME_JS,
        "preview_html": preview,
        "integration_notes": (
            "Mount the HUD as a DOM layer above the game scene; attach javascript once "
            "after rendering; listen on root for 'alui:action' CustomEvent. Toggle works "
            "without the game host; emit only notifies the host. Demo battlefield is not gameplay."
            if game else
            "Mount fragment and CSS, attach javascript once after rendering; use "
            "'alui:action' listener for emit actions."
        ),
        "warnings": audit(spec_json)["warnings"],
        "anti_slop": quality,
        "quality_mode": quality_mode,
    }
