# korean-humanities — 한국학 인문학 연구 플러그인 모음

한국학 연구를 위한 Claude Code 플러그인 **4종**입니다. 저자의 전공이 전근대 한국
한문학이라 그쪽에 초점이 맞춰져 있고, 저자의 식견이 닿지 못한 분야(국어학·한국사·
민속학 등 한국학의 더 넓은 영역)는 충분히 포괄하지 못했습니다. 그래서 처음부터
**각자 커스텀해서 쓰도록** 설계했습니다 — 설정 지점은 각 절에 명시돼 있고, 분야
확장 기여(PR·의견)도 적극 환영합니다.

슈트 전체를 한꺼번에 설치하는 것이 아니라, **필요한 것만 골라 설치**합니다.

```
/plugin marketplace add hw725/korean-humanities
/plugin install korean-humanities        # 연구 방법론 (프롬프트 전용, 준비물 0)
/plugin install gugyeol-decode           # 깨진 구결·옛한글 복원 도구
/plugin install kci-citation-network     # KCI 인용망 수집기 (무료 API 키 필요)
/plugin install kci-korean-studies-trends # KCI 동향 코퍼스·보고서 (키 불필요)
```

## Claude Code가 아니어도 쓸 수 있습니다

플러그인·마켓플레이스는 Claude Code의 **설치 편의 계층**일 뿐이고, 알맹이는 도구
중립입니다. 아래에서 자기 환경을 찾아 그대로 따라 하시면 됩니다. 어느 경우든 먼저
저장소를 받습니다:

```bash
git clone https://github.com/hw725/korean-humanities
# git이 없으면: GitHub 페이지에서 Code → Download ZIP → 압축 해제
```

### Claude Code — 마켓플레이스 없이 수동 설치

원하는 스킬 폴더를 `~/.claude/skills/`에 복사합니다. 예를 들어 gugyeol-decode 하나만:

```bash
# macOS / Linux
cp -r korean-humanities/plugins/gugyeol-decode/skills/gugyeol-decode ~/.claude/skills/
```

```powershell
# Windows (PowerShell)
Copy-Item -Recurse korean-humanities\plugins\gugyeol-decode\skills\gugyeol-decode "$env:USERPROFILE\.claude\skills\"
```

### Codex CLI 등 skills 규약을 쓰는 도구

같은 스킬 폴더를 그 도구의 skills 디렉터리에 복사하면 됩니다 — SKILL.md 규약이
같아 그대로 동작합니다.

```bash
cp -r korean-humanities/plugins/gugyeol-decode/skills/gugyeol-decode ~/.codex/skills/
```

### 다른 LLM·챗봇 (웹 ChatGPT·Gemini 등)

방법론 3종(연구 워크플로·비서 라우터·영문 라이팅)은 실행 코드가 없는 **프롬프트
문서**라서 어떤 LLM에든 쓸 수 있습니다. `plugins/korean-humanities/skills/<스킬>/SKILL.md`
본문을 대화에 붙여 넣고 «이 지침대로 ○○해 주세요»라고 요청하면 됩니다.
`references/` 폴더의 세부 문서는 해당 작업에 필요한 것만 이어서 붙입니다.

### AI 도구 없이 — 터미널만으로

kci 인용망·동향·gugyeol 복원 스크립트는 순수 Python이라 단독 실행됩니다.
Python 3만 있으면 되고(표준 라이브러리 사용), 추가 설치는 gugyeol의 PDF 입력용
`pip install pymupdf` 하나뿐입니다. 실행 명령은 아래 각 플러그인 절의 «사용법»
코드 블록을 그대로 쓰되, Windows는 `py -3`, macOS/Linux는 `python3`을 사용합니다.

### 알아 둘 것 — 선택 단위

폴더 복사의 선택 단위는 **스킬 하나**입니다 — 플러그인(묶음, 4종)보다 잘게, 스킬 6종 중
원하는 것만 골라 복사할 수 있습니다. 각 스킬은 단독 동작하며, 동반 스킬이 없을 때의
동작도 각 SKILL.md에 명시돼 있습니다.

## 각 플러그인의 기능과 보증

### `korean-humanities` — 연구 방법론 (스킬 3종, 준비물 0)

