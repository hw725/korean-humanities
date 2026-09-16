# NOTICE — korean-humanities suite

이 슈트에 포함된 스킬의 출처·저작권·라이선스 고지입니다.

> 이 파일은 마켓플레이스 루트와 **각 플러그인 폴더 안**에 같은 내용으로 놓입니다
> (플러그인만 설치·복사해도 고지를 패키지 안에서 찾을 수 있도록). 그래서 아래 경로는
> 특정 위치 기준의 상대경로가 아니라 **스킬 폴더 기준**으로 적습니다.

## 자체 저작 (MIT — 같은 폴더의 LICENSE)

- `hanmun-research-assistant`
- `academic-research-workflow`
- `kci-korean-studies-trends` — 수집·병합·분석 스크립트와 한국학 학술지 프로파일
  (자체 큐레이션) 포함. 데이터 출처: KCI 공개 검색(robots·rate limit 준수 수집).
- `kci-citation-network` — 수집·검색·렌더 스크립트 포함. 데이터 출처: 한국연구재단
  KCI 참고문헌 서비스(data.go.kr 공공데이터) — 수집 데이터의 이용 조건은 해당 서비스
  약관을 따릅니다.
- `academic-english-editing` — 단 `references/` 3종(`sentence-rules.md`·`ko-to-en.md`·
  `style-guardrails.md`)은 [Yuan1z0825/nature-skills](https://github.com/Yuan1z0825/nature-skills)
  (Apache-2.0)의 nature-polishing에서 파생 — 파일별 파생 관계는 각 파일 머리말,
  원 라이선스는 `academic-english-editing` 스킬 폴더의 `LICENSE.upstream`에 보존
  (마켓플레이스 기준 전체 경로는 `plugins/korean-humanities/skills/academic-english-editing/LICENSE.upstream`).

## 개념·프레임 차용 (Academic Research Skills)

`academic-research-workflow`의 모드 라우터 골격(연구 절차의 분류 체계)과
`hanmun-research-assistant`의 증거 접근 3계층은
[Imbad0202/academic-research-skills](https://github.com/Imbad0202/academic-research-skills)
(및 -codex 자매, CC BY-NC 4.0, Copyright Cheng-I Wu)의 설계를 참조해 CJK 인문학으로
재구성한 것입니다. **원 저장소의 텍스트·코드는 포함돼 있지 않습니다** — 본문은 처음부터
자체 서술이며, 절차 분류라는 아이디어 층위의 차용입니다(아이디어·방법은 저작권 보호
대상이 아니지만, 출처 예우와 재추적을 위해 명기합니다).
`hanmun-research-assistant/scripts/cjk_title_match.py`(2026-09-14)도 같은 관계입니다 —
「CJK 서지 제목은 별도 경로로, 서명 부호·꼬리 마침표·한자 인접 공백만 잡음으로 제거하고
양쪽 모두 CJK일 때만 판정한다」는 발상은 같은 저장소 `_text_similarity.py`에서 왔고,
구현(NFC 정규화·`regex` 문자 판정·판정 불가 반환)은 여기서 새로 썼습니다. ARS의 STEM 절차가 필요하면
원 저장소를 직접 사용하십시오 — 비상업 조건이 붙어 있습니다.
## 자체 저작 — 별도 저장소 병존

- `gugyeol-decode` — 구 단독 저장소 [hw725/gugyeol-decode](https://github.com/hw725/gugyeol-decode)
  (2026-08-26 아카이브, 후속은 이 마켓플레이스)와 동일 저자. 라이선스·매핑 출처 고지는
  스킬 내 `LICENSE`·`ATTRIBUTION.md` 참조(한양 PUA 매핑·AKS 표준 매핑의 출처 포함).
