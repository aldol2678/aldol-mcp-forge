"""BONSAE bounded source audit, design handoff and real render/pixel evidence.

Static heuristics and limited pixel measurements are distinguished from complete
visual acceptance. No caller URL is fetched and no original file is modified.
"""
from __future__ import annotations
import json
import re
from html.parser import HTMLParser
from .common import string, payload

MAX_TEXT = 131072


def _object(value, field, allowed):
    string(value, field, max_length=262144)
    try:
        data = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(field + " must be a JSON object") from exc
    if not isinstance(data, dict) or set(data) - allowed:
        raise ValueError(field + " has unsupported fields")
    return data


class _HTMLAudit(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.nodes = []
        self.stack = []
        self.styles = []
        self.style_depth = 0
        self.lang = False
        self.viewport = False

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_starttag(self, tag, attrs):
        props = dict(attrs)
        if len(self.nodes) >= 4000:
            raise ValueError("HTML exceeds 4000 elements")
        selector = "#" + props["id"] if props.get("id") else tag + ("." + props.get("class", "").split()[0] if props.get("class", "").split() else "")
        node = {"tag": tag, "attrs": props, "line": self.getpos()[0],
                "column": self.getpos()[1] + 1, "selector": selector, "text": "",
                "label_parent": any(n["tag"] == "label" for n in self.stack)}
        self.nodes.append(node)
        if len(self.stack) >= 100:
            raise ValueError("HTML nesting exceeds 100 levels")
        if tag == "img" and props.get("alt"):
            for parent in self.stack:
                if parent["tag"] == "button":
                    parent["text"] += props["alt"][:200]
        if tag == "html":
            self.lang = bool(props.get("lang"))
        if tag == "meta" and (props.get("name") or "").lower() == "viewport":
            self.viewport = bool(props.get("content"))
        if tag == "style":
            self.style_depth += 1
        if tag not in ("area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"):
            self.stack.append(node)

    def handle_endtag(self, tag):
        if tag == "style":
            self.style_depth = max(0, self.style_depth - 1)
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i]["tag"] == tag:
                del self.stack[i:]
                break

    def handle_data(self, text):
        if self.style_depth:
            self.styles.append(text)
        for node in self.stack:
            if len(node["text"]) < 1000:
                node["text"] += text[:1000]


