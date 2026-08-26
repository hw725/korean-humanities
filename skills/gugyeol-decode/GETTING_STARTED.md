# Getting Started — gugyeol-decode 시작하기

> **이게 뭐죠?**: 한국 古典·국어학 **PDF/HWPX/HWP** 문서에서 글자가 깨져 나올 때 이를 자동으로 복원하는 명령행 도구입니다.
>
> Python만 있으면 누구나 사용 가능. Claude Code 같은 별도 도구 없이도 됩니다.

---

## 1. 무엇을 해결하는가

朝鮮 시대 학자들이 한문에 붙인 토(吐)를 다룬 학술 논문 PDF를 컴퓨터로 읽으려고 합니다. 일반 PDF 추출 도구는 다음 두 종류 글자를 못 읽고 깨뜨립니다:

### 깨지는 글자 ① — **구결자(口訣字)**

漢文 옆에 토를 적기 위해 漢字를 약식화한 글자. 예시: `仁(이)鮮(하)(니)(라)`에서 작은 (하)·(니)·(라) 부분이 구결자.

```
(원본)        仁丶(이)鮮ㅎ니라(하니라)
(깨진 추출)   仁(cid:6)(이)鮮(cid:7)(cid:8)(cid:9)(하니라)
(이 도구)     仁(이)鮮하니라(하니라)         ← 정상 복원
```

### 깨지는 글자 ② — **옛한글**

19세기 이전 한국어 표기에 쓰인 자모 (아래아 ㆍ, 반치음 ㅿ 등). 任圭直의 『句讀解法』 본문에 'ᄒᆞ나니라' 같은 형태로 등장.

```
(원본)        4. 종결사 ‘ᄒᆞᄂᆞ니라’ ‘ᄒᆞ다’ ‘ᄒᆞ더라’
(깨진 추출)   4. 종결사 ‘(cid:6)(cid:7)니라’ ‘(cid:6)다’ ‘(cid:6)더라’
(이 도구)     4. 종결사 ‘ᄒᆞᄂᆞ니라’ ‘ᄒᆞ다’ ‘ᄒᆞ더라’   ← 정상 복원
```

### 왜 깨지는가

표준 Unicode에 부호점이 없는 한국 古典 글자가 많아서, 학술 출판사들은 폰트의 PUA(Private Use Area) 영역에 임의로 매핑합니다. 폰트마다 매핑이 달라서 일반 추출 도구가 못 읽습니다. 이 도구는 표준 매핑 데이터를 모아두었다가 자동 복원합니다.

### 본 스킬의 두 축

| 축 | 다루는 글자 | 출처 데이터 | 본 스킬의 역할 |
|----|------------|------------|--------------|
| **구결자** | 漢字 약식 토 표지 + 합자 (兯 등) | 한국학중앙연구원(AKS) 표준 + Unihan K source | **본 스킬의 핵심 기여** — AKS 데이터 캐시화 + 합자 구결 reference 누적 |
| **옛한글** | 아래아·반치음 등 자모 결합 | hypua (kiwiyou/hypua, Unlicense) | **외부 라이브러리 차용** — hypua 매핑 테이블을 `extract_pua.py`에 통합 |

---

## 2. 설치 — 한 줄

### 사전 준비

- **Python 3.9 이상** (`python --version` 으로 확인)
- **인터넷 연결** (1회 setup 시 매핑 데이터 다운로드)

### 원클릭 설치

**Windows (PowerShell)**:
```powershell
iwr -useb https://raw.githubusercontent.com/hw725/gugyeol-decode/master/install.ps1 | iex
```

**macOS / Linux / WSL (bash)**:
```bash
curl -fsSL https://raw.githubusercontent.com/hw725/gugyeol-decode/master/install.sh | bash
```

자동 처리되는 것:
1. `~/.claude/skills/gugyeol-decode/`에 git clone
2. `pymupdf` (필수) + `python-hwpx` (선택) pip install — 실패 시 `--user` 자동 재시도
3. **hypua 옛한글 매핑** (kiwiyou/hypua, public domain, 5660건) 다운로드
4. **AKS 구결자 매핑** (한국학중앙연구원, 255건) 다운로드
5. **AKS 옛한글 카테고리** (5299건) 다운로드
6. **Unihan K source 한자** (합자 구결 후보 풀, 10,919건, 약 8MB) 다운로드

