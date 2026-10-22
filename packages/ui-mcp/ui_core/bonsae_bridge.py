"""Conservative BONSAE -> ALDOL UI MCP handoff.

Accepts the real BONSAE generate_design_spec response (JSON string fields) or
its decoded specification object. This is a structural draft, NOT a pixel or
behaviorally complete implementation. No network, side effects or code eval.
"""
from __future__ import annotations

import json
import re
from typing import Any

from . import core

MAX_INPUT = 128_000
HEX = re.compile(r"#[0-9a-fA-F]{6}\Z")
COLOR_KEYS = {"primary", "background", "foreground"}
TOKEN_KEYS = {"font", "density", "radius"}
SPEC_FIELDS = {
    "goal", "device", "tokens", "components", "layouts", "motion",
    "accessibility", "source", "layout_defaults_proposed",
    "visual_verification", "seum_handoff",
}
COMP_FIELDS = {
    "name", "role", "states", "mobile_behavior", "interaction", "accessibility",
}


def _decode(value: str, label: str) -> dict[str, Any]:
    if not isinstance(value, str) or not 1 <= len(value) <= MAX_INPUT:
        raise ValueError(label + " must be bounded nonempty JSON text")
    try:
        decoded = json.loads(value)
    except (ValueError, TypeError, RecursionError) as exc:
        raise ValueError(label + " must be valid JSON") from exc
    if not isinstance(decoded, dict):
        raise ValueError(label + " must contain a JSON object")
    return decoded


def _text(value: Any, label: str, limit: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(label + " must be nonempty text of at most " + str(limit))
    return value.strip()


def import_bonsae(bonsae_output_json: str, preset: str = "forest") -> dict[str, Any]:
    """Transform BONSAE intent into validated UI *placeholder* structure.

    The handoff intentionally does not infer live data, buttons, navigation,
    game events, loading states or pixel-perfect layout from prose descriptions.
    All unimplemented intent remains visible in the returned handoff report.
    """
    if preset not in core.PRESETS:
        raise ValueError("preset must be one of: " + ", ".join(sorted(core.PRESETS)))
    outer = _decode(bonsae_output_json, "bonsae_output_json")
    if "specification" in outer:
        if set(outer) - {"specification", "constraints"}:
            raise ValueError("BONSAE wrapper has unsupported fields")
        source = _decode(outer["specification"], "specification")
        raw_constraints = outer.get("constraints")
        if raw_constraints is not None and not isinstance(raw_constraints, str):
            raise ValueError("BONSAE constraints must be JSON text")
        constraints = _decode(raw_constraints, "constraints") if raw_constraints else {}
    else:
        source = outer
        constraints = {}
    if set(source) - SPEC_FIELDS:
        raise ValueError("BONSAE specification contains unknown fields")
    goal = _text(source.get("goal"), "goal", 400)
    components = source.get("components")
    if not isinstance(components, list) or not 1 <= len(components) <= 20:
        raise ValueError("BONSAE components must contain 1..20 entries")
    raw_tokens = source.get("tokens", {})
    if not isinstance(raw_tokens, dict) or len(raw_tokens) > 30:
        raise ValueError("BONSAE tokens must be a bounded map")
    if any(not isinstance(k, str) or not isinstance(v, str)
           or len(k) > 60 or len(v) > 120 for k, v in raw_tokens.items()):
        raise ValueError("BONSAE token names/values must be bounded text")
    theme, tokens, unmapped_tokens = {}, {}, []
    for key, value in raw_tokens.items():
        if key in COLOR_KEYS:
            if not HEX.fullmatch(value):
                raise ValueError("BONSAE token " + key + " must be a six-digit hex color")
            theme[key] = value
        elif key in TOKEN_KEYS:
            options = {"font": core.FONTS, "density": core.DENSITIES, "radius": core.RADII}[key]
            if value not in options:
                raise ValueError("Unsupported BONSAE token " + key)
            tokens[key] = value
        else:
            unmapped_tokens.append(key)
    title = goal if len(goal) <= 100 else goal[:99] + "…"
    children: list[dict[str, Any]] = [
        {"type": "text", "text": title, "variant": "heading"},
    ]
    requirements = []
    known_names = set()
    for index, item in enumerate(components):
        if not isinstance(item, dict) or set(item) - COMP_FIELDS:
            raise ValueError("BONSAE component has unsupported fields")
        name = _text(item.get("name"), "component.name", 60)
        role = _text(item.get("role"), "component.role", 120)
        mobile = _text(item.get("mobile_behavior"), "component.mobile_behavior", 240)
        states = item.get("states")
        if (not isinstance(states, list) or not 1 <= len(states) <= 20
                or any(not isinstance(s, str) or not s.strip() or len(s) > 40
                       for s in states)):
            raise ValueError("component.states must be a bounded list of state names")
        if name in known_names:
            raise ValueError("BONSAE component names must be unique")
        known_names.add(name)
        interaction = item.get("interaction")
        accessibility = item.get("accessibility")
        if interaction is not None:
            _text(interaction, "component.interaction", 500)
        if accessibility is not None:
            _text(accessibility, "component.accessibility", 500)
        # Represent only name and role. Do not invent executable controls.
        children.append({"type": "card", "children": [
            {"type": "text", "text": name, "variant": "heading"},
            {"type": "text", "text": role, "variant": "normal"},
        ]})
        requirements.append({
            "source_index": index,
            "name": name,
            "states": states,
            "mobile_behavior": mobile,
            "interaction": interaction,
            "accessibility": accessibility,
            "implementation": "NOT_IMPLEMENTED",
        })
    ui_doc: dict[str, Any] = {
        "version": "0.3",
        "title": title,
        "preset": preset,
        "root": {"type": "stack", "children": children},
        "design": {"context": "product", "brand_note":
                   "BONSAE structural preview only; actions and data require implementation."},
        "data_mode": "demo",
    }
    if theme:
        ui_doc["theme"] = theme
    if tokens:
        ui_doc["tokens"] = tokens
    spec_json = json.dumps(ui_doc, ensure_ascii=False, separators=(",", ":"))
    validity = core.validate(spec_json)
    if not validity.get("valid"):
        raise ValueError("Generated preview failed UI validation: " + str(validity.get("errors")))
    return {
        "status": "HANDOFF_REVIEW_REQUIRED",
        "ui_spec_json": spec_json,
        "ui_validation": validity,
        "source": "BONSAE.generate_design_spec",
        "mapped": {"component_placeholders": len(components),
                   "color_tokens": sorted(theme), "ui_tokens": sorted(tokens)},
        "unmapped_tokens": sorted(unmapped_tokens),
        "unimplemented": {
            "components": requirements,
            "layouts": source.get("layouts"),
            "motion": source.get("motion"),
            "accessibility": source.get("accessibility"),
            "device": source.get("device"),
            "goal_overflow": goal[99:] if len(goal) > 100 else None,
            "constraints": constraints,
        },
        "safe_to_preview": True,
        "functional_ui_complete": False,
        "visual_verification": "NOT_RUN",
        "human_review_required": True,
        "release_authorized": False,
        "note": "Only structural card placeholders are generated. Review BONSAE requirements, replace placeholders with functional controls, then use ui_generate and real browser/device QA.",
    }
