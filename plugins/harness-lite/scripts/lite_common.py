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
SKIP_DIRS = {".git", ".harness", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", ".mypy_cache", "dist", "build"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
DEFAULT_TIMEOUT = 900
MISSING_MODULE_RX = re.compile(r"No module named '?([\w.]+)'?")
FATAL_MARK = "HARNESS::FATAL"
WARN_MARK = "HARNESS::WARN"


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
        return errs + ["conditions 가 비었습니다 — «끝났다»를 확인할 조건을 하나 이상 적으세요"]
    seen = set()
    for i, x in enumerate(conds):
        if not isinstance(x, dict):
            errs.append(f"conditions[{i}] 가 객체가 아닙니다")
            continue
        cid = x.get("id") or f"conditions[{i}]"
        if cid in seen:
            errs.append(f"조건 ID {cid} 가 중복입니다")
        seen.add(cid)
        if not str(x.get("text") or "").strip():
            errs.append(f"{cid}: text(사람 말 한 문장)가 없습니다")
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
    return errs


def _skip(rel_parts: tuple[str, ...]) -> bool:
    return any(p in SKIP_DIRS for p in rel_parts[:-1])


def matches(rel: str, pats: list[str]) -> bool:
    rel = rel.replace("\\", "/")
    if os.name == "nt":  # Windows 파일 시스템은 대소문자를 가리지 않는다(Codex §16-21 리뷰 #9)
        rel, pats = rel.lower(), [p.replace("\\", "/").lower() for p in pats]
    for p in pats:
        if fnmatch.fnmatch(rel, p) or (p.startswith("**/") and fnmatch.fnmatch(rel, p[3:])):
            return True
        if p.endswith("/**") and (rel == p[:-3] or rel.startswith(p[:-2]) or fnmatch.fnmatch(rel, p[:-3])
                                  or (p.startswith("**/") and fnmatch.fnmatch(rel, p[3:-3]))):
            return True  # «폴더/**»는 그 폴더 자신도 가리킨다(폴더째 옮기기 판정 — Codex §16-21 리뷰 #7)
    return False


def source_files(root: Path, watch: list[str]) -> list[str]:
    root = Path(root)
    out = []
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in SKIP_DIRS]
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
            if isinstance(r, dict) and r.get("status") != "decided":
                pending.append(r.get("id"))
        if bad:
            res["reason"] = f"대기열에 읽을 수 없는 줄 {bad}개"
            return res
        res.update(ok=None, pending=len(pending), queue_sha=hashlib.sha256(raw).hexdigest(),
                   reason=f"사람 판정 대기 {len(pending)}건")
        return res
    scratch = vd / cid
    scratch.mkdir(parents=True, exist_ok=True)
    fail = ""
    if chk.get("argv") or chk.get("cmd"):
        argv = [a.replace("{scratch}", str(scratch)) for a in chk["argv"]] if chk.get("argv") else \
            chk["cmd"].replace("{scratch}", str(scratch))
        env = dict(os.environ, HARNESS_SCRATCH=str(scratch), PYTHONUTF8="1")
        t0 = time.time()
        try:
            p = subprocess.run(argv, shell=not chk.get("argv"), cwd=str(root), env=env, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, timeout=int(chk.get("timeout", DEFAULT_TIMEOUT)))
            rc, out = p.returncode, p.stdout.decode("utf-8", "replace")
        except subprocess.TimeoutExpired as e:
            rc, out = None, (e.stdout or b"").decode("utf-8", "replace") + f"\n[harness-lite] 시간 초과 {chk.get('timeout', DEFAULT_TIMEOUT)}초"
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
                fail += f" — 모듈 {miss.group(1)} 이 설치돼 있지 않습니다(설치는 사용자에게 먼저 묻는다)"
        elif f:
            fail = f"치명 표지 {f}건"
        elif chk.get("expect_text") and chk["expect_text"] not in out:
            fail = f"출력에 «{chk['expect_text']}» 가 없습니다"
    if judge == "visual":
        caps = []
        for g in chk.get("captures") or []:
            pat = g.replace("{scratch}", scratch.as_posix())
            pat = pat if Path(pat).is_absolute() else (Path(root) / pat).as_posix()
            caps += [Path(p) for p in sorted(globmod.glob(pat, recursive=True)) if Path(p).is_file()]
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
    if fp1["digest"] != fp0["digest"]:
        problems.append("검사 중에 소스가 바뀌었습니다 — 검사는 소스를 고치지 말고 결과를 {scratch} 로 보내세요")
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
    receipt["ok"] = not problems and not receipt["failed"]
    rp = vd / "receipt.json"
    rp.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    return receipt, rp


def table(c: dict, receipt: dict | None) -> list[str]:
    by = {r["id"]: r for r in (receipt or {}).get("results", [])}
    out = ["| 조건 | 사람 말 | 판정자 | 결과 |", "|---|---|---|---|"]
    for x in c.get("conditions") or []:
        if not isinstance(x, dict) or x.get("status", "active") != "active":
            continue
        r = by.get(x.get("id"))
        res = "미실행" if not r else (r.get("reason") if r.get("ok") is None else ("통과" if r["ok"] else "실패 — " + r.get("reason", "")))
        out.append(f"| {x.get('id')} | {x.get('text', '')} | {x.get('judge')} | {res} |")
    return out


def cli_command(sub: str) -> str:
    """훅 메시지에 찍을 정확한 명령 — 수강생은 플러그인 설치 경로를 모른다."""
    here = Path(__file__).resolve().parent
    return f'sh "{(here / "run.sh").as_posix()}" harness.py {sub}'