**소요 시간**: 약 5-10분 (대부분 AKS 옛한글 lookup). 한 번만 받아두면 끝.

### 수동 설치 (원클릭이 막힌 경우)

```bash
git clone https://github.com/hw725/gugyeol-decode.git ~/.claude/skills/gugyeol-decode
cd ~/.claude/skills/gugyeol-decode
python setup.py            # 의존성 + 데이터 자동 처리
```

### 옵션

```bash
python setup.py --skip-unihan    # 합자 구결 데이터 제외 (3.8MB → 0.6MB)
python setup.py --check          # 설치 상태만 확인
```

### 설치 확인

```bash
python ~/.claude/skills/gugyeol-decode/setup.py --check
```

다음과 같이 모두 ✓ 표시되면 OK:

```
현재 설치 상태:
  ✓ PyMuPDF (fitz) — PDF 처리
  ✓ python-hwpx — HWPX 처리 (선택)
  ✓ hypua 옛한글 매핑 (5660건)
  ✓ AKS 구결자 매핑 (255건)
  ✓ AKS 옛한글 카테고리 (5299건)
  ✓ Unihan K source 한자 (10919건, 선택)
```

### Claude Code 사용자 — 자연어 호출

> "이 PDF에서 옛한글이 깨져 나와 — 풀어줘"

Claude가 자동으로 본 스킬을 활성화하여 워크플로 수행. **Claude Code가 없어도 CLI로 그대로 사용 가능**합니다.

---

## 3. 첫 사용 — 1-step 명령

### 시나리오

- `~/Downloads/논문.pdf` — 구결자·옛한글이 등장하는 한국 학술 PDF
- `~/Downloads/원고.hwpx` — 옛한글 PUA가 들어있는 한컴 한글 문서
- `~/Downloads/원고.hwp` — 구버전 한컴 한글 (자동 변환)

### 한 명령으로 끝 — 입력 확장자만 다르고 사용법 동일

```bash
python scripts/decode.py ~/Downloads/논문.pdf       # PDF
python scripts/decode.py ~/Downloads/원고.hwpx      # HWPX
python scripts/decode.py ~/Downloads/원고.hwp       # HWP (자동 변환)
```

이 명령이 자동으로:
1. 입력 확장자 자동 감지
2. PDF는 PyMuPDF 글리프 추출, HWPX는 python-hwpx TextExtractor 사용
3. hypua + AKS 캐시로 자동 매핑 (대부분 100%)
4. 본문 전체에 PUA → 표준 Unicode 치환
5. **2차 PUA sweep**: 글리프 단계 lookup이 놓친 잔존 PUA를 codepoint 단독 fallback으로 정리
6. **NFC 정규화 자동 적용**: CJK Compatibility Ideographs (讀·寧·李 등) → 표준 한자
7. 깨끗한 markdown으로 저장 → `<원본>.normalized.md`
8. 중간 파일 자동 삭제 (PDF만)

### 출력 예시

```
[1/2] PUA 글자 추출 + 자동 매핑 (논문.pdf)
PDF: 논문.pdf  (38 pages)
발견된 고유 PUA: 32개 (codepoint × font)
hypua 자동 채움: 옛한글 26건 verified (PUA → IPF Unicode jamo)
AKS 자동 채움: 구결자 6건 verified

[2/2] PDF 전체 텍스트 추출 + PUA 치환
  2차 PUA sweep (codepoint 단독): 10회 추가 매핑 적용 → 잔존 0
  NFC 정규화: CJK Compatibility 22종, 192회 등장 → 192회 표준 한자로 변환
저장: ~/Downloads/논문.normalized.md
  매핑 적용 글자 수: 32 종류
  미매핑 (occurrence): 0

✓ 완료: ~/Downloads/논문.normalized.md
  중간 파일 삭제: ~/Downloads/_pua_논문
```

### 옵션

