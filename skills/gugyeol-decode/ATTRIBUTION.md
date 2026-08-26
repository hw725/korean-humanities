# Attribution

본 스킬은 다음 외부 자료·라이브러리·데이터에 의존하며, 모든 출처를 존중하여 명시한다.

## 1. 핵심 변환 라이브러리: hypua

- **저장소**: https://github.com/kiwiyou/hypua
- **저자**: kiwiyou (GitHub user)
- **라이선스**: Unlicense (public domain equivalent)
- **사용 목적**: 한양 PUA(Private Use Area) 옛한글 → IPF(첫가끝) Unicode jamo 결합형 변환
- **포함 파일**: `reference/hypua_table.csv` (5660건 매핑, hypua 저장소의 `table` 파일을 그대로 가져옴)
- **본 스킬이 수정 사항**: 없음. 원본 그대로 사용.
- **감사**: 본 매핑이 없었다면 옛한글 PUA 시각 판독 정확도가 33% 수준에 머물렀을 것. **본 스킬의 정확도는 hypua에 결정적으로 의존**.

## 2. 표준 매핑 데이터 출처: 한국학중앙연구원 (AKS)

- **사이트**: 한국역사정보통합시스템 한국학중앙연구원
  - 옛한글 lookup: http://yoksa.aks.ac.kr/jsp/hh/oldhan.jsp
  - 구결자 lookup: http://yoksa.aks.ac.kr/jsp/hh/gukyul.jsp
- **이용 약관**: 한국학중앙연구원 한국역사정보통합시스템 공공누리(KOGL) 표시조건. 학술·교육·비영리 목적 자유 이용 가능.
- **사용 방식**: `scripts/fetch_aks_gukyul.py`, `scripts/fetch_aks_oldhan.py`로 사용자가 직접 1회 다운로드.
- **포함 파일**: `reference/aks_gukyul_pua.json` (255 PUA × 104 음가), `reference/aks_oldhan_pua.json` (5299 PUA × 23 카테고리)
- **본 스킬이 추가한 가치**: AKS 사이트의 분산된 카테고리 lookup을 단일 JSON 캐시로 정리. 원본 데이터 자체는 변경하지 않음.

## 3. Unicode CJK Source 정보

- **출처**: Unihan Database (Unicode Consortium)
  - https://www.unicode.org/charts/unihan.html
  - https://www.unicode.org/Public/UCD/latest/ucd/Unihan.zip
- **라이선스**: Unicode License (free use with attribution)
- **사용**: K2~K6 source 정보로 한국 특유 한자(구결자 후보) 식별. 본 스킬은 직접 임베드하지 않으나, 합자 구결자 reference 작성 시 참조.

## 4. 학술 reference

- 위키백과 「구결」 (https://ko.wikipedia.org/wiki/구결) — CC BY-SA 4.0
- 한국구결학회 학회지 『구결연구』 — 학술 인용 (저자 권리 존중)
- 黃善燁 「口訣字 字典과 그 表記體系」 — 학술 인용
- 南豊鉉 『國語史를 위한 口訣硏究』 (太學社, 2002, ISBN 89-7626-485-1) — 학술 인용
- 최식, 「漢文讀法의 韓國的 特殊性 -句讀, 懸吐, 口訣-」, 『漢字漢文敎育』 27 (2011) — 학술 인용

## 5. 본 스킬 자체

- **라이선스**: MIT
- **저자**: hw725 (hw725@g.skku.edu) + Claude (Anthropic) collaboration
- **저장소**: 사용자 본인 git repo로 배포 시 본 스킬 디렉터리(`~/.claude/skills/gugyeol-decode/`)를 그대로 push

## 6. 기여·인용 시 권장 형식

본 스킬을 학술·실용 작업에 사용하여 결과를 발표할 때는 다음 형식으로 인용 권장:

```
gugyeol-decode (2026)
Built upon kiwiyou/hypua (Unlicense) and AKS 한국역사정보통합시스템.
https://github.com/hw725/gugyeol-decode
```

또는 BibTeX:

```bibtex
@misc{gugyeol-decode-2026,
  title  = {gugyeol-decode: Korean PDF kugyeol·old hangul recovery},
  year   = {2026},
  note   = {Built upon kiwiyou/hypua (Unlicense) and AKS 한국역사정보통합시스템},
  url    = {https://github.com/hw725/gugyeol-decode}
}
```
