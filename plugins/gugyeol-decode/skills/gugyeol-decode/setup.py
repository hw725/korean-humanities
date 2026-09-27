#!/usr/bin/env python3
"""
gugyeol-decode 1-step setup — 처음 사용자를 위한 모든 의존성·데이터를 한 번에 준비

수행 작업:
  0. 가상환경 확보 — 시스템 파이썬으로 실행하면 스킬 폴더에 .venv를 만들고 그 python으로
     자신을 다시 실행한다. 의존성을 시스템 파이썬에 설치하지 않기 위해서다. 이미 가상환경
     안에서 실행했으면 그 환경을 쓴다.
  1. PyMuPDF (PDF 처리 라이브러리) 설치 확인 → 없으면 가상환경에 pip install
  2. hypua 옛한글 매핑 다운로드 (kiwiyou/hypua, public domain)
  3. AKS 한국학중앙연구원 표준 구결자·옛한글 매핑 다운로드
  4. (선택) Unihan K source 한자 다운로드 — 합자 구결자 후보 풀

사용 (python 자리에는 아무 파이썬 3.9+ — Windows면 py):
  python setup.py              # 전체 setup (.venv 생성 포함)
  python setup.py --skip-unihan  # 합자 구결 데이터 제외 (3.8MB → 0.6MB)
  python setup.py --check      # 설치 상태만 확인

setup 뒤의 스크립트 실행은 .venv의 python으로 한다:
  Windows      .venv\\Scripts\\python.exe scripts\\decode.py <파일>
  macOS/Linux  .venv/bin/python scripts/decode.py <파일>
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import urllib.request
import venv
from pathlib import Path

# CJK 텍스트 계약 E3: Windows 콘솔 기본 cp949에서 한글·한자 출력이
# UnicodeEncodeError로 죽는 것을 막는다 (환경변수에 의존하지 않는 방어선).
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
REF = ROOT / "reference"
SCRIPTS = ROOT / "scripts"

HYPUA_URL = "https://raw.githubusercontent.com/kiwiyou/hypua/master/table"
HYPUA_PATH = REF / "hypua_table.csv"
AKS_GUKYUL_PATH = REF / "aks_gukyul_pua.json"
AKS_OLDHAN_PATH = REF / "aks_oldhan_pua.json"
UNIHAN_KOREAN_PATH = REF / "unihan_korean.json"
VENV = ROOT / ".venv"


def venv_python(env: Path = VENV) -> Path:
    """가상환경 안의 python 실행 파일 경로(OS별)."""
    return env / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def running_in_venv() -> bool:
    """지금 인터프리터가 가상환경인가. 스킬 .venv든 사용자가 켜 둔 다른 venv든 같다."""
    return sys.prefix != getattr(sys, "base_prefix", sys.prefix)


def ensure_venv(env: Path = VENV) -> Path:
    """스킬 .venv가 없으면 만든다(pip 포함). python 경로를 돌려준다."""
    py = venv_python(env)
    if not py.exists():
        print(colored(f"  → 가상환경 생성: {env}", "cyan"), flush=True)
        venv.EnvBuilder(with_pip=True).create(env)
    return py


def colored(text: str, color: str) -> str:
    codes = {"green": "32", "yellow": "33", "red": "31", "cyan": "36", "bold": "1"}
    if not sys.stdout.isatty():
        return text
    return f"\033[{codes.get(color, '0')}m{text}\033[0m"


def check_pymupdf() -> bool:
    try:
        import fitz  # noqa
        return True
    except ImportError:
        return False


def check_python_hwpx() -> bool:
    try:
        import hwpx  # noqa
        return True
    except ImportError:
        return False


def check_status() -> dict[str, bool]:
    return {
        "PyMuPDF (fitz) — PDF 처리": check_pymupdf(),
        "python-hwpx — HWPX 처리 (선택)": check_python_hwpx(),
        "hypua 옛한글 매핑 (5660건)": HYPUA_PATH.exists(),
        "AKS 구결자 매핑 (255건)": AKS_GUKYUL_PATH.exists(),
        "AKS 옛한글 카테고리 (5299건)": AKS_OLDHAN_PATH.exists(),
        "Unihan K source 한자 (10919건, 선택)": UNIHAN_KOREAN_PATH.exists(),
    }


def print_status(status: dict[str, bool]) -> None:
    print(colored("\n현재 설치 상태:", "bold"))
    for name, ok in status.items():
        mark = colored("✓", "green") if ok else colored("✗", "red")
        print(f"  {mark} {name}")


def _pip_install(package: str) -> bool:
    """지금 인터프리터(가상환경)에 pip install. --user 재시도는 하지 않는다 —
    그것이 시스템 파이썬 사용자 영역으로 새어 나가는 경로였다."""
    if not running_in_venv():
        print(colored("  ✗ 가상환경 밖에서는 설치하지 않는다(시스템 파이썬 보호) — setup.py를 다시 실행하면 .venv로 옮겨 간다",
                      "red"))
        return False
    try:
        return subprocess.call([sys.executable, "-m", "pip", "install", package]) == 0
    except Exception:
        return False


def step_pymupdf(auto: bool = True) -> bool:
    if check_pymupdf():
        print(colored("  ✓ 이미 설치됨", "green"))
        return True
    if not auto:
        print(colored("  ✗ 미설치. 수동 설치: pip install pymupdf", "yellow"))
        return False
    print(colored("  → pip install pymupdf 자동 실행", "cyan"))
    if _pip_install("pymupdf") and check_pymupdf():
        print(colored("  ✓ 설치 완료", "green"))
        return True
    print(colored("  ✗ 자동 설치 실패. 수동:  pip install pymupdf", "red"))
    return False


def step_python_hwpx(auto: bool = True) -> bool:
    if check_python_hwpx():
        print(colored("  ✓ 이미 설치됨", "green"))
        return True
    if not auto:
        print(colored("  ℹ 미설치 (HWPX 처리 시에만 필요): pip install python-hwpx",
                      "cyan"))
        return False
    print(colored("  → pip install python-hwpx 자동 실행 (HWPX 입력용)", "cyan"))
    if _pip_install("python-hwpx") and check_python_hwpx():
        print(colored("  ✓ 설치 완료", "green"))
        return True
    print(colored("  ⚠ python-hwpx 설치 실패 — HWPX 입력 시 다시 시도", "yellow"))
    return False


def step_hypua() -> bool:
    if HYPUA_PATH.exists():
        print(colored("  ✓ 이미 다운로드됨", "green"))
        return True
    print(f"  → {HYPUA_URL}")
    try:
        urllib.request.urlretrieve(HYPUA_URL, HYPUA_PATH)
        size = HYPUA_PATH.stat().st_size
        print(colored(f"  ✓ 다운로드 완료 ({size:,} bytes)", "green"))
        return True
    except Exception as e:
        print(colored(f"  ✗ 실패: {e}", "red"))
        return False


def step_aks_gukyul() -> bool:
    if AKS_GUKYUL_PATH.exists():
        print(colored("  ✓ 이미 다운로드됨", "green"))
        return True
    print("  → http://yoksa.aks.ac.kr/jsp/hh/gukyul.jsp 에서 표준 매핑 수집...")
    try:
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "fetch_aks_gukyul.py")],
            capture_output=True, text=True, encoding="utf-8")
        if result.returncode == 0:
            print(colored(f"  ✓ 완료", "green"))
            return True
        else:
            print(colored(f"  ✗ 실패: {result.stderr}", "red"))
            return False
    except Exception as e:
        print(colored(f"  ✗ 실패: {e}", "red"))
        return False


def step_aks_oldhan() -> bool:
    if AKS_OLDHAN_PATH.exists():
        print(colored("  ✓ 이미 다운로드됨", "green"))
        return True
    print("  → http://yoksa.aks.ac.kr/jsp/hh/oldhan.jsp 에서 표준 매핑 수집 (5분 정도 소요)...")
    try:
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "fetch_aks_oldhan.py")],
            capture_output=True, text=True, encoding="utf-8")
        if result.returncode == 0:
            print(colored(f"  ✓ 완료", "green"))
            return True
        else:
            print(colored(f"  ✗ 실패: {result.stderr}", "red"))
            return False
    except Exception as e:
        print(colored(f"  ✗ 실패: {e}", "red"))
        return False


def step_unihan() -> bool:
    if UNIHAN_KOREAN_PATH.exists():
        print(colored("  ✓ 이미 다운로드됨", "green"))
        return True
    print("  → https://www.unicode.org/Public/UCD/latest/ucd/Unihan.zip 다운로드 (8MB)...")
    try:
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "fetch_unihan_korean.py")],
            capture_output=True, text=True, encoding="utf-8")
        if result.returncode == 0:
            print(colored(f"  ✓ 완료", "green"))
            return True
        else:
            print(colored(f"  ✗ 실패: {result.stderr}", "red"))
            return False
    except Exception as e:
        print(colored(f"  ✗ 실패: {e}", "red"))
        return False


def run(cmd: list[str]) -> int:
    """다시 실행용. 테스트가 바꿔 끼울 수 있게 따로 둔다."""
    return subprocess.call(cmd)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="gugyeol-decode 1-step setup")
    parser.add_argument("--check", action="store_true",
                        help="현재 설치 상태만 확인")
    parser.add_argument("--skip-unihan", action="store_true",
                        help="Unihan 한국 source 한자(합자 구결 후보 풀) 건너뛰기")
    args = parser.parse_args(argv)

    # 시스템 파이썬으로 실행됐으면 스킬 .venv로 옮겨 가 같은 인자로 다시 돈다.
    # --check도 옮겨 간다 — 의존성은 .venv 쪽에 설치돼 있으므로 거기서 봐야 맞다.
    if not running_in_venv():
        py = ensure_venv()
        print(colored(f"  → {py} 로 다시 실행", "cyan"), flush=True)  # 자식 출력보다 먼저 보이게
        return run([str(py), str(Path(__file__).resolve()), *(sys.argv[1:] if argv is None else argv)])

    print(colored("=" * 60, "bold"))
    print(colored("gugyeol-decode setup", "bold"))
    print(colored("=" * 60, "bold"))

    if args.check:
        print_status(check_status())
        return 0

    print(colored("\n[1/4] PyMuPDF 확인 + 자동 설치 (PDF 입력용, 필수)", "cyan"))
    pymupdf_ok = step_pymupdf()
    if not pymupdf_ok:
        print(colored("\n→ pymupdf 설치 후 setup.py를 다시 실행하세요.", "yellow"))
        return 1

    print(colored("\n[1.5/4] python-hwpx 확인 + 자동 설치 (HWPX 입력용, 선택)", "cyan"))
    step_python_hwpx()

    print(colored("\n[2/4] hypua 옛한글 매핑 (kiwiyou/hypua, Unlicense)", "cyan"))
    step_hypua()

    print(colored("\n[3/4] AKS 구결자 매핑", "cyan"))
    step_aks_gukyul()

    print(colored("\n[3/4] AKS 옛한글 카테고리 매핑", "cyan"))
    step_aks_oldhan()

    if not args.skip_unihan:
        print(colored("\n[4/4] Unihan K source 한자 (합자 구결 후보 풀, 선택)", "cyan"))
        step_unihan()
    else:
        print(colored("\n[4/4] Unihan 건너뜀 (--skip-unihan)", "yellow"))

    print_status(check_status())

    print(colored("\n다음 단계 — 이 환경의 python으로 실행한다:", "bold"))
    print(colored(f"  {sys.executable} {SCRIPTS / 'decode.py'} <파일경로>     # PDF/HWPX/HWP 자동 분기",
                  "cyan"))
    print(colored("\n또는 GETTING_STARTED.md를 읽어보세요.", "bold"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
