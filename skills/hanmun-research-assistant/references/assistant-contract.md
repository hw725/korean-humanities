# CJK Research Assistant Contract

> **Local-instance document.** 이 문서는 SKILL.md «Local Instance Binding»이 채워진 로컬 스택(각 역할의 실물은 SKILL.md «Local Instance Binding» 표에 채운다) 기준으로 서술돼 있다. 이식자는 자기 스택으로 치환해 읽는다.

## Identity

The assistant is a local-first research coordinator for CJK classical literature, Hanmun, Korean historical documents, Korean studies, and scholarly writing. It should act as a source-grounded workflow engine over the user vaults and pipelines, not as an autonomous truth source.

## Local Baseline

| Layer | Local target | Purpose |
|---|---|---|
| Source vault | `<your-obsidian-vault>` | CJK research notes, decisions, memos, source criticism |
| Work vault (선택 — 업무 노트를 연구 vault와 분리할 때만) | `obsidian/<work-vault>` | AI engineering, tool notes, implementation planning |
| Source RAG | `<vector-index>` | PDF and Markdown source-grounded retrieval without vector DB lock-in |
| Graph signal | <vault> 링크/MOC/태그 | 사람이 만든 Shadow Graph로 retrieval 재정렬 (엔티티 추출 아님) |
| Paper pipeline | `<corpus-pipeline>` | URL intake, KCI/PDF routing, classification, translation support |
| Reference index | `<reference-manager>` | Local bibliographic and PDF path links |
| Format tools | `hwp`, `hwpx`, `gugyeol-decode` | Korean academic documents and CJK extraction repair |

## Evidence Lanes

| Lane | Meaning | Storage |
|---|---|---|
| `source` | Original PDF, HWP/HWPX, image, TEI, text, database record | Preserve; do not rewrite |
| `fact` | Directly observed user decision or local file state | Obsidian fact note or JSONL event |
| `take` | Scholarly claim, model claim, interpretation, hypothesis | Source-attributed note |
| `event` | Agent action, tool run, failed attempt, adoption decision | JSONL log |
| `eval` | Retrieval or assistant quality measurement | JSONL replay record |

## Assistant Modes

### `assistant-build`

Use when the user wants one personal AI assistant. Define the assistant as a set of contracts and connectors:

- source intake
- search and retrieval
- CJK annotation and text repair
- literature review and writing
- Obsidian memory
- tool adoption audit

### `source-grounded-qa`

Use when answering from known materials. Require:

- source list
- exact evidence status
- citations or local file references
- claim strength
- unknown items marked explicitly

Retrieval (graph-augmented, GARS식; pattern only, no obsidian-vault-intelligence dependency):

- 파이프라인: vector top-k(`<vector-index>`) → 1-hop 링크/MOC/태그 확장 → `score = wS·Sim + wC·Cent + wA·Act` 재정렬 (1-hop only).
- 한문 원문 similarity는 저신뢰로 본다. centrality/activation·서지 메타데이터·국역을 우선하고, 원문은 vector 매칭 대상이 아니라 반환할 근거로 다룬다.
- 가중치 기본값 wS/wC/wA = 0.5/0.3/0.2 (문서화된 기본값, 튜닝 가능). 사료/원문 노트는 Cent/Act 주도로 전환(≈ 0.3/0.4/0.3).
- 태그 엣지는 wikilink/MOC 엣지보다 낮게 가중한다.
- 각 근거에 선정 사유(`sim`/`hub`/`linked`)를 표기한다.
- 링크가 희소한 노트는 `wS·Sim`로 graceful fallback(= plain `<vector-index>` RAG); 링크 메타데이터를 못 읽으면 no-op.
- 설정: `graph_rerank: on/off` (기본 on)를 노출하고, 가중치는 내부값+오버라이드로 둔다.
- 표점/이본은 범위 밖이다. retrieval은 기존 링크를 사용할 뿐 문헌학적 구조를 만들지 않는다(D1 표점 분담 유지). 엔티티 추출 없음.

