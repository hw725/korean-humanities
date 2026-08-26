---
name: hanmun-research-assistant
description: Super-router for hanmun (Korean Literary Sinitic) humanities research - build, operate, and audit a source-grounded personal AI research assistant for 한문학·전근대 한국 문헌. Owns the suite-wide CJK text contract (UTF-8 강제·regex 유니코드 매칭·NFC·폰트 정책). Trigger - 한문학 연구 비서, 문집·한문 원문 source-grounded Q&A, 한문 사료 디지털화 워크플로 라우팅, 전근대 문헌 지식관리(Obsidian), 새 학술 AI 도구 비교·도입 심사, 연구 비서 커스터마이징, 한글 인코딩 깨짐·CJK 정규식 문제. Delegates 논문 집필·연구사·심사·인용 감사 to academic-research-workflow, 구결·옛한글 복원 to gugyeol-decode.
metadata:
  author: custom
  version: 0.8.0
  category: cjk-research
  suite: korean-humanities
  tier: portable
  share: korean-humanities
---

# Hanmun Research Assistant

> 구 `cjk-research-assistant` — 2026-08-26 개명. 사용자 전공은 한문학(한국의 전근대
> 한문 기록 문학)이라 C·J 학문까지 암시하는 cjk가 과대 표기였다. 아래 «CJK Text
> Handling Contract» 절 이름의 CJK는 학문 범위가 아니라 **문자 층위**(유니코드
> CJK Unified Ideographs·확장 평면)를 가리키므로 유지한다.

## Overview

Use this skill as the single router for the user research assistant. It does not replace specialist skills; it selects and coordinates them around a CJK humanities contract grounded in local sources, Obsidian structure, JSONL logs, and explicit claim verification.

## Operating Contract

- Treat the assistant as a research workflow, not a generic chatbot.
- Prefer local evidence first — your **vault**, **corpus pipeline**, **vector index**, and **reference manager** — then authoritative external databases. (이 문서는 네 가지를 역할 이름으로 부른다; 실제 설치물 대응은 맨 아래 «Local Instance Binding» 절이 정의한다.)
- Keep source facts, scholarly claims, user decisions, and agent events separate.
- Never convert OCR, translation, NER, or RAG output into a fact without source status and verification scope.
- Use JSONL for work logs, retrieval evaluation, screening decisions, and tool adoption decisions.
- For 100 or more records, require shard, checkpoint, and resume from the first run.

## CJK Text Handling Contract (슈트 전체 필수 — 인코딩·정규식)

한문·옛한글·구결을 다루는 모든 작업의 기반 계약이다. CJK 문자 파이프라인의 만성 사고를
**규율이 아니라 기계 검사**로 차단한다. 슈트의 모든 스킬·스크립트에 적용된다.

1. **모든 텍스트 파일 I/O에 `encoding="utf-8"`을 명시한다.** Windows에서 미명시 기본값은
   locale(cp949)이라 한자·옛한글·구결 PUA가 **예외 없이 조용히** 깨진다. `py -X utf8` /
   `PYTHONUTF8=1` 실행은 권장 사항일 뿐 방어선이 아니다 — 코드가 그것에 의존하면 안 되고,
   명시가 정본이다. (열려는 대상이 바이너리면 `"rb"`/`"wb"`로 그 사실을 드러낸다.)
1-b. **한글·한자를 출력하는 스크립트는 stdout/stderr도 UTF-8로 고정한다.** 파일 I/O만
   막고 표준 출력을 두면 같은 사고가 콘솔에서 난다 — Windows에서 `python foo.py --help`가
   `UnicodeEncodeError: 'cp949' codec can't encode character`로 죽는다(2026-08-26 실측:
   `verify_manuscript_numbers.py --help`가 argparse 도움말의 em dash에서 터졌다).
   진입점 상단에 다음을 둔다:
   ```python
   for _s in (sys.stdout, sys.stderr):
       if hasattr(_s, "reconfigure"):
           _s.reconfigure(encoding="utf-8", errors="replace")
   ```
   `PYTHONUTF8=1`이나 `py -X utf8`은 사용자 환경에 의존하므로 방어선이 아니다(§4 참조).
