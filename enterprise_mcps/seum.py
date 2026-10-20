"""SEUM engineering tools: real static analysis, deterministic patch and release gate.
Never checks out repositories, executes source, applies patches or deploys.
"""
import ast
import difflib
import hashlib
from .common import json_input, string, safe_path, payload

def analyze_code(repository: str, focus: str | None = None) -> dict[str, str]:
    data = json_input(repository, "repository", {"path", "language", "content"})
    path = safe_path(data.get("path"))
    language = string(data.get("language"), "language", max_length=20).lower()
    content = string(data.get("content"), "content", max_length=3500, allow_empty=True)
    if focus is not None:
        string(focus, "focus", max_length=200, allow_empty=True)
    risks = []
    findings = {"path": path, "language": language, "lines": len(content.splitlines()),
                "sha256": hashlib.sha256(content.encode()).hexdigest(), "method": "offline-static-only"}
    if language == "python":
        try:
            tree = ast.parse(content, filename=path)
        except SyntaxError as exc:
            risks.append({"code": "PY_SYNTAX", "line": exc.lineno, "severity": "FAIL",
                          "message": exc.msg})
            findings["parse_ok"] = False
        else:
            findings["parse_ok"] = True
            findings["functions"] = sum(isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef))
                                        for x in ast.walk(tree))
            imports = sorted({alias.name.split(".")[0] for x in ast.walk(tree)
                              if isinstance(x, ast.Import) for alias in x.names}
                             | {x.module.split(".")[0] for x in ast.walk(tree)
                                if isinstance(x, ast.ImportFrom) and x.module})
            findings["imports"] = imports
            for x in ast.walk(tree):
                if not isinstance(x, ast.Call):
                    continue
                func = x.func
                name = func.id if isinstance(func, ast.Name) else (
                    func.value.id + "." + func.attr if isinstance(func, ast.Attribute)
                    and isinstance(func.value, ast.Name) else "")
                if name in ("eval", "exec", "os.system"):
                    risks.append({"code": "DYNAMIC_EXECUTION", "line": x.lineno,
                                  "severity": "HIGH", "message": "Review dynamic code or shell execution"})
                if name in ("subprocess.run", "subprocess.Popen", "subprocess.call"):
                    if any(k.arg == "shell" and isinstance(k.value, ast.Constant)
                           and k.value.value is True for k in x.keywords):
                        risks.append({"code": "SHELL_TRUE", "line": x.lineno,
                                      "severity": "HIGH", "message": "Review shell=True"})
    elif language == "json":
        import json
        try:
            document = json.loads(content)
            findings["parse_ok"] = True
            findings["top_level_type"] = type(document).__name__
        except json.JSONDecodeError as exc:
            findings["parse_ok"] = False
            risks.append({"code": "JSON_SYNTAX", "line": exc.lineno,
                          "severity": "FAIL", "message": exc.msg})
    else:
        raise ValueError("language must be python or json for this MVP")
    findings["focus"] = focus or "general"
    findings["limitations"] = "Static evidence only; no tests, dependencies or live repository fetched"
    return {"summary": payload(findings), "risks": payload(risks)}

def implement_change(repository: str, request: str) -> dict[str, str]:
    data = json_input(repository, "repository", {"path", "content"})
    original = string(data.get("content"), "content", max_length=3500, allow_empty=True)
    path = safe_path(data.get("path"))
    change = json_input(request, "request", {"find", "replace", "expected_sha256"})
    before = string(change.get("find"), "find", max_length=1800)
    after = string(change.get("replace"), "replace", max_length=1800, allow_empty=True)
    expected = string(change.get("expected_sha256"), "expected_sha256", max_length=64)
    actual = hashlib.sha256(original.encode("utf-8")).hexdigest()
    if expected != actual:
        raise ValueError("STALE_SOURCE: expected_sha256 does not match")
    if original.count(before) != 1:
        raise ValueError("Expected text must occur exactly once")
    updated = original.replace(before, after, 1)
    if path.endswith(".py"):
        try:
            ast.parse(updated, filename=path)
        except SyntaxError as exc:
            raise ValueError("Changed Python source fails syntax check: " + exc.msg) from exc
    import json
    if path.endswith(".json"):
        try:
            json.loads(updated)
        except json.JSONDecodeError as exc:
            raise ValueError("Changed JSON source fails parsing") from exc
    diff = "".join(difflib.unified_diff(original.splitlines(True), updated.splitlines(True),
                                       fromfile="a/" + path, tofile="b/" + path))
    if len(diff) > 12000:
        raise ValueError("Proposed diff exceeds output limit")
    return {"change_summary": diff or "NO_CHANGE",
            "verification": payload({"status": "PROPOSAL_ONLY", "source_sha256": actual,
                "new_sha256": hashlib.sha256(updated.encode()).hexdigest(),
                "syntax_checked": path.endswith((".py", ".json")),
                "applied": False, "deployment": False})}

def review_release(release_ref: str) -> dict[str, str]:
    data = json_input(release_ref, "release_ref", {"revision", "checks"})
    revision = string(data.get("revision"), "revision", max_length=128)
    checks = data.get("checks")
    if not isinstance(checks, dict) or set(checks) - {"ci", "tests", "security", "cost", "mobile"}:
        raise ValueError("checks must be a status object of CI/tests/security/cost/mobile")
    keys = ("ci", "tests", "security", "cost", "mobile")
    states = {k: checks.get(k, "UNKNOWN") for k in keys}
    if any(v not in ("PASS", "HOLD", "FAIL", "SKIP", "UNKNOWN") for v in states.values()):
        raise ValueError("Unsupported release status")
    verdict = "FAIL" if "FAIL" in states.values() else (
        "PASS" if all(x == "PASS" for x in states.values()) else "HOLD")
    return {"verdict": verdict, "evidence": payload({"revision": revision, "checks": states,
            "scope": "engineering-readiness-only", "release_authorized": False,
            "unverified": [k for k, v in states.items() if v != "PASS"]})}