def analyze_design(reference: str, target: str | None = None) -> dict[str, str]:
    html = string(reference, "reference", max_length=MAX_TEXT)
    css = string(target, "target", max_length=MAX_TEXT, allow_empty=True) if target is not None else ""
    parser = _HTMLAudit()
    parser.feed(html)
    nodes = parser.nodes
    full_css = css + "\n" + "\n".join(parser.styles) + "\n" + "\n".join(n["attrs"].get("style", "") or "" for n in nodes)
    issues = []
    def add(code, severity, evidence, suggestion, node=None):
        issues.append({"code": code, "severity": severity, "evidence": evidence,
                       "suggestion": suggestion,
                       "location": {k: node[k] for k in ("selector", "line", "column")} if node else {"selector": "document", "line": 1, "column": 1},
                       "method": "HTMLParser" if node else "source heuristic"})
    if not parser.lang:
        add("MISSING_LANG", "MEDIUM", "html lang not found", "Set html lang to the content language")
    if not parser.viewport:
        add("MISSING_VIEWPORT", "MEDIUM", "viewport meta not found", "Add width=device-width,initial-scale=1 viewport meta")
    ids = {}
    labels = {n["attrs"].get("for") for n in nodes if n["tag"] == "label" and n["text"].strip()}
    for n in nodes:
        a = n["attrs"]
        if a.get("id"):
            ids.setdefault(a["id"], []).append(n)
    for key, group in ids.items():
        for n in group[1:]:
            add("DUPLICATE_ID", "HIGH", "Duplicate id=" + key, "Give each element a unique id", n)
    for n in nodes:
        a, tag = n["attrs"], n["tag"]
        labelledby = (a.get("aria-labelledby") or "").split()
        aria_named = bool((a.get("aria-label") or "").strip() or (labelledby and all(k in ids and ids[k][0]["text"].strip() for k in labelledby)))
        if tag == "img" and a.get("alt") is None:
            add("IMG_ALT", "HIGH", "img has no alt attribute", "Provide informative alt or empty alt for decorative images", n)
        if tag in ("input", "textarea", "select") and a.get("type") not in ("hidden", "submit", "button", "reset", "image"):
            if not (aria_named or n["label_parent"] or a.get("id") in labels):
                add("INPUT_LABEL", "HIGH", "Control has no associated accessible label", "Associate a label with for/id or aria-label", n)
        if tag == "button" or a.get("role") == "button":
            if not (aria_named or n["text"].strip()):
                add("BUTTON_NAME", "HIGH", "Button has no text or accessible name", "Provide visible text or an accessible name", n)
            if tag != "button" and a.get("tabindex") != "0":
                add("NON_NATIVE_BUTTON", "MEDIUM", "Non-native button lacks tabindex=0", "Use a native button; verify keyboard activation", n)
        if labelledby and any(k not in ids for k in labelledby):
            add("BROKEN_ARIA_REFERENCE", "HIGH", "aria-labelledby references a missing id", "Reference existing labelled elements", n)
        if tag == "a" and a.get("href") == "#":
            add("PLACEHOLDER_ACTION", "REVIEW", "Anchor links to #", "Implement an actual destination or use a button", n)
        if tag == "meta" and (a.get("name") or "").lower() == "viewport" and re.search(r"user-scalable\s*=\s*no|maximum-scale\s*=\s*1(?:[,;\s]|$)", a.get("content") or "", re.I):
            add("PINCH_ZOOM", "HIGH", "Viewport restricts user zoom", "Allow pinch zoom", n)
    if not any(n["tag"] == "main" or n["attrs"].get("role") == "main" for n in nodes):
        add("MAIN_LANDMARK", "MEDIUM", "No main landmark", "Wrap the primary task area in main")
    if re.search(r"overflow-x\s*:\s*hidden", full_css, re.I):
        add("POTENTIAL_CLIPPING", "REVIEW", "overflow-x:hidden occurs in CSS", "Inspect rendered content; hiding overflow can conceal layout defects")
    if any(n["tag"] in ("button", "input", "select", "textarea") for n in nodes) and not re.search(r":focus(?:-visible|-within)?\b", full_css):
        add("FOCUS_STYLE_UNSPECIFIED", "REVIEW", "No custom focus selector in supplied CSS", "Verify native focus visibility; add focus-visible when needed")
    fixed_widths = re.findall(r"(?<![-\w])(?:min-)?width\s*:\s*([4-9]\d\d|[1-9]\d{3,})px", full_css, re.I)
    if fixed_widths:
        add("FIXED_WIDTH_MOBILE", "REVIEW", "Large fixed widths: " + ",".join(fixed_widths[:10]), "Check 390px overflow; bound width to available space")
    if re.search(r"animation\s*:|transition\s*:", full_css) and "prefers-reduced-motion" not in full_css:
        add("REDUCED_MOTION_UNSPECIFIED", "REVIEW", "Motion declarations without reduced-motion fallback", "Provide a prefers-reduced-motion fallback")
    token_pairs = re.findall(r"(--[\w-]+)\s*:\s*([^;}]+)", full_css)
    declarations = dict(token_pairs)
    token_values = {}
    for name, value in token_pairs:
        token_values.setdefault(name, set()).add(value.strip())
    for name, values in token_values.items():
        if len(values) > 1:
            add("TOKEN_OVERRIDE_REVIEW", "REVIEW", name + " has multiple declarations", "Confirm intentional scope/theme overrides; compare computed tokens at each viewport")
    references = set(re.findall(r"var\(\s*(--[\w-]+)\s*\)", full_css))
    missing = sorted(references - declarations.keys())
    if missing:
        add("UNDEFINED_DESIGN_TOKEN", "MEDIUM", ", ".join(missing), "Define referenced custom properties or provide fallbacks")
    candidates = []
    for pattern, symptom in [(r"linear-gradient|radial-gradient", "gradient use"), (r"backdrop-filter\s*:", "glass/backdrop effect"), (r"box-shadow\s*:", "shadow use")]:
        if re.search(pattern, full_css, re.I):
            candidates.append({"symptom": symptom, "status": "REQUIRES_PURPOSE_REVIEW", "is_automatic_defect": False,
                               "question": "Does this support task hierarchy, legibility or documented brand intent?"})
    return {"findings": payload({"elements": len(nodes), "issues": issues,
                "scope": "HTMLParser semantics plus bounded CSS source heuristics", "rendered_visual_qa": False,
                "design_tokens": declarations, "media_queries": re.findall(r"@media\s*([^{}]+)", full_css)[:30],
                "state_selectors": sorted(set(re.findall(r":(hover|focus-visible|focus|active|disabled|checked)\b", full_css))),
                "unexamined_default_candidates": candidates,
                "not_checked": ["computed contrast", "actual touch dimensions", "state behavior", "rendered alignment"]}),
            "improvements": payload([{"code": i["code"], "location": i["location"], "suggestion": i["suggestion"]} for i in issues])}


