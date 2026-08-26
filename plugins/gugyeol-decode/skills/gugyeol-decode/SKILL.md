---
name: gugyeol-decode
description: Decode Korean academic PDFs and HWPX/HWP documents by recovering gugyeol characters (구결자, MR kugyŏl; 厓·古·爲·匕·兯 abbreviations) and old hangul (옛한글, ᄒᆞ·ᇫ etc.) that extractors render as broken (cid:N) marks or PUA codepoints. Covers 한양 PUA + AKS standard mappings + standard Unicode CJK 합자 구결. Trigger on "구결 풀어줘", "옛한글 복원", "PUA 풀어줘", "한국 학술 PDF 깨짐", "HWPX 옛한글 안 풀려", "(cid:N) 처리".
license: MIT
metadata:
  category: documents
  locale: ko-KR
  version: 1.0.3
  phase: v1
  suite: korean-humanities
  tier: portable
  share: gugyeol-decode
---

# gugyeol-decode (구결자·옛한글 PDF/HWPX 복원)

## What this skill does

한국 인문학·고전·국어학 문서에는 **옛한글**(ᄒᆞ나니라의 ᄒᆞ에 해당하는 아래아 글자, ㅿ 반치음, ㅸ 순경음 비읍 등)과 **구결자**(口訣字 — 厓 → ㄱ-shape, 隱 → ㄴ-shape, 爲 → ㅎ-form 등 漢字를 약식화한 韓國式 토 표지)가 빈번히 등장한다. 이들은 표준 Unicode 부호점이 부여되지 않아 폰트·문서 포맷마다 **PUA(Private Use Area, U+E000-F8FF)에 임의 매핑**되어 있다.

- **학술 PDF**: 출판사가 폰트별로 PUA 매핑 → `pdfplumber`/`pdftotext`가 `(cid:N)` 또는 빈칸으로 떨어뜨림
- **HWPX/HWP**: 한컴 한글이 한양 PUA로 옛한글 표기 → `python-hwpx` TextExtractor가 PUA codepoint 그대로 통과시킴

본 스킬은 입력 포맷을 자동 감지하여:

- **PDF 경로**: PUA 글자별 (codepoint, font, 위치, 컨텍스트) 추출 → hypua + AKS 자동 매핑 → 본문 치환
- **HWPX 경로**: python-hwpx로 텍스트 추출 → codepoint 단독 룩업(한컴 PUA 표준) → 본문 치환
- **HWP 경로**: HWPX 자동 변환(hwpx 스킬 활용) → HWPX 흐름

추가로 모든 경로에서 자동 적용:

- **PUA 폰트 무시 fallback**: 같은 codepoint이지만 다른 폰트로 등장한 PUA가 있을 경우(예: U+F537 = ᄒᆞ가 본문 폰트와 강조 폰트에서 동시 등장) 첫 매핑을 fallback으로 적용. 이전 버전의 잔존 PUA 누락 케이스 해소.
- **NFC 정규화**: CJK Compatibility Ideographs(U+F900-FAFF)가 정규 분해를 가진 경우 표준 CJK Unified Ideographs로 자동 변환(예: 讀 U+F95A → 讀 U+8B80, 寧 U+F95F → 寧 U+5BE7). NFC는 canonical equivalence만 처리하므로 학술 텍스트의 의도된 표기를 건드리지 않는다. 의도적으로 끄려면 `--no-normalize` 사용. NFKC를 사용하지 않는 이유는 halfwidth/fullwidth 변환 등 부수 효과로 학술 텍스트(예: 한문 문장부호, 일본어 인용)에 의도치 않은 영향을 줄 수 있기 때문.

## When to use

- “이 논문 PDF에서 옛한글이 깨져 나와”
- “(cid:6) (cid:38) 같은 게 잔뜩 있어”
- “임규직/박문호/윤근수 등 19세기 학자 논문 PDF 복원해줘”
- “口訣字가 PDF에 나오는데 텍스트 추출이 안 돼”
- “한국 고전 OCR 결과에 PUA 부호점 나옴”
- 한국 인문학 PDF를 wiki/논문/DB에 인용하려는데 옛한글이 손실된 경우

## When NOT to use

- 일반 영문/현대 한글 PDF — 표준 Unicode면 충분
- 스캔 이미지 OCR이 필요한 경우 — 본 스킬은 텍스트 레이어가 있는 PDF 대상. OCR은 별도 도구 (Naver Clova, Tesseract+옛한글 모델)
- 漢文 자체의 異體字 변별 — 본 스킬은 한국 PUA에 한정

## Prerequisites