2. **CJK 문자 클래스·프로퍼티 매칭은 stdlib `re` 금지, `regex` 모듈을 쓴다**
   (`pip install regex` 전제). `re`는 유니코드 프로퍼티를 지원하지 않아 `[가-힣]`·
   `[一-鿿]` 하드코딩으로 흐르는데, 그 범위는 옛한글 첫가끝 자모(U+1100·U+A960·
   U+D7B0), 한자 확장 B 이상(U+20000+), 한양 PUA 구결을 전부 놓친다. `regex`의
   `\p{Han}`·`\p{Hangul}`을 쓴다. ASCII 구조 패턴(XML 태그·ID 형식·공백·파일명
   새니타이즈)은 stdlib `re`로 충분하며 의존성 0을 유지한다.
3. **한글 비교·검색 전 NFC 정규화.** NFD 유입원(macOS 파일명·일부 PDF 추출기)이 섞이면
   눈에 같은 문자열이 매칭에 실패한다. `unicodedata.normalize("NFC", s)`를 입구에서 한 번.
4. **터미널·환경 기본값 고정.** 코드의 `encoding=` 명시(§1)와 별개로, 환경 자체의 깨짐
   뿌리 3곳을 사용자 수준에서 영구 차단한다 — `tools/setup-terminal-utf8.ps1`(idempotent, `-Check` 지원)이 실행체다: ① `PYTHONUTF8=1` 사용자 환경변수(파이썬 파일 I/O 기본값이
   cp949→utf-8; §1의 대체가 아니라 이중 방어선) ② PowerShell 프로필(5.1·7)에 콘솔
   입출력 UTF-8 + `chcp 65001` ③ `git core.quotepath=false`(한글 파일명이 `\354...`
   이스케이프로 깨지는 것 차단). 시스템 ACP(레지스트리 Beta UTF-8)는 **의도적으로 건드리지
   않는다** — HWP 등 구형 한국어 앱을 깨뜨릴 수 있다. 새 PC 셋업 시 이 스크립트를 돌린다.

## 폰트 정책 (산출물 공통 — 사용자 편집 지점)

HTML·artifact·다이어그램·문서 산출물의 폰트는 아래 역할 표를 따른다. **이 표가 SSOT다** —
바꾸고 싶으면 이 표를 고치면 슈트 전체가 따른다. 여기 없는 폰트를 산출물에 임의로 쓰지 않는다.

| 역할 | 1순위 | 대안 (다국어·미설치 폴백) | CSS 스택 |
|---|---|---|---|
| 세리프 (본문·인용·원문) | Noto Serif CJK KR | — | `'Noto Serif KR', 'Noto Serif CJK KR', serif` |
| 산세리프 (UI·제목·표) | Pretendard GOV Variable | Spoqa Han Sans Neo · Noto Sans CJK KR (다국어) | `'Pretendard GOV Variable', 'Pretendard GOV', 'Spoqa Han Sans Neo', 'Noto Sans KR', 'Noto Sans CJK KR', sans-serif` |
| 고정폭 (코드·터미널·대조표) | Sarasa Fixed K | Jetendard | `'Sarasa Fixed K', 'Jetendard', monospace` |

- 터미널 폰트는 자동 설정하지 않는다(Windows Terminal 설정은 사용자 소유) — 고정폭 1순위를
  수동 지정하라고 안내만 한다.
- HWP/HWPX 문서는 **제출처 서식 요구가 이 표보다 우선**한다(기관 지정 서체가 있으면 그것).
- 한계(신뢰도 보통): 위 폰트들의 옛한글 첫가끝 조합·한자 확장 B+ 커버리지는 완전하지 않을
  수 있다. 옛한글 표시가 필요한 산출물은 렌더 확인 후 필요 시 옛한글 지원 폰트를 해당
  산출물에만 예외 지정하고, 예외 사실을 산출물에 기록한다.

**기계 검사**: `tools/check_cjk_text_contract.py`가 E1(open
인코딩)·E2(read_text/write_text 인코딩)·R1(CJK 패턴의 stdlib re 매칭)을 AST로 검사한다.
이 배포물은 빌드 시 이 검사 게이트를 통과했다.
수동 실행:

```bash
py -3 tools/check_cjk_text_contract.py skills/<skill>/scripts
```

적용 경계: 슈트(`suite: korean-humanities`) 소속 스킬. 슈트 밖 스킬(예: humanize-korean —
현대 한국어 산문 전용이라 `[가-힣]`이 정당)에는 강제하지 않는다.

## Evidence Access Layers (증거 접근 계층)

