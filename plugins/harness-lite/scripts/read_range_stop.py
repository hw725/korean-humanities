#!/usr/bin/env python3
"""읽은 범위 Stop 훅 — 잘리거나 가려진 Read 를 복구하지 않고 답하면 《읽은 범위》를 밝히게 한다. 설계: DESIGN-harness-v2 §5-2

이번 턴(마지막 사용자 프롬프트 뒤)의 Read 에서 아래 둘을 찾는다.
  - Read 토큰 상한 잘림: transcript 의 `read_truncation_notice` 첨부(《PARTIAL view — <경로>: showing lines a-b of N》)
  - winnow 플러그인 숨김: Read 결과 속 《[winnow] Lines a-b (… lines) hidden … key <키>》
빠진 행이 《이번 턴》의 다른 정상 Read 로 돌아왔거나, 이번 턴에 같은 키의 winnow_recall 이 《실제로 돌려준》 행이면 복구로 본다
(리뷰 ③ R-6·R-7 — 요청한 범위가 아니라 돌아온 행만, 옛 턴의 Read 는 파일이 바뀌었을 수 있어 세지 않는다).
recall 결과는 실측 형식(2026-10-11 이 PC transcript 6건) `{"result":"winnow recall <키> (Read: <경로>)\\n<본문>"}` 이고 본문에
행 번호가 없다 — 머리 줄 뒤 본문 줄 수만큼 start 부터 센다. 본문에 《행번호\\t》·《행번호→》가 있으면 그 번호를 쓴다.
복구되지 않은 구간이 있는데 응답이 《읽은 범위》와 행 범위 숫자(예: 1-120)를 함께 밝히지 않으면 막는다. 밝힌 구간은
(경로, 구간) 단위로 기억해 다시 묻지 않는다(리뷰 ③ R-8). 재응답(stop_hook_active)도 같은 미충족이면 막고, 같은 사유로
세 번 막힌 뒤에만 systemMessage 로 《검증 없이 완료 주장》과 사유를 남기고 통과시킨다(리뷰 ③ R-1).
일부러 offset·limit 을 준 Read 는 보지 않는다 — 부분 읽기를 스스로 고른 것이라 매번 막으면 마찰만 커진다.
한계: Grep 만 보고 답한 경우, 읽었지만 건너뛴 경우는 못 잡는다. 하네스 모듈에 의존하지 않는다(수강생판에 그대로 들어간다).
"""
from __future__ import annotations

import hashlib
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
# Read 결과의 행 번호. transcript 에는 《12\t내용》으로, 화면에는 《    12→내용》으로 남는다. winnow 표지 줄은 행이 아니다.
LINE_RX = re.compile(r"^\s*(\d+)(?:→|\t)(?!\[winnow\] )", re.M)
PARTIAL_RX = re.compile(r"PARTIAL view — (.+?): showing lines (\d+)-(\d+) of (\d+) total")
WINNOW_RX = re.compile(r"\[winnow\] Lines (\d+)-(\d+) \(\d+ lines\) hidden(?:.|\n){0,600}?cached as key ([0-9a-f]+)")
STATED_RX = re.compile(r"읽은\s*범위")
# 고지 = 《읽은 범위》와 행 범위 숫자(1-120, 1～120, 1~120, 1–120)가 한 줄 안에 가까이(80자) 있을 것
RANGE = r"\d+\s*[-～~–]\s*\d+"
STATED_RANGE_RX = re.compile(rf"읽은\s*범위[^\n]{{0,80}}?{RANGE}|{RANGE}[^\n]{{0,80}}?읽은\s*범위")
RECALL_MISS_RX = re.compile(r"no (?:cached|such)|not found|unknown key|expired|error", re.I)
RECALL_HEAD_RX = re.compile(r"^\s*winnow recall ([0-9a-f]+)\b[^\n]*(?:\n|$)")
MAX_BLOCKS = 3
EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
FENCE = re.compile(r"```.*?```", re.S)


def turn_key(recs: list[dict]) -> str:
    """이번 턴(마지막 사용자 프롬프트)의 식별 — 고지 기억은 턴마다 따로 한다(리뷰 ⑤ p2 R-9)."""
    last = None
    for i, r in enumerate(recs):
        if _is_prompt(r):
            last = (i, r)
    if last is None:
        return "t0"
    i, r = last
    return str(r.get("uuid") or r.get("timestamp") or i)


