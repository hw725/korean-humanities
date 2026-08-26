# 플러그인별 상세 안내

각 플러그인이 무엇을 하고 무엇을 지키는지, 그리고 자기 값(키워드·연도·분야)을
어디에 넣어 실행하는지를 설명합니다. 설치 방법은 [INSTALL.md](INSTALL.md)를 보십시오.

## 기능과 보증

## `korean-humanities` — 연구 방법론 (스킬 3종, 준비물 0)

| 스킬 | 하는 일 | 지키는 것 (행동 보증) |
|---|---|---|
| `academic-research-workflow` | 연구사 리뷰 · 사료비평/이본 교감 · 논증 설계·초고 · 인문학 루브릭 심사 · 인용/원문 충실성 감사 · 투고 직전 원고-데이터 전수 대조 | 사료·참고문헌·수치를 지어내지 않고 미확인은 `unverified`로 남김 · 기계 국역(ITKC aitr 등)은 원문 대조 전 인용 금지 · 표점/독법이 갈리면 경쟁 독법을 함께 제시 · 해석 평가는 개연성·정합성 기준, 단 연대·인용 같은 사실 주장은 검증 대상 |
| `hanmun-research-assistant` | 연구 비서 구축·운영 라우터 — 문집·원문 source-grounded Q&A, 사료 디지털화 워크플로, 새 학술 AI 도구 심사. 슈트 공통 CJK 텍스트 계약(UTF-8·유니코드 정규식·NFC·폰트 정책) 소유 | OCR·번역·검색 결과를 검증 없이 사실로 승격하지 않음 · 증거 접근 3계층(raw/verified/gold) 격리 · 본문이 언급하는 동반 스킬은 권장 조합일 뿐, 없어도 단독 동작 |
| `academic-english-editing` | 한국어 학술 원고 → 영어 — 한국어가 생략한 논리 연결 복원, 문장 길이 밴드, 학술 hedging 보정, CJK 고유명사·간지 연대 표기 고정 | 절 단위 직역 금지 · 과잉주장 점검 · 로마자 표기(MR/RR)는 사용자 설정을 따름 |

동봉 `tools/`: `setup-terminal-utf8.ps1`(Windows 한글 깨짐 뿌리 3곳 영구 차단 — 강력 권장,
idempotent) · `check_cjk_text_contract.py`(자기 스크립트의 인코딩·정규식 계약 검사, AST 기반).

## `gugyeol-decode` — 깨진 구결·옛한글 복원 (도구 스킬)

PDF·HWPX에서 `(cid:6)`이나 PUA로 깨져 나오는 구결자(口訣, MR kugyŏl)·옛한글을 표준
유니코드로 복원합니다. **매핑 데이터(한양 PUA + AKS 표준, 약 3.6MB) 동봉** — 다운로드
불필요. PDF 입력만 `pip install pymupdf`가 필요하고 HWPX는 표준 라이브러리로 처리합니다.
자동 매핑이 못 푸는 글자는 못 풀었다고 보고합니다(추측 치환 없음).

## `kci-citation-network` — KCI 인용망 수집기 (키워드만으로 직접 수집)

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

## `kci-korean-studies-trends` — KCI 동향 코퍼스·보고서 (연도·분야만으로 직접 수집)

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
