# Output Contracts (Humanities-First, v2.1.0)

이 파일은 연구 산출물을 표준 형태로 만들어야 할 때만 읽는다.

## Evidence Matrix (사료·연구사)

| 필드 | 의미 |
|---|---|
| `source_id` | 짧고 안정적인 ID |
| `citation` | 확인된 서지 정보 (인용 문법 절 참고) |
| `identifier` | 實錄 기사 ID, KCI ID, DOI, ISBN, 청구기호, URL 등 |
| `recension` | 판본·이본(異本) 계통 |
| `text_status` | `원문` / `국역` / `기계국역` / `표점본` 구분 |
| `criticism` | 외적·내적 비평 요약 (진위·연대·전승·편향) |
| `pyojeom_choice` | 채택한 표점·句讀·懸吐와 근거 (경쟁 독법 있으면 명시) |
| `main_claim` | 이 사료가 실제로 말하는 것 |
| `used_for` | 내 논증에서 이 사료가 뒷받침하는 해석 (공백 채우기가 아니라 해석적 활용) |
| `verification_status` | `verified`, `partial`, `unverified` |
| `notes` | 한계, 충돌, 확인 필요점 |

## 사료비평 Sheet (Source-Criticism)

| 필드 | 의미 |
|---|---|
| `source_id` | 대상 사료 |
| `external` | 진위, 출처·유래, 성립·편찬 연대, 전승·계통 |
| `internal` | 저자 의도, 당파성·편향, 장르 규약, 침묵 |
| `collation` | 이본 대조 결과 (변이 독법 목록) |
| `adopted_reading` | 채택한 독법·표점과 정당화 근거 |
| `rival_readings` | 기각한 경쟁 독법과 기각 이유 |
| `reliability_flag` | 식민지기 편찬본(예: 『고종실록』·『순종실록』) 등 신뢰성 주의 |

## Citation Grammar (인용 문법, ITKC/대표 국사학 저널 convention)

- 書名 vs 篇名: `『書名』` vs `「篇名」`.
- 『朝鮮王朝實錄』: **왕대 + 年/月/日(干支) + 기사 순번 + 실록 기사 ID**. 예) 『太宗實錄』 태종 5년 1월 1일 갑자 N번째 기사, [기사 ID].
- 文集: **저자, 『文集名』 卷次, 篇名**.
- 항상 **원문 vs 국역**을 구분해 표기한다. 기계 국역(ITKC aitr 등)은 출처에 그 사실을 명시한다.
- **신뢰성 주의 플래그**: 『고종실록』·『순종실록』은 식민지기 편찬본 — 인용 시 편찬 신뢰성 주의를 단다.
- **투고처 우선(house-style)**: 인용·서지 양식을 하드코딩하지 않는다. 대상 학회의 **원고작성요령**을 먼저 확인·반영하고, 없거나 미정이면 ITKC/대표 국사학 저널 convention을 기본값으로 쓴다.
- **참고문헌 배열**: 한국어(가나다) → 일본어·중국어 → 로마자 순. 동양어는 저자 성, 로마자는 알파벳순. 원문 표기 아래에 로마자(설정의 MR/RR 따름)를 보조로 단다.
- **2차 문헌(현대 논문·단행본) 양식** — 1차 사료 문법과 구분: 논문 = 저자, 「논문 제목」, 『학술지』 권(호), 연도, 면. 단행본 = 저자, 『書名』, 출판지: 출판사, 연도. (투고처 요령이 다르면 그쪽을 따른다.)
- **AI 표기/디스클로저**: 투고처가 생성형 AI 사용 고지를 요구하면 사용 범위(번역 초벌·정리 등)를 방법·사사 또는 별도 고지란에 명시한다. 기계 국역(ITKC aitr 등)은 초벌로 표기한다(핵심 원칙 3).

## Source-Fidelity Audit (구 Claim Audit)

