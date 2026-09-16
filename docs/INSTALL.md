# 설치 안내 — 환경별

Claude Code 마켓플레이스 설치가 가장 간단합니다:

```
/plugin marketplace add hw725/korean-humanities
/plugin install korean-humanities        # 연구 방법론 (스킬은 프롬프트 전용, 동봉 헬퍼는 선택)
/plugin install gugyeol-decode           # 깨진 구결·옛한글 복원 도구
/plugin install kci-citation-network     # KCI 인용망 수집기 (무료 API 키 필요)
/plugin install kci-korean-studies-trends # KCI 동향 코퍼스·보고서 (키 불필요)
```

## Claude Code가 아니어도 쓸 수 있습니다

플러그인·마켓플레이스는 Claude Code의 **설치 편의 계층**일 뿐이고, 알맹이는 도구
중립입니다. 아래에서 자기 환경을 찾아 그대로 따라 하시면 됩니다. 어느 경우든 먼저
저장소를 받습니다:

```bash
git clone https://github.com/hw725/korean-humanities
# git이 없으면: GitHub 페이지에서 Code → Download ZIP → 압축 해제
```

## Claude Code — 마켓플레이스 없이 수동 설치

원하는 스킬 폴더를 `~/.claude/skills/`에 복사합니다. 예를 들어 gugyeol-decode 하나만:

```bash
# macOS / Linux
cp -r korean-humanities/plugins/gugyeol-decode/skills/gugyeol-decode ~/.claude/skills/
```

```powershell
# Windows (PowerShell)
Copy-Item -Recurse korean-humanities\plugins\gugyeol-decode\skills\gugyeol-decode "$env:USERPROFILE\.claude\skills\"
```

## Codex CLI 등 skills 규약을 쓰는 도구

같은 스킬 폴더를 그 도구의 skills 디렉터리에 복사하면 됩니다 — SKILL.md 규약이
같아 그대로 동작합니다.

```bash
cp -r korean-humanities/plugins/gugyeol-decode/skills/gugyeol-decode ~/.codex/skills/
```

## 다른 LLM·챗봇 (웹 ChatGPT·Gemini 등)

방법론 3종(연구 워크플로·비서 라우터·영문 라이팅)은 실행 코드가 없는 **프롬프트
문서**라서 어떤 LLM에든 쓸 수 있습니다. `plugins/korean-humanities/skills/<스킬>/SKILL.md`
본문을 대화에 붙여 넣고 «이 지침대로 ○○해 주세요»라고 요청하면 됩니다.
`references/` 폴더의 세부 문서는 해당 작업에 필요한 것만 이어서 붙입니다.

## AI 도구 없이 — 터미널만으로

kci 인용망·동향·gugyeol 복원 스크립트는 순수 Python이라 단독 실행됩니다.
Python 3만 있으면 되고(표준 라이브러리 사용), 추가로 필요한 패키지는 다음뿐입니다.

| 패키지 | 쓰는 곳 |
|---|---|
| `pymupdf` | gugyeol-decode의 **PDF 입력** |
| `python-hwpx` | gugyeol-decode의 **HWPX 입력** |
| `olefile` | academic-research-workflow의 `verify_manuscript_numbers.py`가 **HWP(바이너리) 원고**를 읽을 때. 없으면 그 자리에서 중단합니다(HWPX·DOCX·MD 입력에는 필요 없습니다) |
| `regex` | korean-humanities 동봉 헬퍼 `hanmun-research-assistant/scripts/cjk_title_match.py`(유니코드 프로퍼티 매칭) |

`tools/` 2종은 준비물이 없습니다. 실행 명령은 아래 각 플러그인 절의 «사용법»
코드 블록을 그대로 쓰되, Windows는 `py -3`, macOS/Linux는 `python3`을 사용합니다.

## 알아 둘 것 — 선택 단위

폴더 복사의 선택 단위는 **스킬 하나**입니다 — 플러그인(묶음, 4종)보다 잘게, 스킬 6종 중
원하는 것만 골라 복사할 수 있습니다. 각 스킬은 단독 동작하며, 동반 스킬이 없을 때의
동작도 각 SKILL.md에 명시돼 있습니다.

**한 가지 예외 — `tools/` 2종은 스킬 폴더 밖에 있습니다.** `hanmun-research-assistant`의
SKILL.md는 CJK 텍스트 계약 항목에서 `tools/setup-terminal-utf8.ps1`과
`tools/check_cjk_text_contract.py`를 실행하라고 안내하는데, 이 둘은 스킬 폴더가 아니라
**korean-humanities 플러그인 루트의 `tools/`**에 있습니다. 그 스킬을 폴더 복사로 쓸
생각이면 `tools/`도 함께 복사하고, SKILL.md의 `tools/...` 명령은 복사한 위치 기준으로
경로를 바꿔 실행합니다.

```bash
# 예: 스킬과 공통 도구를 함께 가져오기
cp -r korean-humanities/plugins/korean-humanities/skills/hanmun-research-assistant ~/.claude/skills/
cp -r korean-humanities/plugins/korean-humanities/tools ~/.claude/skills/hanmun-research-assistant/tools
```

마켓플레이스로 설치하면 플러그인 전체가 들어오므로 이 문제는 없습니다.
