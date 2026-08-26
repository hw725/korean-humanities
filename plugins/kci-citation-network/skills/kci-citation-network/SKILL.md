---
name: kci-citation-network
description: Self-serve KCI citation network builder - give it a keyword (연구 주제·인물·저자) and it collects a citation network from the KCI 참고문헌 OpenAPI, then optionally renders linked Obsidian notes with Graph View. For Korean humanities, where OpenAlex has no coverage. Trigger - "OO 키워드로 인용망 수집해줘", 인용망/인용 네트워크/citation graph of 한문학·한국사·국어학 papers, KCI references to Obsidian wikilinks. Needs a free data.go.kr API key (env KCI_DATA_GO_KR_KEY_DECODING).
metadata:
  author: custom
  version: 1.2.0
  category: cjk-research
  suite: korean-humanities
  tier: portable
  share: kci-citation-network
---

# KCI Citation Network

## Overview

Korean humanities citation data is **not in OpenAlex** (verified: Korean journal articles return `referenced_works=0`, `cited_by_count=0`). The working source is the 한국연구재단 **KCI 참고문헌 서비스** on data.go.kr. This skill collects references via that API and renders a citation network into an Obsidian vault — the Korean-humanities equivalent of the Zotero Citation-Network tool, but keyed on KCI IDs instead of DOIs.

**Verified reality (2026-07):** ~25% of a Korean humanities paper's references carry `REFE_BIBL_ARTI_ID` (an exact KCI-article join key → direct citation edge, no fuzzy matching). The rest are 문집·단행본·해외·학위논문 (not KCI-indexed) and stay as text references. A focused corpus (one author/topic) yields a dense connected network; a broad sample yields a sparse one.

## The one non-obvious fact

The reference endpoint is `refInfo/openApiM320List` — **prefix `M`, not `D`**. The `D`-prefix operations are traps:
- `openApiD272List` (OA학술지-참고문헌): OA full-text 반입 논문 전용 → **empty for 한문학/국어학**.
- `openApiD321List` (KCI참고문헌공동저자): partial author subset only (0–10 refs).
- `openApiM320List` (KCI참고문헌): **full reference list** with `TITL`, `CRET_NM`, `PUBI_YR`, and `REFE_BIBL_ARTI_ID`.

Params: `serviceKey`, `pageNo`, `recordCnt` (**max 100** — larger is rejected), `artiId`. Response is XML.

## Prerequisites

- **API key**: a data.go.kr service key with the **KCI 참고문헌 서비스**(15085323) 활용신청 approved (free, 자동승인, 5,000 req/day). Set it as the `KCI_DATA_GO_KR_KEY_DECODING` environment variable, or put it in a `.env` file in your working directory. Scripts never print the key.
- Scripts are **vendored and fully self-contained** (stdlib-only, no pip install): `scripts/kci_citation_collect.py`(수집), `scripts/kci_search.py`(키워드 씨앗 검색), `scripts/kci_graph_to_wiki.py`(Obsidian 렌더 — 선택).
- **외부 결합은 전부 사용자 설정이다**: Obsidian은 렌더 단계의 `--vault` 인자로만 연결되고(렌더를 건너뛰면 JSONL만 남음), LLM 호출은 어디에도 없다. 고급: 자체 수집 파이프라인이 있으면 `KCI_INGEST_DIR` 환경변수로 그쪽 검색기를 우선시킬 수 있다(없으면 동봉 kci_search 사용).

## Workflow

### 0. 스킬 호출 한 줄이면 된다

사용자가 "「운양 김윤식」으로 인용망 수집해줘"처럼 **키워드만 주면**, 이 스킬이 아래 1→2를
대신 실행한다: `--query`로 씨앗을 모으고, 제목 목록을 보여 동명이인·무관 논문을 걸러
확인받은 뒤 수집한다. 키가 없으면 발급 절차(위 Prerequisites)부터 안내한다.

### 1. Collect the network

Run from any working directory — outputs land under `--out-dir` (cwd-relative). `${SKILL_DIR}` below means this skill's directory. (macOS/Linux에서는 `py -3` 대신 `python3`.)

```bash
# 검색어로 씨앗 자동 수집 — 동봉 kci_search가 처리, 추가 설치 불필요
py -3 ${SKILL_DIR}/scripts/kci_citation_collect.py --query "운양 김윤식" --max 40 --out-dir out/kys
# 또는 큐레이션한 artiId 목록(줄당 "ARTID<탭>제목<탭>연도")
py -3 ${SKILL_DIR}/scripts/kci_citation_collect.py --arti-ids seeds.tsv --out-dir out/kys
# 스노볼: 인용된 KCI 논문도 노드로 1홉 확장
py -3 ${SKILL_DIR}/scripts/kci_citation_collect.py --query "운양 김윤식" --snowball --out-dir out/kys
```

실측(2026-08-26): `--query "운양 김윤식" --max 3` → 3편 처리, 노드 17·엣지 14,
직접인용률 26.4% — 아래 「~25%」 서술과 일치.
Outputs `out/kys/{nodes,edges,refs}.jsonl` + `collect.seen` (checkpoint/resume). 100건↑는 나눠 실행.

**Disambiguation matters.** `--query` uses KCI KEYALL and over-matches (e.g. "김윤식" hits both 雲養 金允植 1835 and 국문학자 김윤식 1936). Review titles and curate a seed TSV for a clean set.

### 2. Render into the vault

```bash
py -3 ${SKILL_DIR}/scripts/kci_graph_to_wiki.py --in-dir out/kys \
    --vault "<vault-root>" --folder "wiki/인용망/운양김윤식" --seeds-only
```
- `--seeds-only`: 씨앗 논문만 노드로 (피인용된 외부 KCI 논문 제외) → 깨끗한 코어 인용망. 생략 시 인용된 KCI 논문까지 노드(스노볼형).
- Writes one note per paper with `[[wikilinks]]` for 인용/피인용. Auto region is between `<!-- KCI-AUTO -->` markers; manual 메모 below is preserved on re-run.
- Respects the vault contract: writes only under `wiki/` (never `references/`, `writing/`, `highlights/`).

### 3. Index and view

Obsidian Graph View → filter `path:"인용망/..."` to see the citation network. Foundational papers surface as high-in-degree hubs. If your vault has a search/embedding index (e.g. qmd), re-index after the write — wiki 노트가 새로 생겼기 때문이다.

## Provenance

이 스킬의 `scripts/` 3종이 canonical이다. `<corpus-pipeline>/scripts/`의 동명 파일(collect·graph_to_wiki)은 파이프라인 통합용 사본이며, 로직을 고칠 때는 여기를 먼저 고치고 그쪽에 반영한다. `kci_search.py`는 kci_ingest의 검색 계층 발췌(분기: 한자 감지를 문자클래스에서 코드포인트 판별로 교체 — 확장 B 커버, CJK 계약 준수).

## Limits (state honestly)

- This is a **2차 문헌(연구논문) 간** network. 한문 원전·1차 사료(문집 등)는 KCI 논문이 아니라 노드가 아니다 (text reference로만 남음).
- Exact edges cover only KCI-indexed references (~25%). Non-KCI refs are not linked (could add author+year fuzzy matching against the vault as a future enhancement).
- KCI website's full 참고문헌 view is login-gated, but this API path does not require KCI login — only the data.go.kr key.

## Related

- Suite: `hanmun-research-assistant` (front door) → `academic-research-workflow` (연구사·심사). Local-tier: `kci-korean-studies-trends` (동향 보고 — 로컬 코퍼스 필요).