- **Python 3.9+** (pip install로 의존성 자동 처리)
- 의존성은 `setup.py`가 자동 설치:
  - `PyMuPDF` (필수, PDF 처리)
  - `python-hwpx` (선택, HWPX/HWP 처리)
- Claude Code 또는 멀티모달 LLM 접근 (PDF 시각 판독 fallback용 — 자동 매핑 100% 시 불필요)
- 출력 디렉터리 쓰기 권한

## Install (원클릭)

> **이미 이 스킬 폴더에 `reference/` 매핑 데이터(약 3.6MB)가 들어 있다면** — korean-humanities
> 슈트 배포본이 그렇다 — 아래 원클릭 설치는 불필요하다. PDF 처리를 쓸 때
> `pip install pymupdf`만 하면 된다.

```powershell
# Windows
iwr -useb https://raw.githubusercontent.com/hw725/gugyeol-decode/master/install.ps1 | iex
```

```bash
# macOS/Linux/WSL
curl -fsSL https://raw.githubusercontent.com/hw725/gugyeol-decode/master/install.sh | bash
```

자동 처리: clone → pip install (pymupdf + python-hwpx) → 매핑 데이터 다운로드.

## Inputs

- **PDF** (텍스트 레이어 있는 PDF — 스캔 PDF는 사전 OCR 필요) — PyMuPDF 글리프 추출
- **HWPX** (한컴 한글 .hwpx) — python-hwpx TextExtractor
- **HWP** (한컴 한글 바이너리 .hwp) — hwpx 스킬의 convert_hwp.py로 자동 변환
- 출력 markdown 경로 (기본: `<입력>.normalized.md`)
- (PDF 한정) 중간 디렉터리 `<입력>의 부모/_pua_<stem>/` (자동 생성·삭제)

## Outputs

- **`<입력>.normalized.md`** — 본문 전체에 PUA → 표준 Unicode 치환 + NFC 정규화 완료된 markdown (모든 입력 공통)
- (PDF 한정 중간 산출물 — `--keep-intermediate` 시):
  - `_pua_<stem>/U<HEX>_p<페이지>_<폰트>.png` — PUA 글자별 컨텍스트 PNG
  - `_pua_<stem>/_contexts.txt` — 각 PUA의 등장 페이지·폰트·전후 라인
  - `_pua_<stem>/mapping.json` — 확정된 매핑 테이블 (재사용 캐시)

## 폰트 기반 1차 분류 휴리스틱

확정된 시각 판독에 앞서, 폰트 이름으로 후보를 좁힌다.

| 폰트 패턴 | 추정 글자 종류 | 비고 |
|----------|--------------|------|
| `TT70xx`, 한컴/한양 한글 본문 폰트 | **옛한글** (아래아·반치음·순경음 등) | 한글 본문 컨텍스트 |
| `*명조`, `*신명조`, `Hancom 명조` 류 | **구결자** 또는 옛한글 引用 | 漢文 구결 설명·인용문 |
| `*HCI-*` 라틴/숫자 폰트 | 페이지 번호·서지 — 무시 | |
| `Arial`, `Times` | 일반 — 무시 | |

font 이름이 mojibake(`*ÇÑ¾ç½Å¸íÁ¶`)로 나와도 패턴은 보존된다. CP949 → UTF-8 매핑으로 한글 폰트명 복원 가능 (예: `*ÇÑ¾ç½Å¸íÁ¶` → `*한양신명조`).

## Workflow

### 0. (1회 setup) 표준 매핑 캐시 구축 — **이게 정확도 핵심**

원클릭 install이나 `python setup.py` 실행 시 **모두 자동 처리**됩니다. 아래는 내부적으로 어떤 자료를 받는지의 설명 (수동 fallback이 필요한 경우만 직접 사용).

본 스킬은 다음 외부 자료에 의존한다 (자세한 출처·라이선스는 `ATTRIBUTION.md`):

#### 0a. hypua (옛한글 PUA → IPF Unicode jamo) ⭐⭐⭐

**가장 중요**. `kiwiyou/hypua` (Unlicense, public domain) 5660건 매핑 테이블. setup.py가 자동 다운로드. 수동 fallback:

```bash
curl -L "https://raw.githubusercontent.com/kiwiyou/hypua/master/table" \
  -o reference/hypua_table.csv
```

#### 0b. AKS 한국학중앙연구원 표준 매핑

```bash
python scripts/fetch_aks_gukyul.py    # 구결자 255 PUA × 104 음가
python scripts/fetch_aks_oldhan.py    # 옛한글 5299 PUA × 23 카테고리
```