| 필드 | 의미 |
|---|---|
| `claim_id` | 주장 ID |
| `claim_text` | 검토 대상 문장·주장 |
| `claim_type` | `원문인용`, `국역`, `해석`, `연대/干支`, `표점해석`, `사료-사건시점`, `사실`, `인용` |
| `source_text_provenance` | `원문` / `국역` / `기계국역` (기계국역이면 필수 기록) |
| `source_existence` | `resolved` / `unresolved` / `fabrication-suspected` — 인용 전거가 실재·해소되는가: 실록 기사(왕대+干支+기사 ID) 해소, 文集 卷次·篇名 실재를 로컬 코퍼스·한국고전종합DB·실록 DB에 대조 (오인용과 별개, DOI 아님) |
| `locator` | 전거 위치 앵커: `kind`(실록기사/권면(엽)/조목/직접인용/단락/none) + `value`. `none`이면 `anchorless` 결함 |
| `alignment` | 실재와 별개의 정합 판정: `뒷받침` / `불일치` / `모호` / `원문확인불가`. `불일치`→`contradicted`, `모호`→강도 완화 |
| `sub_claims` | (복합 주장만) 逐句·표점 단위 하위주장 목록과 각 `alignment`. 주장-수준은 약자 합성(아래 분해 원칙). 전거 1개·단일 명제면 생략 |
| `supporting_sources` | 실제로 확인한 사료 ID |
| `status` | `verified`, `partially_verified`, `unverified`, `contradicted` |
| `action` | 유지, 완화, 삭제, 사료 추가, 재작성 |
| `rationale` | 판단 근거 |

원칙: 사료가 주장보다 약하면 주장을 낮춘다. 사료가 없으면 문장을 남기지 않는다. 기계 국역에만 근거하면 최대 `partially_verified`. 인용 사료는 입증 대상 사건·주장보다 **앞서거나 동시대**여야 한다(시대착오 인용 flag). 해소되지 않는 전거는 인용하지 않는다. 연대·인용·사실은 검증 대상, 해석만 개연성 대상이다.

**전거 앵커·게이트·보정(opt-in).** 각 인용에 위치 앵커를 달고(없으면 `anchorless`), 실재(`source_existence`)와 정합(`alignment`)을 분리 판정한다. `주장-사료 불일치`·`시대착오 인용`·`사료 실재성 미상·날조`·`anchorless`·`기계 국역 무대조 인용` 다섯 부류는 초고·투고본에서 게이트로 차단한다. 감사기 자신의 오탐·누락을 골드셋으로 측정하는 보정은 선택이며 기본 OFF다 — 절차·임계값(잠정)·골드셋 격리는 `references/source-fidelity-calibration.md`.

**복합 주장 분해 (sub-claim decomposition).** 한 주장이 **전거를 둘 이상 인용하거나, 표점에 따라 독법이 갈리거나, 명제를 여럿 담을 때만** 판정 전에 逐句·표점 단위로 원자 하위주장으로 쪼개 각 하위주장에 `alignment`를 따로 매긴다. 단순·단일 전거 주장은 분해하지 않는다(1인 검증에 과부하를 주지 않기 위함). 분해 경계가 모호하면(변려문·만연체 등) 분해하지 않고 단일 주장으로 두되 그 사실을 `rationale`에 적는다. 분해 경계는 채택 표점(`pyojeom_choice`)에 종속되므로 **표점을 확정한 뒤** 감사하고, 경쟁 독법이 있으면 분해도 독법별로 분기한다.