| 스킬 | 하는 일 | 지키는 것 (행동 보증) |
|---|---|---|
| `academic-research-workflow` | 연구사 리뷰 · 사료비평/이본 교감 · 논증 설계·초고 · 인문학 루브릭 심사 · 인용/원문 충실성 감사 · 투고 직전 원고-데이터 전수 대조 | 사료·참고문헌·수치를 지어내지 않고 미확인은 `unverified`로 남김 · 기계 국역(ITKC aitr 등)은 원문 대조 전 인용 금지 · 표점/독법이 갈리면 경쟁 독법을 함께 제시 · 해석 평가는 개연성·정합성 기준, 단 연대·인용 같은 사실 주장은 검증 대상 |
| `hanmun-research-assistant` | 연구 비서 구축·운영 라우터 — 문집·원문 source-grounded Q&A, 사료 디지털화 워크플로, 새 학술 AI 도구 심사. 슈트 공통 CJK 텍스트 계약(UTF-8·유니코드 정규식·NFC·폰트 정책) 소유 | OCR·번역·검색 결과를 검증 없이 사실로 승격하지 않음 · 증거 접근 3계층(raw/verified/gold) 격리 · 본문이 언급하는 동반 스킬은 권장 조합일 뿐, 없어도 단독 동작 |
| `academic-english-editing` | 한국어 학술 원고 → 영어 — 한국어가 생략한 논리 연결 복원, 문장 길이 밴드, 학술 hedging 보정, CJK 고유명사·간지 연대 표기 고정 | 절 단위 직역 금지 · 과잉주장 점검 · 로마자 표기(MR/RR)는 사용자 설정을 따름 |

동봉 `tools/`: `setup-terminal-utf8.ps1`(Windows 한글 깨짐 뿌리 3곳 영구 차단 — 강력 권장,
idempotent) · `check_cjk_text_contract.py`(자기 스크립트의 인코딩·정규식 계약 검사, AST 기반).

### `gugyeol-decode` — 깨진 구결·옛한글 복원 (도구 스킬)

PDF·HWPX에서 `(cid:6)`이나 PUA로 깨져 나오는 구결자(口訣, MR kugyŏl)·옛한글을 표준
유니코드로 복원합니다. **매핑 데이터(한양 PUA + AKS 표준, 약 3.6MB) 동봉** — 다운로드
불필요. PDF 입력만 `pip install pymupdf`가 필요하고 HWPX는 표준 라이브러리로 처리합니다.
자동 매핑이 못 푸는 글자는 못 풀었다고 보고합니다(추측 치환 없음).

### `kci-citation-network` — KCI 인용망 수집기 (키워드만으로 직접 수집)

**키워드만 입력하면 됩니다** — “「운양 김윤식」으로 인용망 수집해줘”라고 하면 스킬이 KCI에서
씨앗 논문을 검색하고(동명이인 확인을 거쳐) 참고문헌 API로 인용 엣지를 수집합니다.
OpenAlex가 커버하지 않는 한국 인문학 인용 데이터의 실질적 대안입니다.

