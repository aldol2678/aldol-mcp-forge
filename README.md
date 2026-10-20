# ALDOL MCP Forge v0.4.0 🔧

**New: declarative tool-contract scaffolds for specialized MCP servers.** Existing
curated templates and OpenAPI GET workflows are preserved.

## v0.4 Contract workflow (implementation deliberately NOT generated)

Provide a single JSON object with a tools array. Each tool has name,
description, inputs (name, type, required, optional description), and
output_schema (a closed JSON Schema object with scalar properties).
Supported scalar types: string, integer, number, boolean.
Limitations: 1..12 tools, 0..12 inputs per tool, 1..20 output properties,
120000-character max JSON; no nested / referenced schemas or executable handlers.

For example use examples/seum-mcp-contract.json,
examples/bonsae-mcp-contract.json, examples/majung-mcp-contract.json.

- forge_preview_contract(contract_json): validate and preview, no writes
- forge_create_contract(project_name, contract_json, isolation="auto"):
  generate immutable Python MCP SDK v2 project with contract.json,
  source checksums and a manifest, then test compatibility transport
- forge_test(project_name): verify compiler parity and that every scaffold
  handler rejects with NOT_IMPLEMENTED. It does NOT verify an implementation.
- forge_package(project_name): ZIP the trusted source and contract;
  no deployment, external calls or implementation
- Generated handlers fail closed with NOT_IMPLEMENTED until a developer
  deliberately implements, reviews and tests them. The declared output
  schema is documentation until then, not enforced runtime output validation.

**Production Sites Forge Studio is unchanged.** The newly created tools are
available only when running an updated local Forge entrypoint. They are NOT
yet exposed by the deployed ChatGPT Sites adapter. The official SDK button
in draft PR #8 is a separate workstream; scaffold compatibility checks are
not an SDK execution PASS.

## v0.3.2 previously verified baseline

**자연어 템플릿 + OpenAPI에서 MCP 서버 소스코드를 생성하는 로컬 제작기.**
외부 서비스에 등록하거나 자동 배포하지 않습니다. Python 3.11+ 필요.

## 현재 검증 상태 (v0.3.2 · 2026-10-20)