#### 0c. (선택) Unihan K source 한자 — 합자 구결자 후보 풀

```bash
python scripts/fetch_unihan_korean.py # K2~K6 한국 source 한자 10,919건
```

**우선순위 체계**:
1. `hypua_table.csv` — 한양 PUA 옛한글 (압도적 정확도, 시각 판독 대체)
2. `aks_gukyul_pua.json` — 구결자 PUA → 음가 (한국학중앙연구원 표준)
3. `aks_oldhan_pua.json` — 옛한글 카테고리 (hypua 미수록 잔여분)
4. `hapja_gugyeol.json` — 합자 구결자 (한국 한자 표준 + 학술 검증)
5. `unihan_korean.json` — 후보 풀 (사용자 검증 후 hapja에 등록)
6. 시각 판독 — 위 모두 못 잡는 경우만

### 1. 추출 + 인덱싱 + AKS 자동 룩업

```bash
python scripts/extract_pua.py <PDF경로> [--out <디렉터리>]
```

내부적으로 PyMuPDF의 `page.get_text('dict')`로 글리프-수준 정보를 얻고, `0xE000 ≤ codepoint ≤ 0xF8FF`인 글자만 골라 `(codepoint, font)` 키별 첫 등장 위치를 저장한다. 같은 PUA 부호점이라도 폰트가 다르면 별개 글리프이므로 따로 다룬다.

**AKS 캐시가 있으면 자동으로**:
- `*명조` 등 구결자 폰트 → AKS 구결자 매핑 적용 (verified=true)
- `TT70xx` 등 옛한글 폰트 → AKS 카테고리 매칭 (정확 자모는 시각 판독 필요)

각 (codepoint, font)당 PNG 한 장 + 컨텍스트 라인 한 줄 + mapping_skeleton.json (자동 채워진 항목 + 빈 항목).

### 2. 시각 판독 (Claude/사람)

`_contexts.txt`를 읽고 폰트로 1차 분류 → PNG를 시각 판독:

- **옛한글** 후보:
  - ᄒᆞ (하 with 아래아) — 가장 흔함. ‘ᄒᆞ다’, ‘ᄒᆞ나니라’, ‘ᄒᆞ더라’ 등
  - ᄂᆞ (나 with 아래아)
  - ᄃᆞ (다 with 아래아)
  - ᄉᆞ (사 with 아래아)
  - ᄆᆞ, ᄋᆞ, ᄎᆞ, ᄆᆞ, ᄒᆞ + 받침 ᆯ/ᆫ 등 자모 결합형
  - ᇫ (반치음, 받침)
  - ᄫ (순경음 비읍)
- **구결자** 후보 (`reference/구결자.md` 참조):
  - 厓(애), 隱(은/는), 古(고), 爲(하/하야), 也(야/이/라), 阿(아), 那(나), 隷·豆(다) 등 약식화 form

판독 시 **컨텍스트가 결정적 단서**:
- `'이라(?)'` 형태 → 옛한글 또는 구결 토 표시
- `信從[信?야]` 형태 → 訓借 설명, 구결자
- `'仁(이)鮮ㅗㄴ소(하니라)'` → 구결 例示

### 3. 매핑 테이블 작성

```bash
python -m gugyeol_decode.build_mapping <컨텍스트경로> <PDF경로> [--cache <캐시JSON>]
```

또는 사용자/Claude가 `mapping.json`을 직접 작성:

```json
{
  "font_aliases": {
    "*¸íÁ¶": "*명조",
    "TT7064o00": "한양신명조"
  },
  "mappings": {
    "*명조|F6D0": {"type": "gugyeol", "value": "厓", "modern": "ㄱ", "note": "下 #2 의(ᄋᆞ) 마크"},
    "TT7064o00|F537": {"type": "old_hangul", "value": "ᄒᆞ", "modern": "하", "note": "verb stem 하-"},
    "TT7064o00|E283": {"type": "old_hangul", "value": "ᄒᆞ", "modern": "하"}
  },
  "verified_by": "사용자명",
  "verified_at": "2026-05-09",
  "pdf_metadata": {"title": "...", "isbn": "..."}
}
```

`type`은 `old_hangul` / `gugyeol` / `other` 중 하나.
`value`는 가능하면 **표준 Unicode** (Hangul Jamo U+1100-U+11FF + ㆍ U+11A2 결합) 사용.
`modern`은 현대 한글 정규화 결과.

### 4. 본문 정규화 적용

```bash
python -m gugyeol_decode.apply_mapping <PDF경로> <mapping.json> -o <output.md>
```

