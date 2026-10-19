# ALDOL MCP Forge v0.3.1 — GitHub Actions 실연동 검증 키트

이 패키지는 **ALDOL MCP Forge v0.3.1 원본**과 GitHub Actions 검증 파일을 함께 포함합니다.
이번 키트 자체는 MCP 기능을 새로 릴리스한 것이 아닙니다.

## 최초 실행

1. GitHub에 **별도 Private 저장소** `aldol-mcp-forge`를 만듭니다. ARAM MCP·ARAM Forge 저장소와 혼동하지 마세요.
2. 이 ZIP의 **압축 해제된 루트 파일들**을 새 저장소 `main`에 업로드합니다.
   `.github/workflows/verify-mcp-sdk.yml` 파일까지 포함해야 합니다.
3. GitHub → **Actions** → `ALDOL MCP Forge - official SDK v2 verification`을 열어 실행 결과를 확인합니다.
   첫 main 푸시 때 자동 시작하거나, **Run workflow**로 수동 실행할 수 있습니다.
4. 두 작업(offline-regression, sdk-integration)이 성공해야 최종 PASS입니다.
   상세 JSON은 run → Artifacts → `official-sdk-v2-results`에서 받을 수 있습니다.

## 실행 계약

- `ubuntu-24.04` · Python 3.12 · `mcp==2.0.0` (공식 PyPI stable v2)
- `permissions: contents: read`, API 환경변수 공백, 읽기 전용 dry-run.
- 26개 오프라인 회귀 테스트 + 실제 SDK v2 `Client(server)` 및 별도 stdio 프로세스
- 테스트 대상: `aldol-openapi-pets`, `aldol-game-html-audit`
- 서버의 MCP 도구 조회, 실제 호출, OpenAPI 외부 요청 미발생 점검
- 결과를 JSON으로 저장하고 실패 시 Actions를 FAIL 처리
- 기존 저장소 변경·배포·비밀키 등록·API 쓰기 호출 없음

## 검증 경계

현재 이 파일 자체를 GitHub에 업로드하거나 Actions에서 실행한 것은 아닙니다.
로컬 26개 자동화 테스트는 통과했습니다.
실제 SDK 확인은 GitHub의 결과를 확인해야만 완료 상태로 승격합니다.

보안상 외부에서 받은 미검증 MCP 코드를 이 워크플로에 자동 투입하지 마세요.
일반 GitHub-hosted runner가 완전한 격리 보안 경계는 아닙니다.

## 로컬 실행

```bash
python -m unittest discover -s tests -v
python -m pip install "mcp==2.0.0"
python ci/run_official_sdk.py
```
