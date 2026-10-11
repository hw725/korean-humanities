"""Stop 훅: '전수'+완료 표현이 있는데 '확인 N / 전체 N' 개수가 없거나 두 수가 다르면 응답 종료를 막는다.

완료 주장 탐지와 개수 탐지는 같은 텍스트(코드 블록·인용 줄을 뺀 것, 표 행은 남김)를 본다 — 표 행에 쓴 «전수 … 완료»가
검사를 건너뛰지 않게(리뷰 ③ R-4). 재응답(stop_hook_active)도 같은 미충족이면 막고, 같은 사유로 세 번 막힌 뒤에만
사용자에게 보이는 systemMessage 로 «검증 없이 완료 주장»과 사유를 남기고 통과시킨다(리뷰 ③ R-1).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):  # CJK 계약 E3 — 한국어 Windows 콘솔(cp949)에서 «—» 출력이 죽지 않게
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass

ACK_DIR = Path(os.environ.get("FULL_REVIEW_ACK_DIR") or Path.home() / ".claude" / "harness" / "full_review_ack")
MAX_BLOCKS = 3
# «완료»가 요구사항·조건을 서술하는 꼴(완료 보고 전, 완료라고 쓰지 마라 …)이면 주장이 아니다.
_DONE_VERB = r"((?<!미)완료(?!\s*(보고|전|라고|시\b|조건|하려|되면|여부|를\s*(말|선언|보고))|\S*\s*(금지|못))|끝났|마쳤|마무리했|다 봤|확인했)"
DONE = re.compile(r"전수[^\n.。]{0,40}?" + _DONE_VERB + r"|(완료했|끝났|마쳤)[^\n.。]{0,40}전수")
COUNT = re.compile(r"\d[\d,]*\s*/\s*(전체\s*)?\d[\d,]*")
# 개수 쌍 — «확인 x / 전체 y» 또는 «x/y». 단위(개·건·행·쪽·편·권·장)를 붙여도 된다
PAIR = re.compile(r"(확인\s*)?(\d[\d,]*)\s*(?:개|건|행|쪽|편|권|장)?\s*/\s*(전체\s*)?(\d[\d,]*)")
FENCE = re.compile(r"```.*?```", re.S)
INLINE = re.compile(r"`[^`\n]*`|«[^»\n]*»|\"[^\"\n]*\"|“[^”\n]*”")
RULE = "harness-lite README «전수 규칙»"


def base(text: str) -> str:
    """판정 바탕 = 코드 블록과 인용 줄(>)을 뺀 글. 표 행은 남긴다 — 표 안의 완료 주장도 주장이다."""
    text = FENCE.sub("", text or "")
    return "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith(">"))


def prose(text: str) -> str:
    """완료 주장 판정 대상 — 바탕에서 인용부호 안 문구(언급)를 뺀 것."""
    return INLINE.sub("", base(text))


def count_problem(text: str) -> str | None:
    """개수 문제(없으면 None). «확인 x / 전체 y» 꼴이 있으면 모두 x = y 여야 하고, 없으면 x/y 쌍이 하나 이상 있고 전부 같아야 한다."""
    pairs = [(bool(m.group(1) or m.group(3)), int(m.group(2).replace(",", "")), int(m.group(4).replace(",", "")))
             for m in PAIR.finditer(base(text))]
    labeled = [(x, y) for lab, x, y in pairs if lab]
    if labeled:
        bad = [(x, y) for x, y in labeled if x != y]
        if not bad:
            return None
        x, y = bad[0]
        return (f"전수 완료를 보고했지만 확인 {x} / 전체 {y} — 미완료입니다. 개수가 같지 않으면 '전수 완료'라고 쓰지 말고, "
                f"미확인 {y - x if y > x else '?'}건과 사유를 적으세요({RULE}).")
    # 라벨 없는 쌍은 «전부» 같아야 한다 — 하나만 같으면 통과시키던 것은 «A 1/1, B 3/4»의 미완료를 숨겼다(리뷰 ⑤ p2 R-6)
    bad_pairs = [(x, y) for _, x, y in pairs if x != y]
    if pairs and not bad_pairs:
        return None
    if pairs:
        x, y = bad_pairs[0]
        return (f"전수 완료를 보고했지만 개수 {x}/{y} 가 같지 않습니다 — 미완료입니다. '확인 N / 전체 N' 꼴로 실제 확인 수와 "
                f"전체 수를 적고, 다르면 '전수 완료'라고 쓰지 마세요({RULE}).")
    return ("전수 완료를 보고했지만 '확인 N / 전체 N' 개수가 없습니다. "
            "실제 확인한 항목 수와 전체 수, 미확인 항목과 사유를 적으세요. "
            f"개수가 맞지 않으면 '전수 완료'라고 쓰지 마세요({RULE}).")


def bump_blocks(f: Path, reason: str, retry: bool) -> int:
    """같은 사유로 막힌 횟수(세션 파일 f 안에 사유별로). 새 응답이면 1부터 다시 센다 — 전체판 harness_stop._bump_blocks 와 같다."""
    key = hashlib.sha256(reason.encode("utf-8")).hexdigest()[:16]
    try:
        st = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        st = {}
    cnt = st.get("reasons") if isinstance(st, dict) and isinstance(st.get("reasons"), dict) else {}
    n = int(cnt.get(key) or 0) + 1 if retry else 1
    cnt = {**cnt, key: n} if retry else {key: n}
    try:
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps({"reasons": cnt}), encoding="utf-8")
    except OSError:
        pass
    return n


def last_text(data):
    msg = data.get("last_assistant_message")
    if msg:
        return msg
    p = data.get("transcript_path")
    if not isinstance(p, str) or not p or not Path(p).exists():
        return ""
    for line in reversed(Path(p).read_text(encoding="utf-8", errors="replace").splitlines()):
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(rec, dict) and rec.get("type") == "assistant":  # 객체가 아닌 줄은 건너뛴다(입력 모양 표)
            msg = rec.get("message") if isinstance(rec.get("message"), dict) else {}
            content = msg.get("content") if isinstance(msg.get("content"), list) else []
            texts = [c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"]
            if texts:
                return "\n".join(texts)
    return ""


def main():
    try:
        data = json.loads(sys.stdin.buffer.read().decode("utf-8", "replace") or "{}")
        data = data if isinstance(data, dict) else {}  # 객체가 아닌 JSON 에 Traceback 으로 죽지 않게
    except json.JSONDecodeError:
        return
    text = last_text(data)
    if not DONE.search(prose(text)):
        return
    why = count_problem(text)
    if not why:
        return
    sess = re.sub(r"[^\w.-]", "_", str(data.get("session_id") or data.get("transcript_path") or "x"))[-120:]
    n = bump_blocks(ACK_DIR / (sess + ".json"), why, bool(data.get("stop_hook_active")))
    if n > MAX_BLOCKS:
        out = {"systemMessage": f"[전수] 같은 사유로 {MAX_BLOCKS}번 막혔습니다 — 검증 없이 완료 주장 — 사유: {why}"}
    else:
        out = {"decision": "block", "reason": why}
    sys.stdout.buffer.write(json.dumps(out, ensure_ascii=False).encode("utf-8"))


if __name__ == "__main__":
    main()