모든 산출물은 세 계층 중 하나에 속하고, 승격은 한 방향(게이트 통과)만 가능하다. Layer 3는 답을 생성하는 에이전트의 컨텍스트에 절대 동석시키지 않는다(epistemological firewall). 이 모델은 ARS v3.3.2의 ground-truth isolation(`Imbad0202/academic-research-skills`, CC BY-NC 4.0; Anthropic automated-w2s-researcher 2026에서 유래)을 CJK 인문학으로 재구성한 것이다.

| `data_access_level` | 계층 | CJK 인문학 대응 |
|---|---|---|
| `raw` | Layer 1 (미검증) | 원문 스캔·미교정 OCR, 기계 국역 초벌, 웹·DB 검색 결과, 미검증 참고문헌 — 적대적·환각·오독 가정 |
| `redacted` | 경계 1→2 | 정제됐으나 새 원자료 유입 없음 |
| `verified_only` | Layer 2 (검증) | 원문 대조·표점·교감 확정, 출전 실재 확인 인용, 충실성 감사 통과 산출물 — 논증·초고에 잠정 신뢰 |

- Layer 3(평가 기준): gold sample, 충실성 감사 정답셋, retrieval eval gold. repo에 임베드하지 말고 런타임에 제공한다.
- `source-grounded-qa`·`deep search` 같은 raw 소비 모드는 어떤 사실도 검증 없이 하류로 넘기지 않는다. `primary_data/` 읽기 전용과 100건+ shard·checkpoint는 이 계층의 하위 규칙이다.

## Mode Router

> Partner skills 열은 **권장 조합**이다 — 설치돼 있지 않으면 해당 역할을 수동으로 수행하거나 생략하면 되고, 이 스킬의 라우팅 자체는 단독으로 동작한다.

| User need | Primary mode | Partner skills |
|---|---|---|
| One assistant for CJK research | `assistant-build` | `knowledge-memory-workflow`, `research-file-management`, `obsidian-cli` |
| Compare or adopt a new AI research tool | `tool-adoption-audit` | `url-triage`, `source-command-audit-config`, `model-selection` |
| Literature review or paper plan | `literature-and-writing` | `academic-research-workflow`, `kci-korean-studies-trends`, `cross-validation` |
| Citation or claim verification audit | delegate -> `academic-research-workflow` (`source-fidelity-audit` / 사료 충실성 감사) | `cross-validation`, `knowledge-memory-workflow` |
| Source-grounded Q&A over PDFs or vault notes | `source-grounded-qa` | vector index + graph 재랭킹 over vault 링크/MOC/태그 (graph-augmented retrieval), `knowledge-memory-workflow`, `obsidian-cli` |
| Classical text annotation, hanja, hanmun, old Hangul, gugyeol | `hanmun-philology` | `gugyeol-decode`, `hwp`, `hwpx`, `obsidian-cli` |
| Tool portfolio refresh | `benchmark-refresh` | `source-command-audit-config`, `observability-logging` |

> **graph 재랭킹은 사람이 만든 링크 기반 (CJK-safe).** `source-grounded-qa`의 graph 신호(centrality/activation)는 사용자가 직접 작성한 vault 링크·MOC·태그(Shadow Graph)에서만 나온다. 한문 텍스트에 엔티티 추출(NER)을 하지 않으므로 약한 hanmun NER이 retrieval을 저하시키지 않는다. microsoft식 entity-GraphRAG(엔티티·커뮤니티 추출 인덱싱)는 도입하지 않는다 — graph는 무료의 사람-작성 링크만 사용한다.

## Workflow

1. Classify the request into one mode from the router.
2. Identify evidence boundaries: local source, local derived artifact, external authority, or unverified.
3. Choose the narrowest existing specialist skill or local script before inventing a new tool.
4. Produce a concrete artifact: note, evidence matrix, tool comparison table, JSONL log, connector plan, or edit.
5. If a new external tool is involved, read `references/tool-benchmark.md` and route through `/audit-config`.
6. If a reusable behavior emerges, update this skill or its references instead of adding scattered prompt text.

## Execution Model: Dynamic Harness

The default Claude Code harness is built for coding (Thariq, “A harness for every task: dynamic workflows in Claude Code,” 2026-06-02). Research work writes its own task-specific harness instead of forcing every task through one fixed loop.

