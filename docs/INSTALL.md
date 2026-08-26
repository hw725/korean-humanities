# 설치 안내 — 환경별

Claude Code 마켓플레이스 설치가 가장 간단합니다:

```
/plugin marketplace add hw725/korean-humanities
/plugin install korean-humanities        # 연구 방법론 (프롬프트 전용, 준비물 0)
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
Python 3만 있으면 되고(표준 라이브러리 사용), 추가 설치는 gugyeol의 PDF 입력용
`pip install pymupdf` 하나뿐입니다. 실행 명령은 아래 각 플러그인 절의 «사용법»
코드 블록을 그대로 쓰되, Windows는 `py -3`, macOS/Linux는 `python3`을 사용합니다.

## 알아 둘 것 — 선택 단위

폴더 복사의 선택 단위는 **스킬 하나**입니다 — 플러그인(묶음, 4종)보다 잘게, 스킬 6종 중
원하는 것만 골라 복사할 수 있습니다. 각 스킬은 단독 동작하며, 동반 스킬이 없을 때의
동작도 각 SKILL.md에 명시돼 있습니다.
