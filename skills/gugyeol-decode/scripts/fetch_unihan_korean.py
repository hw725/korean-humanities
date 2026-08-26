#!/usr/bin/env python3
"""
Unihan database에서 한국 source(K2~K6) 한자 추출 → 합자 구결자 후보 풀 구축

K2~K6은 PKS C 5700 시리즈와 KS X 1027 시리즈로 한국 특유 한자(古典·이체자·구결 후보)
를 포함한다. 모두가 구결자는 아니지만, 합자 구결자 候補를 좁히는 데 유용.

사용:
  python scripts/fetch_unihan_korean.py [--unihan-zip <PATH>] [--out reference/unihan_korean.json]

기본 동작:
  1. Unihan.zip이 ~/.cache/gugyeol-decode/Unihan.zip에 없으면 다운로드
  2. K2~K6 source 한자 추출
  3. 음가/뜻/획수 등 메타 포함하여 JSON으로 저장
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
import zipfile
from pathlib import Path

UNIHAN_URL = "https://www.unicode.org/Public/UCD/latest/ucd/Unihan.zip"
DEFAULT_CACHE = Path.home() / ".cache" / "gugyeol-decode" / "Unihan.zip"
SKILL_ROOT = Path(__file__).resolve().parent.parent


def ensure_unihan(path: Path) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    print(f"Unihan.zip 다운로드 중 → {path}")
    urllib.request.urlretrieve(UNIHAN_URL, path)
    print(f"  완료 ({path.stat().st_size:,} bytes)")


def parse_unihan_field(zip_path: Path, filename: str) -> dict[int, dict]:
    """Unihan TSV 파일을 (codepoint → {field: value}) dict로."""
    out: dict[int, dict] = {}
    with zipfile.ZipFile(zip_path) as z:
        with z.open(filename) as f:
            for line in f:
                line = line.decode("utf-8").rstrip("\n")
                if not line or line.startswith("#"):
                    continue
                parts = line.split("\t")
                if len(parts) != 3:
                    continue
                cp_str, field, value = parts
                try:
                    cp = int(cp_str.replace("U+", ""), 16)
                except ValueError:
                    continue
                out.setdefault(cp, {})[field] = value
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--unihan-zip", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--out", type=Path,
                        default=SKILL_ROOT / "reference" / "unihan_korean.json")
    parser.add_argument("--k-sources", default="K2,K3,K4,K5,K6",
                        help="추출할 K source 종류 (쉼표 구분)")
    args = parser.parse_args()

    ensure_unihan(args.unihan_zip)
    target_sources = set(args.k_sources.split(","))

    print("Unihan_IRGSources 파싱 중...")
    irg = parse_unihan_field(args.unihan_zip, "Unihan_IRGSources.txt")
    print("Unihan_Readings 파싱 중...")
    readings = parse_unihan_field(args.unihan_zip, "Unihan_Readings.txt")

    korean_chars: dict[str, dict] = {}
    for cp, fields in irg.items():
        k_src = fields.get("kIRG_KSource", "")
        if not k_src:
            continue
        k_type = k_src.split("-")[0] if "-" in k_src else k_src
        if k_type not in target_sources:
            continue
        rd = readings.get(cp, {})
        korean_chars[f"U+{cp:04X}"] = {
            "char": chr(cp),
            "k_source": k_src,
            "k_type": k_type,
            "g_source": fields.get("kIRG_GSource", ""),
            "j_source": fields.get("kIRG_JSource", ""),
            "korean_reading": rd.get("kKorean", ""),
            "mandarin": rd.get("kMandarin", ""),
            "definition": rd.get("kDefinition", ""),
            "is_korean_only": (
                bool(rd.get("kKorean", "")) and not rd.get("kMandarin", "")
            ),
        }

    out = {
        "_doc": "Unihan database K2~K6 source 한자 추출 — 합자 구결자 후보 풀",
        "_source": UNIHAN_URL,
        "_k_source_meanings": {
            "K2": "PKS C 5700-1 (1994)",
            "K3": "PKS C 5700-2 (1994)",
            "K4": "PKS C 5700-3 (1995)",
            "K5": "KS X 1027-1 (2002)",
            "K6": "KS X 1027-2 (2007)",
        },
        "_total": len(korean_chars),
        "_korean_only": sum(1 for v in korean_chars.values() if v["is_korean_only"]),
        "_note": "is_korean_only=true인 한자가 합자 구결자 가능성 높음 (한국 외 사용 사례 없음)",
        "characters": korean_chars,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    print(f"\n저장: {args.out}")
    print(f"  K2~K6 한국 source 한자: {len(korean_chars):,}건")
    print(f"  한국 전용 (Mandarin 없음): {out['_korean_only']:,}건")
    return 0


if __name__ == "__main__":
    sys.exit(main())
