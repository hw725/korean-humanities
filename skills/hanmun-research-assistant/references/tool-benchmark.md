# Academic AI Assistant Tool Benchmark

> **Local-instance document.** 이 문서는 SKILL.md «Local Instance Binding»이 채워진 로컬 스택(각 역할의 실물은 SKILL.md «Local Instance Binding» 표에 채운다) 기준으로 서술돼 있다. 이식자는 자기 스택으로 치환해 읽는다.

## Use

Read this file when a new AI research assistant, scientific agent, RAG system, scholarly search tool, Obsidian assistant, or annotation platform is proposed. The purpose is to decide whether to keep, cherry-pick, install, fork, connect, watch, or drop it for the CJK humanities assistant.

## Current Baseline as of 2026-06-06

| Tool | Role | License or openness | What to transplant | CJK humanities fit |
|---|---|---|---|---|
| Open Notebook | NotebookLM-style self-hosted research notebook | MIT | Project notebooks, source containers, REST API, multi-provider support, multi-source ingestion | High as UI/API shell, but citation rigor must be strengthened |
| PaperQA2 | Scientific literature RAG with citations | Apache-2.0 | Search, evidence gather, answer, citation flow, local PDF index, deterministic lower-token path | High for secondary literature; weak for premodern source criticism unless adapted |
| Khoj | Self-hosted second brain and custom agents | AGPL-3.0 | Obsidian integration, custom agents, scheduled research, docs and web Q&A | High for Obsidian workflows; AGPL affects redistribution and service design |
| NotebookLM | Closed source benchmark | Closed SaaS | Source-grounded chat, inline citations, study guide, briefing, mind map, audio overview expectations | Good feature benchmark, not a fork target |
| Elicit | Commercial academic review assistant | Closed SaaS with API | Search, reports, screening, extraction tables, sentence-level citation expectation | Useful for social-science review patterns, not CJK source work |
| Consensus | Commercial research answer engine | Closed SaaS | Large scholarly database, weekly refresh, full-text use when available | Useful as search benchmark, not a local assistant base |
| MARKUS | CJK DH annotation platform | AGPL v3 | Person and place tagging, bureaucratic offices, Buddhist terms, TEI export, ctext and CBDB links | Very high for classical Chinese and Hanmun annotation |
| HERITAGE or Hanja Platform | Korean Hanja historical document NLP | Research platform and paper | Punctuation restoration, NER, MT, interactive glossary, expert correction loop | Very high for Korean Hanja source handling |
| Chinese Text Project | Digital text corpus and API | Terms must be checked per use | Canonical text lookup, parallel passages, source identifiers | High for source lookup and comparison, not bulk scraping |
| INCEpTION | Semantic annotation and KB platform | Apache-2.0 | Collaborative annotation, recommender, entity linking, knowledge-base backed labels | High if a corpus annotation workbench is needed |
| AutoScientists | Long-running computational science agent team | Public repo; license must be checked before reuse | Shared state, discussion, queue, dead-end registry, experiment log | Pattern only; domain fit low |
| ToolUniverse | Scientific tool ecosystem and MCP | Apache-2.0 | Tool registry, compact mode, caching, async tool calls | Watchlist; biomedical focus is far from CJK humanities |
| Academic Research Skills (ARS, Imbad0202) | Claude-Code STEM·사회과학 research→publish 스킬 suite (Codex sibling이 academic-research-workflow의 upstream) | CC BY-NC 4.0 (비상업, 비-오픈소스) | L3 충실성 보정(locator anchor + 골드셋 FNR/FPR), data_access_level 3계층 격리, 벤치마크 보고 정직성 스키마 | 전근대 source criticism엔 낮음 — 한문·표점·이본·옛한글·HWPX·Obsidian 없음. 패턴만 차용, 플러그인 통째 설치 안 함 |

## Sources Checked

| Tool | Source |
|---|---|
| Open Notebook | https://github.com/lfnovo/open-notebook |
| PaperQA2 | https://github.com/Future-House/paper-qa |
| Khoj | https://github.com/khoj-ai/khoj |
| NotebookLM | https://support.google.com/notebooklm/answer/16164461 |
| Elicit | https://elicit.com/industries/edu |
| Consensus | https://help.consensus.app/en/articles/10055108-consensus-research-database |
| MARKUS | https://dh.chinese-empires.eu/markus/ |
| HERITAGE | https://arxiv.org/abs/2501.11951 |
| Chinese Text Project API | https://ctext.org/tools/api/ens |
| INCEpTION | https://github.com/inception-project/inception |
| AutoScientists | https://github.com/mims-harvard/AutoScientists |
| ToolUniverse | https://github.com/mims-harvard/ToolUniverse |
| Academic Research Skills (ARS) | https://github.com/Imbad0202/academic-research-skills (v3.11.1, checked 2026-06-06) |

## Evaluation Gates

Reject or watchlist a candidate unless it passes the relevant gates.

