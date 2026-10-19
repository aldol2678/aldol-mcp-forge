# Forge 공식 SDK v2 진입점 (v0.4 후보)

> STATUS: **CANDIDATE / 미병합·미출시**. v0.3.2의 기존 `forge.py` 동작은 보존됩니다.

## 무엇이 바뀌었나

- `forge_sdk.py`: 공식 Python MCP SDK v2 `MCPServer`로 Forge 자체의 8개 도구를 노출하는 stdio 서버.
- `ci/verify_forge_sdk.py`: 공식 SDK v2 클라이언트에서 in-memory와 자식 프로세스 stdio를 각각 시험합니다. 목록, 미리보기, 실제 로컬 생성/검증/패키징과 OpenAPI dry-run까지 포함합니다.
- `ALDOL_FORGE_WORKSPACE_ROOT`: CI 또는 개발자가 **명시적으로** 설정하면 기존 루트 대신 해당 절대 경로에서 프로젝트/백업/ZIP을 생성할 수 있습니다. 이 환경 변수는 *sandbox 정책이 아닙니다*. 폴더는 미리 존재해야 합니다.
- 기존 `forge.py`의 경량 호환 런타임은 v0.4 검증 완료 전까지 그대로 남아 있습니다.

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

- 입력 JSON Schema가 기존 경량 런타임과 필드 수준에서 일치하는지 검증 (SDK 타입 힌트에서 생성하는 스키마 차이 분석 포함)
- 실제 ChatGPT/Claude/Cursor 클라이언트 설정 검증
- 예외 처리/오류 응답 및 격리 보증의 안정화
- 기존 `forge.py` 엔트리포인트의 공식 교체 여부를 결정하고, 문서의 설치 경로 통합

이번 PR은 **실제 릴리스가 아니라 검증 가능한 구현 후보**입니다.
