"""수강생판 하네스 공용 모듈 — 완료 조건 계약을 읽고, 조건을 돌려 영수증을 남기고, 영수증이 지금 소스와 맞는지 본다.

전체판(claude-skills 의 harness_v2)과 같은 계약 필드 이름을 쓴다(intent 아홉 요소·watch·protect·conditions). 그래서 나중에
전체판으로 옮길 때 계약을 다시 쓰지 않는다. 빠진 것: 승인 스냅숏·계수 래칫·보호 검사 파일·리뷰·순환·전수 읽음 증명.
"""
from __future__ import annotations

import fnmatch
import glob as globmod
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

CONTRACT = "harness.contract.json"
LITE_V = "lite-1"
RECEIPT_MARK = "[harness-lite] 영수증 "
INTENT_KEYS = ["purpose", "scope", "evidence", "screen", "data", "original", "verification", "publish", "cost"]
INTENT_LABELS = {"purpose": "1 목적", "scope": "2 범위", "evidence": "3 근거", "screen": "4 화면", "data": "5 자료",
                 "original": "6 원본", "verification": "7 검증", "publish": "8 공개", "cost": "9 비용"}
JUDGES = {"deterministic", "visual", "human"}
STATUSES = {"active", "retired"}  # 전체판(harness_v2.STATUSES)과 같다
SKIP_DIRS = {".git", ".harness", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", ".mypy_cache", "dist", "build"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
DEFAULT_TIMEOUT = 900
MISSING_MODULE_RX = re.compile(r"No module named '?([\w.]+)'?")
FATAL_MARK = "HARNESS::FATAL"
WARN_MARK = "HARNESS::WARN"
ID_RX = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")
# 초안의 조건 문장 머리 — 채우지 않은 채로 verify 가 통과하면 《무엇을 확인했는지》가 비어 있다(수강생 시험 b-4)
PLACEHOLDER_TEXT = "(사람 말 한 문장으로)"
# argv 안의 이 낱말은 verify 를 돌리는 파이썬으로 바꾼다 — 계약을 다른 OS 로 옮겨도 돈다(수강생 시험 b-6)
PY_TOKEN = "{python}"


def python_argv() -> list[str]:
    """이 OS 에서 파이썬 3 을 부르는 명령 — Windows 는 py 런처, macOS·Linux 는 python3(py 가 없다, 수강생 시험 b-6)."""
    return ["py", "-3"] if os.name == "nt" else ["python3"]


def _kill_tree(p: subprocess.Popen) -> None:
    """검사 프로세스와 그 자식 전부를 끈다(내가 띄운 PID 기준 — 이름 기준이 아니다). 시간 초과 뒤 자식이 살아 파일을 쓰지 않게
    (리뷰 ⑤ p4 R-8)."""
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True, timeout=30)
        else:
            import signal
            os.killpg(p.pid, signal.SIGKILL)
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        p.kill()
    except OSError:
        pass


def find_contract(start: Path) -> Path | None:
    p = Path(start).resolve()
    for d in [p, *p.parents]:
        if (d / CONTRACT).is_file():
            return d / CONTRACT
    return None


