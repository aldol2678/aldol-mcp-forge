"""BONSAE design tools: HTML semantic audit, explicit state spec and evidence gate.
No screenshots are rendered or visually inspected by this module.
"""
import json
import re
from html.parser import HTMLParser
from .common import json_input, string, payload

class _HTMLAudit(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.lang = False
        self.viewport = False
        self.alt_missing = 0
        self.ids = set()
        self.duplicates = set()
        self.inputs = []
        self.labels = set()
        self.buttons = []
        self._buttons = []
        self.tags = 0

    def handle_starttag(self, tag, attrs):
        props = dict(attrs)
        self.tags += 1
        if tag == "html":
            self.lang = bool(props.get("lang"))
        elif tag == "meta" and (props.get("name") or "").lower() == "viewport":
            self.viewport = bool(props.get("content"))
        elif tag == "img" and props.get("alt") is None:
            self.alt_missing += 1
        elif tag == "label" and props.get("for"):
            self.labels.add(props["for"])
        elif tag in ("input", "textarea", "select") and props.get("type") != "hidden":
            self.inputs.append({"tag": tag, "id": props.get("id"),
                "accessible": bool(props.get("aria-label") or props.get("aria-labelledby"))})
        if props.get("id"):
            if props["id"] in self.ids:
                self.duplicates.add(props["id"])
            self.ids.add(props["id"])
        if tag == "button":
            self._buttons.append({"accessible": bool(props.get("aria-label") or props.get("title")),
                                  "text": "", "depth": 1})
        elif self._buttons:
            self._buttons[-1]["depth"] += 1

    def handle_endtag(self, tag):
        if self._buttons:
            if tag == "button":
                b = self._buttons.pop()
                self.buttons.append(b)
            else:
                self._buttons[-1]["depth"] = max(1, self._buttons[-1]["depth"] - 1)

    def handle_data(self, data):
        if self._buttons:
            self._buttons[-1]["text"] += data

def analyze_design(reference: str, target: str | None = None) -> dict[str, str]:
    html = string(reference, "reference", max_length=4096)
    css = string(target, "target", max_length=4096, allow_empty=True) if target is not None else ""
    parser = _HTMLAudit()
    parser.feed(html)
    issues = []
    if not parser.lang:
        issues.append({"code": "MISSING_LANG", "severity": "MEDIUM", "evidence": "html lang not found"})
    if not parser.viewport:
        issues.append({"code": "MISSING_VIEWPORT", "severity": "MEDIUM", "evidence": "viewport meta not found"})
    if parser.alt_missing:
        issues.append({"code": "IMG_ALT", "severity": "HIGH", "count": parser.alt_missing})
    if parser.duplicates:
        issues.append({"code": "DUPLICATE_ID", "severity": "HIGH", "ids": sorted(parser.duplicates)})
    unlabeled = sum(not (x["accessible"] or x["id"] in parser.labels)
                    for x in parser.inputs)
    if unlabeled:
        issues.append({"code": "INPUT_LABEL", "severity": "HIGH", "count": unlabeled})
    empty_buttons = sum(not (x["accessible"] or x["text"].strip()) for x in parser.buttons)
    if empty_buttons:
        issues.append({"code": "BUTTON_NAME", "severity": "HIGH", "count": empty_buttons})
    if re.search(r"user-scalable\s*=\s*no", html, re.IGNORECASE):
        issues.append({"code": "PINCH_ZOOM", "severity": "HIGH"})
    if re.search(r"overflow-x\s*:\s*hidden", css, re.IGNORECASE):
        issues.append({"code": "POTENTIAL_CLIPPING", "severity": "REVIEW",
                       "evidence": "overflow-x hidden; visual inspection required"})
    return {"findings": payload({"elements": parser.tags, "issues": issues, "scope": "HTML/CSS static analysis",
                                  "rendered_visual_qa": False}),
            "improvements": payload([x["code"] for x in issues] +
                            ["Verify keyboard focus, responsive layout and contrast in a rendered browser"])}

def generate_design_spec(brief: str) -> dict[str, str]:
    data = json_input(brief, "brief", {"goal", "components", "tokens", "device"})
    goal = string(data.get("goal"), "goal", max_length=400)
    components = data.get("components")
    if not isinstance(components, list) or not 1 <= len(components) <= 20:
        raise ValueError("components must contain 1..20 entries")
    expected = ("default", "loading", "empty", "error", "disabled")
    result = []
    risks = []
    names = set()
    for i, comp in enumerate(components):
        if not isinstance(comp, dict) or set(comp) - {"name", "role", "states", "mobile_behavior"}:
            raise ValueError("component must specify name, role, states and mobile_behavior")
        name = string(comp.get("name"), "component name", max_length=60)
        role = string(comp.get("role"), "component role", max_length=120)
        if name in names:
            raise ValueError("Duplicate component")
        names.add(name)
        states = comp.get("states")
        if not isinstance(states, list) or not states or any(not isinstance(s, str) or len(s) > 40 for s in states):
            raise ValueError("states must be a nonempty list of strings")
        states = list(dict.fromkeys(states))
        missing = [s for s in expected if s not in states]
        if missing:
            risks.append({"component": name, "missing_states": missing})
        mobile = string(comp.get("mobile_behavior"), "mobile_behavior", max_length=240)
        result.append({"name": name, "role": role, "states": states, "mobile_behavior": mobile})
    tokens = data.get("tokens", {})
    if not isinstance(tokens, dict) or len(tokens) > 30 or any(
            not isinstance(k, str) or not isinstance(v, str) or len(k) > 60 or len(v) > 120
            for k, v in tokens.items()):
        raise ValueError("tokens must be a bounded string map")
    device = string(data.get("device", "responsive"), "device", max_length=100)
    specification = {"goal": goal, "device": device, "tokens": tokens, "components": result,
                     "source": "user-provided explicit design intent", "visual_verification": "NOT_RUN"}
    return {"specification": payload(specification),
            "constraints": payload({"state_gaps": risks, "handoff": "BONSAE visual intent; SEUM runtime states",
                                    "verified_in_browser": False})}

def review_visual(artifact: str) -> dict[str, str]:
    data = json_input(artifact, "artifact", {"artifact_id", "viewport", "observations", "screenshot_refs"})
    identifier = string(data.get("artifact_id"), "artifact_id", max_length=160)
    observations = data.get("observations", [])
    shots = data.get("screenshot_refs", [])
    if not isinstance(observations, list) or len(observations) > 20 or not isinstance(shots, list) or len(shots) > 20:
        raise ValueError("observations/screenshot_refs must be bounded arrays")
    if any(not isinstance(x, str) or len(x) > 300 for x in shots):
        raise ValueError("screenshot_refs must be strings")
    cleaned = []
    for item in observations:
        if not isinstance(item, dict) or set(item) != {"issue", "evidence"}:
            raise ValueError("Every observation needs issue and evidence")
        cleaned.append({"issue": string(item["issue"], "issue", max_length=300),
                        "evidence": string(item["evidence"], "evidence", max_length=500)})
    viewport = data.get("viewport", "unspecified")
    string(viewport, "viewport", max_length=100)
    return {"verdict": "HOLD_UNINSPECTED",
            "findings": payload({"artifact_id": identifier, "viewport": viewport,
                "reported_observations": cleaned, "screenshot_refs_unverified": shots,
                "visual_inspection_performed": False,
                "next_step": "Human/browser image inspection is required for visual QA PASS"})}
