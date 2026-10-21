# ALDOL UI MCP Alpha 0.3 설계

`UI JSON 명세(0.1~0.3) → 파서/검증 → (스타일 토큰 + 12 UI 컴포넌트) → Web HTML / DOM Game HUD / React TSX`

### 계약

1. 명세 JSON은 실행 코드가 아님. 자유형 HTML, CSS, JS, 원격 URL을 입력으로 받지 않음.
2. `ui_generate`는 파일/코드 *생성*을 담당. 미리보기 전장은 시각 예제일 뿐 실제 게임 장면이 아님.
3. 콘텐츠 업데이트는 DOM에서 `textContent`와 유한 숫자 기반 진행률만 지원. 게임 자원/경제/권한은 호스트가 소유.
4. React 어댑터는 JSON을 안전한 JSX 콘텐츠로 렌더링하며 HTML 문자열 주입 API를 쓰지 않음. 선택적 `mode="hud"` 렌더링에는 상대 위치 부모가 필요.
5. UI 테마/버전은 검증된 키/값으로만 생성. 0.1, 0.2가 사용하는 기존 7개 컴포넌트는 그대로 받아들임. 신규 0.3 컴포넌트와 토큰은 버전 0.3에서만 사용.
6. HTML CSS는 `.alui-app` / `.alui-hud-overlay`로 스코프를 제한. React CSS는 두 스코프를 포함.
7. 패키지 작성/테스트는 운영환경, Forge, INHA WORLD를 변경하지 않음.

### 후속 연결 (설계만)

- MCP Forge: 로컬 MCP 소스 생성 및 JSON 규격 검사 자동화 후 공식 SDK stdio/HTTP 검증.
- Asset Factory: 검증된 이미지/아이콘 참조를 별도 에셋 참조 인터페이스로 전달. 외부 URL을 JSON에 직접 넣지 않기.
- Game Ops: 스크린샷 회귀, 시인성/터치 영역, 실기기 QA, 이벤트 라우팅 점검.
- 엔진 어댑터: Phaser/PixiJS/PlayCanvas 등에 공통 상태/이벤트 계약을 연결. 실제 2D Canvas/WebGL 네이티브 드로잉은 후속 개발.
