# Forge 공식 SDK v2 진입점 (v0.4 후보)

> STATUS: **SDK 진입점 통합 후보 (정식 v0.4 릴리스 아님)**. 코드 반영 여부는 [PR #2](https://github.com/aldol2678/aldol-mcp-forge/pull/2), 정식 릴리스 여부는 저장소 릴리스 기록을 기준으로 판단하세요. 기존 `forge.py` 동작은 보존됩니다.

## 무엇이 바뀌었나

- `forge_sdk.py`: 공식 Python MCP SDK v2 `MCPServer`로 Forge 자체의 8개 도구를 노출하는 stdio 서버.
- `ci/verify_forge_sdk.py`: 공식 SDK v2 클라이언트에서 in-memory와 자식 프로세스 stdio를 각각 시험합니다. 목록, 미리보기, 실제 로컬 생성/검증/패키징과 OpenAPI dry-run까지 포함합니다.
- 인자 호환성: SDK 2.0.0은 기본 동작에서 알 수 없는 추가 인자를 무시하므로, **도구 호출만 대상으로 하는 거부 전용 미들웨어**로 이전 Forge의 추가 인자 거부를 보존합니다. 스키마의 필수값/길이/허용값은 Pydantic Field와 Literal로 정의했습니다. 미들웨어 인터페이스는 SDK에서 잠정적이므로 이후 SDK 버전 업그레이드 시 재검증이 필요합니다.
- 실행 실패: 사용자 입력이나 기존 프로젝트 중복·누락 등의 예상 가능한 오류는 ToolError로 반환합니다. 예상 밖 예외는 SDK의 기본 오류 은닉을 유지합니다.
- `ALDOL_FORGE_WORKSPACE_ROOT`: CI 또는 개발자가 **명시적으로** 설정하면 기존 루트 대신 해당 절대 경로에서 프로젝트/백업/ZIP을 생성할 수 있습니다. 이 환경 변수는 *sandbox 정책이 아닙니다*. 폴더는 미리 존재해야 합니다.
- 기존 `forge.py`의 경량 호환 런타임은 이번 통합에서도 제거하거나 교체하지 않습니다.

## 설치 및 실행

신뢰할 수 있는 개발 환경의 Python 3.11 이상에서:

```bash
python -m pip install "mcp==2.0.0"
python forge_sdk.py
```

예시 MCP 클라이언트 설정(로컬 파일 절대 경로로 교체):

```json
{
  "mcpServers": {
    "aldol-mcp-forge": {
      "command": "python3",
      "args": ["/ABSOLUTE/PATH/aldol-mcp-forge/forge_sdk.py"]
    }
  }
}
```

Forge의 `forge_create`, `forge_add_tool`, `forge_import_openapi`, `forge_package`는 **로컬 파일을 생성/수정**합니다. 클라이언트에서 실행하기 전에 대상 작업공간과 승인 범위를 확인하세요. 호스트에 대한 권한 격리 기능을 제공하는 것으로 간주하면 안 됩니다.

## CI 완료조건

- PR 전용 CI에서 오프라인 회귀, 기존 생성 서버 2종의 공식 SDK v2 실검증, Forge 자체의 공식 SDK v2 통합 검증이 모두 성공해야 합니다.
- 공식 SDK 엔드포인트는 Forge 자체 8개 도구를 목록으로 제공하고, 미리보기/생성/테스트/패키징을 실제 호출해야 합니다.
- 임시 작업공간을 사용해야 하며, 원격 API 호출/외부 배포/시크릿 접근 없이 실행해야 합니다.
- CI가 실패하면 해당 PR은 **미검증** 상태로 유지합니다. 기존 v0.3.2 성공 기록을 v0.4의 증거로 돌려쓰지 않습니다.

## 남은 범위

- 노출된 JSON Schema의 표현상 차이(예: Pydantic 제목·기본값·additionalProperties 표기)는 호환성 테스트 및 마이그레이션 문서로 추적. 실제 미등록 인자 거부는 도구 호출 레벨에서 검사
- 실제 ChatGPT/Claude/Cursor 클라이언트 설정 검증
- 예외 처리/오류 응답 및 격리 보증의 안정화
- 기존 `forge.py` 엔트리포인트의 공식 교체 여부를 결정하고, 문서의 설치 경로 통합

이 구현을 병합하더라도 **공식 v0.4 버전 릴리스·배포와 동일하지 않습니다**.
