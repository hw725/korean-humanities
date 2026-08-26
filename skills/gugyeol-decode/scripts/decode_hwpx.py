#!/usr/bin/env python3
"""
gugyeol-decode HWPX 처리 — HWP/HWPX 텍스트 추출 + PUA 정규화

PDF용 apply_mapping.py와 달리 HWPX는 글리프-폰트 분리 정보가 없으므로
codepoint 단독으로 hypua + AKS 매핑 테이블을 조회한다.
한컴 한글 표준 PUA(hypua)가 폰트 무관하게 통용되는 전제.

사용:
  python scripts/decode_hwpx.py <HWPX경로> [--out output.md] [--mode value|modern|both]
  python scripts/decode_hwpx.py <HWP경로>  # HWP는 자동 변환 시도

decode.py에서 확장자 분기로 호출되며, 직접 호출도 가능.
"""
from __future__ import annotations

import argparse
import json
import sys
import unicodedata
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

# extract_pua의 매핑 로드 함수 재사용
from extract_pua import _load_hypua_table, _load_aks_caches, _resolve_sound  # noqa: E402


def build_codepoint_lookup() -> dict[int, dict]:
    """codepoint → {value, modern, source} 단일 룩업 테이블.

    HWPX는 폰트별 분기 없이 codepoint 단독으로 매핑. hypua 우선,
    AKS gukyul/oldhan 보조.
    """
    hypua = _load_hypua_table()
    gukyul, oldhan = _load_aks_caches()

    lookup: dict[int, dict] = {}

    # hypua: PUA → IPF jamo 결합형
    for cp, jamo in hypua.items():
        lookup[cp] = {"value": jamo, "modern": "", "source": "hypua"}

    # AKS gukyul: 구결자 (sound 라벨 = 한국어 발음)
    for key, entry in gukyul.items():
        if not key.startswith("U+"):
            continue
        try:
            cp = int(key[2:], 16)
        except ValueError:
            continue
        sound = _resolve_sound(entry.get("sound", ""), gukyul)
        if sound:
            # gukyul은 hypua와 codepoint 영역이 다름 (겹쳐도 gukyul이 의미상 우선)
            lookup[cp] = {"value": sound, "modern": sound, "source": "aks_gukyul"}

    # AKS oldhan: 옛한글 카테고리 (label = 표준 자모 결합)
    for key, entry in oldhan.items():
        if not key.startswith("U+"):
            continue
        try:
            cp = int(key[2:], 16)
        except ValueError:
            continue
        if cp in lookup:
            continue  # hypua 우선
        label = entry.get("label", "")
        if label:
            lookup[cp] = {"value": label, "modern": "", "source": "aks_oldhan"}

    return lookup


def normalize_text(text: str, lookup: dict[int, dict],
                   mode: str = "both") -> tuple[str, list[int]]:
    """텍스트 안의 PUA codepoint를 치환. 미매핑 codepoint 리스트도 반환."""
    buf: list[str] = []
    unmapped: list[int] = []
    for ch in text:
        cp = ord(ch)
        if 0xE000 <= cp <= 0xF8FF:
            entry = lookup.get(cp)
            if entry is None:
                buf.append(f"⟨U+{cp:04X}?⟩")
                unmapped.append(cp)
                continue
            value = entry.get("value", "")
            modern = entry.get("modern", "")
            if mode == "value":
                buf.append(value or modern or f"⟨U+{cp:04X}⟩")
            elif mode == "modern":
                buf.append(modern or value or f"⟨U+{cp:04X}⟩")
            else:  # both
                if value and modern and value != modern:
                    buf.append(f"{value}({modern})")
                else:
                    buf.append(value or modern or f"⟨U+{cp:04X}⟩")
        else:
            buf.append(ch)
    return "".join(buf), unmapped


def extract_hwpx_markdown(hwpx_path: Path) -> str:
    """python-hwpx의 TextExtractor로 markdown 추출."""
    try:
        from hwpx import TextExtractor
    except ImportError:
        print("ERROR: python-hwpx가 필요합니다. 설치:\n  pip install python-hwpx",
              file=sys.stderr)
        sys.exit(1)

    lines: list[str] = []
    with TextExtractor(str(hwpx_path)) as ext:
        for sec_idx, section in enumerate(ext.iter_sections()):
            if sec_idx > 0:
                lines.append("")
                lines.append("---")
                lines.append("")
            for para in ext.iter_paragraphs(section, include_nested=True):
                text = para.text(object_behavior="nested")
                if not text.strip():
                    continue
                if para.is_nested:
                    lines.append(f"  {text}")
                else:
                    lines.append(text)
    return "\n".join(lines)


