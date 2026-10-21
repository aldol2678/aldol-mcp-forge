# ALDOL UI MCP Alpha 0.3.2 · Anti-AI-Slop Patch

웹/브라우저 게임 HUD/React 소스가 함께 사용하는 **선언형 UI JSON 엔진**의 로컬 품질 패치.

**상태:** 로컬 소스·브라우저 미리보기 패키지. 공식 MCP SDK 클라이언트 연결/Forge 반영/GitHub 배포/실제 게임 엔진 연결은 하지 않았습니다.

## 이번 패치

- 기본 UI 스타일의 그림자·유리 효과·장식용 그라디언트 감소, 보다 절제된 타이포그래피/간격/배지·버튼 모양.
- `ui_review`: 구조적인 디자인 슬롭 검사, 발견 경로/근거/수정 지침/예외 사유 제공. **점수로 미학을 단정하지 않음.**
- `ui_audit`에 `anti_slop` 결과 포함, `ui_generate`에서 선택적 `quality_mode="enforce"` 지원.
- 기존 문서 **v0.1·v0.2·v0.3 유지**, `design`(고유 UI 방향)·`data_mode`(데모/외부 연결 선언) 선택 속성 지원.
- 샘플 웹 대시보드의 반복 카드/홍보 카피·게임 HUD 버튼 장식 문자 제거. 두 샘플 모두 엄격 모드 통과.
- 기존 12 컴포넌트, 3개 출력 대상과 동작, 폰트·레이아웃·상태 변경 API 보존.

**중요:** `quality_mode="advisory"`가 기본. `enforce`는 높은 심각도의 미해결 지적을 발견하면 생성하지 않으며 기존 파일은 덮어쓰지 않습니다. 예외는 출처와 이유를 기록합니다.

## 도구 (정의 7개)

`ui_catalog`, `ui_presets`, `ui_validate`, `ui_audit`, **`ui_review`**, **`ui_review_markup`**, `ui_generate`.

`ui_review` 반환값은 `status`/`context`/`findings`/`waived`/`counts`/`human_review_required`를 포함합니다.

## 실행

```bash
python -m unittest discover -s tests -q
python tests/browser_03.py  # Playwright + Chromium 설치 환경
python -m ui_core.cli examples/web-dashboard.json --target web-html --quality-mode enforce --out /tmp/aldol-ui-web-reviewed
python -m ui_core.cli examples/expedition-hud-v03.json --target game-hud-html --quality-mode enforce --out /tmp/aldol-ui-game-reviewed
python -m ui_core.cli examples/web-dashboard.json --target react-tsx --quality-mode enforce --out /tmp/aldol-ui-react-reviewed
```

기존 경로의 완전한 사용법은 `docs/ARCHITECTURE.md`, 안티 슬롭 세부 규칙/예외는 [docs/ANTI_AI_SLOP.md](docs/ANTI_AI_SLOP.md) 참고.

## 출력 및 검증 범위

- `web-html`: 단독 HTML/CSS/JS 미리보기.
- `game-hud-html`: 실제 게임 동작이 아니라 DOM HUD + 장식용 전장 데모.
- `react-tsx`: TSX/CSS 소스 생성, TypeScript 문법 변환 점검. React 실제 앱 빌드 미수행.
- Python MCP SDK v2는 이 환경에서 설치되지 않아 도구 발견/호출 테스트 미실시. **MCP 런타임 연동 완료가 아닙니다.**

외부 URL 로딩, 계정 연동, 호스트의 명령 실행, 저장소 변경은 수행하지 않습니다.

## v0.3.2 패치

- `decorative-accent-rail`(HTML/CSS), `sloganized-declarative-headline`(선언형 JSON·HTML) 두 규칙 추가.
- `ui_review_markup`으로 외부 HTML 스니펫을 **실행하지 않고 정적 검사**.
- 렌더러 기본 안내 카드의 세로 장식선을 제거.
- 이번 소스는 검증 패키지이며 MCP 클라이언트 원격 연결·운영 배포 완료를 의미하지 않음.
