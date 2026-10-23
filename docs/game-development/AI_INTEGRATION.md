# ALDOL Studio | AI 작업 지침 연결 안내

> 상태: **PROPOSAL** · 작성: 2026-10-24  
> 대상: 게임별 GitHub 저장소의 `AGENTS.md`, Codex/Claude 인계서, 기타 AI 작업 지침

## 단일 출처

공통 게임 디자인 판단의 기준 문서:

- [ALDOL Studio 공통 게임 개발 원칙](./PRINCIPLES.md)
- 승인·`main` 반영 후 안정적인 URL: `https://github.com/aldol2678/aldol-mcp-forge/blob/main/docs/game-development/PRINCIPLES.md`

현재 다른 게임 저장소나 AI 클라이언트에 자동 전파되지는 않는다. 원칙을 적용할 때는 프로젝트의 기존 지침·정본·운영 게이트를 먼저 확인한다.

## 개별 게임 작업 지침에 추가할 최소 문구 (복사용)

```md
### ALDOL 공통 게임 개발 원칙
- 공통 참조: https://github.com/aldol2678/aldol-mcp-forge/blob/main/docs/game-development/PRINCIPLES.md
- 새 콘텐츠·시스템 제안 전 핵심 재미의 정의, 제거·통합 대안, 플레이 검증 계획, 복잡도·저장 호환성 영향을 검토한다.
- AI가 구현한 기능이나 CI PASS를 실제 재미 검증 PASS로 표시하지 않는다.
- 게임별 확정 기획·안전·보안·기존 저장/출시 정책과 충돌하면 이를 임의로 덮어쓰지 않고 충돌을 보고한다.
- 이 링크는 공통 디자인 가이드이며 병합·배포·삭제의 승인 권한을 부여하지 않는다.
```

## 도입 순서

1. 본 문서와 `PRINCIPLES.md`의 PR 리뷰 및 `main` 반영을 확인한다.
2. 각 게임의 현행 개발 지침과 충돌 여부를 검토한다.
3. 적용을 승인한 게임 저장소에만 위 참조 문구를 추가한다.
4. 실제 패치 제안·플레이 검증에서 활용 여부를 확인한다.

프로젝트별 파일을 일괄 수정하거나 배포하지 않는다. 링크를 추가했다고 자동으로 모든 AI가 내용을 읽었다고 주장하지 않는다.