def convert_hwp_to_hwpx(hwp_path: Path) -> Path:
    """HWP → HWPX 변환 (claude-skills/skills/hwpx/scripts/convert_hwp.py 활용)."""
    # 탐색 순서: ① HWPX_CONVERTER 환경변수 ② ~/.claude/skills/hwpx (junction 표준 위치).
    # 예전의 개인 저장소 절대 폴백(~/Downloads/REPOSITORY/...)은 제거 — 이식 불가 경로였다.
    env = os.environ.get("HWPX_CONVERTER")
    converter = (Path(env) if env
                 else Path.home() / ".claude" / "skills" / "hwpx"
                 / "scripts" / "convert_hwp.py")
    if not converter.exists():
        print("ERROR: HWP 변환 도구를 찾지 못했습니다.\n"
              "  HWPX_CONVERTER 환경변수로 convert_hwp.py 경로를 지정하거나,\n"
              "  별도 변환 후 .hwpx로 다시 시도하세요.",
              file=sys.stderr)
        sys.exit(1)
    import subprocess
    out_path = hwp_path.with_suffix(".hwpx")
    rc = subprocess.call([sys.executable, str(converter),
                          str(hwp_path), "--out", str(out_path)])
    if rc != 0 or not out_path.exists():
        print(f"ERROR: HWP→HWPX 변환 실패 (exit {rc})", file=sys.stderr)
        sys.exit(1)
    print(f"HWP→HWPX 변환 완료: {out_path.name}")
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="HWPX/HWP → 깨끗한 markdown (PUA 옛한글·구결자 자동 복원)")
    parser.add_argument("input", type=Path, help="입력 .hwpx 또는 .hwp 경로")
    parser.add_argument("--out", type=Path, default=None,
                        help="출력 markdown 경로 (기본: <입력>.normalized.md)")
    parser.add_argument("--mode", choices=["value", "modern", "both"],
                        default="both", help="치환 방식")
    parser.add_argument("--no-normalize", action="store_true",
                        help="NFC 정규화 건너뛰기 (기본은 적용)")
    args = parser.parse_args()

    src = args.input.resolve()
    if not src.exists():
        print(f"ERROR: 파일 없음: {src}", file=sys.stderr)
        return 1

    suffix = src.suffix.lower()
    if suffix == ".hwp":
        src = convert_hwp_to_hwpx(src)
    elif suffix != ".hwpx":
        print(f"ERROR: HWPX/HWP 아님: {suffix}", file=sys.stderr)
        return 1

    out = args.out or src.with_suffix(".normalized.md")

    print(f"[1/2] HWPX 텍스트 추출 ({src.name})")
    raw = extract_hwpx_markdown(src)

    print(f"[2/2] PUA 매핑 적용")
    lookup = build_codepoint_lookup()
    normalized, unmapped = normalize_text(raw, lookup, mode=args.mode)

    # NFC 정규화: CJK Compatibility Ideographs → 표준 한자 (canonical equivalence만, 안전)
    if not args.no_normalize:
        compat_chars = [c for c in normalized if 0xF900 <= ord(c) <= 0xFAFF]
        if compat_chars:
            unique_compat = len(set(compat_chars))
            after = unicodedata.normalize("NFC", normalized)
            remain = sum(1 for c in after if 0xF900 <= ord(c) <= 0xFAFF)
            converted = len(compat_chars) - remain
            print(f"  NFC 정규화: CJK Compatibility {unique_compat}종, "
                  f"{len(compat_chars)}회 → {converted}회 표준 한자 변환"
                  + (f" ({remain}회 잔존)" if remain else ""))
            normalized = after
        else:
            normalized = unicodedata.normalize("NFC", normalized)

    out.write_text(normalized, encoding="utf-8")

    pua_total = sum(1 for ch in raw if 0xE000 <= ord(ch) <= 0xF8FF)
    print(f"저장: {out}")
    print(f"  매핑 테이블 등록: {len(lookup)}건")
    print(f"  PUA 글자 발견 (occurrence): {pua_total}")
    print(f"  미매핑 (occurrence): {len(unmapped)}")
    if unmapped:
        unique = sorted(set(unmapped))
        print(f"  처음 5개 미매핑 codepoint:")
        for cp in unique[:5]:
            print(f"    U+{cp:04X}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
