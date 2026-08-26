#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""korean-humanities 슈트의 CJK 텍스트 처리 계약 기계 검사기.

계약 (정본: skills/hanmun-research-assistant/SKILL.md «CJK Text Handling Contract»):
  E1  builtins.open() 텍스트 모드 호출에 encoding= 명시 의무.
      Windows에서 미명시 기본값은 locale(cp949)이라 한자·옛한글이 조용히 깨진다.
  E2  Path.read_text()/write_text()에 encoding= 명시 의무 (같은 이유).
  E3  한글·한자를 출력하는 스크립트는 stdout/stderr를 UTF-8로 재설정해야 한다.
      Windows 콘솔 기본이 cp949라 argparse 도움말·print의 em dash나 한자에서
      UnicodeEncodeError로 죽는다(2026-08-26 실측). 진입점에
      sys.stdout.reconfigure(encoding="utf-8", errors="replace")를 둔다.
  R1  CJK 문자(한자·한글·옛한글 자모·PUA)를 포함한 패턴을 stdlib `re`로 매칭 금지
      — `regex` 모듈로 \\p{Han}·\\p{Hangul} 프로퍼티를 쓴다. stdlib `re`는 유니코드
      프로퍼티 미지원이라 [가-힣] 하드코딩이 옛한글(U+1100 첫가끝)·한자 확장
      (U+20000+)을 놓친다. ASCII 구조 패턴(태그·ID·공백·파일명 새니타이즈)은 허용.

용법:
  py -3 scripts/check_cjk_text_contract.py <dir> [<dir> ...] [--json]

exit 0 = 위반 없음, exit 2 = 위반 있음, exit 1 = 사용 오류.
AST 기반이라 여러 줄 호출도 정확히 본다 (grep 과다 계상 방지 — 2026-08-26 실측 교훈).
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

# CJK 판정 범위: 한자(+확장 B~), 한글 음절, 첫가끝 자모, 호환 자모, PUA(구결·옛한글 관행 영역)
_CJK_RANGES = (
    (0x1100, 0x11FF),    # 첫가끝 자모
    (0x3130, 0x318F),    # 호환 자모
    (0x3400, 0x4DBF),    # 한자 확장 A
    (0x4E00, 0x9FFF),    # 한자 기본
    (0xA960, 0xA97F),    # 첫가끝 확장 A
    (0xAC00, 0xD7A3),    # 한글 음절
    (0xD7B0, 0xD7FF),    # 첫가끝 확장 B
    (0xE000, 0xF8FF),    # PUA (한양 PUA 구결·옛한글)
    (0xF900, 0xFAFF),    # 한자 호환
    (0x20000, 0x2FA1F),  # 한자 확장 B~F·호환 보충
)

_RE_FUNCS = {"compile", "search", "match", "fullmatch", "sub", "subn",
             "findall", "finditer", "split"}
_TEXT_RW = {"read_text", "write_text"}


def _has_cjk(s: str) -> bool:
    return any(any(lo <= ord(ch) <= hi for lo, hi in _CJK_RANGES) for ch in s)


def _kw(call: ast.Call, name: str) -> bool:
    return any(k.arg == name for k in call.keywords)


def _mode_of_open(call: ast.Call) -> str:
    for k in call.keywords:
        if k.arg == "mode" and isinstance(k.value, ast.Constant) and isinstance(k.value.value, str):
            return k.value.value
    if len(call.args) >= 2 and isinstance(call.args[1], ast.Constant) and isinstance(call.args[1].value, str):
        return call.args[1].value
    return "r"