- Simple or conversational request: answer through the mode router. Do not build a harness.
- Large, repeated, or deterministic work (100+ witness collation, corpus embedding, batch punctuation or translation, citation audit): generate a task-specific harness with the `Workflow` tool.
  - State lives in the filesystem: a layered directory convention plus git, the vault, and JSONL logs as the single source of truth. Do not pull raw data into context.
  - Compute runs as code: heavy steps (CollateX alignment, Scrapling intake, aggregation) run in subprocesses, not in model context. Solve non-coding tasks with code too.
  - Decompose with subagent fan-out: parallel per witness, document, or source. Before any expensive step, run one independent critique (`cross-validation`, `design-review`) to kill dead ends early (AutoScientists pattern).
  - Persist across sessions: shard, checkpoint, and resume. Within a live session, iterate to the completion goal with `/goal` or `/loop`; both stop when the session or PC closes. Work that must survive a closed session goes to cloud `/schedule` (or an OS scheduled task), resuming from the checkpoint. A passing happy path is not verification — see `cc-workflow`’s primitive selection table and deterministic gates.
- Log the harness choice as an `event` so the next run can reuse or improve it.

## Imported Tool Patterns

Use external tools as design evidence, not automatic dependencies.

- From Open Notebook: project notebooks, source containers, multi-source ingestion, REST/API automation, provider choice.
- From PaperQA2: search, evidence gathering, answer synthesis, citation checking, local paper index, lower-token deterministic call paths before agentic paths.
- From Khoj: Obsidian-first second brain, custom agents, scheduled research, local or cloud model choice.
- From NotebookLM, Elicit, and Consensus: source-grounded chat, sentence-level citation expectations, screening and extraction tables, but closed tools stay benchmark references.
- From MARKUS, HERITAGE, Chinese Text Project, and INCEpTION: CJK annotation, entity linking, hanja NLP, TEI/export, and human-in-the-loop correction.

For the current baseline, read `references/tool-benchmark.md`. For the assistant behavior contract, read `references/assistant-contract.md`.

## Output Contract

Always report (대화형 첫 응답·온보딩에서는 mode·decision·next 3필드 요약으로 충분하다 — 전체 6필드는 산출물이 있는 턴에):

- `mode`: selected mode.
- `verified_inputs`: what was read or checked.
- `decision`: keep, cherry-pick, install candidate, build connector, watchlist, or drop.
- `artifact`: file, note, table, log, or plan created.
- `residual_risk`: what remains unverified.
- `next_audit_trigger`: when to compare again.

## Guardrails

- Do not install a new assistant stack merely because it is new or popular.
- Do not route CJK source criticism through STEM benchmark defaults without a local evaluation sample.
- Do not treat social-science evidence synthesis tools as adequate for premodern texts unless original text handling, annotation, and source provenance are tested.
- Do not move or rewrite `primary_data/`.
- Do not recommend `gpt-4` or `gpt-4o` defaults; replace expensive defaults with approved model choices or local endpoints.

## Local Instance Binding (역할 이름 → 내 환경의 실물)

본문은 설치물 이름이 아니라 **역할 이름**으로 말한다. 이 스킬을 다른 환경에 이식할 때는 이 표만 바꾸면 된다.

| 역할 이름 (본문 용어) | 내 환경의 실물 (여기를 채운다) | 요구 조건 |
|---|---|---|
| vault | `<your-obsidian-vault>` | 사람이 링크·MOC·태그를 직접 관리하는 Obsidian vault |
| corpus pipeline | `<corpus-pipeline>` | 논문·코퍼스 수집/정제 산출물이 파일로 남는 파이프라인 |
| vector index | `<vector-index>` | vault·PDF를 임베딩해 벡터 검색을 제공하는 인덱스 |
| reference manager | `<your-reference-manager>` | KCI ID·서지 필드를 보존하는 서지 관리 저장소 |

**바인딩이 비어 있으면(신규 설치)**: 있는 척하지 않는다. 각 모드는 축소 동작한다 —
source-grounded Q&A는 「매 질문마다 원문 직접 재독」의 저효율 경로로, 지식 축적·재랭킹은
불가로 명시하고, 부트스트랩 순서를 안내한다: ① 원자료를 읽기 전용 폴더로 ② 자료
인벤토리(스캔 vs 텍스트층) ③ 바인딩 4칸 채우기 — 도구 선정은 즉석 추천하지 않고
`tool-adoption-audit` 모드로 거친다. 위임 대상 스킬(예: academic-research-workflow)이
미설치면 대행하지 말고 설치를 안내한다.

`references/` 두 문서(assistant-contract·tool-benchmark)는 이 바인딩이 채워진 **로컬 인스턴스 기준**으로 서술돼 있다 — 이식자는 자기 스택으로 대응 항목을 치환해 읽는다.