def stated_for(text: str, paths: list[str]) -> bool:
    """《읽은 범위》와 행 범위 숫자를 밝혔는가. 코드 블록 속 문구는 고지가 아니고, 빠진 파일이 둘 이상이면 파일마다 이름을 적어야 한다
    — 한 줄 고지가 모든 파일의 누락을 면제하던 것(리뷰 ⑤ p2 R-7)."""
    t = FENCE.sub("", text or "")
    if not STATED_RANGE_RX.search(t):
        return False
    if len(paths) <= 1:
        return True
    low = t.lower()
    return all(os.path.basename(p).lower() in low for p in paths)


def norm(p: str) -> str:
    return os.path.normcase(os.path.abspath(str(p).strip().strip("\"'")))


def records(path: str | None) -> list[dict]:
    if not isinstance(path, str) or not path or not Path(path).exists():
        return []
    out = []
    for ln in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            rec = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if isinstance(rec, dict):  # 객체가 아닌 줄은 기록이 아니다(입력 모양 표)
            out.append(rec)
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
        return not c.startswith("<")  # 명령 출력·시스템 알림(《<command-…》, 《<task-notification…》)은 프롬프트가 아니다
    return isinstance(c, list) and any(isinstance(x, dict) and x.get("type") == "text" for x in c) \
        and not any(isinstance(x, dict) and x.get("type") == "tool_result" for x in c)


def recalled_lines(text: str, start, end) -> set[int]:
    """winnow_recall 결과가 《실제로》 돌려준 행(리뷰 ③ R-6). 행 번호가 있으면 그것을, 없으면 실측 머리 줄
    《winnow recall <키> (…)》 뒤 본문 줄 수만큼 start 부터 센다(end 를 넘지 않게). 머리 줄도 행 번호도 없으면 빈 집합."""
    t = text or ""
    s = t.strip()
    if s.startswith("{"):
        try:
            obj = json.loads(s)
        except ValueError:
            obj = None
        if isinstance(obj, dict) and isinstance(obj.get("result"), str):
            t = obj["result"]
    nums = returned_lines(t)
    if nums:
        return nums
    m = RECALL_HEAD_RX.match(t)
    if not m or start is None:
        return set()
    body = t[m.end():].split("\n")
    while body and body[-1] == "":
        body.pop()
    if not body:
        return set()
    a = int(start)
    b = a + len(body) - 1
    if end is not None:
        b = min(b, int(end))
    return set(range(a, b + 1))


