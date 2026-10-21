# Anti-AI-Slop Design Contract · Alpha 0.3.2

**목표:** AI가 자주 만드는 무의미한 화면 장식/반복을 자동 점검하고, 정보 우선순위가 명확한 UI의 기본값을 제공. *개성 있는 디자인을 금지하거나 인간 디자이너의 평가를 대체하지 않습니다.*

## 실제 적용 내용

1. **렌더러 기본 CSS:** 불필요한 유리 효과(`backdrop-filter`)와 그림자, UI 진행 막대 그라디언트 제거. 둥글기 완화(soft 12px, sharp 8px), 상태 배지는 알약 대신 직사각형, 버튼은 48px 이상 터치 영역. 전장 미리보기는 UI가 아닌 데모 배경이므로 연출/그라디언트 유지.
2. **디자인 계약:** 기존 v0.3 JSON에 `design`/`data_mode` 선택 항목 추가. 기존 v0.1~0.3 문서는 그대로 생성할 수 있습니다.
3. **패턴 검사:** `ui_review`가 발견 위치(path)·증거·문제·수정 제안과 심각도를 출력. 정적 휴리스틱이며 임의 품질 점수는 제공하지 않습니다.
4. **엄격 모드:** `quality_mode="enforce"`일 때 높은 심각도의 미해결 규칙이 있으면 생성 차단. `advisory`가 기본이며 모든 기존 문서의 생성 동작은 유지합니다.
5. **추적 가능한 예외:** 특정 규칙을 의도적으로 사용하는 경우 `design.exceptions[{rule,reason}]`으로 근거를 기록. 예외 적용 항목도 검사 결과의 `waived` 배열에 남습니다.
6. **시연 수치 출처:** `data_mode="demo"`는 가짜 현황처럼 보이는 문제를 예방하기 위한 선언과 생성 DOM 속성입니다. `external`을 선언해도 데이터 연결이 실제로 검증된다는 뜻은 아닙니다.

## 지원 규칙

| Rule ID | 검출 단서 | 주의 |
|---|---|---|
| `generic-headline` | 일반적인 홍보 카피 | 원문 문구 기반, 높은 심각도 |
| `ornamental-glyph` | 버튼/배지/제목 앞의 장식 문자 | 특정 게임의 장식은 의도적일 수 있음 |
| `repeated-metric-cards` | 구조가 유사한 지표 카드 4개 이상 | 테이블/요약으로 바꿀지 검토 |
| `badge-overuse` | 배지 4개 이상 | 상태 표시 자체는 금지하지 않음 |
| `no-data-provenance` | 수치 사용 시 data_mode 없음 | 높은 심각도, 기본 실행은 advisory |
| `unclear-button` | 구체적이지 않은 버튼 이름 | UI 흐름에 따라 괜찮을 수 있음 |
| `inactive-button` | 액션이 없는 버튼 | 높은 심각도, 미리보기 동작과 혼동 방지 |
| `primary-action-overload` | 주요 강조 버튼 3개 이상 | 명확한 행동 우선순위 요구 |
| `excessive-nesting` | 패널/카드 3단계 이상 | 정보 구조 재검토 |
| `missing-brand-direction` | design 계약을 쓰지만 brand_note 없음 | 기본 템플릿화를 경계 |

## JSON 예시

```json
{
  "version": "0.3",
  "title": "전투 UI",
  "data_mode": "demo",
  "design": {
    "context": "game",
    "brand_note": "전열 피해를 즉시 확인하는 저채도 군단 전투 HUD",
    "exceptions": [{
      "rule": "ornamental-glyph",
      "reason": "게임 세계관의 표식으로 플레이 테스트 후 확정한 문자 디자인입니다"
    }]
  },
  "root": {"type": "stack", "children": [{"type": "text", "text": "군단", "variant": "heading"}]}
}
```

`context`는 `product`, `editorial`, `game`만 허용하며 설명 및 향후 확장용 힌트입니다. 현재 레이아웃은 `context`에 따라 자동으로 판단·변경되지 않습니다. 임의 CSS/JS/폰트 URL 삽입도 허용하지 않습니다.

## 호출 예시

```python
from pathlib import Path
from ui_core import review, render
src = Path('examples/expedition-hud-v03.json').read_text(encoding='utf-8')
print(review(src))
output = render(src, 'game-hud-html', quality_mode='enforce')
Path('reviewed-hud.html').write_text(output['preview_html'], encoding='utf-8')
```

```bash
python -m ui_core.cli examples/web-dashboard.json --target web-html --quality-mode enforce --out /tmp/ui-reviewed
```

## 품질 게이트의 한계

* **'안티 AI 슬롭'은 객관적인 스타일 판정 인증이 아닙니다.** 휴리스틱은 일부 좋은 UI를 경고하거나 나쁜 UI를 통과시킬 수 있습니다.
* `advisory` 기본에서는 경고를 줘도 파일 생성을 막지 않습니다. `enforce`도 높은 심각도만 차단합니다.
* 수치가 실제인지, 액션이 호스트에서 적절히 구현되었는지, 사용자 맥락에서 디자인이 적절한지 확인하지 않습니다.
* 브라우저 테스트는 터치 영역/오버플로/패널 동작을 검증하지만 WCAG 전체 준수, 실제 사용성, 상용 수준 디자인 평가를 입증하지 않습니다.
* 디자인 판단은 프로젝트 고유성을 유지하도록 컨텍스트를 토대로 수행해야 하며, 무조건적인 모든 그라디언트/색상/장식 금지와는 다릅니다.

## Alpha 0.3.2 추가 검사 (2026-10-21)

| Rule ID | 대상 | 기본 판정 | 설명 |
|---|---|---|---|
| `sloganized-declarative-headline` | JSON `heading` 텍스트, HTML `h1`–`h3` | 높은 심각도(추상적·홍보성 술어), `이다` 계열은 medium | 모든 `~는 ~다` 표현 금지 아님. 기능적·구체적 제목 우선 |
| `decorative-accent-rail` | HTML 인라인 스타일 및 `<style>`의 `border-left: solid` 등 | 단독 medium, 2곳 이상 high | 카드/안내의 반복 장식 검토. 진행 단계/실제 상태 표기 등 의미가 있으면 예외 허용 |

- 새 MCP 도구: `ui_review_markup(html_source, exceptions_json='[]')`. 결과는 `status`, `findings`, `waived`, `high_severity_count` 등.
- 기존 `ui_review(spec_json)`는 선언형 JSON 내부 제목을 분석한다. JSON에서 임의 CSS 허용하지 않으므로 왼쪽 선은 HTML/내장 CSS 도구로 별도 검사한다.
- `ui_generate(..., quality_mode='enforce')`는 선언형 슬로건 high를 차단하며, 예외는 기존 `design.exceptions`에 이유를 남겨야 한다.
- 렌더러 기본 `notice`의 border-left 장식을 제거하여 표준 UI가 새 규칙을 위반하지 않게 한다.
- HTML 검사기는 연결된 외부 스타일시트, 실제 CSSOM, Javascript 동적 스타일 변경을 검사하지 않는다. 정적 휴리스틱으로 거짓 양성·누락 가능.