def load(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def digest(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]


def contract_hash(c: dict) -> str:
    return digest(c)


def validate(c: dict) -> list[str]:
    if not isinstance(c, dict):
        return ["계약 최상위가 JSON 객체가 아닙니다"]
    errs = []
    if c.get("v") != LITE_V:
        errs.append(f"v 는 \"{LITE_V}\" 이어야 합니다")
    watch = c.get("watch")
    if not isinstance(watch, list) or not watch or not all(isinstance(w, str) and w for w in watch):
        errs.append("watch 는 소스 파일 글롭 목록이어야 합니다(예: \"**/*.py\")")
    prot = c.get("protect", [])
    if not isinstance(prot, list) or not all(isinstance(w, str) and w for w in prot):
        errs.append("protect 는 읽기만 할 원본 경로 글롭 목록이어야 합니다(예: \"원본/**\")")
    conds = c.get("conditions")
    if not isinstance(conds, list) or not conds:
        return errs + ["conditions 가 비었습니다 — 《끝났다》를 확인할 조건을 하나 이상 적으세요"]
    seen = set()
    live = 0
    for i, x in enumerate(conds):
        if not isinstance(x, dict):
            errs.append(f"conditions[{i}] 가 객체가 아닙니다")
            continue
        cid = x.get("id")
        # ID 는 작업 폴더·로그 파일 이름이 된다 — 없거나 경로 문자가 들어가면 밖에 쓴다(리뷰 ⑤ p4 R-7)
        if not isinstance(cid, str) or not ID_RX.fullmatch(cid):
            errs.append(f"conditions[{i}].id 는 영문·숫자·-·_ 로 된 이름이어야 합니다(지금 {cid!r})")
            cid = f"conditions[{i}]"
        if cid in seen:
            errs.append(f"조건 ID {cid} 가 중복입니다")
        seen.add(cid)
        # 모르는 status 는 조용히 《실행 안 함》이 되지 않게 형식 오류로 본다(리뷰 ③ R-3)
        st = x.get("status", "active")
        if st not in STATUSES:
            errs.append(f"{cid}: status 는 active·retired 중 하나입니다(지금 {st!r})")
        elif st == "active":
            live += 1
        text = str(x.get("text") or "").strip()
        if not text:
            errs.append(f"{cid}: text(사람 말 한 문장)가 없습니다")
        elif text.startswith(PLACEHOLDER_TEXT):
            errs.append(f"{cid}: text 가 아직 초안의 자리 표시입니다 — 《끝났다》를 사람 말 한 문장으로 바꾸세요")
        j, chk = x.get("judge"), x.get("check")
        if j not in JUDGES:
            errs.append(f"{cid}: judge 는 deterministic·visual·human 중 하나입니다")
        if not isinstance(chk, dict):
            errs.append(f"{cid}: check 가 없습니다")
            continue
        if j == "deterministic" and not (chk.get("argv") or chk.get("cmd")):
            errs.append(f"{cid}: deterministic 은 check.argv(명령 목록) 또는 check.cmd(명령 한 줄)가 필요합니다")
        if j == "visual" and not chk.get("captures"):
            errs.append(f"{cid}: visual 은 check.captures(캡처 파일 글롭)가 필요합니다")
        if j == "human" and not chk.get("queue"):
            errs.append(f"{cid}: human 은 check.queue(사람 판정 대기열 JSONL 경로)가 필요합니다")
        if "argv" in chk and not (isinstance(chk["argv"], list) and chk["argv"] and all(isinstance(a, str) for a in chk["argv"])):
            errs.append(f"{cid}: argv 는 문자열 목록이어야 합니다")
    if not live:
        # 조건을 전부 retired 로 두면 아무것도 돌리지 않은 영수증이 《통과》가 된다(리뷰 ③ R-3)
        errs.append("활성(active) 조건이 하나도 없습니다 — 《끝났다》를 확인할 조건을 하나 이상 active 로 두세요")
    return errs


def matches(rel: str, pats: list[str]) -> bool:
    rel = rel.replace("\\", "/")
    if os.name == "nt":  # Windows 파일 시스템은 대소문자를 가리지 않는다(Codex §16-21 리뷰 #9)
        rel, pats = rel.lower(), [p.replace("\\", "/").lower() for p in pats]
    for p in pats:
        if fnmatch.fnmatch(rel, p) or (p.startswith("**/") and fnmatch.fnmatch(rel, p[3:])):
            return True
        if p.endswith("/**") and (rel == p[:-3] or rel.startswith(p[:-2]) or fnmatch.fnmatch(rel, p[:-3])
                                  or (p.startswith("**/") and fnmatch.fnmatch(rel, p[3:-3]))):
            return True  # 《폴더/**》는 그 폴더 자신도 가리킨다(폴더째 옮기기 판정 — Codex §16-21 리뷰 #7)
    return False


def source_files(root: Path, watch: list[str]) -> list[str]:
    """watch 에 걸리는 파일. 기본으로 건너뛰는 폴더(dist·build …)라도 watch 가 그 폴더를 명시하면 센다 — 명시한 watch 를 조용히
    무시하면 산출물을 바꿔도 지문이 같았다(리뷰 ⑤ p4 R-9)."""
    root = Path(root)
    explicit = {p.replace("\\", "/").lstrip("/").split("/", 1)[0] for p in watch if "/" in p.replace("\\", "/")}
    out = []
    for dp, dns, fns in os.walk(root):
        top = Path(dp) == root
        dns[:] = [d for d in dns if d not in SKIP_DIRS or (top and d in explicit and d not in (".git", ".harness"))]
        for fn in fns:
            rel = (Path(dp) / fn).relative_to(root).as_posix()
            if matches(rel, watch):
                out.append(rel)
    return sorted(out)


def file_sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def source_fp(root: Path, watch: list[str]) -> dict:
    files = source_files(root, watch)
    return {"digest": digest({f: file_sha(Path(root) / f) for f in files}), "n": len(files)}


def _count_marks(text: str) -> tuple[int, int]:
    lines = text.splitlines()
    return sum(WARN_MARK in ln for ln in lines), sum(FATAL_MARK in ln for ln in lines)


def run_condition(x: dict, root: Path, vd: Path) -> dict:
    cid, judge, chk = x["id"], x["judge"], x.get("check") or {}
    res = {"id": cid, "judge": judge, "text": x.get("text", ""), "ok": False, "reason": ""}
    if judge == "human":
        q = Path(chk["queue"]) if Path(chk["queue"]).is_absolute() else Path(root) / chk["queue"]
        res["queue"] = str(q)
        try:
            raw = q.read_bytes()
        except OSError:
            res["reason"] = "대기열 파일이 없습니다 — 대기 0건이면 빈 파일을 두세요"
            return res
        pending, bad = [], 0
        for ln in raw.decode("utf-8", "replace").splitlines():
            if not ln.strip():
                continue
            try:
                r = json.loads(ln)
            except ValueError:
                bad += 1
                continue
            if not isinstance(r, dict):  # null·[]·123 도 깨진 레코드다 — 조용히 넘기면 대기 0건이 된다(리뷰 ③ R-15)
                bad += 1
            elif r.get("status") != "decided":
                pending.append(r.get("id"))
        if bad:
            # 깨진 줄은 판정되지 않은 것이다 — 대기에 넣어 세고, 이 조건은 실패로 둔다
            res.update(pending=len(pending) + bad, queue_sha=hashlib.sha256(raw).hexdigest(),
                       reason=f"대기열에 읽을 수 없는 줄 {bad}개(사람 판정 대기 {len(pending) + bad}건에 포함)")
            return res
        res.update(ok=None, pending=len(pending), queue_sha=hashlib.sha256(raw).hexdigest(),
                   reason=f"사람 판정 대기 {len(pending)}건")
        return res
    scratch = vd / cid
    scratch.mkdir(parents=True, exist_ok=True)
    fail = ""
    started = time.time()
    if chk.get("argv") or chk.get("cmd"):
        argv = [sys.executable if a == PY_TOKEN else a.replace("{scratch}", str(scratch)) for a in chk["argv"]] if chk.get("argv") else \
            chk["cmd"].replace("{scratch}", str(scratch))
        env = dict(os.environ, HARNESS_SCRATCH=str(scratch), PYTHONUTF8="1")
        t0 = time.time()
        grp = {"creationflags": 0x00000200} if os.name == "nt" else {"start_new_session": True}  # 새 프로세스 그룹
        try:
            p = subprocess.Popen(argv, shell=not chk.get("argv"), cwd=str(root), env=env, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, **grp)
            try:
                raw, _ = p.communicate(timeout=int(chk.get("timeout", DEFAULT_TIMEOUT)))
                rc, out = p.returncode, raw.decode("utf-8", "replace")
            except subprocess.TimeoutExpired:
                _kill_tree(p)  # 부모만이 아니라 자식까지 끈다
                try:
                    raw, _ = p.communicate(timeout=30)
                except subprocess.TimeoutExpired:
                    raw = b""
                rc, out = None, raw.decode("utf-8", "replace") + f"\n[harness-lite] 시간 초과 {chk.get('timeout', DEFAULT_TIMEOUT)}초"
        except OSError as e:
            rc, out = None, f"[harness-lite] 실행할 수 없습니다: {e}"
        log = vd / f"{cid}.log"
        log.write_text(out, encoding="utf-8")
        w, f = _count_marks(out)
        res.update(rc=rc, secs=round(time.time() - t0, 1), log=str(log), warnings=w, fatal=f)
        if rc is None:
            fail = out.strip().splitlines()[-1] if out.strip() else "실행 실패"
        elif rc != 0:
            fail = f"종료 코드 {rc}"
            miss = MISSING_MODULE_RX.search(out)
            if miss:  # 수강생 PC 에서 가장 흔한 실패 — 검사가 아니라 준비물 문제임을 밝힌다
                fail += f" — {miss.group(1)} 모듈이 설치돼 있지 않습니다(설치는 사용자에게 먼저 묻는다)"
        elif f:
            fail = f"치명 표지 {f}건"
        elif chk.get("expect_text") and chk["expect_text"] not in out:
            fail = f"출력에 《{chk['expect_text']}》 가 없습니다"
    if judge == "visual":
        caps = []
        for g in chk.get("captures") or []:
            pat = g.replace("{scratch}", scratch.as_posix())
            pat = pat if Path(pat).is_absolute() else (Path(root) / pat).as_posix()
            caps += [Path(p) for p in sorted(globmod.glob(pat, recursive=True)) if Path(p).is_file()]
        # 이번 실행이 만든 캡처만 증거다 — 지난 실행의 PNG 가 남아 있으면 화면을 다시 만들지 않고도 통과했다(리뷰 ⑤ p4 R-10)
        stale = [p for p in caps if p.stat().st_mtime < started - 1]
        if stale and not fail:
            fail = f"이번 실행이 만들지 않은 캡처 {len(stale)}장이 있습니다(예: {stale[0].name}) — 캡처를 만드는 명령을 조건에 넣으세요"
        if caps:
            res["captures"] = [{"path": str(p.resolve()), "sha": file_sha(p)} for p in caps]
        elif not fail:
            fail = "캡처가 하나도 만들어지지 않았습니다"
    res["ok"] = not fail
    res["reason"] = fail
    return res


def verify(cpath: Path) -> tuple[dict, Path]:
    cpath = Path(cpath).resolve()
    root = cpath.parent
    c = load(cpath)
    errs = validate(c)
    vd = root / ".harness" / "lite" / datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    vd.mkdir(parents=True, exist_ok=True)
    watch = c.get("watch") or []
    fp0 = source_fp(root, watch) if not errs else {"digest": "", "n": 0}
    results = [] if errs else [run_condition(x, root, vd) for x in c["conditions"] if x.get("status", "active") == "active"]
    fp1 = source_fp(root, watch) if not errs else fp0
    problems = list(errs)
    if not errs and not fp0["n"]:
        # 지문 대상이 0개면 영수증 뒤 무엇을 바꿔도 《같다》가 된다(리뷰 ⑤ p4 R-9)
        problems.append("watch 에 걸리는 파일이 하나도 없습니다 — 소스 지문이 비어 영수증이 아무것도 증명하지 못합니다. watch 를 고치세요")
    if fp1["digest"] != fp0["digest"]:
        problems.append("검사 중에 소스가 바뀌었습니다 — 검사는 소스를 고치지 말고 결과를 {scratch} 로 보내세요")
    # 처음 읽은 계약으로 돌린 결과가 지금 계약의 영수증이 되면 안 된다(리뷰 ③ R-16)
    try:
        changed = contract_hash(load(cpath)) != contract_hash(c)
    except (OSError, ValueError):
        changed = True
    if changed:
        problems.append("검사 중에 계약(harness.contract.json)이 바뀌었습니다 — 계약을 고친 뒤 다시 verify 하세요")
    blanks = [INTENT_LABELS[k] for k in INTENT_KEYS if not str(((c.get("intent") or {}).get(k) or {}).get("text") or "").strip()]
    receipt = {
        "v": LITE_V, "ts": datetime.now().isoformat(timespec="seconds"), "root": str(root),
        "contract_hash": contract_hash(c), "source_fp": fp1, "results": results,
        "failed": [r["id"] for r in results if r.get("ok") is False],
        "human_pending": sum(int(r.get("pending") or 0) for r in results),
        "warnings": sum(int(r.get("warnings") or 0) for r in results),
        "captures": [cap for r in results for cap in r.get("captures", [])],
        "intent_blank": blanks, "problems": problems,
    }
    # 사람 판정 대기는 《통과》가 아니다(리뷰 ③ R-2) — 대기가 남은 영수증은 ok 가 아니다
    receipt["ok"] = not problems and not receipt["failed"] and not receipt["human_pending"]
    # 계약 오류로 돌리지 못한 활성 조건 — 요약이 《실패 0건》만 보여 성공처럼 읽히지 않게(수강생 시험 c-2)
    conds = c.get("conditions") if isinstance(c.get("conditions"), list) else []
    receipt["not_run"] = 0 if results else sum(1 for x in conds if isinstance(x, dict) and x.get("status", "active") == "active")
    receipt["seal"] = seal(receipt)
    rp = vd / "receipt.json"
    rp.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    return receipt, rp


def seal(r: dict) -> str:
    """영수증 봉인 — 봉인 칸을 뺀 내용의 지문. 손으로 고친 영수증을 알아본다(변경 탐지이지 위조 방지는 아니다, 수강생 시험 c-1)."""
    return digest({k: v for k, v in r.items() if k != "seal"})


def table(c: dict, receipt: dict | None, stale: bool = False) -> list[str]:
    """조건 표. stale 이면 지난 결과를 《낡음》 표시와 함께 보인다 — 전부 《미실행》으로 지우면 지난 결과를 잃는다(수강생 시험 d-2)."""
    by = {r["id"]: r for r in (receipt or {}).get("results", [])}
    out = ["| 조건 | 사람 말 | 판정자 | 결과 |", "|---|---|---|---|"]
    for x in c.get("conditions") or []:
        if not isinstance(x, dict) or x.get("status", "active") != "active":
            continue
        r = by.get(x.get("id"))
        res = "미실행" if not r else (r.get("reason") if r.get("ok") is None else ("통과" if r["ok"] else "실패 — " + r.get("reason", "")))
        if r and stale:
            res += " (낡음 — 다시 verify)"
        out.append(f"| {x.get('id')} | {x.get('text', '')} | {x.get('judge')} | {res} |")
    return out


def cli_command(sub: str) -> str:
    """훅 메시지에 찍을 정확한 명령 — 수강생은 플러그인 설치 경로를 모른다. sh 가 아니라 파이썬으로 부른다 — 사용자가 PowerShell 에
    붙여 넣으면 《sh 를 찾을 수 없다》로 시작조차 못 했다(수강생 시험 a-1). 정슬래시 경로는 PowerShell·Git Bash 둘 다 받는다."""
    harness = (Path(__file__).resolve().parent / "harness.py").as_posix()
    return f'{" ".join(python_argv())} "{harness}" {sub}'


def unlock_command(root: Path) -> str:
    """사용자가 직접 칠 잠금 풀기 명령 — 사용자의 PowerShell 작업 폴더는 프로젝트가 아닐 수 있어 --root 를 붙인다."""
    return cli_command(f'--root "{Path(root).as_posix()}" unlock')
