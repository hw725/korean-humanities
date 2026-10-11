"""수강생판 하네스 명령 — init(계약 만들기)·status(조건 표)·verify(조건 실행 → 영수증)·trash(휴지통으로 보내기).

  sh <플러그인>/scripts/run.sh harness.py init      # 프로젝트 폴더에 harness.contract.json 초안
  sh <플러그인>/scripts/run.sh harness.py verify    # 조건을 전부 돌리고 영수증을 남긴다
  sh <플러그인>/scripts/run.sh harness.py status    # 조건 표와 마지막 영수증
  sh <플러그인>/scripts/run.sh harness.py trash <경로> …   # 영구 삭제 대신 휴지통으로(원본은 거부)
  sh <플러그인>/scripts/run.sh harness.py lock      # 원본을 OS 읽기 전용으로(명령으로 우회 불가) · unlock 은 사용자가
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
        py = "py" if os.name == "nt" else "python3"
        pre = [py, "-3"] if py == "py" else [py]
        return {"argv": [*pre, "-m", "pytest", "-q"], "timeout": 900}
    return None


def cmd_init(a) -> int:
    root = Path(a.root).resolve()
    cp = root / lc.CONTRACT
    if cp.exists():
        print(f"[harness-lite] 이미 계약이 있습니다: {cp} — 고치려면 파일을 직접 여세요.")
        return 1
    c = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    chk = detect_check(root)
    if chk:
        c["conditions"][0]["check"] = chk
        c["conditions"][0]["text"] = "테스트가 모두 통과한다"
    cp.write_text(json.dumps(c, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[harness-lite] 계약 초안을 만들었습니다: {cp}")
    print("다음 아홉 칸을 사용자에게 물어 채우세요(모르는 칸은 비워 두고, 비운 칸은 영수증에 «빈 칸»으로 남습니다):")
    for k in lc.INTENT_KEYS:
        print(f"  - {lc.INTENT_LABELS[k]}: {c['intent'][k].get('hint', '')}")
    print("조건(conditions)은 «사람 말 한 문장 + 확인 명령 하나»입니다. 채운 뒤 사용자에게 표를 보여 주고 확인을 받으세요:")
    print("  " + lc.cli_command("status"))
    if not chk:
        print("테스트 명령을 찾지 못했습니다 — C-001 의 check 를 채우세요.")
    elif "pytest" in chk["argv"]:
        probe = subprocess.run([*chk["argv"][:chk["argv"].index("-m")], "-c", "import pytest"], capture_output=True)
        if probe.returncode != 0:
            print("주의: 이 파이썬에 pytest 가 없습니다 — verify 가 «모듈 없음»으로 실패합니다. "
                  f"설치(`{' '.join(chk['argv'][:chk['argv'].index('-m')])} -m pip install pytest`)는 사용자에게 먼저 물어보세요.")
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
    print("\n".join(lc.table(c, r if r and not stale else None)))
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
    print(f"[harness-lite] 실패 {len(r['failed'])}건{(' (' + ', '.join(r['failed']) + ')') if r['failed'] else ''} · "
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


def _protected_files(root: Path) -> list[Path]:
    import lite_pretool as lp
    cp = root / lc.CONTRACT
    pats = list(lp.DEFAULT_PROTECT) + (lp._protect_of(cp) if cp.is_file() else [])
    out = []
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in (".git", ".harness", "node_modules", ".venv", "venv", "__pycache__")]
        for fn in fns:
            rel = (Path(dp) / fn).relative_to(root).as_posix()
            if lc.matches(rel, pats):
                out.append(Path(dp) / fn)
    return out


def cmd_lock(a) -> int:
    """원본(protect·기본 원본/·primary_data/)을 OS 읽기 전용으로 건다 — 명령을 어떻게 쓰든 쓰기가 실패한다. 훅의 명령 해석은
    미리 알려 주는 안내이고, 이것이 실제로 막는 장치다(2026-10-11 구조 전환). 푸는 것은 `unlock`(사용자가 직접)."""
    import stat
    root = Path(a.root).resolve()
    files = _protected_files(root)
    for f in files:
        os.chmod(f, stat.S_IREAD if a.cmd == "lock" else stat.S_IREAD | stat.S_IWRITE)
    print(f"[harness-lite] 원본 {len(files)}개를 {'읽기 전용으로 걸었' if a.cmd == 'lock' else '쓰기 가능으로 풀었'}습니다.")
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
