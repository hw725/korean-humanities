# gugyeol-decode

> 한국 古典·국어학 PDF/HWPX에서 깨진 글자(구결자·옛한글)를 표준 Unicode로 자동 복원하는 Python CLI.

`pdfplumber` 같은 일반 도구로 한국 학술 PDF를, 또는 한컴 한글에서 만든 HWPX를 텍스트 추출하면 `(cid:6)`이나 PUA codepoint로 깨지는 글자가 두 종류:

- **구결자(口訣字)** — 漢文 옆에 토를 적은 약식 글자 (匕→니, 古→고, 兯→한 등)
- **옛한글** — 아래아·반치음 등이 들어간 자모 (ᄒᆞ, ᇫ 등)

본 도구는 표준 매핑 데이터를 활용해 이들을 정상 Unicode로 복원하고, 본문 전체를 깨끗한 markdown으로 출력합니다.

## 원클릭 설치

**Windows (PowerShell)**:
```powershell
iwr -useb https://raw.githubusercontent.com/hw725/gugyeol-decode/master/install.ps1 | iex
```

**macOS / Linux / WSL (bash)**:
```bash
curl -fsSL https://raw.githubusercontent.com/hw725/gugyeol-decode/master/install.sh | bash
```

이 한 줄이 자동으로:
1. `~/.claude/skills/gugyeol-decode/`에 git clone
2. `pymupdf` (필수) + `python-hwpx` (선택) 자동 pip install
3. hypua + AKS 매핑 데이터 다운로드 (5-10분)

## 사용 방법 (설치 후)

### A. Claude Code 사용자 — 자연어 호출

설치만 하면 끝. Claude Code가 SKILL.md description을 읽고 자동 활성화:

> "이 PDF에서 옛한글이 깨져 나와 — 풀어줘"
> "구결 풀어줘"
> "한컴 HWPX의 ᄒᆞ가 PUA로 안 풀려"

Claude가 자동으로 본 스킬을 호출하여 결과 markdown을 만들어 줍니다.

### B. CLI 사용자 — Python 한 줄

```bash
python ~/.claude/skills/gugyeol-decode/scripts/decode.py <파일.pdf|.hwpx|.hwp>
```

→ `<파일>.normalized.md` 자동 생성.

**자세한 사용법** → [GETTING_STARTED.md](GETTING_STARTED.md)

## 주요 기능

- **1-step CLI**: `decode.py <파일>` 한 번으로 추출 + 매핑 + 정규화. 입력 확장자 자동 감지
- **다중 입력 포맷**: PDF (PyMuPDF) · HWPX (python-hwpx) · HWP (자동 변환)
- **자동 매핑**: hypua + AKS 표준 매핑 데이터로 시각 판독 거의 불필요
- **2차 PUA sweep**: 글리프 단계의 (font, codepoint) lookup이 미스해도 codepoint 단독 fallback으로 잔존 PUA 자동 정리
- **NFC 정규화 자동 적용**: CJK Compatibility Ideographs (U+F900-FAFF, 讀·寧·李 등) → 표준 한자로 자동 변환. canonical equivalence만 처리하므로 학술 텍스트 안전. `--no-normalize`로 우회 가능
- **합자 구결 스캔**: 표준 Unicode CJK 영역의 합자(兯 등)도 옵션 처리 (PDF 한정)
- **Claude Code 스킬**: "구결 풀어줘" 같은 자연어로도 호출 가능

## 외부 데이터 의존성

본 스킬의 정확도는 다음 외부 자료에 의존합니다 (`setup.py`가 자동 다운로드):

| 데이터 | 출처 | 라이선스 | 용도 |
|--------|------|---------|------|
| hypua_table.csv | [kiwiyou/hypua](https://github.com/kiwiyou/hypua) | Unlicense | 옛한글 PUA → IPF Unicode (5660건) |
| aks_*.json | [AKS 한국역사정보통합시스템](http://yoksa.aks.ac.kr/jsp/hh/oldhan.jsp) | KOGL | 구결자 + 옛한글 표준 매핑 |
| unihan_korean.json | [Unicode Unihan](https://www.unicode.org/charts/unihan.html) | Unicode License | K2~K6 한국 source 한자 (합자 구결 후보) |

자세한 출처·인용 형식: [ATTRIBUTION.md](ATTRIBUTION.md)

## 라이선스

**MIT** — 자유롭게 사용·수정·배포 가능. 학술 작업 시 외부 자료(특히 hypua, AKS) 크레딧 함께 명시 권장.

## 한계

- OCR 기반 PDF에는 별도 OCR 도구 필요 (Naver Clova, Tesseract+옛한글)
- 폰트 임베딩 없는 PDF는 시각 판독에만 의존
- 합자 구결자는 Unihan K source 후보 풀에서 학술 검증 후 incremental 등록
