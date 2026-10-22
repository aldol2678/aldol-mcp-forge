# ALDOL RIGHTS v0.5 · 검증된 GitHub 사이트 약관 변경 PR

**현행 상태: Draft 소스 구현. 운영 연결·배포 아님.**
이 기능은 v0.4 외부 사이트 조사/수정계획의 실행 단계다. 사이트가 아닌 **연결·검증된 GitHub 저장소의 정책 파일**에 대한 Draft Pull Request만 만들며 자동 병합/공식 채택/배포는 하지 않는다.

## 인증과 권한 경계
- `RIGHTS` 웹은 기존 Supabase Auth와 RIGHTS 약관 확인으로 사용자 인증. MCP의 기존 `rights:read` 키는 **조회·미리보기 전용**으로 절대 쓰기 권한이 되지 않는다.
- GitHub 서버는 전용 **GitHub App**의 단기 설치 토큰만 사용한다. App 권한: `Contents: Read & write`, `Pull requests: Read & write`, `Metadata: Read`. 발급 시 해당 GitHub repository ID 한 개로 토큰 범위를 좁힌다.
- 독립된 운영자 설정 `RIGHTS_GITHUB_GRANTS_JSON`에서 다음을 **모두** 확인해야 한다: 정확한 RIGHTS 사용자 UUID, HTTPS 사이트 주소, GitHub `owner/repo`, 숫자 GitHub repository ID, installation ID, 허용된 정책 파일 경로, `verified=true`.
- 운영자가 사이트의 실제 통제권을 직접 검증한 뒤 trusted server 환경변수에 매핑해야 한다. 이 버전은 인증된 GitHub 설치 토큰이 해당 저장소에 쓸 수 있는지 확인하지만, **임의의 사이트 URL이 그 저장소에서 서비스되는지 자동 증명하지 않는다.** 도메인만 알고 있어도 편집 권한이 생기지 않는다.
- 권한 매핑은 API 요청으로 변경할 수 없다. 신뢰된 운영자만 연결 및 폐기를 처리한다. 계정 이메일, `user_metadata`, 사용자가 제출한 `verified` 값은 권한 근거로 사용하지 않는다.
- OAuth/self-service GitHub 계정 연결은 **아직 미구현**. 타인 계정에 대한 주기적 GitHub 권한 재검증과 운영자 감사 로그 역시 출시 게이트다.

## 안전한 GitHub App 구성 (배포 전, 비밀키 Git 커밋 금지)
서버 전용 시크릿:
- `RIGHTS_GITHUB_APP_ID`: 설치한 GitHub App ID
- `RIGHTS_GITHUB_APP_PRIVATE_KEY`: 서버 측 PEM 개인키 (줄바꿈 이스케이프 형식도 지원)
- `RIGHTS_GITHUB_GRANTS_JSON`: 특정 실사용자/사이트/저장소/파일 경로 승인 매핑
- `RIGHTS_GITHUB_PR_ENABLED=1`: 기본 OFF, 실제 Draft PR 쓰기 실행을 명시적으로 활성화

예시 **가짜 값**:
```json
[
  {
    "rights_owner_id": "12345678-1234-4234-8234-123456789012",
    "site_url": "https://example.org",
    "repository": "example-owner/example-site",
    "repository_id": 123456,
    "installation_id": 789012,
    "policy_paths": ["docs/privacy.md", "docs/terms.md"],
    "verified": true
  }
]
```
위 JSON은 권한 증명이 아닌 설정 **형식** 예시다. 실제 사용자 UUID, GitHub repo ID 및 설치 ID는 각 공급자 콘솔에서 각각 확인한다. 사이트↔저장소 대응은 Vercel 도메인 연결·프로젝트의 Git 리포지토리 등 신뢰할 수 있는 증거로 확인하고 운영자가 승인한다.