def check_file(path: Path) -> list[dict]:
    try:
        src = path.read_text(encoding="utf-8")
        tree = ast.parse(src)
    except (SyntaxError, UnicodeDecodeError) as e:
        return [{"file": str(path), "line": getattr(e, "lineno", 0) or 0,
                 "rule": "PARSE", "msg": f"파싱 실패: {e.__class__.__name__}"}]

    rows: list[dict] = []

    # E3: 한글·한자를 출력하는 실행 스크립트인데 stdout 재설정이 없음.
    # 대상은 __main__ 진입점이 있는 파일만 — import 전용 모듈은 출력 주체가 아니다.
    if "__main__" in src and _has_cjk(src):
        if not re.search(r"reconfigure\s*\(\s*encoding", src) and "PYTHONIOENCODING" not in src:
            rows.append({"file": str(path), "line": 1, "rule": "E3",
                         "msg": "한글·한자 출력 스크립트인데 stdout/stderr UTF-8 재설정이 없음 "
                                "(Windows cp949 콘솔에서 UnicodeEncodeError)"})

    imports_stdlib_re = any(
        (isinstance(n, ast.Import) and any(a.name == "re" for a in n.names))
        or (isinstance(n, ast.ImportFrom) and n.module == "re")
        for n in ast.walk(tree)
    )

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        # E1: 내장 open() — 텍스트 모드인데 encoding 없음
        if isinstance(node.func, ast.Name) and node.func.id == "open":
            if "b" not in _mode_of_open(node) and not _kw(node, "encoding"):
                rows.append({"file": str(path), "line": node.lineno, "rule": "E1",
                             "msg": "open() 텍스트 모드에 encoding= 없음 (Windows 기본 cp949)"})

        if isinstance(node.func, ast.Attribute):
            # E2: read_text/write_text — encoding 없음
            if node.func.attr in _TEXT_RW and not _kw(node, "encoding"):
                rows.append({"file": str(path), "line": node.lineno, "rule": "E2",
                             "msg": f"{node.func.attr}()에 encoding= 없음"})
            # E1(attr): <expr>.open(...) — Path.open은 mode가 **첫 인자**다 (내장 open과 다름).
            # zipfile member open(z.open(name))처럼 첫 인자가 모드 문자열이 아니면
            # 판정 불가로 보고 건너뛴다 — 오탐이 위반 놓침보다 해롭다(2026-08-26 실측:
            # z.open(member)·path.open("rb")를 내장 open 규칙으로 읽어 둘 다 오탐).
            if node.func.attr == "open" and not _kw(node, "encoding"):
                mode = None
                for k in node.keywords:
                    if k.arg == "mode" and isinstance(k.value, ast.Constant) and isinstance(k.value.value, str):
                        mode = k.value.value
                if mode is None and node.args:
                    a0 = node.args[0]
                    if isinstance(a0, ast.Constant) and isinstance(a0.value, str) and a0.value and all(c in "rwxab+tU" for c in a0.value):
                        mode = a0.value
                    else:
                        mode = "?"  # 모드 아님(zipfile member 등) — 판정 불가
                if mode is None:
                    mode = "r"  # Path.open() 무인자 = 텍스트 기본
                if mode != "?" and "b" not in mode:
                    rows.append({"file": str(path), "line": node.lineno, "rule": "E1",
                                 "msg": ".open() 텍스트 모드에 encoding= 없음"})

            # R1: re.<func>(CJK 포함 패턴)
            if (imports_stdlib_re and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "re" and node.func.attr in _RE_FUNCS):
                if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                    if _has_cjk(node.args[0].value):
                        rows.append({"file": str(path), "line": node.lineno, "rule": "R1",
                                     "msg": "CJK 포함 패턴을 stdlib re로 매칭 — regex 모듈의 \\p{Han}/\\p{Hangul}로 전환"})
    return rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="CJK 텍스트 처리 계약 검사기")
    ap.add_argument("paths", nargs="+", type=Path)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    files: list[Path] = []
    for p in args.paths:
        if p.is_file() and p.suffix == ".py":
            files.append(p)
        elif p.is_dir():
            files.extend(f for f in sorted(p.rglob("*.py"))
                         if ".venv" not in f.parts and "__pycache__" not in f.parts)
    if not files:
        print("[에러] 검사할 .py 없음", file=sys.stderr)
        return 1

    all_rows: list[dict] = []
    for f in files:
        all_rows.extend(check_file(f))

    if args.json:
        print(json.dumps({"files": len(files), "violations": all_rows}, ensure_ascii=False, indent=2))
    else:
        for r in all_rows:
            print(f"{r['rule']}  {r['file']}:{r['line']}  {r['msg']}")
        print(f"-- {len(files)} files, {len(all_rows)} violation(s)")
    return 2 if all_rows else 0


if __name__ == "__main__":
    raise SystemExit(main())