```bash
# 표준 Unicode form만 (학술 인용용)
python scripts/decode.py 논문.pdf --mode value

# 현대 한글 form만 (검색·일반 가독)
python scripts/decode.py 논문.pdf --mode modern

# 출력 경로 지정
python scripts/decode.py 논문.pdf --out 결과.md

# 중간 파일 보존 (디버깅·매핑 검토용)
python scripts/decode.py 논문.pdf --keep-intermediate

# 합자 구결자 스캔 끄기
python scripts/decode.py 논문.pdf --no-hapja

# NFC 정규화 끄기 (원전 그대로 보존이 필요한 디버깅 케이스)
python scripts/apply_mapping.py <pdf> <mapping.json> --no-normalize
```

> NFC 정규화는 학술 텍스트에 안전한 canonical equivalence만 적용 (NFKC가 아님 — halfwidth/fullwidth 등 부수효과 회피). `--no-normalize`는 원본 PDF의 codepoint를 그대로 보존해야 하는 디버깅 작업에서만 사용 권장.

### 결과 확인

`논문.normalized.md`를 열면 PDF 본문이 페이지별로 정리되어 있고, 옛한글·구결자가 표준 Unicode로 정확히 복원되어 있습니다:

```markdown
## Page 15

4. 종결사(斷辭) ‘이라’ ‘이니라’ ‘ᄒᆞᄂᆞ니라’ ‘ᄒᆞ다’ ‘이러라’ ‘ᄒᆞ더라’ ‘이로다’...
```

### 자동 매핑이 100% 안 되는 경우 (드뭄)

`decode.py` 실행 시 `미매핑 (occurrence): N`이 N>0이면 일부 PUA가 자동 매핑 안 된 것. 이때 `--keep-intermediate`로 다시 실행하여 시각 판독:

```bash
python scripts/decode.py 논문.pdf --keep-intermediate
ls ~/Downloads/_pua_논문/
```

- `mapping_skeleton.json` — 자동 매핑 결과 (편집 가능)
- `U<HEX>_*.png` — 미매핑 글자의 시각 판독용 PNG

PNG 보고 매핑 직접 입력 후 `apply_mapping.py`로 재실행 (자세한 건 7부 Q4 참조).

---

## 4. 구결자 (口訣字) — 본 스킬의 핵심

### 구결자란

漢文 원전에 한국식 토(吐)를 적기 위해 漢字를 약식화한 글자.

```
原 漢文:    巧言令色鮮矣仁
구결 표기:  巧言令色이 鮮矣仁이니라
구결 풀이:  巧言令色 + (이) + 鮮矣仁 + (이니라)
                       ↑                  ↑
                  '이' 구결자        '이니라' 구결자 (4글자 결합)
```

### 본 스킬의 구결자 처리

#### A. 단음 구결자 (1 글자 = 1 음절)

`reference/aks_gukyul_pua.json` (AKS 한국학중앙연구원 표준):

| PUA | 모자(母字) | 음가 | 기능 |
|-----|----------|------|------|
| U+F687 | 古 | 고 | 연결어미 |
| U+F6A5 | 匕 (尼와 同音) | **니** | 연결어미 (匕 형태가 흔함) |
| U+F6D5 | 羅 | 라 | 종결사 |
| U+F74F | 伊 | 이 | 주격 조사 |
| U+F775 | 爲 | 하 | 동사 어간 |
| ... | ... | ... | ... (255건) |

`extract_pua.py`가 자동으로 룩업합니다.

#### B. 합자 구결자 (2 글자가 통합된 단일 글리프)

표준 Unicode CJK 영역에 등재된 합자 구결자. 한양 PUA에는 없음.

| 합자 | Unicode | 구성 | 음가 |
|------|---------|------|------|
| 兯 | U+516F | 隹(위) + 隱(은/는) 系 | 한 |
| (incremental 추가) | | | |

`reference/hapja_kugyeol.json`에 검증된 글자만 등록. `--scan-hapja` 옵션으로 PDF 본문에 등장 여부 보고.

또한 `reference/unihan_korean.json`에는 Unihan K2~K6 한국 source 한자 **10,919건**이 후보 풀로 들어 있어, PDF 본문에서 한국 특유 한자가 등장하면 자동 보고합니다 (학술 검증 후 hapja에 정식 등록).

#### C. 구결 reference 자료