주장-수준 합성은 **약자 우선**으로 닫는다. ① 하위주장 중 하나라도 HIGH-WARN 제약 위반(시대착오·`fabrication-suspected`·`anchorless`·기계 국역 무대조; `source-fidelity-calibration.md` §3)이면 합성 결과가 **그 게이트를 그대로 상속**한다 — 부분지지로 희석하지 않는다(제약 위반 > 부분지지). ② 제약 위반이 없을 때, 핵심 하위주장이 `불일치`면 `contradicted`, 비핵심만 `불일치`거나 뒷받침·미뒷받침이 섞이면 `partially_verified`(강도 완화, 완전 해소로 묵인 금지), 전부 `뒷받침`이면 `verified`. ③ `모호`(독법 경쟁) 하위주장은 `불일치`로 합성하지 않는다 — 검증축이 아니라 독법축이므로 `partially_verified` + 경쟁 독법 병기로 닫는다(보정 §4 과탐 방지). 하위주장별 전거가 다르면 시대착오·기계 국역 의존도 하위주장 단위로 판정한다. 이 계약은 **산문 규칙이며 스키마·lint를 두지 않는다**(필드 존재 검증은 충실성 검증이 아니다).

## Fact / Take Split

논문 작업 중 새 지식을 저장할 때는 `knowledge-memory-workflow`의 계약을 따른다.

| 분류 | 저장 대상 | 예시 |
|---|---|---|
| `fact` | 사용자가 직접 말한 연구 조건, 결정, 마감, 선호 | 사용자가 MR 로마자 표기를 원함 |
| `take` | 논문·연구자·기관이 주장한 내용 | A 논문은 B 사건을 C 학파 시각으로 해석함 |
| `source` | 원문, 국역, 이본, PDF, 실록 기사, 회의록 | 실록 기사 메타데이터 |
| `event` | 선별, 제외, 독법 채택, 실패, 재시도 | 2차 사료비평에서 위서로 판정 |

holder가 없는 주장은 take로 저장하지 않는다. 논문 주장을 사용자 fact로 저장하지 않는다.

## Citation / Source-Fidelity Report

포함 항목:

- 확인한 사료·참고문헌 수
- 실록 기사 ID·서지 메타데이터로 확인된 항목
- 원문 ↔ 인용 불일치 (오인용)
- 국역 ↔ 원문 불일치 (오역)
- 연대·간지·음양력 환산 오류
- 본문에는 있으나 출처에 없는 항목 / 출처에는 있으나 본문에 없는 항목
- 기계 국역 의존 항목 (원문 대조 필요)
- 후속 조치

## 심각도 등급 표준 (severity tiers)

`인문학 peer-review`와 `revision-response`가 공유하는 단일 정의(서수 등급, 점수 없음). `source-fidelity-audit`의 `contradicted`/위조·오역 findings도 여기에 매핑된다.

- **치명(critical)**: 핵심 논지를 무효화하거나 연구부정에 해당(위조·표절·논지를 무너뜨리는 오역).
- **주요(major)**: 수정 없이는 수용 곤란한 결함.
- **사소(minor)**: 권고 수준.

## Revision Response Matrix

| 필드 | 의미 |
|---|---|
| `comment_id` | 심사 의견 ID |
| `reviewer_comment` | 원문 요약 |
| `issue_type` | 이론, **사료**, 해석, **표점/번역**, 구조, 표현, **연구사** (통계 제외) |
| `decision` | 수용, 부분 수용, 반박, 설명 요청 |
| `revision_action` | 본문에서 수행할 수정 |
| `location` | 수정 위치 |
| `response_text` | 답변서 문안 초안 |
| `risk` | 남은 리스크 |

**약속 이행 원장 (Commitment Ledger).** 심사 답변서는 ‘무엇을 하겠다’는 약속이고, 약속이 실제 본문에 반영됐는지는 별개의 축이다(설득력 있는 답변이 미이행을 가릴 수 있다). 한 코멘트가 약속 여럿으로 갈라지면(예: ‘사료가 부족하다’ → 사료 추가 + 이본 재교감) 위 Matrix 행을 약속 단위로 분해해 아래 원장에 내린다. 단일 약속이면 Matrix의 `revision_action`·`location`으로 충분하니 원장을 따로 만들지 않는다(이중 기입 금지).

