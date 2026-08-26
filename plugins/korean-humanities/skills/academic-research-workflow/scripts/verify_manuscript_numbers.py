#!/usr/bin/env python3
"""원고-데이터 수치 정합 검증 (manuscript-data-consistency 자동화).

원고(HWP/HWPX/MD/TXT)의 수치를 정본 통계 JSON과 전수 대조한다.
체크리스트가 아니라 원고 전문이 검증 단위다.

- 정본 -> 원고: 정본의 보고 수치가 원고에 존재하는지 (갱신 누락 검출)
- 구버전 -> 원고: --old JSON에만 있는 수치가 원고에 남았는지 (구버전 잔존 검출)

사용 (Windows는 py 런처):
  py verify_manuscript_numbers.py 원고.hwp --stats results/final_stats.json
  py verify_manuscript_numbers.py 원고.hwp --stats 정본.json --old archive/구버전.json --report 대조표.md

종료 코드: 0 통과(또는 누락 경고만) / 1 구버전 잔존 발견 / 3 입력 오류
의존성: 표준 라이브러리. HWP 입력만 olefile 필요(pip install olefile).
"""
from __future__ import annotations

import argparse
import html
import json
import re
import struct
import sys
import zipfile
import zlib
from pathlib import Path

# CJK 텍스트 계약 E3: Windows 콘솔 기본 cp949에서 한글·한자 출력이
# UnicodeEncodeError로 죽는 것을 막는다 (환경변수에 의존하지 않는 방어선).
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

# HWP 5.0 본문 레코드의 인라인/확장 컨트롤 문자 (8 wchar 점유)
_INLINE = {4, 5, 6, 7, 8, 9, 19, 20}
_EXTENDED = {1, 2, 3, 11, 12, 14, 15, 16, 17, 18, 21, 22, 23}
_HWPTAG_PARA_TEXT = 67


def _extract_hwp(path: Path) -> str:
    try:
        import olefile
    except ImportError:
        sys.exit("HWP 입력에는 olefile이 필요합니다: pip install olefile")
    ole = olefile.OleFileIO(str(path))
    compressed = ole.openstream("FileHeader").read()[36] & 1
    sections = sorted(
        "/".join(e) for e in ole.listdir() if e[0] == "BodyText"
    )
    out: list[str] = []
    for name in sections:
        data = ole.openstream(name).read()
        if compressed:
            data = zlib.decompress(data, -15)
        i, n = 0, len(data)
        while i + 4 <= n:
            (hdr,) = struct.unpack_from("<I", data, i)
            i += 4
            tag = hdr & 0x3FF
            size = (hdr >> 20) & 0xFFF
            if size == 0xFFF:
                (size,) = struct.unpack_from("<I", data, i)
                i += 4
            payload = data[i : i + size]
            i += size
            if tag != _HWPTAG_PARA_TEXT:
                continue
            j = 0
            while j + 2 <= len(payload):
                (ch,) = struct.unpack_from("<H", payload, j)
                if ch in _EXTENDED or ch in _INLINE:
                    j += 16
                    continue
                if ch in (10, 13):
                    out.append("\n")
                elif ch >= 32:
                    out.append(chr(ch))
                j += 2
        out.append("\n")
    return "".join(out)


def _extract_hwpx(path: Path) -> str:
    out = []
    with zipfile.ZipFile(path) as z:
        for name in sorted(z.namelist()):
            if re.search(r"Contents/section\d+\.xml$", name):
                xml = z.read(name).decode("utf-8", errors="replace")
                out.append(html.unescape(re.sub(r"<[^>]+>", "\n", xml)))
    return "\n".join(out)


def extract_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".hwp":
        return _extract_hwp(path)
    if suffix == ".hwpx":
        return _extract_hwpx(path)
    return path.read_text(encoding="utf-8-sig", errors="replace")


def collect_numbers(obj, prefix: str = "", min_int: int = 10) -> dict[str, set[str]]:
    """JSON에서 보고 수치 토큰을 수집한다. token -> {key paths}."""
    found: dict[str, set[str]] = {}

    def visit(node, path):
        if isinstance(node, bool):
            return
        if isinstance(node, int):
            if abs(node) >= min_int:
                found.setdefault(str(node), set()).add(path)
        elif isinstance(node, float):
            if 0.001 <= abs(node):
                found.setdefault(repr(node) if node != int(node) else str(node), set()).add(path)
        elif isinstance(node, dict):
            for k, v in node.items():
                visit(v, f"{path}.{k}" if path else str(k))
        elif isinstance(node, list):
            for idx, v in enumerate(node):
                visit(v, f"{path}[{idx}]")

    visit(obj, prefix)
    return found