- `reference/구결자.md` — 한국 古典 구결자 표준 form 표 (단음 + 결합 + 합자)
- 釋讀口訣 vs 順讀口訣 시기 구분
- 학파별 (영남·기호·호론) 차이
- 학술 reference (한국구결학회·黃善燁 자전·南豊鉉 『口訣硏究』)

---

## 5. 옛한글 — hypua 라이브러리 활용

### 옛한글이란

19세기 이전 한국어 표기에 쓰인 자모. 본 스킬에서 가장 자주 등장:

- **ㆍ (아래아)** — 'ᄒᆞ' = ᄒ + 아래아 (현대 '하'에 대응)
- **ㅿ (반치음)** — 'ᇫ' (15-16세기 위주)
- **ㅸ (순경음 비읍)** — 'ᄫ'

### 본 스킬의 옛한글 처리

본 스킬의 옛한글 매핑은 **외부 라이브러리 [kiwiyou/hypua](https://github.com/kiwiyou/hypua) (Unlicense, public domain)** 의 매핑 테이블을 그대로 활용합니다.

#### hypua가 하는 일

한양 PUA 옛한글 codepoint → 표준 Unicode IPF(Initial-Peak-Final, 첫가끝) jamo 결합형 변환.

예시:
```
U+F537  →  ᄒᆞ  (= U+1112 ᄒ + U+119E ᆞ)
U+E1AD  →  ᄀᆞᆯ (= U+1100 ᄀ + U+119E ᆞ + U+11AF ᆯ)
U+EE88  →  ᄋᆞ  (= U+110B ᄋ + U+119E ᆞ)
```

5660건의 매핑 테이블이 한양 PUA 옛한글 codepoint의 거의 전부를 커버.

#### 본 스킬의 기여

- hypua의 `table` 파일을 `reference/hypua_table.csv`로 그대로 포함
- `scripts/extract_pua.py`에 자동 룩업 통합
- 옛한글 폰트 패턴 휴리스틱 (`TT70xx` → 옛한글 자동 분류)
- AKS 옛한글 카테고리 데이터로 hypua 미수록 잔여분 보완

#### 라이선스 명시

`ATTRIBUTION.md`에 hypua의 출처·라이선스·인용 형식이 명시되어 있습니다. 본 스킬을 학술 작업에 사용하면 hypua 크레딧을 함께 명시 권장.

#### 옛한글 reference

- `reference/옛한글.md` — 자모 결합 규칙·정규화 정책

---

## 6. 출력 결과 이해하기

### 표준 Unicode jamo 결합형

옛한글 'ᄒᆞ'는 두 글자의 결합:
- `U+1112` (ᄒ, HANGUL CHOSEONG HIEUH) — 초성
- `U+119E` (ᆞ, HANGUL JUNGSEONG ARAEA) — 중성 (아래아)

표준 Unicode이므로:
- 옛한글 폰트(함초롬바탕 등)로 정상 렌더링
- 검색·복사·붙여넣기 안전
- macOS·Windows·Linux 무관

### 옛한글 폰트 권장

옛한글 글자가 보이지만 정상 렌더링이 안 되면 폰트 추가:
- **함초롬 폰트** (한글학회): https://hangeul.naver.com/font (옛한글 풀세트)
- **Noto Sans CJK** (Google): 일부 옛한글 지원
- macOS 기본 한글 폰트는 옛한글 미지원 → 함초롬 추가 권장

### `apply_mapping.py --mode` 옵션

| 모드 | 출력 | 용도 |
|------|------|------|
| `value` | 표준 Unicode form (ᄒᆞ, ᄃᆡ, 兯) | 학술 인용 |
| `modern` | 현대 한글 form (하, 대, 한) | 검색·일반 가독 |
| `both` (기본) | `value(modern)` 결합 | 디버깅·확인 |

---

## 7. 자주 만나는 문제

### Q1. `ModuleNotFoundError: No module named 'fitz'`

```bash
pip install pymupdf
```

`fitz`가 PyMuPDF의 import 이름.

### Q2. PUA 글자가 발견되지 않음

- PDF가 텍스트 레이어 없는 스캔 PDF — OCR 먼저 필요
- 옛한글·구결이 없는 일반 한국어 PDF — 정상 (할 일 없음)

### Q3. AKS 사이트 접속 안 됨 (한국 외 IP)

`fetch_aks_*.py` 가 `URLError` 내면:
- VPN으로 한국 IP 우회
- 또는 다른 사용자가 받아둔 `aks_*.json` 파일을 받아서 `reference/`에 복사

### Q4. `mapping_skeleton.json`에 자동 매핑 안 된 항목 발견

`hypua_verified`도 `aks_verified`도 없는 항목은 직접 채워야 합니다:

1. `reference/_pua/U<HEX>_*.png` 열어보고 글자 식별
2. `mapping_skeleton.json`에 직접 입력:

```json
{
  "type": "old_hangul",
  "value": "ᄒᆞᇫ",
  "unicode": "U+1112+U+119E+U+11EB",
  "modern": "핫"
}
```

3. `mapping.json`으로 저장 후 `apply_mapping.py` 실행.

### Q5. 폰트명이 깨져 나옴 (`*ÇÑ¾ç½Å¸íÁ¶`)

mojibake (인코딩 오류). 원래 `*한양신명조`. 확인:

```bash
python scripts/font_alias.py "*ÇÑ¾ç½Å¸íÁ¶"
```

매핑에는 mojibake form이 그대로 키로 사용되므로 작동에는 문제 없음.

### Q6. 합자 구결자가 안 잡힘

기본 동작은 PUA만 스캔. 합자 구결자(표준 Unicode CJK 영역)를 같이 스캔:

```bash
python scripts/extract_pua.py <PDF> --scan-hapja
```

`reference/hapja_kugyeol.json` (검증된 합자) + `reference/unihan_korean.json` (K2~K6 한국 source 한자 후보 풀) 활용.

---

## 8. 더 알기 / 기여하기

### 본 스킬의 reference

- `SKILL.md` — Claude Code 스킬 정의 + 워크플로 (자연어 호출용)
- `README.md` — 개요 + 매핑 형식 + 한계
- `ATTRIBUTION.md` — 외부 자료 출처·라이선스·인용 형식
- `reference/구결자.md` — 한국 古典 구결자 표준 form 표
- `reference/옛한글.md` — 옛한글 자모·결합·Unicode 매핑

### 외부 자료

- **위키백과 「구결」**: https://ko.wikipedia.org/wiki/구결
- **위키백과 「옛한글」**: https://ko.wikipedia.org/wiki/옛한글
- **kiwiyou/hypua** (옛한글 매핑 라이브러리): https://github.com/kiwiyou/hypua
- **AKS 한국역사정보통합시스템**: http://yoksa.aks.ac.kr/jsp/hh/oldhan.jsp
- **한국구결학회**: 학회지 『구결연구』 (KCI/DBpia 검색)

### 기여

#### 합자 구결자 추가

새로운 합자 구결자를 학술 자료에서 확인하면 `reference/hapja_kugyeol.json`에 추가:

```json
{
  "characters": {
    "U+5XXX": {
      "char": "X",
      "components": "X + X",
      "sound": "X",
      "function": "토 표지",
      "k_source": "K3-XXXX",
      "verified_source": "黃善燁 자전 p.XX"
    }
  }
}
```

#### 폰트별 매핑 누적

작업하며 검증한 (font, codepoint) → 매핑은 `reference/verified_mappings.json`에 누적. 같은 폰트 PDF가 다시 등장할 때 즉시 적용 가능.

#### 새 폰트 패턴 보고

`scripts/font_alias.py`의 `COMMON_KOREAN_FONTS` dict 확장.

### 학술 작업 인용

본 스킬을 학술 작업에 사용하면 `ATTRIBUTION.md`의 인용 형식 사용 권장. 특히 **kiwiyou/hypua**와 **AKS 한국학중앙연구원**의 기여를 함께 명시할 것.

---

## 마무리 체크리스트

처음 사용 시:

- [ ] Python 3.9+ 확인
- [ ] `pip install pymupdf`
- [ ] `python setup.py` (또는 `python setup.py --skip-unihan` 가벼운 버전)
- [ ] `python setup.py --check` 로 ✓ 모두 확인
- [ ] **`python scripts/decode.py <PDF>`** ← 이게 끝
- [ ] `<PDF>.normalized.md` 검토

질문·버그·기여는 git repo의 issue/PR로.