def gaps(recs: list[dict]) -> dict[str, list[tuple[int, int]]]:
    """이번 턴에 생긴, 복구되지 않은 빠진 구간 {파일: [(처음, 끝), …]}. 복구 증거도 이번 턴의 것만 센다(리뷰 ③ R-7)."""
    reads: dict[str, tuple[str, bool]] = {}   # tool_use_id → (경로, offset·limit 지정 여부)
    covered: list[tuple[int, str, set[int]]] = []  # (레코드 번호, 경로, 돌아온 행)
    recall_req: dict[str, tuple[str, int | None, int | None]] = {}  # tool_use_id → (키, 처음, 끝)
    # 결과가 정상으로 돌아온 recall 만(Codex §16-21 리뷰 #1): (레코드 번호, 키, 처음, 끝, 결과 글)
    recalls: list[tuple[int, str, int | None, int | None, str]] = []
    pending: list[tuple[int, str, int, int, str | None]] = []  # (레코드 번호, 경로, 처음, 끝, winnow 키)
    edits: dict[str, list[int]] = {}  # 경로 → 그 파일을 고친 도구 호출 위치 — 고치기 전 판의 행은 새 판의 복구가 아니다(리뷰 ⑤ p2 R-8)
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
                elif c.get("name") in EDIT_TOOLS and (inp.get("file_path") or inp.get("notebook_path")):
                    edits.setdefault(norm(inp.get("file_path") or inp.get("notebook_path")), []).append(i)
                elif str(c.get("name", "")).endswith("winnow_recall") and inp.get("key"):
                    recall_req[c.get("id")] = (str(inp["key"]), inp.get("start"), inp.get("end"))
            elif r.get("type") == "user" and c.get("type") == "tool_result" and c.get("tool_use_id") in recall_req:
                # 요청만으로는 복구가 아니다 — 오류가 아니고 본문이 돌아온 결과만(캐시 없음·실패는 복구 아님)
                body = _text(c.get("content"))
                if not c.get("is_error") and body.strip() and not RECALL_MISS_RX.search(body.strip()[:300]):
                    k, s, e = recall_req[c["tool_use_id"]]
                    recalls.append((i, k, s, e, body))
            elif r.get("type") == "user" and c.get("type") == "tool_result" and c.get("tool_use_id") in reads:
                if c.get("is_error"):
                    continue
                path, ranged = reads[c["tool_use_id"]]
                t = _text(c.get("content"))
                covered.append((i, path, returned_lines(t)))
                if not ranged:
                    for m in WINNOW_RX.finditer(t):
                        pending.append((i, path, int(m.group(1)), int(m.group(2)), m.group(3)))
    def same_version(path: str, x: int, y: int) -> bool:
        lo, hi = min(x, y), max(x, y)
        return not any(lo < e < hi for e in edits.get(path, []))

    out: dict[str, list[tuple[int, int]]] = {}
    for i, path, a, b, key in pending:
        if i < turn:
            continue
        # 옛 턴의 행 번호는 지금 파일 내용의 증거가 아니다(R-7). 같은 턴이라도 사이에 그 파일을 고쳤으면 다른 판이다(⑤ p2 R-8)
        now: set[int] = set()
        for j, p2, got in covered:
            if p2 == path and j >= turn and same_version(path, i, j):
                now |= got
        miss = set(range(a, b + 1)) - now
        for j, k, s, e, body in recalls:
            if k == key and j >= turn and same_version(path, i, j):
                miss -= recalled_lines(body, s if s is not None else a, e if e is not None else b)
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
        data = data if isinstance(data, dict) else {}  # 객체가 아닌 JSON 에 Traceback 으로 죽지 않게
    except json.JSONDecodeError:
        return 0
    retry = bool(data.get("stop_hook_active"))
    recs = records(data.get("transcript_path"))
    text = data.get("last_assistant_message") or ""
    if not text:
        for r in reversed(recs):
            if r.get("type") == "assistant" and isinstance((r.get("message") or {}).get("content"), list):
                text = "\n".join(c.get("text", "") for c in r["message"]["content"] if isinstance(c, dict) and c.get("type") == "text")
                if text:
                    break
    g = gaps(recs)
    if not g:
        return 0
    sess = re.sub(r"[^\w.-]", "_", str(data.get("session_id") or data.get("transcript_path") or "x"))[-120:]
    ack = ACK_DIR / (sess + ".json")
    try:
        done = {x for x in json.loads(ack.read_text(encoding="utf-8")) if isinstance(x, str)}
    except (OSError, ValueError, TypeError):
        done = set()
    # (경로, 빠진 구간, 턴) 단위 — 파일 하나를 한 번 밝혔다고 그 파일의 다른 구간까지(R-8), 앞 턴의 고지가 새 턴의 누락까지
    # (⑤ p2 R-9) 면제하지 않는다
    tk = turn_key(recs)
    new = {p: [(a, b) for a, b in s if f"{p}|{a}-{b}|{tk}" not in done] for p, s in g.items()}
    new = {p: s for p, s in new.items() if s}
    if not new:
        return 0
    if stated_for(text, list(new)):  # 범위 숫자와 함께(파일이 여럿이면 파일마다) 밝혔을 때만 고지로 인정하고, 그 구간을 기억한다
        try:
            ACK_DIR.mkdir(parents=True, exist_ok=True)
            keys = {f"{p}|{a}-{b}|{tk}" for p, s in new.items() for a, b in s}
            ack.write_text(json.dumps(sorted(done | keys), ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass
        return 0
    lines = [f"{p}: 빠진 행 " + ", ".join(f"{a}-{b}" for a, b in s[:5]) + (" …" if len(s) > 5 else "") for p, s in new.items()]
    n = bump_blocks(ACK_DIR / (sess + ".blocks.json"), "\n".join(lines), retry)
    if n > MAX_BLOCKS:
        msg = (f"[read-range] 같은 사유로 {MAX_BLOCKS}번 막혔습니다 — 검증 없이 완료 주장 — 사유: 끝까지 읽지 않은 Read\n- "
               + "\n- ".join(lines))
        sys.stdout.buffer.write(json.dumps({"systemMessage": msg}, ensure_ascii=False).encode("utf-8"))
        return 0
    reason = ("[read-range] 이번 턴에 끝까지 오지 않은 Read 가 있습니다(Read 토큰 상한 잘림·winnow 숨김):\n- " + "\n- ".join(lines)
              + "\n나머지를 offset 으로 이어 읽거나 winnow_recall 로 되살리세요. 읽지 않고 답하려면 응답에 《읽은 범위》와 실제로 읽은 "
              "행 범위(예: 《읽은 범위: 1-264행》)를 밝히세요.")
    sys.stdout.buffer.write(json.dumps({"decision": "block", "reason": reason}, ensure_ascii=False).encode("utf-8"))
    return 0


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


if __name__ == "__main__":
    sys.exit(main())
