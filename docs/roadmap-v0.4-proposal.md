# ALDOL MCP Forge v0.4 후보 마일스톤 (설계 초안)

> 상태: **PROPOSAL / 미채택**. 현재 공식 구현 기준은 `main`의 v0.3.2.
> 이 문서는 다음 개발 범위와 검증 기준을 명확히 하기 위한 계획이며 구현 완료를 뜻하지 않습니다.

## 배경 / 확인된 사실

- [v0.3.2 Actions run 39315805343](https://github.com/aldol2678/aldol-mcp-forge/actions/runs/39315805343)에서 공식 Python MCP SDK 2.0.0을 설치하여 생성 서버 예제 2개에 대해 인메모리 및 stdio 검증이 성공했습니다.
- 회귀 테스트는 26건 실행 중 25 PASS, 1 SKIP으로 완료됐습니다.
- 그러나 Forge 자체 `forge.py`는 아직 독자적인 경량 stdio JSON-RPC 처리기를 사용합니다.
- Forge 자체를 ChatGPT/Claude/Cursor에 실제로 설치하고 사용한 결과는 아직 확인되지 않았습니다.

## 목표

**M0 (v0.4 핵심): Forge 자체를 공식 MCP Python SDK v2 기반 stdio 서버로 전환하고 생성 도구까지 end-to-end 검증합니다.** 외부 배포나 인증 기능 확장은 이 마일스톤의 필수조건이 아닙니다.

## 작업 범위

1. **기존 계약 고정**: 현행 8개 공개 도구의 이름·JSON 스키마·예상 결과를 테스트로 기록합니다. 이전 클라이언트 구성과의 차이 및 마이그레이션 경로를 문서화합니다.
2. **SDK 런타임 전환**: `forge.py`의 자체 JSON-RPC 처리기를 공식 SDK `MCPServer`/stdio로 이관합니다. 기존 템플릿·OpenAPI 생성 엔진·검증·백업 경계는 변경하지 않습니다.
3. **실제 호출 검증**: 클라이언트가 Forge의 `tools/list` 및 `forge_list_templates`, `forge_preview_openapi`, `forge_import_openapi`, `forge_test` 등을 실제로 호출합니다. 생성한 프로젝트는 공식 SDK로 인메모리 및 stdio 각각 검증합니다.
4. **비파괴 검사**: 작업공간 바깥 경로 쓰기 거부, 선언되지 않은 파일 변경 차단, ZIP 무결성 검증, 중복 프로젝트 방어, 외부 네트워크 비사용을 회귀로 검사합니다.
5. **CI 및 문서 보강**: 새 Forge-runtime 검증 job 추가 또는 기존 CI에 별도 단계로 추가. 로컬 회귀와 공식 SDK 검증은 서로 다른 상태로 보고하며, 스킵은 PASS로 계산하지 않습니다.

## 검증 완료 기준

- [ ] 공식 Python SDK v2 설치 상태에서 Forge 자체의 stdio 초기화 성공
- [ ] 현재 8개 도구 전부 `tools/list`에 노출됨 (명세/스키마 일치)
- [ ] 주요 읽기/생성/검증 동작을 실제 `tools/call`로 호출해 기대 결과 확인
- [ ] v0.3.2 회귀 테스트 결과 악화 없음; 스킵·실패 원인 개별 표시
- [ ] 생성된 `aldol-game-html-audit` 및 `aldol-openapi-pets`의 SDK in-memory/stdio 검증 성공
- [ ] 테스트에서 시크릿 유출·외부 API 전송·프로덕션 배포 없음
- [ ] README/설치 가이드/Actions 링크가 현재 확인된 실행 상태와 일치

## 보류 사항 (v0.4 밖)

- OpenAPI 인증(API key, OAuth), POST/PUT/PATCH/DELETE 자동 생성
- 원격 MCP 호스팅, ChatGPT/Claude 실제 설치, 플러그인 공개 배포
- 임의의 제3자 MCP 코드 실행 및 완전한 격리 샌드박스 구현
- 자동 커밋·병합·릴리스·공식 채택

## 실패 시 처리

공식 SDK 통합 테스트 실패 시 기존 8도구 사용 가능성과 원인을 분리해 보고합니다. 기존 v0.3.2 동작을 보존하고, 검증 완료 전에는 버전을 정식 릴리스로 승격하지 않습니다.