| Gate | Required evidence |
|---|---|
| Source grounding | Answers can cite source passages, pages, or stable local IDs |
| Local sovereignty | Data can stay local or export cleanly to local storage |
| Obsidian fit | Markdown, frontmatter, backlinks, or API path to vault notes |
| CJK text handling | Unicode, Hanja, Hanmun, old Hangul, PDF/HWPX extraction, or annotation tested |
| Citation audit | Claim-to-evidence checking is explicit, not just bibliography links |
| Corpus scale | Supports shard, checkpoint, and resume for 100 or more records |
| License | Fork, connector, or internal use rights are clear |
| Replaceability | Can be removed without corrupting source data or vault structure |
| Cost model | Avoids expensive default models and supports approved local or low-cost models |
| Logging | Produces or can be wrapped with JSONL events |

## Decision Rules

| Result | Use when | Action |
|---|---|---|
| `keep-current` | Existing local stack is better | Do not adopt |
| `cherry-pick` | Tool has one transferable pattern | Update this skill, local script, or audit-config benchmark |
| `connector` | Tool provides a useful source, API, or annotation path | Build a narrow connector |
| `install-candidate` | Tool fills a real gap and passes gates | Ask before install or fork |
| `watchlist` | Interesting but immature, costly, off-domain, or unclear license | Record and revisit |
| `drop` | Marketing-only, duplicate, unverifiable, or incompatible | Do not save beyond brief note |

## Audit Table

Use this table in `/audit-config` reports.

```markdown
| Candidate | Closest baseline | Passed gates | Failed gates | Decision | Customization target | Evidence |
|---|---|---|---|---|---|---|
```

## Benchmark Honesty (비교 보고 정직성)

로컬 스택 대 외부 도구 비교를 보고할 때(예: 「로컬이 X보다 낫다」류 주장)는 아래 없이는 벤치마크가 아니라 일화다. ARS v3.3.5 benchmark_report_pattern에서 방식만 차용.

- 표본 수(n) 명시 — 0 금지, n≤2면 경고와 함께 명시.
- 채점 독립성 명시 — `self-scored`는 경고, `blind-scored`(채점자가 어느 쪽이 로컬 산출물인지 모름)가 공개 주장의 최소 기준.
- 인간 기준선 출처 — 누가 수행했는지, 도구 허용 여부, 소요 시간. 도구 없는 인간 대 풀 파이프라인 비교는 인프라 격차를 재는 것이지 품질을 재는 게 아니다.
- caveats ≥ 1 — 한계 없는 보고는 자격 미달.
- cherry-picked win 금지 — 통과한 gate만 고르지 말고 실패 gate도 함께 보고한다(Evaluation Gates 전부).

## Current Build Recommendation

The default build remains:

1. `hanmun-research-assistant` for routing and adoption decisions.
2. `<vault>` for durable research memory.
3. `<vector-index>` for source-grounded document retrieval.
4. `<corpus-pipeline>` for paper intake and KCI/PDF routing.
5. `<reference-manager>` for bibliographic links.
6. Optional Open Notebook or Khoj only as UI layers after a small pilot.
7. PaperQA2 patterns for citation RAG, not as a wholesale replacement for CJK source criticism.
8. ARS 패턴(L3 충실성 보정, data_access_level 격리, 벤치마크 정직성)은 차용하되 플러그인 suite는 통째 설치하지 않는다 — ARW·`/deep-research`와 기능 중복, STEM 기본값 재유입. `/audit-config` 2026-06-06 판정: keep-current + cherry-pick.
9. Semantica 패턴(W3C PROV-O provenance, 결정 계보 `derived_from`, 충돌 기록)은 `knowledge-memory-workflow`의 facts/takes/thread_event 계약에 **문서 수준으로만** 차용하고 소프트웨어는 설치하지 않는다 — 그래프 스토어·벡터 스토어·Docker/Kubernetes를 전제하는 엔터프라이즈 구성이라 이 환경에 과하고, CJK 텍스트 처리 특화도 없다. 추가 필드 3개(`prov`·`derived_from`·`conflicts_with`)는 기존 JSONL에 얹히며 새 DB를 만들지 않는다. `/audit-config` 2026-08-11 판정: cherry-pick (AUD-20260810-163430-92f29e7e).

## Audit 이력 (개별 판정)

| 일자 | Candidate | Closest baseline | Passed gates | Failed gates | Decision | Customization target | Evidence |
|---|---|---|---|---|---|---|---|
| 2026-08-11 | Semantica (MIT) | knowledge-memory-workflow + hanmun-research-assistant | W3C PROV-O provenance · self-hostable · CLI/MCP/REST · 결정 이력·audit trail 명시 | CJK 텍스트 처리 특화 부재 · Obsidian 로컬 워크플로 직접 적합성 낮음 · 그래프·벡터 스토어 전제의 운영 복잡도 | cherry-pick | `knowledge-memory-workflow/references/knowledge-contracts.md` §Provenance와 결정 계보 | [저장소](https://github.com/semantica-agi/semantica) · [LICENSE](https://github.com/semantica-agi/semantica/blob/main/LICENSE) · AUD-20260810-163430-92f29e7e |
