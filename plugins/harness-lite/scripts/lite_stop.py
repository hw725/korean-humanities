"""수강생판 Stop 훅 — «완료했다»를 상태로 확인한다. 문장이 아니라 영수증을 본다.

응답이 완료를 말하고, 이번 세션이 계약 폴더 안을 고쳤으면 아래가 모두 맞아야 통과한다.
  1) 마지막 편집 뒤에 `harness.py verify` 가 만든 영수증이 있다(이 세션 transcript 에 찍힌 것)
  2) 영수증 뒤로 계약과 소스(watch)가 바뀌지 않았다
  3) 실패나 사람 판정 대기가 남아 있지 않다 — 남아 있으면 «완료» 주장은 막고, «완료하지 못했다»·«미완료» 보고만 통과한다
     (리뷰 ③ R-2: 건수 문구만 적으면 실패를 두고 «완료»가 통과했다). 경고가 있으면 응답에 «경고 N건»
  4) 캡처가 있으면 영수증 뒤에 전부 Read 로 열었다
계약이 없는 폴더를 고치고 완료를 말하면 세션에 한 번 계약 만들기를 권한다(막는 것은 그 한 번뿐).
한 번 막힌 뒤의 재응답(stop_hook_active)도 같은 미충족이면 다시 막는다. 끝없이 막히지 않게 같은 사유로 세 번 막힌 뒤에만
통과시키고, 그때는 사용자에게 보이는 systemMessage 로 «검증 없이 완료 주장»과 사유를 남긴다(리뷰 ③ R-1, 전체판 v2 와 같다).
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
# git 은 하위 명령 앞 전역 옵션(--no-pager·-P·-C 경로…)을 건너뛰고 본다. 작업 트리를 바꾸는 하위 명령은 모두 편집이다
# — rm·switch·clean 이 빠져 «git rm -f»로 계약 폴더를 바꾸고 verify 없이 «완료»가 통과했다(전수 S-20261011-175508-48d241 F3)
SHELL_WRITE_RX = re.compile(r"(?<![<>=-])>{1,2}(?!&)|\bsed\s+-i|\btee\b|Set-Content|Add-Content|Out-File|Copy-Item|Move-Item"
                            r"|New-Item|\b(mv|cp|touch|patch)\b"
                            r"|\bgit(?:\s+-[CcP](?:\s+\S+)?|\s+--[\w-]+(?:=\S+|\s+[^-\s]\S*)?)*\s+(apply|checkout|checkout-index|restore|reset|"
                            r"stash|rm|switch|clean|read-tree|am|cherry-pick|merge|rebase|pull|revert)\b", re.I)
# 완료 주장 판정 — 전체판(harness_stop.py)과 같은 정규식(시험이 같은지 본다)
CLAIM_RX = re.compile(r"((?<!미)완료(했|됐|되었|입니다|합니다|하였)|작업\s*완료|끝났|끝냈|마쳤|마무리했|다 만들었|모두 처리했|"
                      r"전부 처리했|처리를 마|산출(을|이)?\s*(끝|마)|\bdone\b|\bfinished\b)", re.I)
NOT_CLAIM = re.compile(r"(완료|끝|마치|마무리)\w{0,4}\s*(않|못)|아직\s*\w{0,3}\s*(완료|끝|마치|마무리)"
                       r"|(완료|끝|마치|마무리)\w{0,3}\s*(전에|예정|하려면|하면|후에|하겠|할\s*것)")
# 절 나누기 — 한 문장 안의 미완료 표현이 다른 절의 완료 주장까지 지우지 않게(리뷰 ③ R-14). 전체판과 같은 정규식
CLAUSE_RX = re.compile(r"[,，、;；]|(?<=지만)\s|(?<=는데)\s|(?<=며)\s")
FENCE = re.compile(r"```.*?```", re.S)
INLINE = re.compile(r"`[^`\n]*`|«[^»\n]*»|\"[^\"\n]*\"|“[^”\n]*”")
MAX_BLOCKS = 3
RECEIPT_RX = re.compile(re.escape(lc.RECEIPT_MARK) + r"(.+?receipt\.json)")
VERIFY_CMD_RX = re.compile(r"harness\.py[\"']?\s+(?:--root\s+\S+\s+)?verify\b")
ROOT_RX = re.compile(r"--root\s+(\"[^\"]+\"|'[^']+'|\S+)")
CD_RX = re.compile(r"^(?:cd|Set-Location|pushd)\s+(\"[^\"]+\"|'[^']+'|\S+)\s*$", re.I)


def prose(text: str) -> str:
    """표 칸의 완료 주장도 주장이다 — 표 행은 남기고 칸 구분(|)만 지운다(리뷰 ⑤ p2 R-2, 전체판과 같다)."""
    text = FENCE.sub("", text)
    lines = [ln.replace("|", " ") for ln in text.splitlines() if not ln.lstrip().startswith(">")]
    return INLINE.sub("", "\n".join(lines))


def claims_done(text: str) -> bool:
    return any(CLAIM_RX.search(c) and not NOT_CLAIM.search(c)
               for s in re.split(r"(?<=[.!?。])\s+|\n", prose(text)) for c in CLAUSE_RX.split(s))


def bump_blocks(f: Path, reason: str, retry: bool) -> int:
    """같은 사유로 막힌 횟수(세션 파일 f 안에 사유별로). 새 응답(재응답이 아님)이면 1부터 다시 센다 — 전체판 _bump_blocks 와 같다."""
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
                if runs_verify(cmd):  # 영수증은 verify 를 «실행한» 명령의 결과에 찍힌 것만(Codex §16-21 리뷰 #5, 리뷰 ⑤ p4 R-1)
                    found = RECEIPT_RX.findall(out)
                    for p in found:
                        receipts.append((i, p.strip()))
                    if not found:
                        # 출력을 잘라 읽으면(| tail·출력 압축기) 영수증 줄이 없다 — 그 계약의 디스크 영수증으로 대신한다(수강생 시험 c-1)
                        vcp = verify_contract(cmd, cwd)
                        rp = disk_receipt(vcp) if vcp else None
                        if rp:
                            receipts.append((i, rp))
                for cp in shell_edit_contracts(cmd, cwd):
                    if cp is None:
                        loose_edit = True
                    else:
                        last_edit[_norm(cp)] = i
    return last_edit, receipts, reads, loose_edit, last_text


ECHO_WORDS = {"echo", "printf", "write-host", "write-output", "cat", "type", "print"}


def _runs_verify_seg(s: str) -> bool:
    if not VERIFY_CMD_RX.search(s):
        return False
    first = re.split(r"\s+", s, maxsplit=1)[0].strip("\"'").lower()
    return re.split(r"[/\\]", first)[-1] not in ECHO_WORDS


def runs_verify(cmd: str) -> bool:
    """명령이 harness.py verify 를 «실행»하는가 — 그 낱말을 출력(echo 등)하기만 하는 구간은 아니다(리뷰 ⑤ p4 R-1)."""
    return any(_runs_verify_seg(seg.strip()) for seg in re.split(r"&&|\|\||[;\n|]", cmd))


def verify_contract(cmd: str, cwd: Path) -> Path | None:
    """verify 를 실행한 구간이 겨눈 계약 — `--root` 가 있으면 그 폴더, 없으면 `cd` 를 따라간 작업 폴더에서 찾는다."""
    base = Path(cwd)
    for seg in re.split(r"&&|\|\||[;\n|]", cmd):
        s = seg.strip()
        m = CD_RX.match(s)
        if m:
            t = Path(m.group(1).strip("\"'"))
            base = t if t.is_absolute() else base / t
        elif _runs_verify_seg(s):
            r = ROOT_RX.search(s)
            if r:
                t = Path(r.group(1).strip("\"'"))
                base = t if t.is_absolute() else base / t
            return lc.find_contract(base)
    return None


def disk_receipt(cp: Path) -> str | None:
    """이 계약의 영수증 가운데 봉인이 맞고(손대지 않음) 지금 계약 해시·소스 지문과 같은 가장 새 것의 경로(수강생 시험 c-1).

    전체판 harness_stop._shared_receipt 와 같은 생각이다 — 판정 기준은 «무엇을 검증했나»(계약·소스)다. 수강생판에는 원장이 없어
    봉인(lite_common.seal)으로 손 편집을 알아보고, 보관소(.harness/lite) 쓰기는 PreToolUse 가 막는다(위조 방지는 아니다).
    영수증 «뒤» 편집은 이 경로와 상관없이 막힌다 — 대신하는 영수증의 위치는 verify 를 돌린 그 자리다."""
    try:
        c = lc.load(cp)
    except (OSError, ValueError):
        return None
    want_c, want_fp = lc.contract_hash(c), None
    for rp in sorted((Path(cp).parent / ".harness" / "lite").glob("*/receipt.json"), reverse=True):
        try:
            r = lc.load(rp)
        except (OSError, ValueError):
            continue
        if not isinstance(r, dict) or r.get("seal") != lc.seal(r) or r.get("contract_hash") != want_c:
            continue
        if want_fp is None:
            want_fp = lc.source_fp(Path(cp).parent, c.get("watch") or [])["digest"]
        if (r.get("source_fp") or {}).get("digest") == want_fp:
            return str(rp)
    return None


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
        # verify 를 실행만 하는 구간은 편집이 아니지만, verify 낱말이 들었다고 쓰기 구간을 빼지는 않는다(리뷰 ⑤ p4 R-2)
        if not SHELL_WRITE_RX.search(s):
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
    # 계약 경로는 비교용으로 소문자(normcase)가 되어 온다 — 메시지에는 실제 대소문자로 보인다(수강생 시험 c-3)
    cp = Path(os.path.realpath(cp))
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
    # 영수증이 지금 계약의 활성 조건 «전부»의 결과를 담았는가 — 결과가 빠진 영수증은 증거가 아니다(리뷰 ⑤ p4 R-1)
    want = {x.get("id") for x in c.get("conditions") or [] if isinstance(x, dict) and x.get("status", "active") == "active"}
    got = {x.get("id") for x in r.get("results") or [] if isinstance(x, dict)}
    if want != got:
        bad.append(f"영수증 {rp} 에 활성 조건 결과가 다 있지 않습니다(빠짐 {sorted(want - got)}) — 다시 verify 하세요")
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
    # 실패·사람 판정 대기가 남은 채로는 «완료»가 아니다 — 건수를 적어도, ack 가 있어도 막는다(리뷰 ③ R-2).
    # 고치지 못한 것을 정직하게 보고하는 응답(«완료하지 못했다»·«미완료»)은 완료 주장이 아니라 여기 오지 않는다
    failed = r.get("failed") or []
    if failed:
        bad.append(f"완료 조건 실패 {len(failed)}건({', '.join(failed)})을 두고 완료를 주장합니다 — 고친 뒤 다시 verify 하거나, "
                   f"고치지 못했으면 «완료하지 못했다»고 «실패 {len(failed)}건»·조건 ID와 함께 보고하세요.")
    hp = int(r.get("human_pending") or 0)
    if hp:
        bad.append(f"사람 판정 대기 {hp}건이 남아 완료가 아닙니다 — 사람이 판정한 뒤 다시 verify 하거나, "
                   f"«미완료 — 사람 판정 대기 {hp}건»으로 보고하세요.")
    if key not in acked:
        w = int(r.get("warnings") or 0)
        if w and not re.search(rf"경고\s*{w}\s*건", text):
            bad.append(f"경고 {w}건입니다 — 응답에 «경고 {w}건»과 내용을 적으세요.")
    return bad, key


def main() -> int:
    try:
        data = json.loads(sys.stdin.buffer.read().decode("utf-8", "replace") or "{}")
        data = data if isinstance(data, dict) else {}  # 객체가 아닌 JSON 에 Traceback 으로 죽지 않게
    except json.JSONDecodeError:
        return 0
    retry = bool(data.get("stop_hook_active"))
    recs = records(data.get("transcript_path"))
    cwd = Path(data.get("cwd") if isinstance(data.get("cwd"), str) and data.get("cwd") else os.getcwd())
    last_edit, receipts, reads, loose, last = scan(recs, cwd)
    # 명령 해석으로 못 잡은 편집(파이썬 한 줄 쓰기 등)도 놓치지 않게, 이 세션에서 verify 한 계약은 지문으로 다시 본다 — 마지막
    # 영수증 뒤 소스 지문이 바뀌었으면 «영수증 뒤 편집»이다(리뷰 ⑤ p4 R-2)
    for at, rp in receipts:
        cp = lc.find_contract(Path(rp).parent)
        if not cp or _norm(cp) in last_edit:
            continue
        mine = [(i, p) for i, p in receipts if lc.find_contract(Path(p).parent) and _norm(lc.find_contract(Path(p).parent)) == _norm(cp)]
        i_last, p_last = max(mine)
        try:
            r_last, c_now = lc.load(Path(p_last)), lc.load(cp)
            if r_last.get("source_fp", {}).get("digest") != lc.source_fp(cp.parent, c_now.get("watch") or [])["digest"]:
                last_edit[_norm(cp)] = len(recs)
        except (OSError, ValueError):
            last_edit[_norm(cp)] = len(recs)
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
        n = bump_blocks(af.with_name(af.stem + ".blocks.json"), "\n".join(bad), retry)
        if n > MAX_BLOCKS:  # 끝없이 막지 않는다 — 대신 사용자 눈에 보이게 남긴다(리뷰 ③ R-1)
            out = {"systemMessage": f"[harness-lite] 같은 사유로 {MAX_BLOCKS}번 막혔습니다 — 검증 없이 완료 주장 — 사유:\n- "
                                    + "\n- ".join(bad)}
        else:
            out = {"decision": "block", "reason": "[harness-lite] 완료 확인이 끝나지 않았습니다:\n- " + "\n- ".join(bad)}
        sys.stdout.buffer.write(json.dumps(out, ensure_ascii=False).encode("utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
