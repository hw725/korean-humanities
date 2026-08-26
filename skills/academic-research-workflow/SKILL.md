---
name: academic-research-workflow
description: Humanities research-deliverable router for Korean classical literature and history in hanmun (Literary Sinitic) sources - produces and evaluates research outputs, not text tooling. Modes - 연구사 review, 사료비평·교감 (표점/句讀 treated as interpretive claims to argue, not apply), thesis- and source-grounded argument planning and drafting, 인문학 peer review, source-fidelity audit (원문·국역·干支; machine 국역 such as ITKC aitr is draft-only), and manuscript-data consistency audit before 투고. Also covers 논문 심사, 투고 수정, 인용 충실성 검증, 원고 수치 검증, and supporting quantitative reporting (κ, confidence intervals). Delegates hanmun text production, OCR/표점 application, TEI, vault knowledge management, source-grounded Q&A, and tool adoption to hanmun-research-assistant. PRISMA and DH evaluation are opt-in; romanization, 기년, 한자 병기 are exposed settings.
metadata:
  author: custom
  version: 2.4.3
  category: academic-research
  upstream_reference: Imbad0202/academic-research-skills-codex
  suite: korean-humanities
  tier: portable
  share: core
---

# Academic Research Workflow (Humanities-First)

이 스킬은 CJK 고전문학·역사학 연구의 **산출물 생산과 평가**를 라우팅하는 인문학 우선 오케스트레이터다. 한문 텍스트를 만들거나 고치는 일(OCR 교정, 표점 적용, TEI 주석, 디지털화)은 `hanmun-research-assistant`/`hanmun-philology`가 맡고, 이 스킬은 그 사료를 **평가·교감하여 논증·논문으로 만드는 일**을 맡는다. 일반 인문학(텍스트 기반 해석 연구)에도 적용되지만 기본은 CJK 고전·사학이다.

## 경계: HRA ↔ ARW (산출물 vs 환경, D1 표점 분담)

- **산출물(이 스킬)**: 연구사, 사료비평·교감 평가, 해석 논증, 심사, 인용·원문 충실성 검증.
- **환경(HRA)**: AI 비서 구축·운영·커스터마이징, 한문 텍스트 생산/수정, source-grounded Q&A, 새 도구 채택.
- **표점/句讀 분담(D1)**: 어떻게 끊을지 **판단하고 근거를 제시**하는 일은 ARW(사료비평). 그 판단을 디지털 텍스트에 **적용**하는 일은 `hanmun-philology`.
- 한 문장: “한문 텍스트를 만들거나 고치는 일 = hanmun-philology. 그 텍스트를 사료로 평가·교감하여 논증에 쓰는 일 = ARW 사료비평.”
- **문헌·집필 vs 비서 구축**: 연구사·논증·초고·심사 등 산출물 자체를 만드는 일은 ARW, 그 작업을 자동 수행할 literature/writing 비서를 구축·운영하는 일은 `hanmun-research-assistant`. ‘논문 비교·정리해 줘’ → ARW, ‘문헌 비서 만들어 줘’ → HRA.

## 핵심 원칙