def generate_design_spec(brief: str) -> dict[str, str]:
    data = _object(brief, "brief", {"goal", "components", "tokens", "device", "motion", "accessibility", "layouts"})
    goal = string(data.get("goal"), "goal", max_length=400)
    components = data.get("components")
    if not isinstance(components, list) or not 1 <= len(components) <= 20:
        raise ValueError("components must contain 1..20 entries")
    expected = ("default", "loading", "empty", "error", "disabled")
    result, risks, names = [], [], set()
    for comp in components:
        if not isinstance(comp, dict) or set(comp) - {"name", "role", "states", "mobile_behavior", "interaction", "accessibility"}:
            raise ValueError("component has unsupported fields")
        name = string(comp.get("name"), "component name", max_length=60)
        role = string(comp.get("role"), "component role", max_length=120)
        if name in names:
            raise ValueError("Duplicate component")
        names.add(name)
        states = comp.get("states")
        if not isinstance(states, list) or not 1 <= len(states) <= 20 or any(not isinstance(s, str) or not s.strip() or len(s) > 40 for s in states):
            raise ValueError("states must be a bounded nonempty list of strings")
        states = list(dict.fromkeys(states))
        missing = [s for s in expected if s not in states]
        if missing:
            risks.append({"component": name, "missing_states": missing, "status": "REVIEW_APPLICABILITY"})
        mobile = string(comp.get("mobile_behavior"), "mobile_behavior", max_length=240)
        result.append({"name": name, "role": role, "states": states, "mobile_behavior": mobile,
                       "interaction": string(comp.get("interaction", "Explicit trigger/behavior to be supplied"), "interaction", max_length=500),
                       "accessibility": string(comp.get("accessibility", "Verify keyboard operation, accessible naming and visible focus"), "accessibility", max_length=500)})
    tokens = data.get("tokens", {})
    if not isinstance(tokens, dict) or len(tokens) > 30 or any(not isinstance(k, str) or not isinstance(v, str) or len(k) > 60 or len(v) > 120 for k, v in tokens.items()):
        raise ValueError("tokens must be a bounded string map")
    layouts = data.get("layouts", {"390": "Single column; accessible drawer navigation; preserve all meaning and actions", "820": "Two-pane layout only when content fits; keep comparison tables scrollable", "1280": "Sidebar with bounded readable work area"})
    if not isinstance(layouts, dict) or set(layouts) != {"390", "820", "1280"} or any(not isinstance(v, str) or len(v) > 500 for v in layouts.values()):
        raise ValueError("layouts must define 390,820,1280 string descriptions")
    motion = string(data.get("motion", "Task console: minimal motion, duration 120–180ms where useful; respect prefers-reduced-motion"), "motion", max_length=600)
    accessibility = string(data.get("accessibility", "Semantic landmarks; keyboard access; visible focus; descriptive errors; 44px target review; contrast and representative Korean glyph runtime checks"), "accessibility", max_length=800)
    specification = {"goal": goal, "device": string(data.get("device", "responsive"), "device", max_length=100),
                     "tokens": tokens, "components": result, "layouts": layouts, "motion": motion,
                     "accessibility": accessibility, "source": "user-provided explicit design intent plus labelled proposed defaults",
                     "layout_defaults_proposed": "layouts" not in data, "visual_verification": "NOT_RUN",
                     "seum_handoff": {"component_structure": result, "responsive_semantics": layouts,
                         "critical_states": "Preserve supplied states; review listed applicability gaps",
                         "data_boundary": "No invented metrics, source freshness or hidden mobile fields",
                         "acceptance": ["Meaning/actions retained at all viewports", "loading/error/empty behavior checked", "keyboard/focus checked", "runtime rendered and drift classified"],
                         "drift_categories": ["semantic", "structural", "behavioral", "state", "visual"]}}
    return {"specification": payload(specification), "constraints": payload({"state_gaps": risks,
                "handoff": "BONSAE visual intent; SEUM runtime implementation; product owner final adoption",
                "verified_in_browser": False, "release_authorized": False})}


