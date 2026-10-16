"""UserPromptSubmit 훅: 전수 관련 표현이 있으면 전수 규칙을 컨텍스트에 주입."""
import json
import re
import sys

for _stream in (sys.stdout, sys.stderr):  # CJK 계약 E3
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass

KEYS = re.compile(r"전수|전부\s*다시|전체\s*다시|다\s*다시|빠짐없이|모두\s*확인|모든\s*행|하나도\s*빠")
RULE = (
    "[전수 규칙 - harness-lite README 《전수 규칙》] 전수 = 전체 목록의 모든 항목을 최소 단위"
    "(행·레코드·파일·문서·페이지 등)로 하나씩 실제 내용을 열어 확인. 표본·필터·의심 유형만·"
    "이전 결과 재사용은 전수가 아님(내용 해시가 같은 항목의 판정 잇기만 예외 — 이어받은 수를 따로 밝힐 것). 시작 전 전체 개수 N을 확정해 말할 것. 범위 축소가 필요하면 "
    "작업 전에 규모를 말하고 승인받을 것. 완료 보고에는 '확인 N / 전체 N'과 미확인 항목·사유 필수."
)


def main():
    try:
        data = json.loads(sys.stdin.buffer.read().decode("utf-8", "replace") or "{}")
        data = data if isinstance(data, dict) else {}  # 객체가 아닌 JSON 에 Traceback 으로 죽지 않게
    except json.JSONDecodeError:
        return
    if KEYS.search(str(data.get("prompt") or "")):
        out = {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": RULE}}
        sys.stdout.buffer.write(json.dumps(out, ensure_ascii=False).encode("utf-8"))


main()