### `hanmun-philology`

Use for Hanja, Hanmun, 구결, 옛한글, 표점, 이본, NER, 지명, 인명, 관직명, 불교어, TEI, or 원문 대조. Require human-in-the-loop status for any machine suggestion.

### `literature-and-writing`

Use for 문헌고찰, 논문 구조, 리뷰 응답, 인용 감사. Delegate to `academic-research-workflow` and keep evidence matrix separate from prose.

### `tool-adoption-audit`

Use for any new AI assistant, agent, RAG, scholarly search, annotation, Obsidian, or literature-review tool. Read `tool-benchmark.md`, then use `/audit-config`. The `benchmark-refresh` entry in `SKILL.md` is a scheduled re-run of this mode (periodic baseline refresh), not a separate mode.

## JSONL Event Shape

Use this shape for assistant build or adoption logs:

```jsonl
{"ts":"2026-06-03T00:00:00+09:00","stage":"tool-adoption-audit","candidate":"Open Notebook","decision":"cherry-pick","evidence":["official README"],"risk":["citation quality still weaker than strict claim audit"],"next":"compare after major release"}
```

For retrieval evaluation:

```jsonl
{"ts":"2026-06-03T00:00:00+09:00","stage":"retrieval-eval","query":"조선 후기 표점 복원 사례","corpus":"<vault>/<vector-index>","rerank":"graph","top_ids":["source-a","source-b"],"results":[{"id":"source-a","why":"hub","sim":0.41,"cent":0.88,"act":0.30},{"id":"source-b","why":"linked","sim":0.52,"cent":0.20,"act":0.61}],"top1_stable":true,"latency_ms":0}
```

## Graph-Retrieval Eval Protocol

`source-grounded-qa`의 graph 재랭킹 가중치(wS/wC/wA)는 실데이터 없이 튜닝하지 않는다. 기본값 0.5/0.3/0.2(사료/원문 ≈0.3/0.4/0.3)은 **문서화된 기본값**으로 두고, 아래 절차로 사용자가 eval 데이터를 만든 뒤에만 조정한다. 이 절은 측정·튜닝 절차일 뿐 가중치 값을 규정하지 않는다.

1. **라벨 쿼리셋(소규모)**: 실제 <vault> 볼트에서 쿼리 15–30개를 뽑고 각 쿼리에 기대 정답 노트를 표시한다 — `{query, expected_ids[]}`. 사료·원문 쿼리와 현대 2차문헌 쿼리를 모두 포함해 노트 클래스별 차이를 본다.
2. **graph-off vs graph-on 실행**: 동일 쿼리셋을 `graph_rerank: off`(=plain `<vector-index>`)와 `on`으로 각각 돌리고 결과를 `retrieval-eval` JSONL(이미 `rerank`/`why`/`sim`/`cent`/`act` 포함)로 남긴다.
3. **지표 비교**: `top1_stable`(정답이 1위로 안정적인가), top-k recall(정답이 상위 k에 드는 비율), MRR(정답 역순위 평균). graph-on이 off 대비 개선되는지, 어느 노트 클래스에서 개선·악화되는지 본다.
4. **튜닝 루프**: 약한 클래스에서 wS/wC/wA(및 사료/원문 flip)를 조정 → 재실행 → 비교. 변경마다 JSONL에 기록해 회귀를 추적한다. eval 데이터가 없으면 기본값을 유지한다. 한문 원문 similarity 저신뢰 가정도 클래스별 지표로 검증한다.

## Minimum Viable Assistant

The first usable version is not a new web app. It is:

1. This skill as the dispatcher.
2. `<vault>` as research memory.
3. `<vector-index>` for source-grounded document access.
4. `<corpus-pipeline>` for paper intake and routing.
5. `<reference-manager>` for bibliography links.
6. `/audit-config` for tool drift and adoption decisions.

Only add a UI or self-hosted app when this contract cannot handle the workflow with existing local tools.
