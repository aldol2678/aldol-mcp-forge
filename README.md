# ALDOL MCP Forge v0.3.1 🔧

**자연어 템플릿 + OpenAPI에서 MCP 서버 소스코드를 생성하는 로컬 제작기.**
외부 서비스에 등록하거나 자동 배포하지 않습니다. Python 3.11+ 필요.

## v0.3.1 공식 SDK 검증기 보강 (2026-10-20)

- `verify_sdk.py`를 실제 **MCP Python SDK v2**의 `Client(app)` 인메모리 및 `Client(StdioServerParameters(...))` stdio 두 연결 모드로 검증하도록 개선했습니다.
- 도구 발견, 호출, 구조화 응답, OpenAPI dry-run/외부 요청 미발생 조건을 각각 확인합니다. 외부 API 호출 환경변수는 강제로 비활성화합니다.
- SDK 미설치 또는 v1인 경우 **실연동 PASS로 둔갑시키지 않도록** `passed: false`, 종료 코드 `2`를 반환합니다. 검증 실패는 종료 코드 `1`, 통과는 `0`입니다.
- 기존 오프라인 호환 테스트와 실제 SDK 검증은 **서로 다른 검증**입니다.
- 이 작업 환경에서는 공식 SDK를 설치할 수 없어 SDK 자체를 통한 연결은 **미검증**입니다. 공식 SDK 문서와의 정적 대조 및 기존 오프라인 회귀 시험만 수행했습니다.

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
5. **실 SDK 검증 절차 강화**: `verify_sdk.py`를 OpenAPI형에도 적용했습니다. **현재 환경에 공식 Python `mcp` 패키지가 없어 실제 SDK 연동은 실행하지 않았으며 미검증입니다**. 별도의 경량 호환 테스트와 혼동하지 마세요.

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
      "args": ["/ABSOLUTE/PATH/aldol-mcp-forge-v0.3/forge.py"]
    }
  }
}
```

Forge 자체는 기능이 제한된 stdio JSON-RPC 경량 런타임을 계속 사용합니다. **Forge 서버 자체가 공식 SDK 서버로 이전된 것은 아닙니다.**

## 도구 총 8개

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

## 검증 상태 (2026-10-19)

- 로컬 자동화 회귀 **22/22 PASS**.
- OpenAPI GET 2도구 생성·호출, POST 제외, 경로 값 인코딩 및 타입 검증 PASS.
- 격리 모드에서 프로젝트 읽기 전용·네트워크 차단 검증 PASS.
- `v0.2.x` 프로젝트 승계·패키징 회귀 PASS.
- 실제 MCP Python SDK v2, Inspector, Claude/ChatGPT 클라이언트 실연동 **미검증** (SDK 미설치).
- 완전한 샌드박스·운영 API 라이브 요청 시험 **미검증**.

결과를 `examples/verification_v03.json`에 저장했습니다. 개인 플러그인 설치, GitHub 업로드, 프로덕션 배포를 하지 않았습니다.