- 공개 저장소: [aldol2678/aldol-mcp-forge](https://github.com/aldol2678/aldol-mcp-forge), `main` 커밋 `769bd658adb3c041aee4d17d3bbf6a1820c289d4`.
- 공식 GitHub Actions [run 39315805343](https://github.com/aldol2678/aldol-mcp-forge/actions/runs/39315805343): 두 작업 모두 **success**.
- 오프라인 회귀: **26 tests, 25 passed, 1 skipped** (Python 3.12, Ubuntu 24.04). `OK (skipped=1)`은 26건 전부 개별 PASS와 다릅니다.
- 공식 Python MCP SDK `mcp==2.0.0`: 생성 예제 `aldol-openapi-pets`와 `aldol-game-html-audit`의 인메모리 및 stdio 도구 조회·호출 **2/2 예제 PASS**. 테스트 환경에서는 외부 API 요청을 비활성화했습니다.
- CI 증거: [SDK results artifact](https://github.com/aldol2678/aldol-mcp-forge/actions/runs/39315805343/artifacts/12217900746), 만료 예정 2026-11-02 UTC. 로그는 해당 Actions run에서 확인할 수 있습니다.
- 검증 **범위 밖**: ChatGPT/Claude 실제 클라이언트 연결, 임의의 제3자 MCP 코드 격리, 실제 운영 API 호출, 완전한 보안 샌드박스.
- **Forge 자체**의 `forge.py`는 경량 stdio JSON-RPC 런타임이며 아직 공식 SDK 기반으로 전환하지 않았습니다. 공식 SDK PASS는 *Forge가 생성한 예제 서버*에 관한 결과입니다.

과거 버전(v0.3/v0.3.1)의 미검증 기록은 아래에 역사적 맥락으로 남겨두었습니다. **현재 결론은 이 절을 우선**해 주세요.

## v0.3.2 공식 SDK 2.0.0 호환 수정 (2026-10-20)

- 생성 도구의 반환 타입을 `dict[str, Any]`로 지정해 구조화 응답을 보장하고, 기존 CI 프로젝트와 체크섬을 재생성했습니다.
- stdio 검증 연결을 `Client(stdio_client(params), raise_exceptions=True)`로 수정했습니다.
- `workspace/projects`를 추적 가능하게 하고 `ci-results/`를 제외해 CI 대상 누락을 방지했습니다.

## v0.3.1 공식 SDK 검증기 보강 (2026-10-20)

- `verify_sdk.py`를 실제 **MCP Python SDK v2**의 `Client(app)` 인메모리 및 `Client(StdioServerParameters(...))` stdio 두 연결 모드로 검증하도록 개선했습니다.
- 도구 발견, 호출, 구조화 응답, OpenAPI dry-run/외부 요청 미발생 조건을 각각 확인합니다. 외부 API 호출 환경변수는 강제로 비활성화합니다.
- SDK 미설치 또는 v1인 경우 **실연동 PASS로 둔갑시키지 않도록** `passed: false`, 종료 코드 `2`를 반환합니다. 검증 실패는 종료 코드 `1`, 통과는 `0`입니다.
- 기존 오프라인 호환 테스트와 실제 SDK 검증은 **서로 다른 검증**입니다.
- **당시 v0.3.1 생성 환경**에서는 공식 SDK를 설치할 수 없어 실연동이 미검증이었습니다. 이후 v0.3.2의 GitHub Actions에서 생성 서버 검증을 완료했습니다. 현재 상태는 문서 맨 위 절을 참조하세요.

SDK가 설치 가능한 신뢰된 개발 환경에서 (`pip install 'mcp>=2,<3'`):

```bash
python verify_sdk.py workspace/projects/aldol-openapi-pets --mode both
python verify_sdk.py workspace/projects/aldol-game-html-audit --mode both
```

단, 위 `verify_sdk.py`는 생성된 `server.py`를 import/실행하므로 **신뢰하는 프로젝트에 대해서만** 실행하세요.

## v0.3 변경점

1. **OpenAPI 3.0/3.1 JSON → MCP GET 도구**: API 문서를 붙여 넣으면 `operationId`마다 공식 Python MCP SDK v2용 `@app.tool()` 함수를 생성합니다. 최대 12개 GET, 인라인 경로·쿼리 매개변수의 문자열/정수/불리언 타입만 지원합니다. 모든 POST/PUT/PATCH/DELETE 등은 제외합니다.
2. **안전한 기본 모드**: 생성된 GET 도구를 호출해도 실제 API에 요청하지 않고 경로와 매개변수를 반환하는 `dry_run`이 기본입니다. 명시적으로 공개 HTTPS 기반 URL과 같은 호스트 허용값을 *모두* 제공했을 때만 원격 GET을 허용합니다. 리다이렉트, 비공개 주소, 일반 HTTP, 응답 크기 초과를 차단합니다. 인증은 아직 지원하지 않습니다.
3. **일관된 패키징·검증**: 스펙/소스의 SHA-256, 재생성 결과, 심볼릭 링크 및 예기치 않은 파일 검사. 신규 프로젝트는 임시 디렉터리에서 검증한 다음 생성합니다. Linux namespace 가용 시 네트워크 차단/읽기 전용 바인드 마운트; 불가하면 일반 자원 제한 프로세스로 폴백합니다. `strict` 모드는 격리가 불가능하면 거부합니다.
4. **회귀 수리**: 기존 v0.2.1 이상 패키지에서 `requirements.txt`가 누락되던 문제를 수정했습니다. v0.1에서 v0.2로 이어진 기존 프로젝트와 도구 추가 기능은 그대로 유지했습니다.
5. **실 SDK 검증 절차 강화**: v0.3 시점에는 `verify_sdk.py`를 OpenAPI형에도 적용했지만 SDK 미설치로 미검증이었습니다. 이후 v0.3.2에서 실제 SDK v2 연동이 확인됐습니다. 별도의 경량 호환 테스트와 혼동하지 마세요.

## 로컬 실행

```bash
python3 forge.py
python3 -m unittest discover -s tests -v
python3 examples/run_openapi_demo.py
```

실제 클라이언트에서 이 Forge 자체를 stdio 서버로 실행하려면 MCP 서버 설정에 아래 항목을 등록하세요. 파일 경로는 사용자 환경의 절대 경로로 바꿔야 합니다.

```json
{
  "mcpServers": {
    "aldol-mcp-forge": {
      "command": "python3",
      "args": ["/ABSOLUTE/PATH/aldol-mcp-forge/forge.py"]
    }
  }
}
```

Forge 자체는 기능이 제한된 stdio JSON-RPC 경량 런타임을 계속 사용합니다. **Forge 서버 자체가 공식 SDK 서버로 이전된 것은 아닙니다.**

## 도구: 기존 8개 + 신규 2개

| 도구 | 기능 |
|---|---|
| `forge_list_templates` | 기존 3개 읽기 전용 템플릿 조회 |
| `forge_preview` | 자연어 템플릿 매칭 |
| `forge_create` | 기존 HTML/JSON/텍스트 도구 프로젝트 생성 |
| `forge_add_tool` | 기존 큐레이션 프로젝트에 안전한 도구 추가 및 백업 |
| `forge_test` | 프로젝트 소스 무결성 및 호환 스모크 테스트. SDK 설치 시 인메모리 검증 |
| `forge_package` | 로컬 ZIP 작성. 동일 버전 덮어쓰기 방지 |
| `forge_preview_openapi` | OpenAPI 3 JSON의 지원 GET·제외 작업 미리보기 |
| `forge_import_openapi` | `project_name`, `spec_json`, 선택적 `isolation`로 새 OpenAPI GET 프로젝트 생성 |
| `forge_preview_contract` | JSON 계약 미리보기 및 안전성 검증(읽기 전용) |
| `forge_create_contract` | JSON 계약으로 미구현 MCP SDK v2 골격 생성(호출 시 NOT_IMPLEMENTED) |

예제 JSON은 `examples/pets_openapi.json`에 있습니다. 그대로 `forge_preview_openapi`나 `forge_import_openapi`의 `spec_json` 값으로 전달할 수 있습니다. Swagger/OpenAPI의 YAML, 서버 URL 직접 가져오기, `$ref`/요청 바디/고급 parameter encoding/인증/쓰기 작업 자동 생성은 지원하지 않습니다.

## 공식 SDK 직접 연동 검사 (SDK 설치된 환경)

```bash
python3 -m pip install 'mcp>=2,<3'
python3 verify_sdk.py workspace/projects/aldol-openapi-pets
python3 workspace/projects/aldol-openapi-pets/server.py
```

공식 Python SDK v2 문서: https://py.sdk.modelcontextprotocol.io/v2/

## 네트워크/보안 제한

생성된 도구는 기본으로 `dry_run`입니다. 실제 읽기 요청을 허용하려면 생성된 프로젝트의 서버 프로세스 환경에서 아래 값을 설정해야 합니다. 실제 API의 주소를 정확히 알고 신뢰할 때에만 수행하세요.

```bash
ALDOL_API_BASE_URL='https://api.example.com/v1'
ALDOL_API_ALLOWED_HOST='api.example.com'
```

실제 연결 모드에서는 공개 IP로 해석되는 HTTPS:443 목적지만 허용하고 리다이렉트 없이 JSON 응답을 제한 크기 내에서 수신합니다. **DNS 재바인딩·프록시 환경을 완전하게 격리하는 보안 경계는 아니며, OAuth/API 키는 구현되지 않았습니다.** 외부 실행은 실제 사용자가 별도 승인·설정해야 합니다. 임의의 신뢰할 수 없는 코드나 OpenAPI 문서를 운영 환경에 곧바로 배포하면 안 됩니다.

## v0.3 최초 검증 기록 (2026-10-19 · 역사적 참고)

아래는 **v0.3 초기 검증 당시의 스냅샷**이며, 위의 v0.3.2 CI 실연동 결과가 현재 기준입니다.

- 로컬 자동화 회귀 **22/22 PASS**.
- OpenAPI GET 2도구 생성·호출, POST 제외, 경로 값 인코딩 및 타입 검증 PASS.
- 격리 모드에서 프로젝트 읽기 전용·네트워크 차단 검증 PASS.
- `v0.2.x` 프로젝트 승계·패키징 회귀 PASS.
- 당시 MCP Python SDK v2와 Inspector, Claude/ChatGPT 클라이언트 실연동 **미검증** (SDK 미설치). 이후 v0.3.2에서 SDK로 생성 예제를 검증했지만 Inspector·실제 클라이언트는 여전히 미검증.
- 완전한 샌드박스·운영 API 라이브 요청 시험 **미검증**.

v0.3 당시 결과를 `examples/verification_v03.json`에 저장했습니다. 당시에는 GitHub 업로드도 하지 않았으나, v0.3.2는 현재 공개 저장소로 운영 중입니다. 운영 배포는 실행하지 않았습니다.
