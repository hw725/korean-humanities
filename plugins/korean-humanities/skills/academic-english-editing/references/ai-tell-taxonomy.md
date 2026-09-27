# 영문 학술 원고의 AI티 점검표

> 출처: [matsuikentaro1/humanizer_academic](https://github.com/matsuikentaro1/humanizer_academic) `aa724808`
> (`SKILL.md` v2.2.0 패턴 1–34 + `references/reader-clarity.md`)의 **선별 재서술**. 전재가 아니다.
> MIT, Copyright (c) 2025 Kentaro Matsui, based on [blader/humanizer](https://github.com/blader/humanizer)(MIT).
> 고지 정본은 저장소 `NOTICE.md`, 도입 판정은 `AUD-20260927-173649-2c1e4ecc`.
> **로컬 변경**: upstream은 의학 논문 저자 1인의 문체 프로필에 맞춰져 있다. 그 프로필과 의학 통계 전제 규칙은 빼고(맨 끝 「들이지 않은 것」), 예문은 인문학 원고로 새로 썼다.

이미 영어로 된 학술 산문, 그리고 이 스킬이 방금 만든 영문을 **마지막에** 훑는 표다.
문장 길이 밴드는 `sentence-rules.md`, hedging의 강도는 `style-guardrails.md` 「논증 강도 사다리」가 정한다. 이 표는 그 둘을 뒤집지 않는다.

## 먼저: 독자가 복원해야 하는 것이 있는가

AI티보다 먼저 **압축**을 본다. 압축된 문장은 행위자·대상·비교 기준·조건·논리 관계 가운데 하나를 빼고, 독자가 그것을 짐작하게 만든다. 짧은 문장이나 전문 용어가 문제인 것이 아니다.

- **추상 동사**: `adds value`, `shapes`, `reflects`가 무엇을 무엇과 비교해 말하는지 적는다. 원고에 근거가 없으면 지어 채우지 말고 `Revision notes:`에 묻는다.
- **지시어**: `This`·`the difference`가 가리키는 것이 둘 이상이면 명사로 바꾼다. 명사로 바꿨다고 인과가 생기지는 않는다.
- **쌓인 조건**: 판본·시기·비교 대상이 수식어 하나에 몰려 있으면 문장을 나눈다.
- **명사 사슬**: `late-Joseon commentary-tradition reception` 같은 사슬은 누가 무엇을 했는지로 푼다.
- **예고만 하는 문장**: `Another difference emerges.` 다음에 차이가 나오면 예고를 지우고 차이를 바로 쓴다.

줄이는 순서: ① 반복 요약·빈 예고·우선순위 낮은 문장 → ② 군더더기 구 → ③ 그래도 넘치면 저자에게 선택지를 보인다. 행위자·비교 기준·조건을 지워서 분량을 맞추지 않는다.

## 걷어낼 것

| 묶음 | 신호 | 처리 |
|---|---|---|
| 의의 부풀리기 | `stands as a testament`, `pivotal`, `enduring legacy`, `evolving landscape`, `sets the stage for`, `deeply rooted` | 무엇이 확인됐는지만 남긴다 |
| 내용 없는 평가문 | `This is a significant finding.` 로 끝나는 독립 문장 | 지운다. 바로 뒤에 **구체적 이유**가 이어지면 남긴다 |
| 끝머리 `-ing` | `…, highlighting / underscoring / reflecting …` | 지우거나 근거 있는 독립 문장으로 |
| 홍보 어조 | `groundbreaking`, `profound`, `rich`(비유), `remarkable`, `renowned` | 중립 서술로 |
| 막연한 권위 | `Scholars argue`, `It is widely believed` + 인용 없음 | 연구자·문헌을 대거나 지운다 |
| 틀에 박힌 과제·전망 절 | `Despite these challenges, … future` | 실제 한계만 구체적으로 |
| AI 어휘 | `delve`, `intricate`, `multifaceted`, `interplay`, `tapestry`, `underscore`(동사), `showcase`, `foster`, `holistic` | 평이한 동사로. 서너 개가 한 문단에 같이 나오면 거의 확실한 신호다 |
| 계사 회피 | `serves as`, `stands as`, `represents a` | `is` / `are` |
| 부정 병렬 과용 | `not only … but also`, `It is not merely X; it is Y` | 문단에 한 번 정도의 자연스러운 쓰임은 둔다 |
| 셋 묶기 | 근거 없이 매번 세 항목 | 실제 항목 수대로 |
| 동의어 돌려쓰기 | 같은 대상을 `text / work / treatise / volume`으로 번갈아 부름 | **한 개념 한 이름.** 반복은 결함이 아니다 |
| 거짓 범위 | `from X to Y`인데 X와 Y가 한 척도 위에 있지 않음 | 나열로 |
| 같은 주장 되풀이 | `In other words`, `That is`, `Put differently` 뒤 같은 내용 | 가장 구체적인 문장 하나만 남긴다 |
| 장식 부사 | `markedly`, `strikingly`, `profoundly`, `fundamentally`, 검정 없는 `significantly` | 지워 봐서 정보가 줄지 않으면 장식이다. `approximately`, `largely`, `consistently`처럼 크기·빈도를 나르는 부사는 둔다 |
| 헐거운 `where` | 장소·자료·조건이 아닌데 `, where …` 로 덧붙임 | `with …` 구나 새 문장으로. `in which`를 기본 대체어로 쓰지 않는다 |
| 쌓인 hedge | `may suggest … have the potential to …` | **한 겹으로 줄인다. hedge를 없애지 않는다.** 강도는 논증 강도 사다리 |
| em dash | `—` | 출력에 **0개**. 쉼표·괄호·마침표·쌍반점으로 바꾼다. 마지막에 문자 검색으로 확인한다 |

### 인문학 원고에서 특히 보이는 것 (로컬 추가)

- **호칭 돌려쓰기**: 한국어 원고는 한 인물을 이름·자·호·시호로 번갈아 부르는 일이 흔하다. 영문에서는 첫 등장에 병기하고 이후 하나로 고정한다. 어느 형을 쓸지는 `terminology-authorities.md`를 따른다.
- **「의의가 있다」 결말**: 국문 초록 끝의 「~라는 점에서 의의가 있다」를 옮기면 `This study is significant in that …`이 된다. `in that` 뒤에 구체적 내용이 있으면 둔다. 없으면 위 「내용 없는 평가문」이다.

## 걷어내지 말 것

과잉 제거는 그 자체로 기계 윤문의 흔적이다.

- **근거가 붙은 전환·귀속 표현**: `Notably,`, `Moreover,`, `In contrast,`, `Nevertheless,`, 인용이 뒤따르는 `Previous studies have shown that …`. 한 문단에 셋 이상 몰릴 때만 줄인다.
- **논리를 드러내는 접속어**: `Although`, `Whereas`, `Thus`, `Hence`, `Based on these readings`, `As expected`. 가르는 질문은 하나다 — 의미를 **부풀리는가**(지운다), 논리를 **드러내는가**(둔다).
- **접속어를 지우면 이음을 되살린다**: 문두 전환어나 연결절을 지웠는데 두 문장의 관계가 남아 있으면 ① 다른 접속어 ② 앞 문장의 핵심어를 받아 시작 ③ 두 문장 합치기 가운데 하나로 잇는다. 끊긴 문장만 나열된 글은 다듬은 것이 아니다.
- **접속어 바꿔 쓰기는 반복을 피할 때만**: 관계(결과·추가·대조·양보·이유·순서)를 먼저 정하고 같은 관계 안에서 고른다. `albeit`, `whereby`, `heretofore`를 사람 냄새용으로 뿌리지 않는다.
- **문단 결속**: 편집 뒤 문단마다 ① 첫 문장이 문단의 주장을 말하는가 ② 둘째 문장부터 접속어나 되받은 핵심어로 앞 문장에 이어지는가 ③ 문단을 여는 대조·연속 표지가 필요한 자리에 남아 있는가를 본다.
- **주장을 담은 짧은 문장**: `Two readings follow.`, `The variant is late.` 같은 문장은 리듬을 맞추려고 옆 문장에 붙이지 않는다. 내용 없는 극적 단문(`The answer? Surprising.`)만 지운다. 새 단문을 만들어 넣지는 않는다.
- **리듬은 이해를 위해서만**: 길이 분산이나 탐지기 점수를 목표로 삼지 않는다. 길이가 비슷한 문장이 이어지는 것 자체는 결함이 아니다.
- **저자가 승인한 입장**: `We argue that …`을 관습적으로 조심스럽게 들린다는 이유로 `may possibly suggest`로 낮추지 않는다. 다만 저자 의견과 실증된 사실은 구분하고, 근거와 어긋나는 사실 주장은 `Revision notes:`에 적는다.
- **저자의 절 구분 빈 줄**과 조판 지시.

## 두 번 읽기

1. **초고**: 압축부터 풀고, 위 표를 적용한다.
2. **자기 점검**: 「이 초고에서 아직 AI가 쓴 것처럼 보이는 곳은 어디인가?」 흔히 남는 것 — 비교 기준이 빠진 문장, 셋 이상 같은 방식으로 시작하는 문장, 어휘 표에서 빠져나간 단어, 끊긴 접속 사슬.
3. **마감 검사**: em dash 0개 → 문단 결속 → 한 번 읽어 이해되는가.

## 들이지 않은 것

| upstream 규칙 | 들이지 않은 이유 |
|---|---|
| 저자 문체 프로필(문장 20–40어, 접속어 목록, 결론 서두 `In conclusion,`) | 특정 의학 저자 1인의 프로필이다. 문장 길이는 이 스킬의 10–30어 밴드가 정한다 |
| 관찰 연구 주장에 쿠션 한 겹 더하기(`may reduce` → `may help reduce`) | hedge 중첩 금지(논증 강도 사다리)와 충돌한다. 강도 판정은 사다리의 전거·판본 게이트로 한다 |
| `linked to` → `associated with` | 통계적 연관을 전제한 의학 규칙이다 |
| `yield`·`remain`·`given`·`via`·`Beyond` 치환 | 저자 개인 취향에 가깝고 AI 신호라는 근거가 upstream에도 제시돼 있지 않다 |
| 제목의 문장식 대소문자 강제 | 목표 저널 관행이 정한다 |
| 곡선 따옴표 → 직선 따옴표 | 목표 저널·조판 관행이 정한다 |
