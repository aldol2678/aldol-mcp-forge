# Forge SDK Cloud Run 운영 연결 — 2026-10-20

## 결과

**부분 실행·검증됨. 운영 연결 전체는 차단됨.** 기존 비공개 Forge Studio를 v7 → **v8**로 업데이트하고 실제 연결된 MCP 도구 8개를 재검사했다. Cloud Run은 배포하지 않았으며 운영 SDK 결과는 **SKIP/UNKNOWN**이다.

GCP 프로젝트·Slack 서비스명은 사용자가 제공한 대상이다. 이 세션에는 GCP 관리 커넥터, 인증된 gcloud/ADC 환경이 없고 Cloud Console 탐색도 `Site Unavailable / Unable to access this site`를 반환했다. 프로젝트 부재나 서비스 장애가 확인된 것은 아니다. GCP 접근을 확보하지 못한 상태에서 리전·리비전·크레딧·IAM·Slack 정상 여부를 추정하지 않았다.

## 확인한 현행 상태

| 대상 | 관측 결과 |
|---|---|
| GitHub main | 시작 시 `67b96b99bc1d509537759435258bd8592acf4e0b` |
| PR #6 | 병합됨, 2026-10-20 05:12:33 UTC |
| PR #7/#8/#9/#11 | 모두 open Draft; 병합하지 않음 |
| PR #11 시작 HEAD | `e7e15a84778e6ad48bf43a1774b9f35adbcf09d5` |
| PR #11 기반 | PR #9 브랜치 `feat/studio-sdk-private-integration-20261020`; 누적 변경을 한 번만 적용 |
| PR #5 | 별도 Python 브리지, 이번 작업에서 변경하지 않음 |
| GCP 프로젝트 | `aram-slack-bridge-2026` — 실제 존재/권한 미확인 |
| Slack Cloud Run | `slack-bridge-receiver` 및 `/slack/events` — 현재 리전/리비전/이벤트 수신 미확인 |
| 신규 Cloud Run | 목표 `forge-sdk-verifier`; 이번 작업에서는 생성·배포하지 않음 |
| Cloud Run URL / 리전 / 리비전 | UNKNOWN, 임의 값 설정 없음 |
| Secret Manager / 실행 계정 | 가용성·권한 미확인; 실제 비밀값 생성/조회/변경 없음 |
| 크레딧 잔액 / 만료일 | 미조회·미확인; 과거 기억의 잔액을 현재값으로 사용하지 않음 |

## 실제 Sites 배포

- URL: https://aldol-forge-readonly-20261020.al-dori.chatgpt.site
- 기존 project: `appgprj_6ad6bde7a48881918c1767e3e9f1252f`
- 버전: **8**, 배포 상태 **succeeded**
- 배포 ID: `appgdep_6ad73e4377e88191a695c0ac0b0f739e`
- 저장 버전: `appgprj_6ad6bde7a48881918c1767e3e9f1252f~appgver_ee286dc913a88191b1ca7bcbe03423e3`
- Site source commit: `3dba694b497fafc992a7f42125bebc0f227f5806`
- `has_mcp=true`; 기존 MCP 연결/플러그인 ID 유지. 새 Site·플러그인 생성 없음.
- 소유자 한 명만 허용된 custom 정책과 정책 revision 1 유지. 외부 방문자 0명 유지.
- R2 `BUCKET`과 `FORGE_WRITES_VERIFIED=1` 유지.
- 실제 환경 변경: `SDK_BRIDGE_ENABLED=0` 추가. 환경 revision **2**. URL·HMAC·Google 자격증명은 임의 설정하지 않음.
- 실제 `/studio.js` HTTP 200: 로컬 `worker/client.js`와 바이트 일치, SHA-256 `a8eb6cf5fef9160a483414bd8646a69275bba45106f6f161d809d52a56df5e39`.
- 실제 `/api/session`: `local_qa=false`, `storage=R2`, `sdk_verifier_available=false`, `python_execution=SKIP`, `sdk=UNKNOWN`.
- 위 HTTP readback은 Sites 전용 service-access 인증이다. 방문자 ID를 제공하지 않으므로 사용자 로그인/브라우저 E2E 성공으로 세지 않는다. 이 접근으로 SDK 프로젝트 API를 요청하면 실제 **403**을 반환한다.
- Worker는 소스 helper의 pushed commit → 빌드/패키징 → 해당 commit의 saved version → 성공 배포 연결을 확인했다. 원격 Worker 전체 바이트 직접 추출은 제공된 도구에서 지원하지 않아 재다운로드 비교는 하지 못했다. 브라우저 JS 바이트 일치는 별도로 확인했다.

