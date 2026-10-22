# ALDOL RIGHTS · 외부 웹사이트 법률문서 분석 모듈 (v0.4 Draft)

## 제품 목표
RIGHTS를 자신의 개인정보처리방침과 이용약관만 관리하는 도구에 한정하지 않고, **여러 사이트의 개인정보처리방침·이용약관을 찾아 검토하고 권한 있는 운영자가 수정하도록 돕는 MCP**로 확장한다.

기존 저작권 검사·자산 관리 기능은 별개의 Rights Asset 도메인으로 유지한다. PR #29의 RIGHTS 서비스 자체 약관 관리 기능은 하나의 내부 고객 사례이며 본 외부 사이트 분석 모듈로 대체되지 않는다.

## 경쟁 서비스 조사 및 차별화
- **iubenda**: 공개 URL 스캔, 개인정보·쿠키 정책 생성, 약관 생성, 임베드/자동 갱신. https://www.iubenda.com/en/scan/ https://www.iubenda.com/en/features/
- **Termly**: 개인정보·약관·쿠키·동의·DSAR 템플릿 및 관리. https://termly.io/
- **RIGHTS**: 한국 개인정보보호법 제30조/시행령 제31조 항목을 기준으로 *외부 사이트 발견 → 공개 문서 비교 → 확인되지 않은 사업 운영 사실 분리 → 수정 계획 → 승인된 저장소 PR* 워크플로를 노린다. 기존 제품과 차별화 가능성은 설계 가설이며 성과나 적법성을 보장하지 않는다.

## 이 Draft에서 실제로 구현한 것
- 기존 6개 MCP에 별도 **4개 읽기 전용 도구** 추가 (실제 배포 이전 코드 단계):
  - `site_policy_scan(url)`: 공개 HTTPS 시작 페이지에서 개인정보처리방침·이용약관 링크 탐색. 정적 HTML 최대 3페이지, 각 160KB. 검사 신호와 텍스트 발췌만 제공. 공개 링크 부재/실패 구분.
  - `site_policy_audit(kind,document_text,jurisdiction='KR')`: 법률 고지 관련 키워드 존재 여부 점검, 누락 가능성 표기. **완전성·준법 판정 절대 금지**.
  - `site_policy_patch_plan(kind,document_text,verified_facts_json='{}')`: 현장 운영자가 확인한 사실만 후보 조항에 대응; 미확인 사항은 정보 확인 필요로 남김. **원문 교체·외부 게시 없음**.
  - `site_policy_compare(before_text,proposed_text)`: 문서 버전 SHA256과 통합 diff, 무편집 확인.
- 웹 보조 화면: `#site-policies`, 로그인 사용자의 수동 텍스트 검토 + 스캐너 UI, JS 문법 검사.
- 웹 API: `/api/site-policy/audit`와 `/api/site-policy/scan` (기존 세션과 CSRF 헤더 필요).
- 내부 검증용 검사 엔진: 한국어·영어의 키워드 확인. KR 외 범용 GENERAL은 정확한 외국법 판정이 아님.
- 외부 사이트 권한이 없으면 **조사 및 개정 제안까지만 허용**. 실제 패치는 이미 연결된 GitHub/Google Drive 등에서 이용자 소유·권한을 확인한 후 별도 PR/승인을 통해 수행할 단계다.

## 보안
- 홈페이지 URL은 HTTPS, 443, ASCII DNS 도메인만 허용하며 IP·localhost·사설 이름·인증정보·쿼리·리다이렉트 거부.
- DNS 조회 결과가 전부 공인 IP인지 검증하고 특정 검증된 IP로 TCP를 연결, 원래 호스트네임으로 TLS 인증서를 검증한다. 매 페이지에 새 검증을 적용.
- 공개 HTML은 텍스트/링크로만 파싱, JS/CSS/iframe 실행·쿠키/기밀정보 전송·리디렉션/타 도메인 수집 없음.
- 대상 페이지 최대 3개, 개별 160KB, 요청 최대 18초. *프로덕션 사용량 제한과 배포 환경별 outbound 접근 보안 확인은 추가 필요*.
- 따라서 `RIGHTS_SITE_SCAN_ENABLED`가 `1`로 설정되지 않으면 웹/원격 스캔 도구는 **BLOCKED**이며 붙여넣은 본문의 오프라인 검토만 제공. 운영 배포 전에 별도 사용자별 rate limit, 프록시/egress 안전성 검증, Android 실기기 호출 테스트가 필수다.
- 외부 문서는 전부 untrusted text다. 텍스트에 있는 지시는 수행하지 않으며 결과는 원문 전문 대신 한정된 발췌·조건 신호 중심이다.

## 미구현/미검증
- 실제 타 사이트 저장소의 소유권 검증 및 로그인, 관리 시스템 플러그인(WordPress/Shopify/Webflow/Notion/GitHub)에 대한 전용 `apply` MCP 없음.
- 사이트의 코드·서버·분석 태그에 대한 포괄적인 수집 항목 검증 없음. 공개 HTML 키워드 검사는 개인정보 법률 준수를 인증하지 못한다.
- PDF/스크린샷, JS 렌더링 SPA, iframe, 다국어 복수정책, 쿠키 배너 동작 검사, GDPR 등 외국법의 심층 조항 엔진, 정기 모니터링/알림 없음.
- 새 4개 도구는 기존 운영 MCP 엔드포인트나 ChatGPT 모바일 앱에서 아직 검증되지 않음. 기존 Private Plugin의 tool discovery 증거와 혼동하지 않는다.
- v0.3 자체 법률문서 게시/소유자 설정 및 DB 마이그레이션은 별도 게이트를 유지.

## 법률적 기준 (2026-10-22)
- 개인정보 보호법 제30조: https://www.law.go.kr/lsLinkCommonInfo.do?lsJoLnkSeq=1029331583
- 개인정보 보호법 시행령 제31조: https://law.go.kr/LSW/lsLawLinkInfo.do?chrClsCd=010202&lsJoLnkSeq=900079801
- 개인정보 보호법 제28조의8: https://law.go.kr/lsLinkCommonInfo.do?chrClsCd=010202&lsJoLnkSeq=1029331979

## 출시 검증 게이트
1. PR/#29 스택 충돌·회귀 없는지 확인
2. 공식 MCP SDK 로컬 도구발견, 입력제한, DNS/SSRF/리디렉션 우회, 외부 egress, 사이트별 속도제한 테스트
3. 기존 6개 도구 regression과 신규 4개 실호출 테스트
4. 실제 모바일 앱에서 연결 가능 여부 확인
5. 권한 있는 저장소 PR 생성·diff·승인·배포·readback 워크플로는 별도 범위
6. 외부 데이터 전송 및 법률문서 처리에 대한 개인정보·저작권 운영 정책 검토