1. 사료·참고문헌·수치를 지어내지 않는다. 확인 못 한 것은 `unverified`로 둔다.
2. 사료비평이 논증보다 앞선다. 진위·연대·전승·이본을 따지기 전에 사료를 근거로 쓰지 않는다.
3. 기계 국역(예: ITKC aitr)은 초벌이다. 원문 대조 없이는 인용 불가이며, 최대 `partially_verified`.
4. 증거·해석·권고를 분리한다. 사료가 말하는 것과 내가 제안하는 해석을 섞지 않는다.
5. 타당성은 통계적 유의성·재현성이 아니라 **개연성·정합성·사료 충실성·경쟁 해석 설명력**으로 판단한다. 단, **연대·인용·사실 주장은 개연성이 아니라 검증(verified) 대상**이고, 개연성·정합성은 **해석(interpretation)** 에만 적용한다. 복합 주장은 판정 전에 하위주장으로 분해해 각각 검증하고 약자 합성한다(부분지지를 완전 해소로 묵인하지 않으며, 제약 위반 하위주장은 게이트를 상속한다).
6. 원자료(`primary_data/`, 원문)는 읽기만 한다. 변환물과 로그는 기존 연구 파일 규칙을 따른다.
7. 표점·句讀·懸吐 선택은 드러내고 정당화한다. 의미가 갈리면 경쟁 독법을 함께 제시한다.
8. 연대·간지(干支)·음양력 환산, 왕대년↔서기는 명시적으로 확인한다.
9. 서브에이전트 병렬은 사용자가 명시적으로 요청했을 때만 쓴다.
10. 원고에 들어간 모든 수치는 데이터 정본에서 재계산 가능해야 한다. 데이터 정제·표본 변경이 일어나면 영향 범위는 ‘재분석한 절’이 아니라 ‘원고 전체의 수치’이며, 체크리스트가 아니라 전수 대조로 닫는다.
11. 핵심 주장·사료·가정에는 안정적 ID(주장 C1, 사료 S1, 가정 A1 등)를 부여하고 가정은 본문에 인라인으로 태깅한다. 충실성·정합 감사를 막연한 체크리스트가 아니라 ID 대조(주장 Cn ↔ 근거 Sn)로 닫고, 미해소 가정 An은 드러내 추적한다.
12. 확증 사료만 모으지 않는다. 채택하려는 독법·연대·진위 판정마다 그것을 **무너뜨릴 반증 사료·이본·이설**을 의도적으로 탐색하고, 탐색 예산의 일정 비율을 반증 쪽에 배분한다. 반증을 못 찾았으면 「찾지 못함」을 명시하되, 반증 탐색을 생략한 채 확증을 결론으로 삼지 않는다. 이는 원칙 5(경쟁 해석 설명력)의 사료 단계 대응물이다.

## 빠른 라우팅

| 사용자 의도 | 모드 | 첫 산출물 |
|---|---|---|
| 주제·문제의식만 있고 연구질문이 없음 | `문제설정 / research-scoping` | 연구질문 1-3개 + close-reading 축 + 사료 가용성 + 연구사 내 위치 |
| 선행연구를 비판적으로 정리, 학설사 | `연구사 / historiographical-review` | 해석 계보도: 학파 → 대표 연구 → 지배적 독법 → 공백/은폐 → 개입 지점 |
| 사료 진위·연대·전승 비평, 이본 교감 | `사료비평·교감 / source-criticism-collation` | 사료비평 시트 + 이본 대조표 + 채택 독법 근거 |
| 논문 논증 구조·초고 | `해석 논증 / hermeneutic-argument-planning` | 주제별/연대기 구조안 + 사료 근거 지도 |
| 심사 의견 대응, 투고 수정 | `revision-response` | 코멘트별 대응표 + 약속 이행 원장(advisory) + 수정 우선순위 |
| 인문학 논문 심사 | `인문학 peer-review` | 치명/주요/사소 결함 + 판정 근거 (인문학 루브릭) |
| 인용·원문·국역·연대 충실성 검증 | `사료 충실성 감사 / source-fidelity-audit` | 주장별 충실성 상태표 |
| 원고 수치↔데이터 정본 일치 확인 (투고·수정 직전, 정제 직후) | `원고-데이터 정합 감사 / manuscript-data-consistency` | 전수 대조표 + 갱신 대응표 + 내부 모순 목록 |
| (옵션) 대규모 코퍼스 선별·동향 | `systematic-review` (DH opt-in) | 검색식·포함/제외 기준·선별 로그 |
| (옵션) DH 평가 프로토콜 | `experiment-planning` (DH-eval stub, opt-in) | 평가 설계 + 재현성 리스크 |
| 연구질문부터 논문까지 전체 | `full-pipeline` | 단계표 + 체크포인트 계획 |

상세 모드 기준은 `references/mode-router.md`, 산출물 형식과 설정은 `references/output-contracts.md`를 읽는다. 사료 충실성 감사의 전거 앵커·게이트·감사기 보정(선택)은 `references/source-fidelity-calibration.md`를 읽는다. 원고 수치 전수 대조 절차(HWP 직접 파싱 포함)는 `references/manuscript-data-consistency.md`, 계량 요소가 있는 논문의 보고 표준(κ·95% CI·층화·합의 정의 민감도·LLM-as-judge 특칙)은 `references/quantitative-humanities.md`를 읽는다.