## 보완한 코드

1. **IAM + HMAC 분리**: `cloudrun-sync`에서는 HMAC만으로 sdkReady가 되지 않는다. Forge 전용 호출 계정의 서버 측 자격증명으로 고정된 Google OAuth endpoint에서 audience가 일치하는 ID token을 받아 Authorization 헤더에 싣는다. HMAC은 별도로 ZIP·사용자 해시·프로젝트·타임스탬프를 인증한다.
2. **인증 코드의 검증 한계**: 실제 RSA 서명/검증과 Google 응답 테스트 대역으로 검증했다. 실제 Google 토큰 발급·Invoker 통과는 **미검증**이다. 키 없는 WIF가 우선 대안이나 Sites의 신뢰 가능한 외부 OIDC 발급 기능은 확인되지 않았다. 현재 구현은 사전에 검토된 기존 전용 서비스 계정 키를 위한 대안이며, 키를 자동 생성하지 않는다. 관리자가 해당 경로를 채택하기 전에는 비활성 상태로 둔다.
3. **별도 runtime identity**: 배포 스크립트가 `forge-sdk-verifier@aram-slack-bridge-2026.iam.gserviceaccount.com`을 명시하도록 수정했다. 기본 계정·Slack 실행 계정 공유를 거부한다. 호출 계정은 `forge-sites-invoker@aram-slack-bridge-2026.iam.gserviceaccount.com`만 허용한다.
4. **자식 프로세스 경계**: 실제 SDK 자식 프로세스에는 최소 환경만 전달한다. 부모의 HMAC·Google 자격증명·Python 주입·프록시 환경을 상속하지 않는다. 75초 제한으로 verifier와 stdio 자식들을 같은 프로세스 그룹에서 종료한다.
5. **결과 진실성**: SDK `2.0.0`과 두 transport 성공, `network_used=false`를 모두 요구한다. TIMEOUT을 503으로 뭉개지 않고 최종 상태로 보존한다.
6. **중복/비용 제어**: 같은 immutable 프로젝트/ZIP의 저장된 PASS/FAIL을 재사용한다. Cloud Run handler는 단일 실행과 90초 재전송 캐시를 사용한다. Sites는 R2 atomic 조건부 쓰기로 사용자별 **UTC 하루 30회** 신규 실행 시도를 제한한다. 인증/실행 실패도 시도 한도에 포함된다.
7. **배포 보호**: gcloud 스크립트는 명시적인 `--deploy`에서만 동작한다. 기존 API·이미지 저장소·Forge secret·전용 계정·Slack Ready 상태를 요구한다. 프로젝트/API/저장소/계정/IAM grant를 자동 생성하지 않는다. Slack spec·annotations·ready revision·IAM을 전후 비교하고 drift 시 활성화를 중단한다. Slack 복구/재배포 명령은 없다.
8. **기존 테스트 보정**: SDK가 없다는 가정을 고정한 회귀 테스트가 SDK 설치 환경에서 3개 subcase를 실패시켰다. 실제 설치 여부에 따라 정확한 결과를 검사하도록 수정했으며 최종 전체 suite가 통과했다.