## 실제 워크플로 (운영 시)
1. 사용자 사이트 정책 조사 후 실제 처리 현황으로 문서를 작성한다. 법적 최종 검토·운영자 권한은 별도 판단한다.
2. 웹사이트 `#site-policies`에서 HTTPS 사이트, GitHub 리포지토리, 미리 승인된 정책 파일 경로, 변경 본문을 제출한다.
3. `POST /api/site-policy/github/prepare`: 서버는 실제 GitHub App 설치 인증 및 저장소 정체(ID)를 재조회한다. 기본 브랜치의 파일 UTF-8과 blob SHA를 확인하고 통합 diff + SHA256 미리보기 지문을 제공한다. **GitHub 변경 없음.**
4. 화면에서 diff를 확인하고 별도로 PR 생성에 체크한다. `POST /api/site-policy/github/submit`은 쓰기 기능 플래그와 모든 매핑·원본 SHA·미리보기 지문을 다시 확인한다.
5. 서버가 `rights-policy/<digest>` 단일 새 브랜치를 생성하고 **허용된 기존 정책 파일 한 개만** 수정한 뒤 GitHub **Draft PR**을 만든다.
6. 생성된 PR이 draft/open인지, head/base가 예상한 브랜치인지, 바뀐 파일이 정확히 1개인지 GitHub API에서 **readback**한다.
7. 응답 `DRAFT_PR_VERIFIED`는 PR 생성 검증이지, 정책 법률검토·병합·배포·도메인 적용 검증이 아니다. CI·법무 검토·최종 사용자 승인이 있어야 별도 병합 가능하다.

## 중복·실패 대응
- 예상 SHA 변경 및 미리보기 불일치: 차단. 동일 변경 브랜치가 이미 있으면 덮어쓰기/중복 PR 생성하지 않고 차단.
- 브랜치를 만든 이후 API 오류: `PARTIAL_NEEDS_READBACK`으로 처리, 브랜치 식별자를 반환. 추가 외부 쓰기 전 해당 GitHub 브랜치와 PR을 재조회해야 한다.
- 현재 설계는 GitHub에 있는 **기존 파일**만 수정한다. 없던 정책을 자동으로 새 파일로 만들거나 여러 파일을 동시에 변경하지 않는다.
- GitHub Contents REST API와 Draft Pull Request API 사용. Draft PR도 외부 알림이나 CI 트리거를 발생시킬 수 있다.
- GitHub App 자체의 설정이 미완성이거나 RIGHTS 자체 약관/DB 관리 기능이 배포되지 않았다면 새 기능은 동작하지 않는다.

## API/플러그인
- MCP `site_policy_github_pr_preview`: 설치·권한 확인 + 정책 파일 미리보기 (**readOnlyHint=true**). 기존 MCP 토큰으로 외부 GitHub 수정 불가.
- 웹 `/api/site-policy/github/prepare`: 미리보기.
- 웹 `/api/site-policy/github/submit`: 별도 권한과 사용자 확인을 요구하는 Draft PR 발행. 기본 OFF.
- PR 실행은 웹 세션을 통해서만 수행하며, 별도 OAuth GitHub 권한/스코프 없는 읽기 전용 ChatGPT 연결에서 GitHub PR을 직접 생성할 수 있다고 주장하지 않는다.

## 출시 차단 게이트
- 기존 v0.2/0.3/0.4 스택 PR의 정본 여부와 병합 순서, CI 재확인
- 신뢰된 운영자 권한/도메인·저장소 대응 사실 확인 및 문서화
- GitHub App 직접 설치, 저장소별 최소 권한 검증, GitHub Actions 등 자동화 영향 조사
- 실제 GitHub App 인증/토큰 발급/권한 거부/만료/레이트리밋/부분실패 테스트
- GitHub PR 생성·읽기 재조회 후 파일 diff 수동 검토
- Android ChatGPT 연결, Android 모바일 웹 터치·키보드·세로/가로 QA
- 사용자별 PR 생성 제한, 감사 로그, 악의적인 대량 생성 방지(운영 시 필수)
- 외부 정책에 대한 법률 검수 및 기존 서비스 데이터 변경의 영향 평가
- 사용자 승인 없이는 운영 배포/정본 정책 게시/PR 병합 없음

공식 GitHub 문서:
- https://docs.github.com/en/rest/pulls/pulls
- https://docs.github.com/en/rest/apps/apps
- https://docs.github.com/en/rest/repos/contents
