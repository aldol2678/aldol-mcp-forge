# ALDOL RIGHTS v0.2.0 배포·검증 보고

기준: 2026-10-22 (한국시간). **배포됨·필수 사용자/기기 검증 미완료**. 전체 완료 선언이 아니다.

## 주소와 소스

- 웹사이트: https://rights.aldol.app/
- 원격 MCP: https://rights.aldol.app/mcp
- 비공개 개인 플러그인: https://chatgpt.com/plugins/plugins_6ad9d79f00348191b5573e9bab6f7fa6
- Draft PR: https://github.com/aldol2678/aldol-mcp-forge/pull/25
- PR23(v0.1) 위에 쌓은 독립 개발 브랜치. PR23과 main은 수정/병합하지 않았다.
- 배포 소스 커밋: `b1eff31c1edad13c157188d3d0196fd0213afbf3`
- 배포: `dpl_GqLtbTkMuhGi2xg8QH5Fb9CCVxXq`, Vercel READY, 도메인 verified=true, alias 반영 확인.
- CI 순서 수정 커밋: `8d0400d770f376b48ecbb195d145115787f852a9` (제품 코드 변경 없음).
- 운영 리전 icn1. Railway 미사용. 기존 ARAM Supabase에 RIGHTS 전용 테이블/버킷만 추가했다. 불필요한 새 DB·저장소·판정 서버는 만들지 않았다.

## 구현 범위

단일 FastAPI 앱이 한국어 반응형 화면, 인증 API, 공식 SDK MCP를 제공한다. 웹과 MCP가 `service/policy.py` 및 기존 Python core 판정, 동일 PostgreSQL 자산 데이터와 검사 기록을 공유한다. Next.js/Node 런타임을 추가하지 않았다.

웹: 로그인/가입, 대시보드, 종류별 등록, URL·원저작자·증빙·프로젝트·사용목적, 비공개 파일 업로드·다운로드, 검색/필터, 정보 수정, 재검사, 자산 버전과 검사 스냅샷 이력, 프로젝트 보고서·저작자 표시 문구·Markdown/JSON 다운로드, 다크모드, 하단 내비게이션, 재시도 시 입력 보존. 360px를 대상으로 CSS와 44px 이상 주요 조작 영역을 구현했다. **이는 실기기/해당 뷰포트 통과를 의미하지 않는다.**

MCP: `inspect_license`, `list_assets`, `check_usage`, `generate_credits`, `rights_report`, `review_history`의 조회 전용 6개. 원본 파일 조회·자산 등록/수정은 노출하지 않는다. 기존 로컬 stdio 5개 도구와 SQLite API는 그대로 유지했다.

판정: 조건상 적합/조건 충돌/추가 검토 필요/미확인. 모든 결과에 근거·조건·누락정보·신뢰수준·검사시점·엔진버전을 제공한다. `legal_clearance=false`가 고정된다. SA 수정물 호환성, MIT·Apache·GPL·OFL·개별 계약은 자동 승인하지 않는다. 외부 파일은 실행하거나 시스템 지시로 해석하지 않는다.

## 인증과 저장

웹: Supabase Auth 및 서버에서 검증하는 HttpOnly/Secure/SameSite 쿠키. MCP: 별도 48바이트 난수 연결 키, SHA256만 저장, 조회 전용 scope/resource, 만료(최대90일), 즉시 폐기. 프런트엔드에는 publishable key 설정만 존재하며 service_role 비밀키를 사용하지 않는다.

테이블 3개 모두 RLS=true, anon SELECT=false, authenticated 전체 UPDATE=false와 명시적 컬럼 권한을 재조회했다. 비공개 버킷은 10MiB 제한, 확장자/MIME/실제 파일 매직을 검사한다. 공개 파일 URL과 타계정 API/Storage 접근을 차단했다. 원본은 인증된 첨부 다운로드로만 반환한다.

