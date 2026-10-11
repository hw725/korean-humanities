"""Stop 훅: '전수'+완료 표현이 있는데 'N / N' 개수가 없으면 응답 종료를 막는다."""
import json
import re
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):  # CJK 계약 E3 — 한국어 Windows 콘솔(cp949)에서 «—» 출력이 죽지 않게
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass

# «완료»가 요구사항·조건을 서술하는 꼴(완료 보고 전, 완료라고 쓰지 마라 …)이면 주장이 아니다.
_DONE_VERB = r"(완료(?!\s*(보고|전|라고|시\b|조건|하려|되면|여부|를\s*(말|선언|보고))|\S*\s*(금지|못))|끝났|마쳤|마무리했|다 봤|확인했)"
DONE = re.compile(r"전수[^\n.。]{0,40}?" + _DONE_VERB + r"|(완료했|끝났|마쳤)[^\n.。]{0,40}전수")
COUNT = re.compile(r"\d[\d,]*\s*/\s*(전체\s*)?\d[\d,]*")
FENCE = re.compile(r"```.*?```", re.S)
INLINE = re.compile(r"`[^`\n]*`|«[^»\n]*»|\"[^\"\n]*\"|“[^”\n]*”")


def prose(text: str) -> str:
    """판정 대상 = 서술 문장. 코드 블록·표 행·인용·인용부호 안 문구는 주장이 아니라 언급이다."""
    text = FENCE.sub("", text)
    lines = [ln for ln in text.splitlines() if not ln.lstrip().startswith(("|", ">"))]
    return INLINE.sub("", "\n".join(lines))


def last_text(data):
    msg = data.get("last_assistant_message")
    if msg:
        return msg
    p = data.get("transcript_path")
    if not p or not Path(p).exists():
        return ""
    for line in reversed(Path(p).read_text(encoding="utf-8", errors="replace").splitlines()):
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get("type") == "assistant":
            content = rec.get("message", {}).get("content", [])
            texts = [c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"]
            if texts:
                return "\n".join(texts)
    return ""


def main():
    try:
        data = json.loads(sys.stdin.buffer.read().decode("utf-8", "replace") or "{}")
    except json.JSONDecodeError:
        return
    if data.get("stop_hook_active"):
        return
    text = last_text(data)
    if DONE.search(prose(text)) and not COUNT.search(FENCE.sub("", text)):  # 코드 블록 속 «1/100» 은 개수가 아니다
        out = {"decision": "block",
               "reason": "전수 완료를 보고했지만 '확인 N / 전체 N' 개수가 없습니다. "
                         "실제 확인한 항목 수와 전체 수, 미확인 항목과 사유를 적으세요. "
                         "개수가 맞지 않으면 '전수 완료'라고 쓰지 마세요(harness-lite README «전수 규칙»)."}
        sys.stdout.buffer.write(json.dumps(out, ensure_ascii=False).encode("utf-8"))


if __name__ == "__main__":
    main()
