---
name: harness-lite
description: 완료 조건 계약(harness.contract.json)을 만들고 확인하는 수강생판 하네스 안내. 사용자가 «완료 조건 만들어 줘»·«계약 만들어 줘»·«검증 장치»·«하네스»를 말하거나, harness-lite 훅이 «verify 하세요»·«계약 만들기»를 알렸을 때 쓴다.
metadata:
  author: hw725
  version: 0.1.0
  category: verification
---

# harness-lite

«완료»는 말이 아니라 영수증으로 확인한다. 이 플러그인의 Stop 훅이 그것을 확인하고, 이 문서는 Claude가 계약을 만들고 영수증을 남기는 법이다.

## 명령 경로

명령은 훅 메시지에 절대 경로로 찍혀 나온다(`sh "…/scripts/run.sh" harness.py verify`). 메시지가 없으면 Glob으로 `**/harness-lite/**/scripts/harness.py`를 플러그인 설치 폴더(`~/.claude/plugins/`)에서 찾는다. 경로를 지어내지 않는다.

| 명령 | 하는 일 |
|---|---|
| `harness.py init` | 지금 폴더에 계약 초안을 만들고, 테스트 명령을 찾으면 C-001에 넣는다 |
| `harness.py status` | 조건 표와 마지막 영수증(낡았으면 표시) |
| `harness.py verify` | 조건을 전부 돌리고 `.harness/lite/<시각>/receipt.json`을 남긴다 |
| `harness.py trash <경로> …` | 영구 삭제 대신 휴지통으로 |

## 계약 만들기

1. `init`을 돌린다.
2. 아홉 칸(`intent`)을 사용자에게 묻는다. 사용자가 말한 것은 `"source": "user"`와 원문 일부(`quote`), 짐작한 것은 `"assumed"`, 모르는 것은 `"blank"`로 둔다. 짐작을 사용자 말처럼 적지 않는다.
3. 조건은 «사람 말 한 문장 + 확인 명령 하나»로 쓴다. 기계가 판정할 수 없는 것(번역·판독·디자인 취향)은 `human` 판정자로 사람에게 넘긴다. 대기열은 JSONL 한 줄에 `{"id": …, "status": "pending"}`이고, 판정을 마친 줄은 `"status": "decided"`, 대기 0건이면 빈 파일이다.
   - `watch`는 이 프로젝트가 고치는 파일 형식에 맞춘다(기본은 py·js·ts·html·css·md). 여기 없는 파일을 고치면 영수증이 낡은 것을 장치가 모른다.
   - `protect`는 계약 폴더 기준 상대 글롭이나 절대 경로 글롭이다(폴더 밖 원본은 절대 경로로).
   - 검사 스크립트가 경고를 알리려면 출력 줄 머리에 `HARNESS::WARN`을, 곧바로 실패시키려면 `HARNESS::FATAL`을 쓴다.
4. `status` 표를 사용자에게 보이고 «이게 끝난 상태가 맞는지» 확인받는다. 확인받기 전에는 조건을 기준으로 삼지 않는다.

## 일하는 동안

- 고친 뒤 «완료»를 말하기 전에 `verify`를 돌리고 출력을 읽는다. 실패하면 고치거나, 고치지 못했으면 «완료하지 못했다»와 실패 건수·조건 ID를 보고한다.
- 검사를 통과시키려고 조건을 느슨하게 고치지 않는다. 조건이 틀렸다고 보이면 사용자에게 먼저 말한다.
- 캡처가 나오면 전부 Read로 열어 본 뒤 보고한다.
