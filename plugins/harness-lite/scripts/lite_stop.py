"""수강생판 Stop 훅 — «완료했다»를 상태로 확인한다. 문장이 아니라 영수증을 본다.

응답이 완료를 말하고, 이번 세션이 계약 폴더 안을 고쳤으면 아래가 모두 맞아야 통과한다.
  1) 마지막 편집 뒤에 `harness.py verify` 가 만든 영수증이 있다(이 세션 transcript 에 찍힌 것)
  2) 영수증 뒤로 계약과 소스(watch)가 바뀌지 않았다
  3) 실패가 있으면 응답에 «실패 N건»과 조건 ID, 사람 판정 대기가 있으면 «사람 판정 대기 N건», 경고가 있으면 «경고 N건»
  4) 캡처가 있으면 영수증 뒤에 전부 Read 로 열었다
계약이 없는 폴더를 고치고 완료를 말하면 세션에 한 번 계약 만들기를 권한다(막는 것은 그 한 번뿐).
한 번 막힌 뒤의 재응답(stop_hook_active)은 막지 않는다 — 끝없이 막히지 않게.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lite_common as lc  # noqa: E402

for _stream in (sys.stdout, sys.stderr):  # CJK 계약 E3
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass
ACK_DIR = Path(os.environ.get("HARNESS_LITE_ACK_DIR") or Path.home() / ".claude" / "harness-lite" / "ack")
EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
SHELL_WRITE_RX = re.compile(r"(?<![<>=-])>{1,2}(?!&)|\bsed\s+-i|\btee\b|Set-Content|Add-Content|Out-File|Copy-Item|Move-Item"
                            r"|New-Item|\b(mv|cp|touch|patch)\b|git\s+(apply|checkout|restore|reset|stash)", re.I)
# 완료 주장 판정 — 전체판(harness_stop.py)과 같은 정규식(시험이 같은지 본다)
CLAIM_RX = re.compile(r"(완료(했|됐|되었|입니다|합니다|하였)|작업\s*완료|끝났|끝냈|마쳤|마무리했|다 만들었|모두 처리했|"
                      r"전부 처리했|처리를 마|산출(을|이)?\s*(끝|마)|\bdone\b|\bfinished\b)", re.I)
NOT_CLAIM = re.compile(r"(완료|끝|마치|마무리)\w{0,4}\s*(않|못)|아직\s*\w{0,3}\s*(완료|끝|마치|마무리)"
                       r"|(완료|끝|마치|마무리)\w{0,3}\s*(전에|예정|하려면|하면|후에|하겠|할\s*것)")
FENCE = re.compile(r"```.*?```", re.S)
INLINE = re.compile(r"`[^`\n]*`|«[^»\n]*»|\"[^\"\n]*\"|“[^”\n]*”")
RECEIPT_RX = re.compile(re.escape(lc.RECEIPT_MARK) + r"(.+?receipt\.json)")
VERIFY_CMD_RX = re.compile(r"harness\.py[\"']?\s+(?:--root\s+\S+\s+)?verify\b")
CD_RX = re.compile(r"^(?:cd|Set-Location|pushd)\s+(\"[^\"]+\"|'[^']+'|\S+)\s*$", re.I)


def prose(text: str) -> str:
    text = FENCE.sub("", text)
    lines = [ln for ln in text.splitlines() if not ln.lstrip().startswith(("|", ">"))]
    return INLINE.sub("", "\n".join(lines))


def claims_done(text: str) -> bool:
    return any(CLAIM_RX.search(s) and not NOT_CLAIM.search(s) for s in re.split(r"(?<=[.!?。])\s+|\n", prose(text)))


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


def _norm(p) -> str:
    return os.path.normcase(os.path.abspath(str(p).strip().strip("\"'")))


def scan(recs: list[dict], cwd: Path):
    """(계약별 마지막 편집 위치, 영수증 [(위치, 경로)], 정상 Read [(위치, 경로)], 계약 없는 편집 여부, 마지막 응답)."""
    uses, last_edit, receipts, reads = {}, {}, [], []
    loose_edit, last_text = False, ""
    for i, r in enumerate(recs):
        msg = r.get("message") if isinstance(r.get("message"), dict) else {}
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        if r.get("type") == "assistant":
            t = "\n".join(c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text")
            if t:
                last_text = t
            for c in content:
                if isinstance(c, dict) and c.get("type") == "tool_use":
                    uses[c.get("id")] = (c.get("name"), c.get("input") or {})
            continue
        for c in content:
            if not isinstance(c, dict) or c.get("type") != "tool_result" or c.get("tool_use_id") not in uses:
                continue
            name, inp = uses[c["tool_use_id"]]
            if c.get("is_error"):
                continue
            if name == "Read" and inp.get("file_path"):
                reads.append((i, _norm(inp["file_path"])))
            fp = inp.get("file_path") or inp.get("notebook_path")
            if name in EDIT_TOOLS and fp:
                cp = lc.find_contract(Path(fp).resolve().parent)
                if cp:
                    last_edit[_norm(cp)] = i
                else:
                    loose_edit = True
            cmd = inp.get("command") if name in ("Bash", "PowerShell") else None
            if isinstance(cmd, str):
                out = _text(c.get("content"))
                if VERIFY_CMD_RX.search(cmd):  # 영수증은 verify 를 부른 명령의 결과에 찍힌 것만(Codex §16-21 리뷰 #5)
                    for p in RECEIPT_RX.findall(out):
                        receipts.append((i, p.strip()))
                for cp in shell_edit_contracts(cmd, cwd):
                    if cp is None:
                        loose_edit = True
                    else:
                        last_edit[_norm(cp)] = i
    return last_edit, receipts, reads, loose_edit, last_text


def shell_edit_contracts(cmd: str, cwd: Path) -> list[Path | None]:
    """셸 명령이 고친 계약 폴더들(Codex §16-21 리뷰 #6). 구간마다 `cd` 를 따라가며, 쓰는 구간의 경로 인수가 속한 계약을 찾는다.
    경로 인수가 없으면 그때의 작업 폴더 계약으로 보고, 계약을 찾지 못하면 None(계약 없는 편집). verify 호출 구간 자체는 편집이 아니다."""
    out: list[Path | None] = []
    base = Path(cwd)
    for seg in re.split(r"&&|\|\||[;\n|]", cmd):
        s = seg.strip()
        m = CD_RX.match(s)
        if m:
            t = Path(m.group(1).strip("\"'"))
            base = (t if t.is_absolute() else base / t)
            continue
        if not SHELL_WRITE_RX.search(s) or VERIFY_CMD_RX.search(s):
            continue
        hits = []
        for tok in re.findall(r"\"([^\"]+)\"|'([^']+)'|(\S+)", s):
            t = next(x for x in tok if x).lstrip(">")
            if not t or t.startswith("-") or not re.search(r"[/\\.]", t):
                continue
            p = Path(t) if Path(t).is_absolute() else base / t
            cp = lc.find_contract(p.parent if not p.is_dir() else p)
            if cp:
                hits.append(cp)
        out += hits or [lc.find_contract(base)]
    return out


def _ack_file(data: dict) -> Path:
    return ACK_DIR / (re.sub(r"[^\w.-]", "_", str(data.get("session_id") or data.get("transcript_path") or "x"))[-120:] + ".json")


def problems(cp: Path, edit_at: int, receipts, reads, text: str, acked: set[str]) -> tuple[list[str], str | None]:
    root = cp.parent
    mine = [(i, p) for i, p in receipts if i > edit_at and lc.find_contract(Path(p).parent) and
            _norm(lc.find_contract(Path(p).parent)) == _norm(cp)]
    if not mine:
        return [f"{root} 를 고친 뒤 완료 조건을 확인하지 않았습니다 — 실행: {lc.cli_command('verify')}"], None
    at, rp = max(mine)
    try:
        r = lc.load(Path(rp))
        c = lc.load(cp)
    except (OSError, ValueError) as e:
        return [f"영수증·계약을 읽을 수 없습니다({e}) — 다시 verify 하세요"], None
    bad = []
    # 이 프로젝트의 verify 가 제자리에 남긴 영수증인가 — 다른 프로젝트 영수증을 복사해 오면 안 된다(Codex §16-21 리뷰 #5)
    home = (root / ".harness" / "lite").resolve()
    if r.get("v") != lc.LITE_V or _norm(r.get("root", "")) != _norm(root) or Path(rp).resolve().parent.parent != home:
        return [f"영수증 {rp} 는 이 프로젝트({root})의 verify 가 남긴 것이 아닙니다 — 다시 verify 하세요"], None
    if r.get("contract_hash") != lc.contract_hash(c):
        bad.append("영수증 뒤 계약이 바뀌었습니다 — 다시 verify 하세요")
    elif r.get("source_fp", {}).get("digest") != lc.source_fp(root, c.get("watch") or [])["digest"]:
        bad.append("영수증 뒤 소스가 바뀌었습니다 — 다시 verify 하세요")
    for p in r.get("problems") or []:
        bad.append(f"영수증 문제: {p}")
    # 사람 판정 대기열·캡처가 영수증 뒤에 바뀌었으면 그 영수증의 건수·열람은 지금 것이 아니다(Codex §16-21 리뷰 #4)
    for x in r.get("results") or []:
        if x.get("queue_sha"):
            try:
                cur = hashlib.sha256(Path(x["queue"]).read_bytes()).hexdigest()
            except OSError:
                cur = None
            if cur != x["queue_sha"]:
                bad.append(f"{x.get('id')}: 사람 판정 대기열이 영수증 뒤 바뀌었습니다 — 다시 verify 하세요")
    for cap in r.get("captures") or []:
        try:
            same = lc.file_sha(Path(cap["path"])) == cap.get("sha")
        except OSError:
            same = False
        if not same:
            bad.append(f"캡처 {cap['path']} 가 영수증 뒤 바뀌거나 사라졌습니다 — 다시 verify 하세요")
    unread = [cap["path"] for cap in r.get("captures") or [] if not any(j > at and q == _norm(cap["path"]) for j, q in reads)]
    if unread:
        bad.append(f"캡처 {len(unread)}장을 열어 보지 않았습니다(완료 전에 Read 로 전부 여세요): {unread[:3]}")
    key = hashlib.sha256(Path(rp).read_bytes()).hexdigest()[:16]
    if key not in acked:
        failed = r.get("failed") or []
        if failed and not (re.search(rf"실패\s*{len(failed)}\s*건", text) and all(f in text for f in failed)):
            bad.append(f"완료 조건 실패 {len(failed)}건({', '.join(failed)})입니다 — 고치거나, 고치지 못했으면 «완료하지 못했다»와 "
                       f"«실패 {len(failed)}건»·조건 ID를 적으세요.")
        hp = int(r.get("human_pending") or 0)
        if hp and not re.search(rf"사람\s*판정\s*대기\s*{hp}\s*건", text):
            bad.append(f"사람 판정 대기 {hp}건입니다 — 응답에 «사람 판정 대기 {hp}건»을 적으세요(통과로 세지 않습니다).")
        w = int(r.get("warnings") or 0)
        if w and not re.search(rf"경고\s*{w}\s*건", text):
            bad.append(f"경고 {w}건입니다 — 응답에 «경고 {w}건»과 내용을 적으세요.")
    return bad, key


def main() -> int:
    try:
        data = json.loads(sys.stdin.buffer.read().decode("utf-8", "replace") or "{}")
    except json.JSONDecodeError:
        return 0
    if data.get("stop_hook_active"):
        return 0
    recs = records(data.get("transcript_path"))
    cwd = Path(data.get("cwd") or os.getcwd())
    last_edit, receipts, reads, loose, last = scan(recs, cwd)
    text = data.get("last_assistant_message") or last
    if not text or not claims_done(text):
        return 0
    af = _ack_file(data)
    try:
        st = json.loads(af.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        st = {}
    acked = set(st.get("receipts", []))
    bad, keys = [], []
    for cpn, at in last_edit.items():
        b, k = problems(Path(cpn), at, receipts, reads, text, acked)
        bad += b
        if k:
            keys.append(k)
    if not last_edit and loose and not st.get("hinted"):
        st["hinted"] = True
        bad.append("완료 조건 계약이 없는 폴더를 고쳤습니다. «끝났다»를 확인할 기준을 만들어 두면 다음부터 영수증으로 확인합니다: "
                   f"{lc.cli_command('init')} (이번 한 번만 알립니다 — 필요 없으면 그 사유를 밝히고 끝내세요)")
    if not bad:
        st["receipts"] = sorted(acked | set(keys))
    try:
        ACK_DIR.mkdir(parents=True, exist_ok=True)
        af.write_text(json.dumps(st, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass
    if bad:
        sys.stdout.buffer.write(json.dumps({"decision": "block", "reason": "[harness-lite] 완료 확인이 끝나지 않았습니다:\n- "
                                            + "\n- ".join(bad)}, ensure_ascii=False).encode("utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