`rights_mcp_read`는 별도 연결 키를 검사하는 의도적인 SECURITY DEFINER 신뢰 경계다. 고정된 읽기 동작만 허용하고, 모든 질의에서 해당 키 소유자로 제한한다. Supabase advisor의 anon/authenticated 실행 가능 WARN 2개는 이 함수에 대한 의도된 경고이며 숨기지 않는다. 다른 ARAM 기존 권고는 이번 범위 밖이다. [경고 설명](https://supabase.com/docs/guides/database/database-linter?lint=0028_anon_security_definer_function_executable)

SQLite 기존 실사용 데이터는 체크아웃에서 발견하지 못했다. 기존 사용자의 로컬 파일을 전수 조회한 것은 아니므로 외부 SQLite 데이터 존재 여부는 UNKNOWN이며, 임의 이전하지 않았다.

## 실행한 검증

| 항목 | 결과 | 증거·범위 |
|---|---|---|
| 운영 URL·TLS·정적 화면·버전 | PASS | 실제 HTTPS 200, 브라우저 로그인 화면 및 주요 버튼46px 이상 확인 |
| 기존 RIGHTS 회귀 | PASS | 원래17개 테스트 통과 |
| 저장소 오프라인 회귀 | PASS | 43개 실행, 42개 통과·namespace1개 skip |
| 새 정책·API 방어 | PASS | pytest10개 통과; 상태분류/SA/입력/CSRF/파일위장/크기/Host/내보내기 escape |
| 배포 웹/API 기능 | PASS | 합성 계정2개를 이용한21개; 등록·검사·저장·파일·보고서·직접 RLS 차단 |
| 추가 배포 안전성 | PASS | 10개; 무인증/잘못된 키/폐기된 키·CSRF·10MB초과·재검사 목적 영속화·재배포 후 복구 |
| MCP 공식 SDK | PASS | 초기화/도구목록/6도구 실호출을 계정2개로 검증, 총16개 기대결과 충족; 타계정 조회 거부 포함 |
| 최신 MCP wire | PASS | 2026-07-28 메타/헤더를 포함한 tools/list 200. SDK 호환 초기화2025-11-25도 확인 |
| 기존 stdio 실호출 | PASS | 공식 SDK로 기존5도구 호출, 프로세스 재시작 뒤 SQLite 복구 |
| 프런트엔드 DOM | PASS | jsdom8개: 화면 이동/검색/XSS escape/네트워크 실패 입력보존/등록→검사/보고서 다운로드/설정/다크모드. 응답 모의 테스트이며 실브라우저 통합이 아님 |
| GitHub 보존·PR | PASS | 소스·테스트를 원격 커밋으로 보존, PR25 Draft·mergeable=true |
| ChatGPT 플러그인 생성 | PASS | 개인·비공개, 버전0.2.0, 원격 URL/API-key bearer 설정 readback |
| ChatGPT 웹 설치·인증·대화 실호출 | BLOCKED | 검증 브라우저의 ChatGPT 세션은 로그아웃 상태. 새 RIGHTS 도구는 현재 대화 도구 목록에 나타나지 않음 |
| Android 실기기 | BLOCKED | 실제 기기가 연결돼 있지 않음. 세로/가로·키보드·터치·파일선택·다운로드 실기기 미검증 |
| 모바일 브라우저 에뮬레이션 | BLOCKED | 제공 브라우저 API에 뷰포트·터치 에뮬레이션 제어가 없음. 360px 레이아웃 PASS로 표시하지 않음 |
| 실제 신규가입 메일 도착 | UNKNOWN | 기존 Auth 설정을 계승하며, 합성 QA 계정은 개발용으로 확인 처리함. 실사용 주소의 메일 수신은 확인하지 않음 |
| PWA 설치 | UNKNOWN | manifest만 제공. 실제 Android 설치·오프라인 동작 검증 없음 |

기계판독 증거: `evidence/rights-live-results.json`, `evidence/rights-safety-results.json`, `evidence/rights-mcp-results.json`. 합성 QA 비밀번호·연결 키·세션은 포함하지 않았다. 합성 계정의 MCP 연결 키는 모두 폐기하고 readback까지 확인했다.

처음 발견한 MCP Host 거부(421)는 운영 도메인만 허용하고 공격자 Host는 거부하는 회귀 테스트로 해결했다. 최초 CI 실패는 기존 Forge가 SDK 미설치 환경을 가정하는데 SDK를 먼저 설치한 실행 순서 때문이었다. 기존 테스트 수정 없이 순서를 바로잡았다. [CI 재검증](https://github.com/aldol2678/aldol-mcp-forge/actions/runs/39757600580)은 completed/success로 확인했다.

## ChatGPT·Android의 정확한 지원 상태

현행 OpenAI 문서는 플러그인을 웹/데스크톱/모바일에서 사용할 수 있다고 안내한다. 계정·플랜·플러그인 설정에 따른 실제 이용 가능성과 이 플러그인의 Android 실행은 별도다. Pro에서 쓰기가 일괄 불가하다고 단정하지 않았으며, 이번 서버는 요청의 조회·검사 경로에 맞춰 읽기 전용으로 제공한다.

이번 패키지는 ChatGPT 플러그인 포맷의 API-key bearer 설정을 사용한다. OAuth/DCR/CIMD는 구현하지 않았다. **OAuth만 허용하는 ChatGPT 연결 화면/클라이언트에는 연결할 수 없다.** 플러그인 생성 성공과 MCP SDK 성공을 ChatGPT 인증 성공으로 대신하지 않는다. 이 제한 때문에 최종 완료계약 6번은 미충족이다.

참고 공식 문서: [Plugins](https://learn.chatgpt.com/docs/plugins), [연결/테스트](https://developers.openai.com/plugins/deploy/connect-chatgpt), [인증](https://developers.openai.com/plugins/build/auth), [MCP 2026-07-28 전송](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http), [Vercel FastAPI](https://vercel.com/docs/frameworks/backend/fastapi). 정책 근거는 각 라이선스 원문 URL을 결과와 README에 제공한다.

## 사용자가 필요한 단계와 보류 범위

1. 웹사이트에서 계정 생성/로그인(기존 ARAM Auth 계정도 같은 인증 기반 사용). 메일 확인이 필요하면 확인 후 웹으로 돌아와 로그인한다.
2. 웹의 연결 화면에서 조회 전용 키를 만들고, 비공개 ALDOL RIGHTS 플러그인을 설치해 **인증 입력란**에만 넣는다. 대화에 키를 붙여넣지 않는다. API-key 입력이 제공되지 않는 환경은 OAuth 추가 구현이 필요하다.
3. ChatGPT 대화에서 실제 도구 호출과 Android 세로/가로 등록→검사→다운로드를 확인한다.

추가 한계: 큰 원본은10MiB 이상 직접업로드 대신 URL 등록, 보고서500개 상한, 교체 파일 자동정리·OCR/유사저작물 검색·증빙 진위검증·권리 자동확정·고급 상업계약 자동판정·OAuth는 보류다. 판정 결과는 어떠한 법적 안전 보증도 아니다.
