---
name: academic-english-editing
description: "한국어 학술 원고를 영어로 번역·윤문한다 - 논리 연결 복원, 문장 길이 밴드(10-30어), 학술 hedging 보정, 과잉주장 점검, em dash 제거, CJK 고유명사·서명·간지 연대 표기 고정. Trigger on 영문 초록, 논문 영역, 영어 논문 윤문, abstract 영작, 학술 영어, 투고용 영문, English abstract, academic English editing, proofread my abstract. 인문학 논증·구조·심사는 academic-research-workflow, 비학술 일반 영어 산문은 stop-slop이 맡는다."
license: Apache-2.0
metadata:
  author: custom
  version: 1.0.0
  category: academic-research
  upstream_reference: Yuan1z0825/nature-skills @ 745c5f38d1b4a0600bd2f5f5682e394a34fc28b2 (nature-polishing, Apache-2.0)
  suite: korean-humanities
  tier: portable
  share: korean-humanities
---

# Academic English Editing (한국어 → 영어 학술 산문)

한국어로 쓴 학술 원고를 **투고 가능한 영어**로 옮기고 다듬는다. 문장 하나든 초록 전체든 같은 절차를 쓴다.

## 이 스킬의 유래와 범위

`nature-polishing`(Apache-2.0)에서 **언어·문체 규칙만** 체리픽했다. 도입하지 않은 것: Nature/Nature Communications/NMI 저널 포맷, Results-Discussion 분리 규율, 통계 보고 규칙, LaTeX 조판, 그래픽 초록. 이들은 STEM 실증 논문 전제라 CJK 인문학 원고(KCI·HWP 제출)와 맞지 않는다.

라이선스 원문은 `LICENSE.upstream`, 파일별 파생 관계는 각 `references/*.md` 머리말에 있다.

## 경계

| 요청 | 담당 |
|---|---|
| 국문 원고를 영어로, 영문 초록 다듬기 | **이 스킬** |
| 논증 구조·연구사·사료비평·심사·투고 수정 판단 | `academic-research-workflow` |
| 비학술 영어 산문의 AI티 제거 | `stop-slop` |
| 한문 텍스트 생산·표점 적용·TEI | `hanmun-research-assistant` |
| 원고 수치와 데이터 대조 | `academic-research-workflow` (원고-데이터 정합 감사) |

**학술 원고에 `stop-slop`을 쓰지 않는다.** 그쪽의 부사 전면 삭제와 수동태 금지가 학술 hedging을 지우고 서술을 1인칭으로 강제한다(2026-08-21 A/B 실측).

## 절차

### 1. 설정 확정 (첫 실행 1회)

`references/style-guardrails.md`의 노출 설정 표를 읽고 **철자 변종·로마자 표기·인칭**을 확정한다. 목표 저널이 정해져 있으면 그 관행을 따르고, 없으면 사용자에게 묻는다. 확정값을 한 줄로 보고해 사용자가 싸게 정정할 수 있게 한다.

### 2. 논리 재구성 (문장을 만들기 전)

`references/ko-to-en.md`를 읽고 그 절차를 적용한다. 핵심 명제를 평이한 영어로 먼저 나열하고, 한국어가 생략한 인과·대조·한계 연결을 복원한다. 고유명사·서명·간지 연대는 이 단계에서 고정한다.

절 단위 직역을 하지 않는다.

### 3. 문장·문단 규칙 적용

`references/sentence-rules.md`를 읽고 적용한다. 10~30 단어 밴드는 **기계적 게이트**다. 위반 문장은 재구성하고, 겉만 다듬지 않는다.

### 4. 가드레일 점검

`references/style-guardrails.md`의 관사·숫자·과잉주장·무결성 절을 마지막에 훑는다.

## 출력 형식

1. 윤문된 본문을 코드블록 없이 산문으로 제시한다.
2. `Revision notes:` — 주요 구조·문체 변경 3~5개를 짧은 불릿으로.
3. 설정값(철자·로마자·인칭)을 한 줄로 명시한다.
4. 사용자가 대조를 요청하면 `Original` / `Polished` / `Why changed` 3단으로 낸다.

내용을 지어내지 않고는 고칠 수 없는 구조 문제가 있으면, 덮지 말고 `Revision notes:`에 적는다.

## Gotchas

- **연대 환산을 지어내지 않는다.** 간지·연호를 서기로 옮길 때 확신이 없으면 `unverified`로 두고 사용자에게 돌린다.
- **로마자 표기를 원고 안에서 섞지 않는다.** MR과 RR이 뒤섞인 원고는 심사에서 지적된다.
- **영국식 철자는 기본값이 아니다.** upstream은 강제했지만 여기서는 설정으로 내렸다. 국내 학술지 영문 초록은 대개 미국식이다.
- **hedging은 걷어내는 것이 아니라 맞추는 것이다.** 한국어의 중첩 hedging(`~것으로 보인다` + `~라고 할 수 있다`)은 하나로 줄이되, 증거가 약한 주장을 단정으로 바꾸지 않는다.
