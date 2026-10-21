# ALDOL UI MCP Alpha 0.3.2 검증 (2026-10-21)

## Source
- Library `ALDOL-UI-MCP-Alpha-0.3.1-Anti-Slop.zip` 원본에서 분기하여 패치. 원본 버전 보존.
- `ui_core/anti_slop.py` 기존 10개 규칙 + 2개 신규 규칙 및 waiver 통합.
- `ui_core/core.py`에 `review_markup()` 인터페이스 추가, 기본 notice border-left 제거.
- `ui_core/server.py`에 MCP 도구 `ui_review_markup` 추가; 기존 6개 도구 유지.
- 기존 UI spec 0.1/0.2/0.3 지원 유지.

## Tested
- `python -m unittest discover -s tests -q`: **68/68 PASS** (기존 59 + 신규 9).
- `python tests/browser_03.py`: **8/8 PASS** (web/game, 360/390/768/1280).
- `python -m compileall -q ui_core tests`: **PASS**.
- CLI strict mode renders: web-html, game-hud-html, react-tsx **PASS**.
- `ui_review`의 새 headline rule high → enforce 차단; 사유가 있는 예외는 허용.
- `ui_review_markup`에서 CSS 왼쪽 강조선 중복 2개 high + 선언형 제목 1개 high 검출.

## Unverified / blocked
- Official Python MCP SDK 2.x unavailable in this runtime, pip DNS resolution failed, thus live SDK tool discovery/invocation NOT TESTED.
- No deployed UI MCP endpoint discovered in accessible connected services; other ALDOL services unchanged.
- Native Android devices and actual production React runtime not tested.
- No WCAG certification or aesthetic quality guarantee.
- GitHub PR/merge and live deployment are separate from this local test record.

## Security
- HTML source passed to static parser, no execution. Inputs limited to 120000 characters; waiver input limited 6000 chars and validated.
- Existing no arbitrary JS/CSS-in-spec policy retained.