## 실행 절차

### 1단계: 분류

연구질문이 불명확하면 `문제설정`부터 시작한다. 사료비평이 안 된 사료가 있으면 `사료비평·교감`을 논증보다 **먼저** 돌린다. 이미 사료비평·근거·구조가 있으면 그 단계에서 시작한다.

### 2단계: 증거 경계

- 사용자 제공 자료 / 로컬 사료·코퍼스에서 확인한 자료 / 외부 권위 DB에서 확인할 자료 / 미확인
- **원문 vs 국역을 항상 구분**한다. 기계 국역은 출처와 검증 상태를 명시한다.

### 3단계: 기존 스킬 연결

| 필요한 일 | 함께 쓸 스킬 |
|---|---|
| 한문 원문 생산·OCR 교정·표점 적용·TEI 주석 | `hanmun-research-assistant` → `hanmun-philology` (환경) |
| 연구 프로젝트 폴더·원자료 보존·진행 일지·투고 동결(submission-freeze) | `research-file-management` |
| JSONL 로그, 선별·제외 이유 기록 | `observability-logging` |
| KCI 한국학 동향·대표 논문 후보 | `kci-korean-studies-trends` |
| 분석 코드·통계 로직 검증 (DH) | `cross-validation` |
| 모델·도구 비용 선택 | `model-selection` |
| HWP/HWPX 논문·보고서 작성·변환 | `hwp`, `hwpx` |
| Obsidian 문헌 노트·볼트 작업 | `obsidian-cli` |
| facts/takes 분리, thread event, 검색 평가 | `knowledge-memory-workflow` |

### 4단계: 체크포인트

- 연구질문이 바뀌어 사료 선별 기준도 바뀌는 경우
- 표점·독법 선택이 결론을 바꾸는 경우
- 100건 이상 사료 선별 또는 충실성 감사
- 식민지기 편찬 사료(『고종실록』·『순종실록』 등) 신뢰성 판단
- 연대·간지 환산이 논지에 결정적인 경우
- 데이터 정제·표본 재추출이 일어난 경우 — 원고 수치 전수 재대조(`manuscript-data-consistency`) 전에는 투고·제출하지 않는다

### 5단계: 검증 가능한 산출물

기본 산출물에 포함한다: 현재 모드·단계 / 입력 사료와 확인 범위(원문 vs 국역) / 핵심 해석과 근거 / 미검증 항목 / 다음 체크포인트.

## 실패 처리

| 실패 상황 | 대응 |
|---|---|
| 주제가 너무 넓음 | 연구질문 수렴 질문으로 돌아간다 |
| 사료가 부족·접근 불가 | 공백을 명시하고 추가 탐색 또는 대체 사료 계획을 낸다 |
| 이본·사료끼리 충돌 | 대조표를 만들고 판정 유보 또는 독법 우선순위를 제안한다 |
| 인용·원문 불일치 | `unverified`로 표시하고 주장 강도를 낮춘다 |
| 기계 국역에만 의존 | 초벌로 표시하고 원문 대조 전에는 인용하지 않는다 |
| 논증이 사료보다 앞서감 | 충실성 감사표를 만들고 근거 없는 문장을 삭제·완화한다 |

## 금지 패턴

- 참고문헌·사료를 기억이나 관행으로 채우기
- 사료비평 없이 사료를 근거로 인용하기
- 표점·독법을 말없이 선택하고 경쟁 독법을 숨기기
- 기계 국역을 원문 검증 없이 인용하기
- 통계·재현성·Risk-of-Bias 기준으로 인문학 논문을 평가하기
- 한문 텍스트 생산·표점 적용을 이 스킬에서 직접 수행하기 (→ `hanmun-philology`)
- 데이터 정제 후 재분석한 절의 체크리스트만 갱신하고 ‘원고 반영 완료’로 종결하기 (→ 전수 대조)
- 계량 수치를 점추정(χ²·p)만으로 보고하기 (→ `quantitative-humanities.md` 최소선)