def review_visual(artifact: str) -> dict[str, str]:
    data = _object(artifact, "artifact", {"artifact_id", "viewport", "observations", "screenshot_refs", "html", "css", "viewports", "image_base64", "intent_tokens"})
    identifier = string(data.get("artifact_id"), "artifact_id", max_length=160)
    observations, shots = data.get("observations", []), data.get("screenshot_refs", [])
    if not isinstance(observations, list) or len(observations) > 20 or not isinstance(shots, list) or len(shots) > 20:
        raise ValueError("observations/screenshot_refs must be bounded arrays")
    if any(not isinstance(x, str) or len(x) > 300 for x in shots):
        raise ValueError("screenshot_refs must be strings")
    cleaned = []
    for item in observations:
        if not isinstance(item, dict) or set(item) != {"issue", "evidence"}:
            raise ValueError("Every observation needs issue and evidence")
        cleaned.append({"issue": string(item["issue"], "issue", max_length=300), "evidence": string(item["evidence"], "evidence", max_length=500)})
    viewport = string(data.get("viewport", "unspecified"), "viewport", max_length=100)
    findings = {"artifact_id": identifier, "viewport": viewport,
                "reported_observations": cleaned, "screenshot_refs_unverified": shots,
                "visual_inspection_performed": False, "semantic_visual_review": "NOT_RUN",
                "next_step": "Human/image-model inspection is required for whole-screen visual acceptance"}
    verdict = "HOLD_UNINSPECTED"
    from .bonsae_visual import inspect_image, render_html
    if "image_base64" in data:
        try:
            findings["image_pixels"] = inspect_image(data["image_base64"])
            findings["visual_inspection_performed"] = True
            verdict = "HOLD_PARTIAL_VISUAL"
        except ImportError:
            findings["image_pixels"] = {"pixel_decode_performed": False, "reason": "PILLOW_NOT_INSTALLED"}
    if "html" in data:
        rendered = render_html(data["html"], data.get("css", ""), data.get("viewports", [390, 820, 1280]), data.get("intent_tokens", {}))
        findings["browser"] = rendered
        if rendered.get("rendered"):
            findings["visual_inspection_performed"] = True
            verdict = "HOLD_PARTIAL_VISUAL"
            failures = []
            for r in rendered["viewports"]:
                for check, bad in [("horizontal overflow", r["overflow"]), ("clipped containers", bool(r["clippedContainers"])), ("small touch targets", bool(r["smallTouchTargets"])), ("contrast", any(not c["passes"] for c in r["contrast"])), ("token drift", bool(r["tokenDrift"]))]:
                    if bad:
                        failures.append({"viewport": r["viewport"], "check": check})
            findings["render_check_failures"] = failures
            if failures:
                verdict = "FAIL_RENDER_CHECKS"
    findings["whole_screen_pass"] = False
    findings["scope"] = "Bounded decoded pixels/render geometry; observations and remote refs are never trusted as inspected evidence"
    return {"verdict": verdict, "findings": payload(findings)}