- 준비물: [data.go.kr](https://www.data.go.kr)에서 KCI 참고문헌 서비스(15085323) 활용신청
  (무료·자동승인) 후 키를 `KCI_DATA_GO_KR_KEY_DECODING` 환경변수로 설정.
- 산출: `nodes/edges/refs.jsonl` (checkpoint·resume 내장). Obsidian 노트 렌더는 **선택**이며
  `--vault <내 vault 경로>` 인자로만 연결됩니다 — 렌더를 건너뛰면 JSONL만 남습니다.
- 스크립트는 전부 표준 라이브러리이고 **LLM 호출이 없습니다**.
- 알려진 한계: 정확 엣지는 KCI 수록 참고문헌(실측 약 25%)에 한정 — 문집·단행본·해외
  문헌은 텍스트 참조로만 남습니다.

**사용법** — 키워드를 자기 연구 주제로 바꿔 넣습니다.

```bash
# Claude Code에서: 자연어 한 줄이면 스킬이 검색→확인→수집을 진행합니다
"「내 키워드」로 인용망 수집해줘"

# AI 도구 없이 CLI로: <스킬 폴더> = plugins/kci-citation-network/skills/kci-citation-network
py -3 <스킬 폴더>/scripts/kci_citation_collect.py --query "내 키워드" --max 40 --preview        # 씨앗 미리보기 (키 불필요)
py -3 <스킬 폴더>/scripts/kci_citation_collect.py --query "내 키워드" --max 40 --out-dir out/내주제  # 본 수집 (키 필요)
```

미리보기 결과에서 동명이인·무관 논문을 지운 목록을 `seeds.tsv`로 저장해
`--query` 대신 `--arti-ids seeds.tsv`를 지정하면 더 깨끗한 씨앗으로 수집합니다.
(macOS/Linux는 `py -3` 대신 `python3`.)

### `kci-korean-studies-trends` — KCI 동향 코퍼스·보고서 (연도·분야만으로 직접 수집)

**연도·분야만 지정하면 됩니다** — “2025년 한문학 동향 코퍼스 만들어 보고서 내줘”라고 하면
스킬이 저널 프로파일 기준으로 KCI를 서버 부담을 줄이는 간격으로 수집(sleep·체크포인트 내장, API 키
불필요)하고, 주제 클러스터·대표 논문 후보·학술지 분포가 담긴 보고서를 만듭니다.

- **핵심 설정은 저널 프로파일**: 동봉된 한국학 47종 큐레이션(`assets/`)을 사본으로
  복사해 자기 분야 학술지로 편집하면 그 목록이 곧 커버리지입니다.
- 작업 루트는 `KCI_TRENDS_DIR` 환경변수(기본: cwd의 `kci-trends/`), Obsidian 적재는
  명시 인자를 줄 때만 켜집니다.
- 범위 고지: 초록·키워드 기반 분석이며(보고서가 `verification_scope: abstract-only`를
  스스로 명시), 다년 전분야 전수는 며칠 단위 — 표본 옵션으로 시작하는 것을 권합니다.

**사용법** — 연도와 분야를 자기 것으로 바꿔 넣습니다.

```bash
# Claude Code에서: 자연어 한 줄
"2025년 hanmun 분야 동향 코퍼스 만들어 보고서 내줘"

# AI 도구 없이 CLI로: <스킬 폴더> = plugins/kci-korean-studies-trends/skills/kci-korean-studies-trends
py -3 <스킬 폴더>/scripts/kci_ingest.py --journal-profile --journal-field hanmun --year 2025     --dry-run --corpus-out kci-trends/corpus.jsonl --no-robots-check                     # ① 수집
py -3 <스킬 폴더>/scripts/kci_trend_analysis.py --corpus kci-trends/corpus.jsonl     --year 2025 --field hanmun --out-dir kci-trends --report kci-trends/report.md        # ② 보고서
```

동봉 프로파일이 제공하는 분야 값: `hanmun` · `hanmun_education` · `history_education` ·
`korean_history` · `korean_language` · `korean_literature` · `korean_studies`.
자기 분야가 목록에 없으면 프로파일 JSON(`assets/`)을 사본으로 복사해 학술지와 분야명을
추가하고 `--journal-profile <사본 경로>`로 지정합니다 — 그 목록이 곧 수집 범위입니다.
동봉 47종은 한문학 전공자인 저자의 시야에서 고른 것이라, 다른 분야는 물론 각 분야
안의 학술지 커버리지도 불완전합니다. 자기 분야의 더 나은 학술지 목록을 만드셨다면
PR로 기여해 주시면 프로파일에 반영하겠습니다.
처음에는 `--per-journal-max 2` 같은 표본 옵션으로 소요 시간을 가늠하는 것을 권합니다.

## 알아 둘 것

- 스킬 본문이 언급하는 일부 동반 스킬(문서 도구·로깅·교차검증 등)은 이 마켓플레이스에
  없는 **권장 조합**입니다 — 없어도 각 스킬은 독립 동작합니다.
- 외부 연결은 전부 사용자 소유입니다: Obsidian은 명시적 `--vault` 인자로만, LLM API
  호출은 어떤 스크립트에도 없습니다.
- 산출물 폰트 기본값(세리프 Noto Serif CJK KR / 산세리프 Pretendard GOV Variable /
  고정폭 Sarasa Fixed K)은 `hanmun-research-assistant` SKILL.md의 «폰트 정책» 표가
  정의하며, 그 표를 고치면 전체가 따릅니다.
- 언어: 스킬 지침은 한국어·영어 혼용입니다. 대상 사용자가 한국학 연구자이기 때문입니다.

## 함께 쓰면 좋은 것 (별도 설치)

현대 한국어 산문 품질 도구는 전근대 문헌 연구라는 이 모음의 축과 달라 포함하지
않았습니다. 검토를 거쳐 함께 쓰는 외부 스킬은 다음과 같습니다.

| 용도 | 외부 스킬 |
|---|---|
| AI 티 제거 (문체·리듬) | [epoko77-ai/im-not-ai](https://github.com/epoko77-ai/im-not-ai) |
| 맞춤법·문서 스타일 일관성 | [DaleSeo/korean-skills](https://github.com/DaleSeo/korean-skills) |
| 번역문 번역투 교정 | [amondnet/yoonmoon](https://github.com/amondnet/yoonmoon) |
| 전보문 한국어 예방 (출력 스타일) | [snflkd/fluent-korean](https://github.com/snflkd/fluent-korean) |

## 라이선스

스킬별로 다릅니다 — `NOTICE.md`를 참고하십시오. 자체 저작분은 MIT입니다.
