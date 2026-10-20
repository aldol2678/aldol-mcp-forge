"""Generate differential cases by running the unchanged Python Forge handlers.

Development/CI only. This file is never part of the deployed Worker artifact.
"""
import copy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
import forge
from mcp_runtime import _validate

cases = []
SCHEMAS = {
    "forge_list_templates": forge._schema(()),
    "forge_preview": forge._schema(("description",)),
    "forge_preview_openapi": forge._schema(("spec_json",)),
}
HANDLERS = {"forge_list_templates": lambda a: forge.TEMPLATE_INFO,
            "forge_preview": forge._preview,
            "forge_preview_openapi": forge._preview_openapi}


def case(label, name, args):
    try:
        _validate(SCHEMAS[name], args)
        result = {"output": HANDLERS[name](args)}
    except (ValueError, RuntimeError) as error:
        result = {"error": str(error)}
    cases.append({"label": label, "name": name, "args": args, **result})


case("templates", "forge_list_templates", {})
for i, text in enumerate([
    "HTML 게임 검사", "JSON 검사", "텍스트 길이", "단어", "문장", "글자",
    "웹 게임", "웹게임", "웹페이지", "WEBPAGE", "Web Game", "Word count",
    "제이슨 검사", "json html text", "JSON text", "자동 결제 구현", "셸 실행",
    " ", "\u0085\u001c", "\ufeff", "jſon", "🐈" * 1996 + "html",
    "🐈" * 1997 + "html", "x" * 2000, "x" * 2001,
]):
    case(f"preview-{i}", "forge_preview", {"description": text})
for name in SCHEMAS:
    for i, args in enumerate([None, [], "bad", 1, {"unrecognized": "x"},
                              {"__proto__": {}}, {"constructor": "x"}]):
        case(f"arguments-{name}-{i}", name, args)
for i, args in enumerate([{}, {"description": ""}, {"description": 3},
                           {"description": None}, {"description": True},
                           {"description": "html", "a": 1, "b": 2}]):
    case(f"preview-schema-{i}", "forge_preview", args)

spec = {"openapi": "3.1.0", "info": {"title": "Test"},
        "paths": {"/pets": {"get": {"operationId": "listPets"}}}}


def api(label, value):
    case(label, "forge_preview_openapi", {"spec_json": json.dumps(value, ensure_ascii=False)})


api("basic", spec)
case("example-pets", "forge_preview_openapi",
     {"spec_json": (ROOT / "examples/pets_openapi.json").read_text()})
for version in ["3.0.0", "3.1.10", "3.2.0", "2.0", "3.1.0\n", 3, None]:
    api(f"version-{version!r}", {**spec, "openapi": version})
for value in [None, [], {}, "invalid", True]:
    api(f"doc-{value!r}", value)
for value in [None, [], "text", 0]:
    api(f"info-{value!r}", {**spec, "info": value})
for value in [None, [], {}, {f"/p{i}": {} for i in range(65)}]:
    api(f"paths-{type(value).__name__}-{len(value) if value is not None else 0}", {**spec, "paths": value})
for path in ["/", "//example.com/x", "/../x", "/./x", "/a%2Fb", "/pets?x=1",
             "/a\\b", "/pets\n", "/x/{id", "/한글", "/a-b_c.d~1", "/a//b"]:
    api(f"path-{path!r}", {**spec, "paths": {path: spec["paths"]["/pets"]}})
for item in [None, [], {"$ref": "#/paths/x"}, {"post": {}}, {"get": None},
             {"get": {"$ref": "#/x"}}, {"get": {"operationId": "ok"}, "post": {}, "delete": {}}]:
    api(f"path-item-{len(cases)}", {**spec, "paths": {"/pets": item}})
for name in ["class", "async", "True", "_hidden", "bad-name", "x\n", "app", "sys",
             "MCPServer", "OPERATIONS", "call_operation", "Tool", "serve", "x" * 65,
             "constructor", "toString", "get_pets", "match", "case", None, 3]:
    api(f"operation-{name!r}", {**spec, "paths": {"/pets": {"get": {"operationId": name}}}})
for count in [12, 13]:
    api(f"op-count-{count}", {**spec, "paths": {
        f"/p{i}": {"get": {"operationId": f"op{i}"}} for i in range(count)}})
api("duplicate-operations", {**spec, "paths": {"/a": spec["paths"]["/pets"], "/b": spec["paths"]["/pets"]}})
parameter = {"in": "path", "name": "id", "required": True, "schema": {"type": "string"}}
def params_case(label, params, path="/pets/{id}", **extra):
    api(label, {**spec, "paths": {path: {"get": {"operationId": "getPet", "parameters": params}, **extra}}})
params_case("path-required", [parameter])
params_case("path-missing", [])
params_case("path-surplus", [parameter], path="/pets")
params_case("path-duplicate", [parameter, parameter])
params_case("inherited", [], parameters=[parameter])
params_case("inherited-duplicate", [parameter], parameters=[parameter])
for value in [None, {}, "bad", [None], [{"$ref": "#/x"}]]:
    params_case(f"params-shape-{len(cases)}", value)
for key, values in {
    "in": ["header", "cookie", None], "name": ["class", "bad-name", "id\n", None],
    "required": [False, 1, None], "schema": [None, {}, {"type": "object"}, {"type": "number"}, {"type": "string", "$ref": "#/x"}],
    "content": [{}], "style": ["simple"], "explode": [False], "allowReserved": [False],
}.items():
    for value in values:
        params_case(f"parameter-{key}-{value!r}", [{**parameter, key: value}])
for typ in ["string", "integer", "boolean"]:
    params_case(f"query-{typ}", [{"in": "query", "name": "q", "schema": {"type": typ}}], path="/pets")
params_case("thirteen-params", [{"in": "query", "name": f"q{i}", "schema": {"type": "string"}} for i in range(13)], path="/pets")
for text in ["{", "openapi: 3.1.0", "{}", "x" * 120001]:
    case(f"json-error-{len(text)}", "forge_preview_openapi", {"spec_json": text})
max_spec = json.dumps(spec)
case("spec-exact-max", "forge_preview_openapi", {"spec_json": max_spec + " " * (120000 - len(max_spec))})
print(json.dumps({"schemas": SCHEMAS, "cases": cases}, ensure_ascii=False))