| 필드 | 의미 |
|---|---|
| `comment_id` | 분해 출처가 된 Matrix 코멘트 (연결 키) |
| `commitment_id` | 약속 ID (한 `comment_id` 아래 1..N) |
| `promised_change` | 약속한 구체적 수정 (Matrix `revision_action`을 약속 단위로 내린 것) |
| `commitment_type` | `사료추가` / `사료비평재수행`(진위·연대·전승) / `이본재교감` / `표점·번역재검토` / `연구사보강` / `구조변경` / `표현수정` / `기타` |
| `required_evidence_type` | 이행을 입증할 산출물: `대조표` / `표점근거` / `사료비평시트` / `본문수정` / `기타` |
| `fulfilled_status` | `이행` / `부분이행` / `미이행` / `명시적거부(근거동반)` |
| `unfulfilled_rationale` | `이행`이 아니면 **필수·비공백**. `이행`이면 칸을 비우지 말고 **생략·해당없음**으로 둔다(빈 placeholder 금지) |
| `evidence_location` | 이행 증거의 본문 위치 (Matrix `location`을 약속 단위로 내린 것) |

원칙: `fulfilled_status`는 답변서 작성 시점이 아니라 **수정본 대조 시점**에 채운다. 이행 상태는 별도 목록이 아니라 각 약속 행 안에 함께 둔다(약속과 이행이 어긋나 매핑이 깨지지 않도록). 미이행·부분이행이 `unfulfilled_rationale` 없이 남으면 `COMMITMENT_GAP` — 이는 **차단 게이트가 아니라 표면화(advisory) 신호**다. 투고를 막지 않으며 최종 책임은 저자에게 있다. 약속 이행은 검증축이 아니라 저자 의도·노력의 축이므로 원칙 10의 투고 전 전수 대조 게이트나 HIGH-WARN 차단과는 분리한다. 해제는 ‘무시’가 아니라 **근거 보충**(`unfulfilled_rationale` 기입 + `observability-logging`의 event 기록)으로 닫는다. 이 계약은 **산문 규칙이며 스키마·lint를 두지 않는다.**

## Research Passport

장기 파이프라인이나 resume이 필요한 작업은 아래를 남긴다.

- 연구질문과 연구사 좌표
- 범위와 제외 기준
- 사료 위치와 원자료 보존 상태 (원문 vs 국역)
- 이본·판본 목록과 채택 독법
- 사료비평 시트 위치
- evidence matrix / source-fidelity audit 위치
- 미검증 항목
- 다음 체크포인트

## Exposed Settings (노출 설정)

산출물마다 의도적으로 선택한다. 묵시적 기본값을 쓰지 않는다.

| 설정 | 값 | 비고 |
|---|---|---|
| `romanization` | McCune-Reischauer (MR) / Revised Romanization (RR) | 서구 학계 다수 MR, 국내·정부 RR. 투고처에 맞춘다 |
| `era_dating` | 干支+서기 병기 on/off, 음력↔양력 표시 | 사학 논문 기본 병기 권장 |
| `hanja_exposure` | 첫 등장 시 한자 병기 / 전면 병기 / 한글 전용 | 투고처 규정에 맞춘다 |

## JSONL Logging Stages

권장 stage 이름(인문학 우선):

- `research-scope`
- `source-collection` (구 source-search)
- `source-criticism`
- `collation`
- `historiography`
- `argument-design`
- `source-fidelity-audit` (구 claim-audit + citation-check)
- `peer-review`
- `revision-response`
- `format-check`
- `fact-capture`
- `take-capture`
- `retrieval-eval`
- (DH opt-in일 때만) `corpus-screening`, `deduplication`

각 로그는 최소한 `stage`, `timestamp`, `input_id`, `output_summary`, `reason`을 둔다. 제외·기각한 사료·독법은 이유를 반드시 기록한다.
