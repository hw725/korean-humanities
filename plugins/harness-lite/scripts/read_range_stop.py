#!/usr/bin/env python3
"""읽은 범위 Stop 훅 — 잘리거나 가려진 Read 를 복구하지 않고 답하면 «읽은 범위»를 밝히게 한다. 설계: DESIGN-harness-v2 §5-2

이번 턴(마지막 사용자 프롬프트 뒤)의 Read 에서 아래 둘을 찾는다.
  - Read 토큰 상한 잘림: transcript 의 `read_truncation_notice` 첨부(«PARTIAL view — <경로>: showing lines a-b of N»)
  - winnow 플러그인 숨김: Read 결과 속 «[winnow] Lines a-b (… lines) hidden … key <키>»
빠진 행이 세션의 다른 정상 Read 로 돌아왔거나, 같은 키의 winnow_recall 이 그 구간을 되살렸으면 복구된 것으로 본다.
복구되지 않은 파일이 있는데 응답에 «읽은 범위»가 없으면 막는다. 파일마다 세션당 한 번만 막는다.
일부러 offset·limit 을 준 Read 는 보지 않는다 — 부분 읽기를 스스로 고른 것이라 매번 막으면 마찰만 커진다.
한계: Grep 만 보고 답한 경우, 읽었지만 건너뛴 경우는 못 잡는다. 하네스 모듈에 의존하지 않는다(수강생판에 그대로 들어간다).
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass

ACK_DIR = Path(os.environ.get("READ_RANGE_ACK_DIR") or Path.home() / ".claude" / "harness" / "read_ack")
# Read 결과의 행 번호. transcript 에는 «12\t내용»으로, 화면에는 «    12→내용»으로 남는다. winnow 표지 줄은 행이 아니다.
LINE_RX = re.compile(r"^\s*(\d+)(?:→|\t)(?!\[winnow\] )", re.M)
PARTIAL_RX = re.compile(r"PARTIAL view — (.+?): showing lines (\d+)-(\d+) of (\d+) total")
WINNOW_RX = re.compile(r"\[winnow\] Lines (\d+)-(\d+) \(\d+ lines\) hidden(?:.|\n){0,600}?cached as key ([0-9a-f]+)")
STATED_RX = re.compile(r"읽은\s*범위")
RECALL_MISS_RX = re.compile(r"no (?:cached|such)|not found|unknown key|expired|error", re.I)


def norm(p: str) -> str:
    return os.path.normcase(os.path.abspath(str(p).strip().strip("\"'")))


def records(path: str | None) -> list[dict]:
    if not path or not Path(path).exists():
        return []
    out = []
    for ln in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            out.append(json.loads(ln))
        except json.JSONDecodeError:
            continue
    return out


def _text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text")
    return ""


def returned_lines(text: str) -> set[int]:
    return {int(x) for x in LINE_RX.findall(text or "")}


def _is_prompt(r: dict) -> bool:
    if r.get("type") != "user" or r.get("isMeta"):
        return False
    c = (r.get("message") or {}).get("content") if isinstance(r.get("message"), dict) else None
    if isinstance(c, str):
        return not c.startswith("<")  # 명령 출력·시스템 알림(«<command-…», «<task-notification…»)은 프롬프트가 아니다
    return isinstance(c, list) and any(isinstance(x, dict) and x.get("type") == "text" for x in c) \
        and not any(isinstance(x, dict) and x.get("type") == "tool_result" for x in c)


def gaps(recs: list[dict]) -> dict[str, list[tuple[int, int]]]:
    """이번 턴에 생긴, 복구되지 않은 빠진 구간 {파일: [(처음, 끝), …]}."""
    reads: dict[str, tuple[str, bool]] = {}   # tool_use_id → (경로, offset·limit 지정 여부)
    covered: dict[str, set[int]] = {}
    recall_req: dict[str, tuple[str, int | None, int | None]] = {}  # tool_use_id → (키, 처음, 끝)
    recalls: list[tuple[str, int | None, int | None]] = []  # 결과가 정상으로 돌아온 recall 만(Codex §16-21 리뷰 #1)
    pending: list[tuple[int, str, int, int, str | None]] = []  # (레코드 번호, 경로, 처음, 끝, winnow 키)
    turn = 0
    for i, r in enumerate(recs):
        if _is_prompt(r):
            turn = i
        att = r.get("attachment")
        if isinstance(att, dict) and att.get("type") == "read_truncation_notice":
            m = PARTIAL_RX.search(att.get("banner", ""))
            if m and int(m.group(3)) < int(m.group(4)):
                pending.append((i, norm(m.group(1)), int(m.group(3)) + 1, int(m.group(4)), None))
            continue
        msg = r.get("message") if isinstance(r.get("message"), dict) else {}
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        for c in content:
            if not isinstance(c, dict):
                continue
            if r.get("type") == "assistant" and c.get("type") == "tool_use":
                inp = c.get("input") or {}
                if c.get("name") == "Read" and inp.get("file_path"):
                    reads[c.get("id")] = (norm(inp["file_path"]), inp.get("offset") is not None or inp.get("limit") is not None)
                elif str(c.get("name", "")).endswith("winnow_recall") and inp.get("key"):
                    recall_req[c.get("id")] = (str(inp["key"]), inp.get("start"), inp.get("end"))
            elif r.get("type") == "user" and c.get("type") == "tool_result" and c.get("tool_use_id") in recall_req:
                # 요청만으로는 복구가 아니다 — 오류가 아니고 본문이 돌아온 결과만(캐시 없음·실패는 복구 아님)
                body = _text(c.get("content")).strip()
                if not c.get("is_error") and body and not RECALL_MISS_RX.search(body[:300]):
                    recalls.append(recall_req[c["tool_use_id"]])
            elif r.get("type") == "user" and c.get("type") == "tool_result" and c.get("tool_use_id") in reads:
                if c.get("is_error"):
                    continue
                path, ranged = reads[c["tool_use_id"]]
                t = _text(c.get("content"))
                covered.setdefault(path, set()).update(returned_lines(t))
                if not ranged:
                    for m in WINNOW_RX.finditer(t):
                        pending.append((i, path, int(m.group(1)), int(m.group(2)), m.group(3)))
    out: dict[str, list[tuple[int, int]]] = {}
    for i, path, a, b, key in pending:
        if i < turn:
            continue
        miss = set(range(a, b + 1)) - covered.get(path, set())
        for k, s, e in recalls:
            if k == key:
                miss -= set(range(int(s or a), int(e or b) + 1))
        if miss:
            out.setdefault(path, []).extend(_spans(miss))
    return out


def _spans(nums: set[int]) -> list[tuple[int, int]]:
    out: list[list[int]] = []
    for n in sorted(nums):
        if out and n == out[-1][1] + 1:
            out[-1][1] = n
        else:
            out.append([n, n])
    return [(a, b) for a, b in out]


def main() -> int:
    try:
        data = json.loads(sys.stdin.buffer.read().decode("utf-8", "replace") or "{}")
    except json.JSONDecodeError:
        return 0
    if data.get("stop_hook_active"):
        return 0
    recs = records(data.get("transcript_path"))
    text = data.get("last_assistant_message") or ""
    if not text:
        for r in reversed(recs):
            if r.get("type") == "assistant" and isinstance((r.get("message") or {}).get("content"), list):
                text = "\n".join(c.get("text", "") for c in r["message"]["content"] if isinstance(c, dict) and c.get("type") == "text")
                if text:
                    break
    g = gaps(recs)
    if not g or STATED_RX.search(text):
        return 0
    ack = ACK_DIR / (re.sub(r"[^\w.-]", "_", str(data.get("session_id") or data.get("transcript_path") or "x"))[-120:] + ".json")
    try:
        done = set(json.loads(ack.read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError):
        done = set()
    new = {p: s for p, s in g.items() if p not in done}
    if not new:
        return 0
    try:
        ACK_DIR.mkdir(parents=True, exist_ok=True)
        ack.write_text(json.dumps(sorted(done | set(new)), ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass
    lines = [f"{p}: 빠진 행 " + ", ".join(f"{a}-{b}" for a, b in s[:5]) + (" …" if len(s) > 5 else "") for p, s in new.items()]
    reason = ("[read-range] 이번 턴에 끝까지 오지 않은 Read 가 있습니다(Read 토큰 상한 잘림·winnow 숨김):\n- " + "\n- ".join(lines)
              + "\n나머지를 offset 으로 이어 읽거나 winnow_recall 로 되살리세요. 읽지 않고 답하려면 응답에 «읽은 범위»를 밝히세요"
              "(파일마다 세션당 한 번만 막습니다).")
    sys.stdout.buffer.write(json.dumps({"decision": "block", "reason": reason}, ensure_ascii=False).encode("utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
