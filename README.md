# korean-humanities — 한국학 인문학 연구 플러그인 모음

한국학 연구를 위한 Claude Code 플러그인 **4종**입니다. 저자의 전공이 전근대 한국
한문학이라 그쪽에 초점이 맞춰져 있고, 저자의 식견이 닿지 못한 분야(국어학·한국사·
민속학 등 한국학의 더 넓은 영역)는 충분히 포괄하지 못했습니다. 그래서 처음부터
**각자 커스텀해서 쓰도록** 설계했습니다 — 설정 지점은 각 절에 명시돼 있고, 분야
확장 기여(PR·의견)도 적극 환영합니다.

슈트 전체를 한꺼번에 설치하는 것이 아니라, **필요한 것만 골라 설치**합니다.

## 설치

```
/plugin marketplace add hw725/korean-humanities
/plugin install korean-humanities        # 연구 방법론 (프롬프트 전용, 준비물 0)
/plugin install gugyeol-decode           # 깨진 구결·옛한글 복원 도구
/plugin install kci-citation-network     # KCI 인용망 수집기 (무료 API 키 필요)
/plugin install kci-korean-studies-trends # KCI 동향 코퍼스·보고서 (키 불필요)
```

다른 설치 방법(Claude Code 수동, **Codex CLI 등 다른 도구**, 웹 LLM, AI 없이
터미널만)은 [docs/INSTALL.md](docs/INSTALL.md)에 환경별로 정리돼 있습니다.
폴더 복사의 선택 단위는 플러그인보다 잘은 **스킬 하나**입니다.

## 플러그인 4종 요약

| 플러그인 | 하는 일 | 준비물 |
|---|---|---|
| `korean-humanities` | 연구 방법론 스킬 3종 — 연구사·사료비평·논증·심사 / 연구 비서 라우터·CJK 텍스트 계약 / 학술 영문 라이팅 | 없음 (프롬프트 전용) |
| `gugyeol-decode` | PDF·HWPX의 깨진 구결자·옛한글을 표준 유니코드로 복원 | PDF 입력만 `pip install pymupdf` |
| `kci-citation-network` | 키워드만으로 KCI 인용망 수집 (선택: Obsidian 렌더) | 무료 data.go.kr API 키 |
| `kci-korean-studies-trends` | 연도·분야만으로 KCI 동향 코퍼스·보고서 | 없음 (키 불필요) |

각 플러그인의 행동 보증·사용법(값 넣는 지점·명령)·알려진 한계는
[docs/USAGE.md](docs/USAGE.md)에 있습니다.

## 함께 쓰면 좋은 것 (별도 설치)

현대 한국어 산문 품질 도구는 전근대 문헌 연구라는 이 모음의 축과 달라 포함하지
않았습니다. 검토를 거쳐 함께 쓰는 외부 스킬은 다음과 같습니다.

| 용도 | 외부 스킬 |
|---|---|
| AI 티 제거 (문체·리듬) | [epoko77-ai/im-not-ai](https://github.com/epoko77-ai/im-not-ai) |
| 맞춤법·문서 스타일 일관성 | [DaleSeo/korean-skills](https://github.com/DaleSeo/korean-skills) |
| 번역문 번역투 교정 | [amondnet/yoonmoon](https://github.com/amondnet/yoonmoon) |
| 전보문 한국어 예방 (출력 스타일) | [snflkd/fluent-korean](https://github.com/snflkd/fluent-korean) |

## 라이선스

스킬별로 다릅니다 — `NOTICE.md`를 참고하십시오. 자체 저작분은 MIT입니다.
