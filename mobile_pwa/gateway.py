"""Session-gated calls into the same in-process MCP servers the HTTP mounts use.

The browser never receives the bearer key. This module does not open a second
network hop and does not log arguments.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any

from mcp.server.mcpserver.exceptions import ToolError, UnexpectedToolError

CALLABLE = {
    "bonsae": {"generate_design_spec"},
    "ui": {"ui_import_bonsae", "ui_generate"},
}
_BRIEF_FIELDS = {"goal", "components", "tokens", "device", "motion", "accessibility", "layouts"}
_REQUEST_FIELDS = _BRIEF_FIELDS | {"preset"}
_COMPONENT_FIELDS = {"name", "role", "states", "mobile_behavior", "interaction", "accessibility"}
_SCRIPT = re.compile(r"<script\b[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL)


class FlowError(Exception):
    def __init__(self, step: str, message: str):
        super().__init__(message)
        self.step = step
        self.message = message


def _servers():
    import app as design_app
    return design_app.bonsae_mcp, design_app.ui_mcp


def public_message(exc: BaseException) -> str:
    cause: BaseException = exc
    nested = exc.__cause__
    if isinstance(nested, ValueError):
        cause = nested
    elif not isinstance(exc, (ValueError, ToolError)):
        return "tool_failed"
    text = " ".join(str(cause).split())
    if len(text) > 240:
        text = text[:240]
    secret = os.getenv("ALDOL_DESIGN_MCP_KEY", "")
    lowered = text.lower()
    if not text or "bearer" in lowered or "traceback" in lowered or (secret and secret in text):
        return "tool_failed"
    return text


def _payload(result) -> dict[str, Any]:
    if result.is_error:
        raise FlowError("tool", "tool_failed")
    data = result.structured_content
    if not isinstance(data, dict):
        raise FlowError("tool", "tool_failed")
    return data


async def list_catalog() -> dict[str, Any]:
    bonsae, ui = _servers()
    return {
        "transport": "in-process MCP list_tools",
        "pwa_calls": ["generate_design_spec", "ui_import_bonsae", "ui_generate"],
        "note": "이 페이지의 실행 버튼은 위 세 도구만 순서대로 호출합니다. 나머지 도구는 여기에 연결되어 있지 않습니다.",
        "servers": {
            "bonsae": await _describe(bonsae, "bonsae"),
            "ui": await _describe(ui, "ui"),
        },
    }


async def _describe(server, group: str) -> list[dict[str, Any]]:
    tools = await server.list_tools()
    return [{
        "name": tool.name,
        "description": tool.description or "",
        "callable_from_pwa": tool.name in CALLABLE[group],
    } for tool in tools]


def _text(value: object, field: str, limit: int, required: bool = True) -> str | None:
    if value is None or value == "":
        if required:
            raise FlowError("generate_design_spec", field + " is required")
        return None
    if not isinstance(value, str):
        raise FlowError("generate_design_spec", field + " must be text")
    cleaned = value.strip()
    if not cleaned or len(cleaned) > limit:
        raise FlowError("generate_design_spec", field + " must be nonempty text within its limit")
    return cleaned


def _brief(payload: dict[str, Any]) -> dict[str, Any]:
    if set(payload) - _REQUEST_FIELDS:
        raise FlowError("request", "unsupported fields")
    brief: dict[str, Any] = {"goal": _text(payload.get("goal"), "goal", 400)}
    components = payload.get("components")
    if not isinstance(components, list) or not 1 <= len(components) <= 20:
        raise FlowError("generate_design_spec", "components must contain 1..20 entries")
    cleaned = []
    for item in components:
        if not isinstance(item, dict) or set(item) - _COMPONENT_FIELDS:
            raise FlowError("generate_design_spec", "component has unsupported fields")
        states = item.get("states")
        if (not isinstance(states, list) or not states
                or any(not isinstance(state, str) or not state.strip() or len(state) > 40 for state in states)):
            raise FlowError("generate_design_spec", "states must be a nonempty list of short names")
        component = {
            "name": _text(item.get("name"), "component.name", 60),
            "role": _text(item.get("role"), "component.role", 120),
            "states": [state.strip() for state in states],
            "mobile_behavior": _text(item.get("mobile_behavior"), "component.mobile_behavior", 240),
        }
        for optional, limit in (("interaction", 500), ("accessibility", 500)):
            text = _text(item.get(optional), "component." + optional, limit, required=False)
            if text:
                component[optional] = text
        cleaned.append(component)
    brief["components"] = cleaned
    for optional, limit in (("device", 100), ("motion", 600), ("accessibility", 800)):
        text = _text(payload.get(optional), optional, limit, required=False)
        if text:
            brief[optional] = text
    if "tokens" in payload:
        tokens = payload["tokens"]
        if not isinstance(tokens, dict):
            raise FlowError("generate_design_spec", "tokens must be an object")
        brief["tokens"] = tokens
    if "layouts" in payload:
        brief["layouts"] = payload["layouts"]
    return brief


def _static_preview(html: object) -> str:
    if not isinstance(html, str) or "<html" not in html.lower():
        raise FlowError("ui_generate", "preview_unavailable")
    stripped, count = _SCRIPT.subn("", html)
    if count < 1 or re.search(r"<\s*script\b", stripped, re.IGNORECASE):
        raise FlowError("ui_generate", "preview_unavailable")
    return stripped


async def _call(server, step: str, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    try:
        result = await server.call_tool(name, arguments)
    except (ToolError, UnexpectedToolError, ValueError) as exc:
        raise FlowError(step, public_message(exc)) from exc
    try:
        return _payload(result)
    except FlowError as exc:
        raise FlowError(step, exc.message) from exc


async def run_flow(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise FlowError("request", "invalid_json")
    preset = payload.get("preset", "forest")
    if preset not in ("forest", "studio", "slate"):
        raise FlowError("ui_import_bonsae", "preset must be forest, studio, or slate")
    brief = _brief(payload)
    bonsae, ui = _servers()
    steps = []
    spec = await _call(bonsae, "generate_design_spec", "generate_design_spec", {
        "brief": json.dumps(brief, ensure_ascii=False, separators=(",", ":")),
    })
    steps.append({"server": "bonsae", "tool": "generate_design_spec", "transport": "in-process MCP call_tool", "ok": True})
    handoff = await _call(ui, "ui_import_bonsae", "ui_import_bonsae", {
        "bonsae_output_json": json.dumps(spec, ensure_ascii=False, separators=(",", ":")),
        "preset": preset,
    })
    steps.append({"server": "ui", "tool": "ui_import_bonsae", "transport": "in-process MCP call_tool", "ok": True})
    generated = await _call(ui, "ui_generate", "ui_generate", {
        "spec_json": handoff["ui_spec_json"],
        "target": "web-html",
        "quality_mode": "advisory",
    })
    steps.append({"server": "ui", "tool": "ui_generate", "transport": "in-process MCP call_tool", "ok": True})
    specification = json.loads(spec["specification"])
    constraints = json.loads(spec["constraints"])
    return {
        "ok": True,
        "steps": steps,
        "specification": specification,
        "constraints": constraints,
        "handoff": {
            "status": handoff["status"],
            "functional_ui_complete": handoff["functional_ui_complete"],
            "human_review_required": handoff["human_review_required"],
            "release_authorized": handoff["release_authorized"],
            "visual_verification": handoff["visual_verification"],
            "safe_to_preview": handoff["safe_to_preview"],
            "note": handoff["note"],
            "mapped": handoff["mapped"],
            "unmapped_tokens": handoff["unmapped_tokens"],
            "unimplemented": handoff["unimplemented"],
            "ui_spec_json": handoff["ui_spec_json"],
        },
        "preview_html": _static_preview(generated.get("preview_html")),
        "quality_mode": generated.get("quality_mode"),
        "warnings": generated.get("warnings", []),
        "high_severity_count": (generated.get("anti_slop") or {}).get("high_severity_count"),
        "runtime_script": "removed",
        "android_device_verified": False,
    }
