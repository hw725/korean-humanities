"""수강생판 하네스 명령 — init(계약 만들기)·status(조건 표)·verify(조건 실행 → 영수증)·trash(휴지통으로 보내기).

  py -3 "<플러그인>/scripts/harness.py" init      # 프로젝트 폴더에 harness.contract.json 초안(macOS·Linux 는 python3)
  py -3 "<플러그인>/scripts/harness.py" verify    # 조건을 전부 돌리고 영수증을 남긴다
  py -3 "<플러그인>/scripts/harness.py" status    # 조건 표와 마지막 영수증
  py -3 "<플러그인>/scripts/harness.py" trash <경로> …   # 영구 삭제 대신 휴지통으로(원본은 거부)
  py -3 "<플러그인>/scripts/harness.py" lock      # 원본 파일을 OS 읽기 전용으로 · unlock 은 사용자가 직접
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lite_common as lc  # noqa: E402

for _stream in (sys.stdout, sys.stderr):  # CJK 계약 E3 — 한국어 Windows 콘솔(cp949)에서 죽지 않게
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass
TEMPLATE = Path(__file__).resolve().parent.parent / "templates" / lc.CONTRACT
# 폴더의 읽기 전용은 POSIX 에서만 새 파일 만들기·지우기·이름 바꾸기를 막는다 — Windows 는 폴더의 읽기 전용 속성을 무시한다
# (수강생 시험 b-2). 그래서 Windows 에서는 폴더를 건드리지 않고 파일만 잠근다
DIR_LOCK = os.name != "nt"
LOCK_REC = Path(".harness") / "lite" / "lock.json"


def detect_check(root: Path) -> dict | None:
    """테스트 실행 명령을 하나 찾는다(없으면 None — 조건은 사람이 채운다)."""
    root = Path(root)
    if (root / "package.json").is_file():
        try:
            scripts = json.loads((root / "package.json").read_text(encoding="utf-8")).get("scripts") or {}
        except ValueError:
            scripts = {}
        if "test" in scripts:
            return {"argv": ["npm", "test", "--silent"], "timeout": 900}
    has_py_tests = any((root / d).is_dir() for d in ("tests", "test")) or list(root.glob("test_*.py"))
    if has_py_tests:
        return {"argv": [*lc.python_argv(), "-m", "pytest", "-q"], "timeout": 900}
    return None


def cmd_init(a) -> int:
    root = Path(a.root).resolve()
    cp = root / lc.CONTRACT
    if cp.exists():
        print(f"[harness-lite] 이미 계약이 있습니다: {cp} — 고치려면 파일을 직접 여세요.")
        return 1
    c = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    chk = detect_check(root)
    cond = c["conditions"][0]
    if chk:
        cond["check"] = chk
        cond["text"] = "테스트가 모두 통과한다"
    argv = cond["check"]["argv"]
    if argv[:1] == [lc.PY_TOKEN]:  # 초안의 파이썬 자리를 이 OS 의 명령으로 — 전체판으로 옮겨도 그대로 돈다(수강생 시험 b-6)
        cond["check"]["argv"] = argv = [*lc.python_argv(), *argv[1:]]
    cp.write_text(json.dumps(c, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[harness-lite] 계약 초안을 만들었습니다: {cp}")
    print("다음 아홉 칸을 사용자에게 물어 채우세요(모르는 칸은 비워 두고, 비운 칸은 영수증에 «빈 칸»으로 남습니다):")
    for k in lc.INTENT_KEYS:
        print(f"  - {lc.INTENT_LABELS[k]}: {c['intent'][k].get('hint', '')}")
    print("조건(conditions)은 «사람 말 한 문장 + 확인 명령 하나»입니다. 채운 뒤 사용자에게 표를 보여 주고 확인을 받으세요:")
    print("  " + lc.cli_command("status"))
    if not chk:
        print(f"테스트 명령을 찾지 못했습니다 — C-001 은 pytest 를 돌리는 초안입니다. text 의 자리 표시(«{lc.PLACEHOLDER_TEXT} …»)를 "
              "사람 말 한 문장으로 바꾸고 check 를 이 프로젝트에 맞추세요(자리 표시가 남으면 verify 가 거부합니다).")
    if "pytest" in argv:
        # 테스트 폴더를 못 찾아 초안 그대로 둔 때도 본다 — 종전에는 찾았을 때만 봐서 verify 에서야 «모듈 없음»이 났다(수강생 시험 b-4)
        pre = argv[:argv.index("-m")]
        try:
            missing = subprocess.run([*pre, "-c", "import pytest"], capture_output=True).returncode != 0
        except OSError as e:
            print(f"주의: 파이썬을 실행하지 못했습니다({' '.join(pre)}: {e}) — C-001 의 check 를 이 PC 의 파이썬 명령으로 고치세요.")
        else:
            if missing:
                print("주의: 이 파이썬에 pytest 가 없습니다 — verify 가 «pytest 모듈이 설치돼 있지 않습니다»로 실패합니다. "
                      f"설치(`{' '.join(pre)} -m pip install pytest`)는 사용자에게 먼저 물어보세요.")
    return 0


def _contract(a) -> tuple[Path, dict] | None:
    cp = lc.find_contract(Path(a.root))
    if not cp:
        print(f"[harness-lite] 계약(harness.contract.json)이 없습니다 — 먼저: {lc.cli_command('init')}")
        return None
    return cp, lc.load(cp)


def latest(root: Path) -> tuple[dict | None, Path | None]:
    d = Path(root) / ".harness" / "lite"
    rs = sorted(d.glob("*/receipt.json")) if d.is_dir() else []
    if not rs:
        return None, None
    try:
        return lc.load(rs[-1]), rs[-1]
    except (OSError, ValueError):
        return None, rs[-1]


def cmd_status(a) -> int:
    got = _contract(a)
    if not got:
        return 1
    cp, c = got
    errs = lc.validate(c)
    for e in errs:
        print(f"  ✗ {e}")
    r, rp = latest(cp.parent)
    stale = ""
    if r:
        if r.get("contract_hash") != lc.contract_hash(c):
            stale = " — 영수증 뒤 계약이 바뀜"
        elif not errs and r.get("source_fp", {}).get("digest") != lc.source_fp(cp.parent, c.get("watch") or [])["digest"]:
            stale = " — 영수증 뒤 소스가 바뀜(다시 verify)"
    print(f"[harness-lite] 계약 {cp} · 마지막 영수증 {rp or '없음'}{stale}")
    print("\n".join(lc.table(c, r, stale=bool(stale))))
    return 0 if not errs else 2


def cmd_verify(a) -> int:
    got = _contract(a)
    if not got:
        return 1
    cp, c = got
    r, rp = lc.verify(cp)
    print(f"{lc.RECEIPT_MARK}{rp}")
    print("\n".join(lc.table(c, r)))
    for p in r["problems"]:
        print(f"  ✗ {p}")
    if r["intent_blank"]:
        print(f"  · 빈 칸 {len(r['intent_blank'])}개: {', '.join(r['intent_blank'])}")
    # 계약 오류로 조건을 못 돌렸을 때 «실패 0건»만 보이면 성공처럼 읽힌다 — 판정·문제·미실행을 함께 적는다(수강생 시험 c-2)
    print(f"[harness-lite] {'통과' if r['ok'] else '완료 아님'} — "
          f"실패 {len(r['failed'])}건{(' (' + ', '.join(r['failed']) + ')') if r['failed'] else ''} · "
          f"문제 {len(r['problems'])}건 · 미실행 {r['not_run']}건 · "
          f"사람 판정 대기 {r['human_pending']}건 · 경고 {r['warnings']}건 · 캡처 {len(r['captures'])}장")
    if r["captures"]:
        print("[harness-lite] 완료라고 말하기 전에 캡처를 전부 Read 로 여세요:")
        for cap in r["captures"]:
            print(f"  {cap['path']}")
    return 0 if r["ok"] else 4


def send_to_trash(p: Path) -> str | None:
    """휴지통으로 보낸다. 실패하면 사유. 경로는 절대 경로로만 바꾸고 링크를 따라가지 않는다 — resolve 는 심볼릭 링크 대신 그
    대상(원본)을 보냈다(리뷰 ⑤ p4 R-11)."""
    p = Path(os.path.abspath(p))
    if not p.exists() and not p.is_symlink():
        return "없는 경로"
    if os.name == "nt":
        ps = ("Add-Type -AssemblyName Microsoft.VisualBasic; $p = $env:HARNESS_TRASH; "
              "if (Test-Path -LiteralPath $p -PathType Container) { [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteDirectory($p, 'OnlyErrorDialogs', 'SendToRecycleBin') } "
              "else { [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile($p, 'OnlyErrorDialogs', 'SendToRecycleBin') }")
        r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], env=dict(os.environ, HARNESS_TRASH=str(p)),
                           capture_output=True)
        return None if r.returncode == 0 and not p.exists() else (r.stderr.decode("utf-8", "replace").strip() or "실패")
    if sys.platform == "darwin":
        # 경로는 스크립트 문자열에 끼우지 않고 인수(argv)로 넘긴다 — 큰따옴표가 든 경로가 문자열을 닫고 명령을 덧붙이지
        # 못하게(전수 S-20261011-175508-48d241 F2)
        r = subprocess.run(["osascript", "-e", "on run argv", "-e",
                            'tell application "Finder" to delete POSIX file (item 1 of argv)', "-e", "end run",
                            p.as_posix()], capture_output=True)
        return None if r.returncode == 0 else r.stderr.decode("utf-8", "replace").strip() or "실패"
    if shutil.which("gio"):
        r = subprocess.run(["gio", "trash", str(p)], capture_output=True)
        return None if r.returncode == 0 else r.stderr.decode("utf-8", "replace").strip() or "실패"
    return "이 시스템에서 휴지통을 찾지 못했습니다(gio 없음) — 사용자에게 직접 지워 달라고 하세요"


def cmd_trash(a) -> int:
    import lite_pretool as lp
    base = Path(a.root).resolve()
    bad = 0
    for s in a.paths:
        if lp.is_protected(s, base) or lp.holds_protected(s, base):
            # 공식 휴지통 명령도 원본은 옮기지 않는다(리뷰 ⑤ p4 R-3)
            bad += 1
            print(f"  ✗ {s}: 원본(읽기만 할 자료)이거나 원본을 품은 폴더입니다 — 휴지통으로 보내지 않습니다")
            continue
        why = send_to_trash(Path(s) if Path(s).is_absolute() else base / s)
        if why:
            bad += 1
            print(f"  ✗ {s}: {why}")
        else:
            print(f"  ✓ 휴지통으로 보냄: {s}")
    return 1 if bad else 0


def _protected_paths(root: Path) -> tuple[list[Path], list[Path]]:
    """(원본 파일, 원본 폴더). 폴더는 «원본/**»처럼 폴더째 지킨 것과 그 아래 폴더."""
    import lite_pretool as lp
    cp = root / lc.CONTRACT
    pats = list(lp.DEFAULT_PROTECT) + (lp._protect_of(cp) if cp.is_file() else [])
    files, dirs = [], []
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in (".git", ".harness", "node_modules", ".venv", "venv", "__pycache__")]
        for names, out in ((dns, dirs), (fns, files)):
            for n in names:
                if lc.matches((Path(dp) / n).relative_to(root).as_posix(), pats):
                    out.append(Path(dp) / n)
    return files, dirs


def cmd_lock(a) -> int:
    """원본(protect·기본 원본/·primary_data/)을 OS 읽기 전용으로 건다. 잠긴 파일에 쓰는 명령은 OS 가 거부한다 — 훅의 명령 해석은
    미리 알려 주는 안내이고, 이것이 실제로 막는 장치다(2026-10-11 구조 전환). 다만 읽기 전용을 푸는 명령(attrib·chmod·
    Remove-Item -Force)은 막지 못하고, Windows 에서는 원본 폴더에 새 파일을 만드는 것도 막지 못한다(수강생 시험 b-2).
    잠근 것은 원래 권한과 함께 기록해 두고, `unlock`(사용자가 직접)은 그 기록만 되돌린다 — 처음부터 읽기 전용이던 파일까지
    «풀었다»고 세던 것(수강생 시험 b-2)."""
    import stat
    root = Path(a.root).resolve()
    rp = root / LOCK_REC
    try:
        rec = lc.load(rp)
    except (OSError, ValueError):
        rec = None
    rec = rec if isinstance(rec, dict) and isinstance(rec.get("files"), dict) and isinstance(rec.get("dirs"), dict) else None
    if a.cmd == "unlock":
        if rec is None:
            print(f"[harness-lite] 잠근 기록이 없습니다({rp}) — 이 도구가 건 잠금이 없어 풀 것이 없습니다.")
            return 1
        n = {}
        for kind in ("dirs", "files"):  # 폴더부터 — POSIX 에서 폴더가 잠겨 있으면 안의 파일 이름을 못 바꾼다
            n[kind] = 0
            for rel, mode in rec[kind].items():
                p = root / rel
                if p.exists():
                    os.chmod(p, mode)
                    n[kind] += 1
        rp.unlink()
        print(f"[harness-lite] 잠갔던 원본 파일 {n['files']}개·폴더 {n['dirs']}개를 원래 권한으로 풀었습니다.")
        return 0
    rec = rec or {"files": {}, "dirs": {}}
    files, dirs = _protected_paths(root)
    new_f = [f for f in files if os.access(f, os.W_OK)]  # 이미 읽기 전용인 것은 내가 잠근 것이 아니다
    new_d = [d for d in dirs if os.access(d, os.W_OK)] if DIR_LOCK else []
    for f in new_f:
        rec["files"][f.relative_to(root).as_posix()] = stat.S_IMODE(f.stat().st_mode)
        os.chmod(f, stat.S_IREAD)
    for d in new_d:
        rec["dirs"][d.relative_to(root).as_posix()] = stat.S_IMODE(d.stat().st_mode)
        os.chmod(d, stat.S_IREAD | stat.S_IEXEC)
    rp.parent.mkdir(parents=True, exist_ok=True)
    rp.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[harness-lite] 원본 파일 {len(new_f)}개·폴더 {len(new_d)}개를 읽기 전용으로 걸었습니다(기록: {rp}).")
    if not DIR_LOCK:
        print("  · Windows 는 폴더를 잠그지 못합니다 — 원본 폴더에 새 파일을 만드는 것은 훅의 원본 쓰기 거부가 맡습니다.")
    print(f"  · 풀 때는 사용자가 PowerShell(macOS·Linux 는 터미널)에 직접 붙여 넣습니다: {lc.unlock_command(root)}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="수강생판 하네스 — 완료 조건 계약과 영수증")
    ap.add_argument("--root", default=".", help="프로젝트 폴더(기본: 지금 폴더)")
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("init", help="계약 초안 만들기")
    sp.add_parser("status", help="조건 표와 마지막 영수증")
    sp.add_parser("verify", help="조건 전부 실행 → 영수증")
    t = sp.add_parser("trash", help="영구 삭제 대신 휴지통으로")
    t.add_argument("paths", nargs="+")
    sp.add_parser("lock", help="원본을 OS 읽기 전용으로 건다(명령으로 우회할 수 없게)")
    sp.add_parser("unlock", help="원본의 읽기 전용을 푼다(사용자가 직접)")
    a = ap.parse_args(argv)
    return {"init": cmd_init, "status": cmd_status, "verify": cmd_verify, "trash": cmd_trash,
            "lock": cmd_lock, "unlock": cmd_lock}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
