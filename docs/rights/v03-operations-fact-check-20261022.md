# ALDOL RIGHTS · 운영정보 검증 기록 (2026-10-22 KST)

검증 범위: v0.3 정책 문안의 실제 운영정보 확인. 읽기 전용 Supabase/Vercel API와 GitHub 코드 및 공급업체/한국 법령을 대조했다. **운영 DB 변경, 정책 게시, 이용자 정보 조회, 프로덕션 배포는 하지 않았다.**

## 확정된 사실 (2026-10-22 현재, 운영 readback)
| 항목 | 실제 상태 | 근거·권위 |
| --- | --- | --- |
| 운영 서비스 | rights.aldol.app → Vercel `aldol-rights`, READY | Vercel project/deployment readback, deployment `dpl_GqLtbTkMuhGi2xg8QH5Fb9CCVxXq` |
| 운영 코드 | v0.2 `b1eff31c1edad13c157188d3d0196fd0213afbf3` | Vercel deployment git metadata |
| 서버 실행 위치 | Vercel functions `icn1` (서울) | Vercel production deployment regions |
| 회원 인증과 DB | ARAM Supabase project `aettjhzcmifjijxkwnmb` | source `packages/rights/service/store.py`, Supabase project readback |
| DB/Auth/Storage 위치 | Supabase region `ap-southeast-1` (싱가포르) | Supabase project region; official data residency FAQ |
| 기존 권리 DB | `rights_assets`, `rights_checks`, `rights_connection_keys` | Supabase read-only schema introspection; all RLS enabled |
| 기존 비공개 버킷 | `rights-private`, `public=false`, 10MiB 파일 제한 | Supabase storage.buckets readback |
| 등록 내용 | 저작자·권리보유자·출처·라이선스·프로젝트·메모·이용목적·파일 경로, 과거 검사 스냅샷 | information_schema + RIGHTS v0.2 service source |
| MCP 연결키 | 무작위 키의 해시만 DB에 저장, 1–90일 유효기간, 폐기 기능 | rights service main.py and SQL |
| 로그인 세션 | HttpOnly/Secure/SameSite Strict 쿠키, 액세스 최대 1시간/갱신 최대 30일 | rights service main.py source |
| RIGHTS 자동 파기 | `cron.job`에서 RIGHTS 관련 작업 0건, 소스에도 기본 자료/파일 삭제 경로 확인되지 않음 | read-only query & inspected source |
| 신규 v0.3 정책 DB | `rights_legal_documents`, `rights_policy_acceptances`, `rights_privacy_requests`, `rights_policy_admins` 테이블 아직 없음 | Supabase `list_tables`, migration PR #29 source-only |

## 법률·공급업체 근거
- 개인정보 보호법 현행 제30조: 개인정보 처리 목적, 보유기간, 파기, 위탁, 정보주체 권리, 연락처 등의 공개
  https://www.law.go.kr/lsLinkCommonInfo.do?lsJoLnkSeq=1029331583
- 제28조의8: 국외 보관·위탁·제공의 적법 근거를 판단하고 적용되는 사전고지/동의 요건을 충족해야 함
  https://www.law.go.kr/LSW/lsLinkCommonInfo.do?chrClsCd=010202&lsJoLnkSeq=1029334869
- Supabase 데이터 레지던시 설명 (2026-10-06): 기본 Auth/DB/Storage 리전과 해외 지원·로그/CDN 가능성을 별도 구분
  https://supabase.com/legal/privacy-resources/data-residency-and-transfers-faq
- Supabase DPA: 공급업체의 처리 및 하위처리자 업무
  https://supabase.com/legal/customer-resources/data-processing-addendum
- Vercel DPA: 미국 및 다른 처리국가, 하위처리자 등
  https://vercel.com/legal/dpa

## 아직 UNKNOWN인 정보: 법적 공식 게시 게이트
1. **개인정보처리자 실제 법적 주체**: 법인/개인사업자/개인 여부, 공개 가능한 업무 연락처, 보호책임자 또는 부서. GitHub 소유자명은 법적 운영주체의 증명이 아니다.
2. **정확한 보유 및 파기 정책**: 계정·자산·증빙·검사스냅샷·만료 키·요청 이력의 각 보유기간, 삭제 처리 SLA, 파일 교체 이전 객체·백업·로그의 실제 잔존기간. 90일 키 만료는 90일 데이터 삭제가 아니다.
3. **개별 법적 처리 근거**: 국외이전 해당 항목·목적·국가·방식·수탁 법인명과 연락처, 재위탁, 거부권·효과, 계약이행 필요성/고지 또는 별도 동의 요건 검토. 서울 함수 리전이 모든 개인정보 국내처리를 뜻하지 않는다.
4. **운영 계약**: 실제 Vercel/Supabase 고객 계약 및 DPA 체결/적용, 로그·분석도구·서드파티, 실제 지원/접근 인력 범위.
5. **가입/탈퇴 및 데이터 권리 행사**: ARAM 공용 계정 연계 정책, 원본 포함 전량 열람 및 삭제 절차, 신고·접수 연락처, 처리 주체 및 응답 경로. v0.3 개인정보 메뉴는 아직 배포되지 않음.
6. **미성년자/해외 이용자 정책**: 대상 사용자 연령, 보호자 동의 필요성, 적용법과 실제 운영 상황.

## 적용 내용 및 완료 판정
- Draft PR #29의 `packages/rights/service/public/legal-privacy-template.txt`에 **확인한 사실만** 반영했다.
- 미확인 사항에는 `[확인 필요]`를 유지해 PublishApproval API가 게시를 차단하도록 보존했다.
- 본 검증은 **기술 운영정보 일부 검증 완료**, **법률 문안 최종 승인/게시 미완료**.
- v0.2 프로덕션 변경 없음; v0.3 SQL 미실행; 새 관리자 계정 미지정.