def token_in_text(token: str, flat: str) -> bool:
    """숫자 경계를 지켜 토큰 존재를 확인한다 (0.21이 0.219에 매칭되지 않게)."""
    return re.search(rf"(?<![\d.]){re.escape(token)}(?![\d.])", flat) is not None


def digit_count(token: str) -> int:
    return sum(c.isdigit() for c in token)


def load_json(path: Path):
    with open(path, encoding="utf-8-sig") as f:
        return json.load(f)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="원고-데이터 수치 정합 검증")
    ap.add_argument("manuscript", help="원고 파일 (.hwp/.hwpx/.md/.txt)")
    ap.add_argument("--stats", nargs="+", required=True, help="정본 통계 JSON (복수 가능)")
    ap.add_argument("--old", nargs="*", default=[], help="구버전 JSON — 잔존 검출용")
    ap.add_argument("--min-int", type=int, default=10, help="정수 최소 절대값 (노이즈 컷)")
    ap.add_argument("--min-digits-stale", type=int, default=3,
                    help="구버전 잔존 판정에 요구하는 최소 자릿수")
    ap.add_argument("--report", help="대조표 markdown 출력 경로")
    args = ap.parse_args(argv)

    ms_path = Path(args.manuscript)
    if not ms_path.exists():
        print(f"원고 없음: {ms_path}")
        return 3
    text = extract_text(ms_path)
    flat = text.replace(",", "")
    print(f"원고 추출: {ms_path.name} ({len(text):,}자)")

    canon: dict[str, set[str]] = {}
    for p in args.stats:
        for tok, paths in collect_numbers(load_json(Path(p)), Path(p).name, args.min_int).items():
            canon.setdefault(tok, set()).update(paths)

    missing = {t: ps for t, ps in canon.items() if not token_in_text(t, flat)}
    present_n = len(canon) - len(missing)
    print(f"정본 토큰 {len(canon)}개 중 원고 존재 {present_n} / 누락 {len(missing)}")

    stale: dict[str, set[str]] = {}
    if args.old:
        old_tokens: dict[str, set[str]] = {}
        for p in args.old:
            for tok, paths in collect_numbers(load_json(Path(p)), Path(p).name, args.min_int).items():
                old_tokens.setdefault(tok, set()).update(paths)
        for tok, paths in old_tokens.items():
            if tok in canon or digit_count(tok) < args.min_digits_stale:
                continue
            if token_in_text(tok, flat):
                stale[tok] = paths
        print(f"구버전 전용 토큰 중 원고 잔존: {len(stale)}")

    lines = ["# 원고-데이터 정합 대조표", "",
             f"원고: {ms_path.name} / 정본: {', '.join(args.stats)}", ""]
    if stale:
        lines += ["## 구버전 잔존 (정정 필수)", "", "| 값 | 구버전 출처 |", "|---|---|"]
        for tok in sorted(stale, key=digit_count, reverse=True):
            lines.append(f"| {tok} | {sorted(stale[tok])[0]} 외 {len(stale[tok])-1} |"
                         if len(stale[tok]) > 1 else f"| {tok} | {sorted(stale[tok])[0]} |")
        lines.append("")
    if missing:
        lines += ["## 정본 수치 원고 누락 (검토 — 미보고 항목일 수 있음)", "",
                  "| 값 | 정본 위치 |", "|---|---|"]
        for tok in sorted(missing, key=digit_count, reverse=True)[:200]:
            lines.append(f"| {tok} | {sorted(missing[tok])[0]} |")
        lines.append("")
    lines.append(f"판정: {'구버전 잔존 — 정정 필요' if stale else '구버전 잔존 없음'}"
                 f" / 누락 {len(missing)}건은 보고 범위 여부를 확인할 것")

    if args.report:
        Path(args.report).write_text("\n".join(lines), encoding="utf-8")
        print(f"대조표: {args.report}")
    else:
        for tok in sorted(stale, key=digit_count, reverse=True):
            print(f"  [구버전 잔존] {tok}  <- {sorted(stale[tok])[0]}")
        for tok in sorted(missing, key=digit_count, reverse=True)[:30]:
            print(f"  [정본 누락] {tok}  <- {sorted(missing[tok])[0]}")

    return 1 if stale else 0


if __name__ == "__main__":
    raise SystemExit(main())