ZIP 크기·파일명·CRC·SHA256SUMS·원래 Forge 생성 코드와의 정확한 동등성 검사는 유지된다. 임의 Python/셸 입력이나 공개 ZIP URL을 추가하지 않았다.

## 실행한 검증

| 테스트 | 결과 | 증거/한계 |
|---|---|---|
| JavaScript 전체 suite | 224 PASS | `evidence/cloudrun-ops-20261020/node-tests.log` |
| Python HTTP/SDK/ZIP/배포 보호 | 22 PASS | `python-tests.log` |
| SDK 설치 환경 회귀 | 26 중 24 PASS, 2 SKIP | `regression-sdk-installed.log`; Linux namespace 미지원, SDK 부재 전용 검사 생략 |
| Forge 자체 공식 SDK | in-memory/stdio PASS, 도구 8개 | `forge-official-sdk.json`; 로컬 실행 |
| 실제 Sites generator의 HTML v0.2.0 ZIP | SDK 2.0.0 두 transport PASS | `generated-zip-sdk-local.json`; 운영 R2에서 다운로드한 ZIP이 아닌 동일 generator의 로컬 산출물 |
| HTML+JSON v0.2.1 ZIP | SDK 2.0.0 두 transport PASS | 위와 동일 |
| OpenAPI GET ZIP | SDK 2.0.0 두 transport PASS | 외부 API 호출 없음 |
| 배포 형태 Worker 빌드 | PASS | ESM import, SDK endpoint/실패 폐쇄, client.js 일치 |
| 실제 Sites MCP 도구 8개 | PASS | v8 배포 후 각 도구 호출; `sites-v8-live.json` |
| 기존 v7 테스트 자료 유지 | PASS | v8에서 재조회한 무결성/패키지 SHA가 기존 값과 일치 |
| 화면 검사 | 로컬 QA에서 SDK 버튼 disabled/SKIP | 가상 사용자·메모리 저장소; 운영 브라우저 E2E 아님 |

### 필수 운영 E2E 14개 항목

| # | 항목 | 운영 판정 |
|---|---|---|
| 1 | HTML 검사 MCP | 실제 Sites 생성/무결성/패키징 PASS, Cloud Run SDK SKIP |
| 2 | JSON 포함 v0.2.1 | 실제 Sites 새 버전/무결성/패키징 PASS, Cloud Run SDK SKIP |
| 3 | OpenAPI GET | 실제 Sites 생성/무결성/패키징 PASS, Cloud Run SDK SKIP |
| 4 | SDK in-memory | LOCAL PASS / 운영 SKIP |
| 5 | SDK stdio | LOCAL PASS / 운영 SKIP |
| 6 | 정상 요청 PASS | LOCAL PASS / 운영 SKIP |
| 7 | 미인증 요청 거부 | Sites 사용자 ID 없는 요청 실제 403; Cloud Run IAM은 UNKNOWN |
| 8 | 사용자별 격리 | LOCAL PASS / 운영 두 번째 사용자 로그인 시험 미실시 |
| 9 | HMAC/ZIP/SHA 변조 | LOCAL PASS / 운영 SKIP |
| 10 | timeout/실패 처리 | LOCAL PASS / 운영 SKIP |
| 11 | 반복 검증 | LOCAL PASS, 결과 재사용 / 운영 SDK SKIP |
| 12 | 새로고침 후 SDK 결과 보존 | 모의 R2 LOCAL PASS / 운영 SDK SKIP |
| 13 | 기존 MCP 8개 | 실제 v8 연결에서 PASS |
| 14 | Slack 이벤트 수신/메시지 처리 | UNKNOWN; GCP/Slack bridge 실행 로그에 접근하지 못함 |

**Forge Studio → Cloud Run → SDK → R2 → 브라우저 새로고침 전체 운영 E2E는 성공하지 않았다.** 운영 SDK PASS를 기록하거나 버튼을 활성화하지 않았다.

## Slack 보호 상태

