#!/usr/bin/env python3
"""
gugyeol-decode — Step 1: PDF에서 PUA(Private Use Area) 글자 추출

PyMuPDF로 글리프 단위 추출하여 0xE000-0xF8FF 영역 글자를 모은다.
각 (codepoint, font) 조합당 첫 등장 위치를 PNG로 잘라 저장 + 컨텍스트 라인.

사용법:
  python scripts/extract_pua.py <PDF경로> [--out <출력디렉터리>] [--dpi 5]

기본 출력 디렉터리: <PDF경로 부모>/_pua/
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
GUKYUL_CACHE = SKILL_ROOT / "reference" / "aks_gukyul_pua.json"
OLDHAN_CACHE = SKILL_ROOT / "reference" / "aks_oldhan_pua.json"
HAPJA_REF = SKILL_ROOT / "reference" / "hapja_kugyeol.json"
HYPUA_TABLE = SKILL_ROOT / "reference" / "hypua_table.csv"


def _load_hypua_table() -> dict[int, str]:
    """hypua (kiwiyou/hypua, Unlicense) 한양 PUA → IPF jamo 결합형 매핑.

    Format: PUA_HEX,JAMO_HEX&JAMO_HEX[&JAMO_HEX]
    """
    mapping: dict[int, str] = {}
    if not HYPUA_TABLE.exists():
        return mapping
    for line in HYPUA_TABLE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or "," not in line:
            continue
        try:
            pua_hex, jamo_seq = line.split(",", 1)
            cp = int(pua_hex, 16)
            jamo = "".join(chr(int(x, 16)) for x in jamo_seq.split("&"))
            mapping[cp] = jamo
        except ValueError:
            pass
    return mapping


def _load_aks_caches() -> tuple[dict, dict]:
    """AKS 캐시 로드 (없으면 빈 dict). PUA → 라벨 매핑."""
    gukyul: dict[str, dict] = {}
    oldhan: dict[str, dict] = {}
    if GUKYUL_CACHE.exists():
        d = json.loads(GUKYUL_CACHE.read_text(encoding="utf-8"))
        gukyul = d.get("pua_to_sound", {})
    if OLDHAN_CACHE.exists():
        d = json.loads(OLDHAN_CACHE.read_text(encoding="utf-8"))
        oldhan = d.get("pua_to_label", {})
    return gukyul, oldhan


def _resolve_sound(sound: str, gukyul: dict, depth: int = 0) -> str:
    """sound 자체가 PUA 글자라면 한 단계 더 lookup. 최대 2단계 재귀."""
    if not sound or depth >= 2:
        return sound
    pua_count = sum(1 for ch in sound if 0xE000 <= ord(ch) <= 0xF8FF)
    if pua_count == 0:
        return sound
    # 첫 PUA 글자의 lookup 시도
    for ch in sound:
        cp = ord(ch)
        if 0xE000 <= cp <= 0xF8FF:
            key = f"U+{cp:04X}"
            inner = gukyul.get(key)
            if inner:
                return _resolve_sound(inner["sound"], gukyul, depth + 1)
    return sound


def main() -> int:
    parser = argparse.ArgumentParser(description="PDF에서 PUA 글자 추출 + 컨텍스트 PNG 저장")
    parser.add_argument("pdf", type=Path, help="입력 PDF 경로")
    parser.add_argument("--out", type=Path, default=None,
                        help="출력 디렉터리 (기본: <pdf부모>/_pua/)")
    parser.add_argument("--dpi", type=float, default=5.0,
                        help="PNG 렌더링 매트릭스 배율 (5x=고해상도, 기본 5)")
    parser.add_argument("--context-chars", type=int, default=120,
                        help="컨텍스트 라인 잘라낼 길이")
    parser.add_argument("--scan-hapja", action="store_true",
                        help="합자 구결자(reference/hapja_kugyeol.json) 등장 여부도 추가 보고")
    args = parser.parse_args()

    try:
        import fitz  # PyMuPDF
    except ImportError:
        print("ERROR: PyMuPDF가 필요합니다. 설치: pip install pymupdf", file=sys.stderr)
        return 1

    pdf_path = args.pdf.resolve()
    if not pdf_path.exists():
        print(f"ERROR: PDF 없음: {pdf_path}", file=sys.stderr)
        return 1

    out_dir = (args.out or pdf_path.parent / "_pua").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(pdf_path)
    print(f"PDF: {pdf_path.name}  ({len(doc)} pages)")

    # (codepoint, font) -> (page_idx, line_bbox, context)
    found: dict[tuple[int, str], tuple[int, tuple, str]] = {}
    # 전체 등장 빈도 (보고용)
    counter: Counter = Counter()

    for page_idx, page in enumerate(doc):
        text_dict = page.get_text("dict")
        for block in text_dict.get("blocks", []):
            if "lines" not in block:
                continue
            for line in block["lines"]:
                line_text = "".join(span.get("text", "") for span in line["spans"])
                for span in line["spans"]:
                    text = span.get("text", "")
                    font = span.get("font", "")
                    for ch in text:
                        cp = ord(ch)
                        if 0xE000 <= cp <= 0xF8FF:
                            key = (cp, font)
                            counter[key] += 1
                            if key not in found:
                                found[key] = (page_idx, tuple(line["bbox"]),
                                              line_text[:args.context_chars])

    print(f"\n발견된 고유 PUA: {len(found)}개 (codepoint × font)")
    print(f"전체 등장 횟수: {sum(counter.values())}")

    # 상위 빈도 보고
    if counter:
        print("\n빈도 상위 10:")
        for (cp, font), n in counter.most_common(10):
            print(f"  U+{cp:04X}  {font[:30]:30s}  {n}회")

    # 각 PUA 첫 등장 라인 PNG 저장
    print(f"\nPNG 저장 → {out_dir}")
    matrix = fitz.Matrix(args.dpi, args.dpi)
    pad = 3
    saved_lines = []
    for (cp, font), (page_idx, line_bbox, ctx) in sorted(found.items()):
        page = doc[page_idx]
        rect = fitz.Rect(line_bbox[0] - pad, line_bbox[1] - pad,
                         line_bbox[2] + pad, line_bbox[3] + pad)
        pix = page.get_pixmap(matrix=matrix, clip=rect)
        safe_font = re.sub(r'[\\/*?:"<>|]', "_", font)[:20]
        fname = f"U{cp:04X}_p{page_idx + 1:02d}_{safe_font}.png"
        pix.save(out_dir / fname)
        saved_lines.append(
            f"U+{cp:04X}  font={font}  page={page_idx + 1}  freq={counter[(cp, font)]}\n"
            f"  → {fname}\n"
            f"  ctx: {ctx}"
        )

    contexts_md = "\n\n".join(saved_lines)
    (out_dir / "_contexts.txt").write_text(contexts_md, encoding="utf-8")

    # AKS 캐시 + hypua 테이블 로드 (있으면 자동 prefill)
    gukyul_cache, oldhan_cache = _load_aks_caches()
    hypua_table = _load_hypua_table()
    auto_filled = 0
    hypua_filled = 0

    # 매핑 테이블 스켈레톤 생성 (AKS + hypua 매핑이 있으면 자동 채움)
    keys = sorted(found.keys())
    skeleton = {
        "_doc": "gugyeol-decode mapping. hypua/AKS에서 자동 채운 항목은 verified=true. 나머지는 시각 판독 후 type/value/modern 입력.",
        "_hypua_loaded": bool(hypua_table),
        "_aks_gukyul_loaded": bool(gukyul_cache),
        "_aks_oldhan_loaded": bool(oldhan_cache),
        "font_aliases": {},
        "mappings": {},
        "verified_by": "",
        "verified_at": "",
        "pdf": pdf_path.name,
    }
    for cp, font in keys:
        key = f"{font}|{cp:04X}"
        cp_hex = f"U+{cp:04X}"
        entry = {"type": "<old_hangul|kugyeol|other|unknown>",
                 "value": "", "unicode": "", "modern": "", "note": ""}

        # 폰트 휴리스틱 (mojibake 폰트명도 처리)
        font_lower = font.lower()
        is_myeongjo = ("명조" in font or "Hancom" in font or
                       "¸íÁ¶" in font or "myeongjo" in font_lower)
        if is_myeongjo:
            entry["type"] = "kugyeol"
        elif font.startswith("TT70"):
            entry["type"] = "old_hangul"

        # 1순위: hypua (한양 PUA → IPF Unicode jamo) ⭐ 가장 정확
        ipf = hypua_table.get(cp)
        if ipf:
            entry["type"] = "old_hangul"
            entry["value"] = ipf  # 표준 Unicode jamo 결합 (예: ᄒᆞ)
            entry["unicode"] = "U+" + "+U+".join(f"{ord(c):04X}" for c in ipf)
            entry["note"] = f"hypua (kiwiyou/hypua) auto-mapped to IPF"
            entry["hypua_verified"] = True
            hypua_filled += 1

        # 2순위: AKS 구결자 (hypua가 못 잡으면)
        gk = gukyul_cache.get(cp_hex)
        if gk and entry["type"] == "kugyeol" and not ipf:
            sound = gk["sound"]
            resolved = _resolve_sound(sound, gukyul_cache)
            entry["value"] = sound
            entry["modern"] = resolved
            entry["note"] = (f"AKS gukyul pcd={gk['pcd']}" +
                             (f", resolved sound: {resolved}" if resolved != sound else ""))
            entry["aks_verified"] = True
            auto_filled += 1
        # 3순위: AKS 옛한글 카테고리만 (hypua 미수록 옛한글)
        elif oldhan_cache.get(cp_hex) and entry["type"] == "old_hangul" and not ipf:
            oh = oldhan_cache[cp_hex]
            entry["note"] = f"AKS oldhan pcd={oh['pcd']} (대표 라벨: {oh['label']}) — 시각 판독 필요"
            entry["aks_category_only"] = True

        skeleton["mappings"][key] = entry

    (out_dir / "mapping_skeleton.json").write_text(
        json.dumps(skeleton, ensure_ascii=False, indent=2), encoding="utf-8")
    if hypua_table:
        print(f"\nhypua 자동 채움: 옛한글 {hypua_filled}건 verified (PUA → IPF Unicode jamo)")
    if gukyul_cache:
        print(f"AKS 자동 채움: 구결자 {auto_filled}건 verified")
    if oldhan_cache:
        unmapped_oh = sum(1 for k, v in skeleton["mappings"].items()
                          if v.get("aks_category_only"))
        if unmapped_oh:
            print(f"AKS 카테고리만: 옛한글 {unmapped_oh}건 (hypua 미수록, 시각 판독 필요)")

    # 합자 구결자 옵션 스캔 (PDF 본문에 표준 Unicode 합자/한국 source 한자가 등장하는지)
    if args.scan_hapja:
        # 1순위: 검증된 합자 구결자 (hapja_kugyeol.json)
        if HAPJA_REF.exists():
            hapja_data = json.loads(HAPJA_REF.read_text(encoding="utf-8"))
            hapja_chars = {entry["char"]: (key, entry)
                           for key, entry in hapja_data.get("characters", {}).items()}
            if hapja_chars:
                print(f"\n합자 구결자 스캔 (검증 {len(hapja_chars)}종):")
                hapja_hits: dict[str, list[int]] = {}
                for page_idx in range(len(doc)):
                    page_text = doc[page_idx].get_text("text")
                    for char in hapja_chars:
                        if char in page_text:
                            hapja_hits.setdefault(char, []).append(page_idx + 1)
                if hapja_hits:
                    for char, pages in hapja_hits.items():
                        key, entry = hapja_chars[char]
                        print(f"  {char} ({key}, {entry['sound']}): pages {pages[:5]}"
                              + (f" +{len(pages)-5}" if len(pages) > 5 else ""))
                else:
                    print(f"  검증된 합자 구결자 미발견.")

        # 2순위: 한국 source 한자 (Unihan K2~K6 후보 풀)
        UNIHAN_KOREAN = SKILL_ROOT / "reference" / "unihan_korean.json"
        if UNIHAN_KOREAN.exists():
            print(f"  Unihan 한국 source 한자(K2~K6) 후보 스캔 중...")
            unihan = json.loads(UNIHAN_KOREAN.read_text(encoding="utf-8"))
            korean_chars = {v["char"]: (k, v) for k, v in unihan.get("characters", {}).items()}
            korean_hits: dict[str, list[int]] = {}
            for page_idx in range(len(doc)):
                page_text = doc[page_idx].get_text("text")
                for ch in set(page_text):
                    if ch in korean_chars:
                        korean_hits.setdefault(ch, []).append(page_idx + 1)
            if korean_hits:
                print(f"  Unihan K2~K6 한국 source 한자 {len(korean_hits)}종 발견:")
                # 상위 10개만 보고 (전체는 mapping_skeleton에 추가됨)
                for ch, pages in list(korean_hits.items())[:10]:
                    key, info = korean_chars[ch]
                    src = info.get("k_source", "")
                    rd = info.get("korean_reading", "") or info.get("definition", "")[:30]
                    print(f"    {ch} ({key}, {src}): pages {pages[:3]}, 한국음/뜻: {rd!r}")
                if len(korean_hits) > 10:
                    print(f"    ... 외 {len(korean_hits)-10}종")
                print(f"  → 합자 구결자 가능성. 학술 reference로 검증 후 hapja_kugyeol.json에 등록 권장.")
            else:
                print(f"  Unihan K2~K6 한국 source 한자 미발견.")

    print(f"\n완료. 다음 단계:")
    print(f"  1. {out_dir}/_contexts.txt 와 PNG 파일을 확인")
    print(f"  2. {out_dir}/mapping_skeleton.json 의 각 항목에 type/value/modern 채우기")
    print(f"  3. python scripts/apply_mapping.py <PDF> {out_dir}/mapping.json -o <output.md>")

    doc.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