PDF를 다시 추출하면서 매핑 테이블에 따라 PUA 글자를 옛한글 또는 구결자로 치환. 결과는 깔끔한 markdown.

### 5. 저장 + 공유

- `<vault>/references/journals/<논문>_PUA정규화.md` — 정규화 후 본문
- `<vault>/references/_pua_cache/<font_id>.json` — 폰트별 매핑 캐시
- 위키·원고에서 인용할 때는 정규화 본문에서 직접 옮김

## Reference Files

- `reference/구결자.md` — 한국 古典 구결자 표준 form 표
- `reference/옛한글.md` — 옛한글 자모·결합 규칙·Unicode 매핑
- `reference/구결자.md`, `reference/옛한글.md`, `ATTRIBUTION.md` — 최식2011 작업 근거와 학술 인용

## Done when

- 모든 PUA 글자 (codepoint, font) 조합이 매핑 테이블에 등록됨
- 의도적으로 미식별로 남긴 글자는 `type: "unknown"` + 사유 기재
- 정규화된 본문이 검증 가능한 형태로 저장됨
- 위키·논문에 인용할 때 PUA 손실 없이 옮길 수 있음

## Guardrails

- **매핑 날조 금지**: PUA codepoint의 대응 글자를 추측으로 배정하지 않는다. hypua 테이블·AKS 캐시에 없고 시각 판독으로도 불확실하면 `type: "unknown"`으로 남긴다. 잘못된 매핑은 학술 텍스트의 의미를 왜곡한다.
- **시각 판독 신뢰도 명시**: Claude/Gemini의 시각 판독 결과에도 오인식이 있을 수 있다. 특히 유사 형태의 구결자(厓/广, 隱/恩 등)는 판독 신뢰도를 [?] 표시하고, 원본 이미지와 1:1 대조를 권장한다.
- **매핑 출처 추적**: mapping.json의 각 항목이 어떤 소스(hypua 자동 매핑 / AKS 룩업 / 시각 판독 / 사용자 수동)로 확정되었는지 `verified` 필드로 구분한다. 출처 없는 매핑은 검증 불가능하다.
- **NFC/NFKC 구분 엄수**: NFC만 적용하고 NFKC는 사용하지 않는다. NFKC의 부수 효과(halfwidth/fullwidth 변환)가 학술 텍스트의 의도된 표기를 손상시킬 수 있다. `--no-normalize` 옵션의 존재를 사용자에게 안내한다.
- **“복원 완료” ≠ “정확성 보장”**: PUA 매핑 적용 후에도 매핑 테이블에 `unknown`이 남아 있으면 “완전 복원”이라 주장하지 않는다. 미매핑 건수를 정직하게 보고한다.

## Failure modes

- **폰트 임베딩 안 됨**: 일부 PDF는 PUA 글자에 폰트가 없거나 mojibake 폰트명만 남는다 → 폰트별 클러스터링 불가, 시각 판독에만 의존
- **OCR 기반 PDF**: 텍스트 레이어가 OCR이라면 PUA 글자가 부정확하게 인식되어 있을 수 있음 → 원본 이미지 직접 OCR 권장
- **희귀 구결자**: 시각 판독으로도 식별 불가능한 약식 form은 `unknown`으로 두고 사용자 후속 검토 의뢰
- **동일 codepoint 다른 글자**: 같은 폰트 다른 글리프가 우연히 같은 PUA 부호점이면 매핑 충돌. 폰트 서브셋 PDF에서 가끔 발생
- **합자 구결자(合字)**: 兯(U+516F, 한 = 隹+隱) 같이 두 글자가 시각적으로 합쳐진 글리프는 표준 Unicode CJK Unified Ideographs/Extensions에 있고 PUA에 없다. **본 스킬의 PUA 스캔 범위(U+E000-F8FF)에 미포함**. 한양 PUA의 한계. PDF 본문에 합자 구결이 등장하면 일반 漢字로 추출되어 사용자 수동 식별·매핑 필요. 자세한 처리 방안은 [reference/구결자.md](reference/구결자.md#합자-구결자) 참조

## Notes for sharing

- 매핑 테이블 (`mapping.json`)은 폰트 ID 기준이므로 다른 PDF에 재사용 가능
- 표준 폰트(한양신명조 등) 캐시가 충분히 쌓이면 새 PDF는 자동 매핑 비율 높아짐
- Unicode 6.0+에서 옛한글 자모는 표준화되었으므로 매핑 결과는 modern 도구에서 정상 렌더링됨
- 구결자는 일부만 Unicode 표준화 (Hanja 영역). 표준 부호점이 없으면 `value`에 약식 form 또는 음가 표기 사용