이번 작업은 Slack 서비스·환경·시크릿·IAM·라우팅·도메인·데이터에 변경 API를 호출하지 않았다. 그러나 GCP 접근이 없어 기존 이미지·리비전·오류율·지연·실제 메시지 처리를 전후 조회하지 못했다. **변경하지 않았다는 사실과 정상 작동을 검증했다는 주장은 구분한다.**

## 비용과 제한

실제 GCP 서비스 설정은 미적용이다. 준비된 배포값은 min 0 / max 1 / concurrency 1 / CPU 1 / memory 1GiB / request timeout 120초, request-based CPU, CPU boost 비활성이다. Python 검증 하위 제한은 75초다. Sites의 하루 30회 제한 코드가 v8에 반영되었으나 SDK 전체가 비활성 상태다.

공식 us-central1 요청 기반 기준 단가로, 1 vCPU·1GiB를 요청당 30초 사용하면 **1,000회에 약 US$0.80**의 CPU/메모리/요청 비용이다(무료 사용량 적용 전 계산). 30회/일 × 30일이면 같은 가정에서 약 $0.72, 매번 75초라면 약 $1.79다. 이는 리전 미확정 상태의 예시이며 시작/종료 시간, 빌드, Artifact Registry, Secret Manager, 네트워크, 로그, 기존 R2 비용은 제외한다. 서비스 전체 비용 상한이나 무료 보장은 아니다.

요청 기반 무료 사용량은 월 CPU 180,000 vCPU-seconds / 메모리 360,000 GiB-seconds / 요청 200만 회이며 **billing account의 여러 프로젝트에 걸쳐 합산**된다. 기존 Slack 등의 사용량과 잔여 크레딧을 확인하지 못했으므로 무료 범위가 남아 있다고 단정하지 않는다. 별도 유료 모니터링 자원은 만들지 않았다.

## 재개에 필요한 실제 조건

1. 해당 프로젝트를 조회·배포할 수 있는 **인증된 GCP 실행 경로**. gcloud 설치만으로는 부족하다. 실제 Slack 리전/Ready revision/IAM/로그와 billing account의 잔액·크레딧 만료를 먼저 확인한다.
2. 전용 runtime 계정과 Forge 전용 Secret Manager secret, 해당 secret만의 접근 권한. 호출 계정에는 **forge-sdk-verifier 한 서비스 범위의** `roles/run.invoker`만 부여하는 경로를 검토한다. Slack/프로젝트 전체 권한을 재사용하지 않는다.
3. Sites에서 사용할 검토된 Google 인증 경로. WIF/OIDC 지원이 확인되지 않으면 현재 대안의 전용 키 보관·회전·권한 범위를 명시적으로 검토한다. 키/토큰을 대화·GitHub·브라우저 JS로 전달하지 않는다.
4. 확인된 REGION, FORGE_SERVICE_ACCOUNT, FORGE_SDK_SECRET_REF로 `bash deploy/cloudrun_sdk/prepare_and_deploy.sh --deploy`를 실행한다. 준비되지 않은 전제조건을 자동 생성/공개 전환해서 우회하지 않는다.
5. 실제 private URL/ID token/HMAC·ZIP 검증, 결과의 R2 보관/재조회, 소유자 격리, Slack 전후 정상 여부를 증명한 뒤에만 최종 `SDK_BRIDGE_ENABLED=1`로 전환한다. 아직 이 단계에 도달하지 않았다.

## 출처

- https://docs.cloud.google.com/run/docs/authenticating/service-to-service
- https://docs.cloud.google.com/run/docs/configuring/billing-settings
- https://docs.cloud.google.com/run/docs/configuring/request-timeout
- https://cloud.google.com/run/pricing
- https://github.com/aldol2678/aldol-mcp-forge/pull/11

코드·운영 증거는 이 문서와 동일 PR의 누적 변경에 보존한다. main 수정·PR 병합·공개 릴리스는 수행하지 않았다.
