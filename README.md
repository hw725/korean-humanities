# korean-humanities — 한국학 인문학 연구 스킬 슈트

한국학·CJK 고전 인문학 연구를 위한 Claude Code 스킬 모음입니다. 사료비평·해석 논증·인문학
심사 같은 **연구 산출물의 생산과 평가**를 다루며, STEM 연구 도구가 전제하는 것
(통계적 유의성·재현성·영어 논문)과 인문학 연구가 실제로 하는 것(사료 충실성·경쟁 독법·
해석의 정합성) 사이의 간극을 메우는 것이 설계 목표입니다.

**설치 즉시 동작합니다** — API 키·외부 서비스·별도 데이터가 필요 없습니다. 유일한 선택적 의존성은 `gugyeol-decode`의 PDF 처리용 `pip install pymupdf`(HWPX만 다루면 불필요)입니다.

## 구성 스킬

| 스킬 | 하는 일 |
|---|---|
| `hanmun-research-assistant` | 슈트 앞문 — 비서 구축·도구 채택 심사·source-grounded Q&A 라우팅. 증거 접근 3계층(raw/verified/gold)의 epistemological firewall 포함 |
| `academic-research-workflow` | 학술 엔진 — 연구사 리뷰, 사료비평·이본 교감(표점을 적용이 아니라 **논증할 해석 판단**으로 다룸), 해석 논증 설계·초고, 인문학 루브릭 심사, 인용·원문 충실성 감사, 투고 직전 원고-데이터 전수 대조 |
| `academic-english-editing` | 한국어 학술 원고 → 영어 — 절 단위 직역이 아니라 한국어가 생략한 논리 연결을 먼저 복원, 학술 hedging 보정, CJK 고유명사·간지 연대 표기 고정 |
| `gugyeol-decode` | PDF·HWPX에서 깨진 구결자(口訣)·옛한글을 표준 Unicode로 복원 — 한양 PUA + AKS 매핑 내장 |
## 설치

**가장 간단한 방법** — `skills/` 아래의 스킬 폴더들을 `~/.claude/skills/`에 복사(또는
링크)하면 끝입니다. zip으로 받았다면 압축을 풀고 같은 방식으로 복사하세요.

마켓플레이스 방식:

```
/plugin marketplace add hw725/korean-humanities
/plugin install korean-humanities
```

## 설정 (전부 선택 사항)

- `hanmun-research-assistant`: SKILL.md의 «Local Instance Binding» 표에 자기 환경의
  vault·코퍼스 파이프라인·벡터 인덱스·서지 관리자를 채우면 라우팅이 그 환경에 맞게
  동작합니다. **비워 둬도 됩니다** — 해당 모드가 안내와 함께 축소 동작합니다.
## 동봉 도구 (`tools/`)

- `setup-terminal-utf8.ps1` — 터미널·파이썬·git의 한글 깨짐 뿌리를 사용자 수준에서 영구
  차단합니다(`PYTHONUTF8=1`·PowerShell 프로필 UTF-8·`git core.quotepath=false`).
  Windows에서 처음 쓸 때 한 번 돌리는 것을 강하게 권합니다. idempotent, `-Check` 지원.
- `check_cjk_text_contract.py` — 자기 스크립트가 CJK 텍스트 계약(UTF-8 명시·유니코드
  정규식)을 지키는지 AST로 검사합니다.

## 폰트 정책

산출물(HTML·다이어그램·문서)의 기본 폰트는 `hanmun-research-assistant` SKILL.md의
«폰트 정책» 표가 정의합니다 — 세리프 Noto Serif CJK KR, 산세리프 Pretendard GOV Variable
(다국어: Spoqa Han Sans Neo·Noto Sans CJK KR), 고정폭 Sarasa Fixed K·Jetendard.
**그 표를 고치면 슈트 전체가 따릅니다** — 자기 취향의 폰트로 바꿔 쓰세요.

## 설계 원칙 (요약)

1. **사료가 논증보다 앞선다.** 사료비평 없이 사료를 근거로 쓰지 않고, 검증 못 한 것은 `unverified`로 남긴다.
2. **기계 번역·OCR은 초벌이다.** 원문 대조 전에는 인용하지 않는다.
3. **표점·독법은 선택이 아니라 주장이다.** 의미가 갈리면 경쟁 독법을 함께 제시한다.
4. **해석의 타당성은 p값이 아니다.** 개연성·정합성·사료 충실성·경쟁 해석 설명력으로 평가한다 —
   단 연대·인용 같은 사실 주장은 검증 대상이다.

## 알아 둘 것

- 스킬 본문이 언급하는 일부 동반 스킬(문서 도구·로깅·교차검증 등)은 이 배포에 포함되지
  않은 **권장 조합**입니다 — 없어도 각 스킬은 독립 동작하며, 자기 환경의 대응물로
  바꿔 읽으면 됩니다.
- 언어: 스킬 지침은 한국어·영어 혼용입니다. 대상 사용자가 한국학 연구자이기 때문입니다.

## 함께 쓰면 좋은 것 (슈트 밖 — 링크 안내)

- **한국어 산문 AI 티 제거**: [epoko77-ai/im-not-ai](https://github.com/epoko77-ai/im-not-ai)
  — 초록·소개문 등 현대 한국어 산문의 번역투·기계적 문체를 다듬을 때. 이 슈트는
  전근대 문헌 연구용이라 축이 달라 포함하지 않았습니다.
- **KCI 인용망**: 한국연구재단 KCI 참고문헌 OpenAPI(data.go.kr, 무료·자동승인)로 한국
  인문학 논문 인용망을 만들 수 있습니다. 필요한 세부 분야가 사람마다 달라 각자
  수집하는 게 맞는 영역이라 슈트에서 뺐습니다 — 수집·Obsidian 렌더 스크립트가 필요하면
  이 저장소 이슈로 요청하세요.

## 라이선스

스킬별로 다릅니다 — `NOTICE.md`를 보세요. 이 슈트의 자체 저작분은 MIT입니다.
