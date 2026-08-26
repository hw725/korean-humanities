#!/usr/bin/env python3
"""
gugyeol-decode — Step 3: 매핑 테이블을 적용해 PDF 본문을 정규화

PDF를 다시 글리프 단위로 추출하면서, mapping.json에 정의된 PUA 글자를
표준 Unicode (옛한글 자모 결합 / 구결자 모자 등)로 치환한다.

자동 처리:
  - PUA 매핑 적용
  - 같은 codepoint이지만 폰트가 다른 경우 폰트 무시 fallback (잔존 PUA 최소화)
  - NFC 정규화 (CJK Compatibility Ideographs U+F900-FAFF → 표준 한자)
    NFC는 canonical equivalence만 처리하므로 학술 텍스트에 안전. NFKC는
    halfwidth/fullwidth, ligature 등도 변환하므로 의도치 않은 변경 가능성 존재.

사용법:
  python scripts/apply_mapping.py <PDF경로> <mapping.json> [--out <output.md>] [--mode value|modern|both] [--no-normalize]

--mode:
  value  : 표준 Unicode form 우선 (예: ᄒᆞ, 厓)
  modern : 현대 한글 form 우선 (예: 하, ㄱ)
  both   : "value(modern)" 형태로 둘 다 표기 (기본)

--no-normalize:
  NFC 정규화 건너뛰기 (디버깅 등 원본 그대로 보존이 필요한 경우)
"""
from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="매핑 테이블 적용 → 정규화 텍스트")
    parser.add_argument("pdf", type=Path, help="입력 PDF 경로")
    parser.add_argument("mapping", type=Path, help="mapping.json 경로")
    parser.add_argument("--out", type=Path, default=None,
                        help="출력 .md 경로 (기본: <pdf>.normalized.md)")
    parser.add_argument("--mode", choices=["value", "modern", "both"],
                        default="both", help="치환 방식")
    parser.add_argument("--no-normalize", action="store_true",
                        help="NFC 정규화 건너뛰기 (기본은 적용)")
    args = parser.parse_args()

    try:
        import fitz
    except ImportError:
        print("ERROR: PyMuPDF가 필요합니다. 설치: pip install pymupdf", file=sys.stderr)
        return 1

    if not args.pdf.exists():
        print(f"ERROR: PDF 없음: {args.pdf}", file=sys.stderr)
        return 1
    if not args.mapping.exists():
        print(f"ERROR: mapping 없음: {args.mapping}", file=sys.stderr)
        return 1

    mapping_data = json.loads(args.mapping.read_text(encoding="utf-8"))
    raw_mappings = mapping_data.get("mappings", {})

    # key 형식 "font|HEX" → (codepoint, font) 룩업
    lookup: dict[tuple[int, str], dict] = {}
    # 같은 codepoint의 임의 매핑 (폰트가 다르더라도 같은 글자라면 fallback)
    cp_fallback: dict[int, dict] = {}
    for key, val in raw_mappings.items():
        if "|" not in key:
            continue
        font, hex_str = key.rsplit("|", 1)
        try:
            cp = int(hex_str, 16)
        except ValueError:
            continue
        lookup[(cp, font)] = val
        # 같은 codepoint의 첫 매핑을 fallback으로 저장
        if cp not in cp_fallback:
            cp_fallback[cp] = val
        # 단 다른 매핑값이 있으면 conflict 표시 (사용자 검토용)
        elif cp_fallback[cp].get("value") != val.get("value"):
            cp_fallback[cp] = {"_conflict": True, **val}

    out_path = args.out or args.pdf.with_suffix(".normalized.md")

    doc = fitz.open(args.pdf)
    output_lines: list[str] = []
    unmapped_warnings: list[str] = []

    for page_idx, page in enumerate(doc):
        text_dict = page.get_text("dict")
        output_lines.append(f"\n## Page {page_idx + 1}\n")
        for block in text_dict.get("blocks", []):
            if "lines" not in block:
                continue
            for line in block["lines"]:
                buf: list[str] = []
                for span in line["spans"]:
                    text = span.get("text", "")
                    font = span.get("font", "")
                    for ch in text:
                        cp = ord(ch)
                        if 0xE000 <= cp <= 0xF8FF:
                            entry = lookup.get((cp, font))
                            # fallback: 폰트는 다르지만 같은 codepoint의 매핑 사용
                            if entry is None:
                                fallback = cp_fallback.get(cp)
                                if fallback and not fallback.get("_conflict"):
                                    entry = fallback
                                    unmapped_warnings.append(
                                        f"page {page_idx + 1}: U+{cp:04X} font={font} "
                                        f"(폰트 무시 fallback 적용)")
                            if entry is None:
                                buf.append(f"⟨U+{cp:04X}?⟩")
                                unmapped_warnings.append(
                                    f"page {page_idx + 1}: U+{cp:04X} font={font} (매핑 없음)")
                            else:
                                value = entry.get("value", "")
                                modern = entry.get("modern", "")
                                if args.mode == "value":
                                    buf.append(value or modern or f"⟨U+{cp:04X}⟩")
                                elif args.mode == "modern":
                                    buf.append(modern or value or f"⟨U+{cp:04X}⟩")
                                else:  # both
                                    if value and modern and value != modern:
                                        buf.append(f"{value}({modern})")
                                    else:
                                        buf.append(value or modern or f"⟨U+{cp:04X}⟩")
                        else:
                            buf.append(ch)
                output_lines.append("".join(buf))

    final_text = "\n".join(output_lines)

    # 2차 패스: 본문 단계에서 잔존 PUA가 남아 있으면 codepoint 단독으로 다시 매핑.
    # 글리프 단계에서 (font, codepoint) lookup을 미스해 빠져나간 케이스를 잡는다.
    leftover_before = sum(1 for c in final_text if 0xE000 <= ord(c) <= 0xF8FF)
    if leftover_before > 0:
        def _format_entry(entry: dict) -> str:
            value = entry.get("value", "")
            modern = entry.get("modern", "")
            if args.mode == "value":
                return value or modern or ""
            elif args.mode == "modern":
                return modern or value or ""
            else:  # both
                if value and modern and value != modern:
                    return f"{value}({modern})"
                return value or modern or ""

        replaced = 0
        for cp, entry in cp_fallback.items():
            if entry.get("_conflict"):
                continue
            ch = chr(cp)
            if ch in final_text:
                replacement = _format_entry(entry)
                if replacement:
                    count_before = final_text.count(ch)
                    final_text = final_text.replace(ch, replacement)
                    replaced += count_before
        leftover_after = sum(1 for c in final_text if 0xE000 <= ord(c) <= 0xF8FF)
        if replaced:
            print(f"  2차 PUA sweep (codepoint 단독): {replaced}회 추가 매핑 적용"
                  + (f" → {leftover_after}회 잔존" if leftover_after else " → 잔존 0"))

    # NFC 정규화: CJK Compatibility Ideographs (U+F900-FAFF) → 표준 한자
    # NFC는 canonical equivalence만 처리하므로 학술 텍스트에 안전
    if not args.no_normalize:
        # CJK Compat 통계 (변환 전)
        compat_chars = [c for c in final_text if 0xF900 <= ord(c) <= 0xFAFF]
        if compat_chars:
            unique_compat = len(set(compat_chars))
            normalized = unicodedata.normalize("NFC", final_text)
            # 변환 효과 측정
            remain = sum(1 for c in normalized if 0xF900 <= ord(c) <= 0xFAFF)
            converted = len(compat_chars) - remain
            print(f"  NFC 정규화: CJK Compatibility {unique_compat}종, "
                  f"{len(compat_chars)}회 등장 → {converted}회 표준 한자로 변환"
                  + (f" ({remain}회 잔존)" if remain else ""))
            final_text = normalized
        else:
            # 다른 NFC 변환 사항이 있을 수 있으므로 그래도 적용
            final_text = unicodedata.normalize("NFC", final_text)

    out_path.write_text(final_text, encoding="utf-8")
    print(f"저장: {out_path}")
    print(f"  매핑 적용 글자 수: {len(lookup)} 종류")
    print(f"  미매핑 (occurrence): {len(unmapped_warnings)}")
    if unmapped_warnings:
        print("  처음 5개 미매핑:")
        for w in unmapped_warnings[:5]:
            print(f"    {w}")
    doc.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
