---
name: kci-korean-studies-trends
description: Self-serve KCI Korean-studies trend reports - build your own year x field corpus from KCI (no API key; rate-limited collection - robots 고지 참조) and generate hallucination-resistant 동향 보고서 with topic clusters, representative-paper candidates, and journal breakdowns. Trigger - "OO년 OO분야 KCI 동향 코퍼스 만들어 보고서 내줘", 한국학/한문학/국어학/한국사 학술지 전수조사, 연도별·전공별 동향 보고서, 대표 논문 후보. 저널 프로파일(어떤 학술지를 어떤 전공으로 묶는지)은 동봉 기본값을 사용자가 편집해 자기 분야에 맞춘다.
metadata:
  version: 2.0.3
  category: academic-research
  suite: korean-humanities
  tier: portable
  share: kci-korean-studies-trends
---

# KCI Korean Studies Trends

기억이 아니라 **자기 코퍼스**로 동향 보고서를 만든다. 스크립트·저널 프로파일이 전부
이 스킬에 동봉돼 있어(2026-08-26 이식) 별도 파이프라인 없이 동작한다 — 코퍼스는
각자 수집한다. 필요한 세부 분야가 사람마다 다르기 때문이다.

## 사용자 설정 지점 (이식의 핵심)

| 설정 | 무엇 | 기본값 |
|---|---|---|
| **저널 프로파일** | 어떤 학술지를 어떤 전공(field)으로 묶는지 — **이 스킬의 핵심 설정**. `assets/kci_korean_studies_journals.json`(한국학 47종 큐레이션)을 사본으로 복사해 자기 분야 학술지로 편집하고 `--journal-profile <사본>`으로 지정 | 동봉 47종 |
| `KCI_TRENDS_DIR` (환경변수) | 코퍼스·큐·보고서가 쌓이는 작업 루트 | cwd의 `kci-trends/` |
| `--sleep` | KCI 요청 간격(초) — 수집 에티켓상 줄이지 않는다 | 스크립트 기본 |
| `--citation-lag-years` | 인용수 사용 하한(발행 후 N년 — 최신 논문 인용수는 무의미) | 2 |
| (선택) `--inbox` / `KCI_VAULT_NAME` | Obsidian vault 노트 적재 — **명시할 때만 켜짐**, 동향 용도에는 불필요 | 꺼짐 |

API 키 불필요 — 공개 검색 페이지를 수집한다. **robots 고지**: KCI의 robots.txt는
전면 Disallow라, robots를 준수하면 이 수집 자체가 불가능하다. 스크립트는 요청 간격
(sleep)·소규모 개인 연구 범위를 지키는 조건으로 `--no-robots-check`를 쓰며, 그 판단과
책임은 사용자에게 있다 — 대량·상업적 수집에는 쓰지 않는다. LLM 호출은 어떤 스크립트에도 없다.

## Grounding Rules

- 학술지·주제·논문·인용수·동향 주장을 지어내지 않는다 — 코퍼스에 없으면 없다.
- KCI 메타데이터·초록·키워드는 Layer 2. 보고서는 `verification_scope: abstract-only`를 명시한다.
- 원문 PDF를 읽기 전에는 주제·대표 논문을 «후보»라고 부른다.
- 논문 개별 언급에는 최소 제목·저자·학술지·연도·KCI ID를 붙인다.
- 인용수는 발행 연도가 `citation-lag-years`(기본 2년) 이상 지난 논문에만 적용한다.

## Workflow

### 0. 한 줄 호출로 시작한다

“2025년 hanmun 분야 동향 코퍼스 만들어 보고서 내줘”처럼 **연도·분야만 지정하면** 이 스킬이
아래 1→3을 대신 실행한다. 프로파일에 없는 분야면 프로파일 편집(사본 생성)부터 안내한다.

### 1. 코퍼스 수집 (연도 × 분야 샤드)

`${SKILL_DIR}` = 이 스킬 디렉터리. (macOS/Linux는 `py -3` 대신 `python3`.)

```bash
py -3 ${SKILL_DIR}/scripts/kci_ingest.py --journal-profile --journal-field hanmun \
    --year 2025 --dry-run --corpus-out kci-trends/kci_2025_hanmun_corpus.jsonl --no-robots-check
```

- `--journal-profile`(값 없이) = 동봉 기본 프로파일. 사본 경로를 주면 그것을 쓴다.
- `--dry-run`이 핵심 — vault 적재 없이 코퍼스 JSONL만 쓴다.
- 체크포인트 내장(`.queue/`) — 끊겨도 재실행하면 이어서 받는다.
- **소요 시간 고지**: 분야 하나·한 해 전수는 저널 수 × 논문 수 × sleep으로 수십 분,
  다년 전분야 전수는 며칠 단위다. `--per-journal-max`·`--journal-scan-max`로
  표본 수집부터 시작한다. 실측(2026-08-26): hanmun 4저널 × 2편 = 18편, 수 분.

### 2. (다년/다분야일 때) 샤드 병합

```bash
py -3 ${SKILL_DIR}/scripts/kci_merge_year_corpus.py --year 2025
```

샤드를 손으로 이어붙이지 않는다 — 중복 제거·프로파일 정합은 병합기가 한다.

### 3. 분석·보고서

```bash
py -3 ${SKILL_DIR}/scripts/kci_trend_analysis.py \
    --corpus kci-trends/kci_2025_hanmun_corpus.jsonl --year 2025 --field hanmun \
    --out-dir kci-trends --report kci-trends/2025_hanmun_trend.md
```

산출: 분야·세부분야·학술지·주제 CSV + 토픽 클러스터 JSON + 대표 논문 후보 +
Markdown 보고서(frontmatter에 `verification_scope: abstract-only` 명시).
`--field`를 빼면 전분야 종합 보고서.

## 알려진 한계

- 초록·키워드 기반이다 — 본문을 읽은 분석이 아니다. 보고서가 그 사실을 스스로 밝힌다.
- 프로파일에 없는 학술지는 존재하지 않는 것과 같다 — 커버리지는 프로파일 편집 품질에 비례한다.
- KCI 검색 화면 기준이라 등재 지연·검색 누락이 있을 수 있다(0-result 저널은 보고서 residual risk에 기록).

## Related

- `kci-citation-network` (같은 마켓플레이스) — 동향이 넓게 훑는다면 인용망은 깊게 잇는다.
- `academic-research-workflow` — 동향 보고서에서 연구사 서술로 넘어갈 때.
