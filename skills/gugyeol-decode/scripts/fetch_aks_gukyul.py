#!/usr/bin/env python3
"""
한국학중앙연구원 (AKS) 한국역사정보통합시스템 구결자 lookup → PUA 매핑 캐시 구축

URL: http://yoksa.aks.ac.kr/jsp/hh/gukyul.jsp
출처: 한국학중앙연구원 — 표준 음가별 PUA 부호점 매핑

각 음가(예: '니' = pcd 020)에 매핑된 PUA codepoint를 모두 수집하여
reference/aks_gukyul_pua.json 으로 저장.

사용:
  python scripts/fetch_aks_gukyul.py [--out reference/aks_gukyul_pua.json]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "http://yoksa.aks.ac.kr/jsp/hh/gukyul"
HEADERS = {"User-Agent": "Mozilla/5.0 gugyeol-decode/1.0"}


def fetch_top() -> list[tuple[str, str]]:
    """음가 코드 + 음가 표기 목록 추출."""
    req = urllib.request.Request(f"{BASE}/gukyulTop.jsp", headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as resp:
        html = resp.read().decode("utf-8", errors="replace")
    pat = re.compile(r"goList\('(\d+)'\)\"\s*>([^<]*)</a>")
    return pat.findall(html)


def fetch_category(pcd: str) -> list[int]:
    """단일 음가 카테고리의 PUA codepoint 리스트."""
    data = urllib.parse.urlencode({"pcd": pcd}).encode()
    req = urllib.request.Request(
        f"{BASE}/gukyulBottom.jsp", data=data, headers=HEADERS, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as e:
        print(f"  WARN: pcd={pcd} fetch failed: {e}", file=sys.stderr)
        return []
    cps = []
    for ch in html:
        cp = ord(ch)
        if 0xE000 <= cp <= 0xF8FF and cp not in cps:
            cps.append(cp)
    return cps


def main() -> int:
    parser = argparse.ArgumentParser(description="AKS 구결자 PUA 매핑 캐시 구축")
    parser.add_argument("--out", type=Path,
                        default=Path(__file__).parent.parent / "reference" / "aks_gukyul_pua.json")
    parser.add_argument("--delay", type=float, default=0.3,
                        help="요청 간 지연 (초). 서버 배려.")
    args = parser.parse_args()

    print("AKS 구결자 카테고리 목록 가져오는 중...")
    categories = fetch_top()
    print(f"  {len(categories)}개 카테고리 발견")

    # PUA codepoint -> {sound, pcd, sound_label} (역인덱스도 만들 수 있음)
    pua_to_sound: dict[str, dict] = {}
    sound_to_pua: dict[str, list[int]] = {}
    skipped = []

    for pcd, sound in categories:
        sound_label = sound.strip() or f"<empty_pcd_{pcd}>"
        if not sound.strip():
            skipped.append(pcd)
        cps = fetch_category(pcd)
        sound_to_pua[sound_label] = cps
        for cp in cps:
            key = f"U+{cp:04X}"
            existing = pua_to_sound.get(key)
            if existing:
                existing.setdefault("alt_sounds", []).append(sound_label)
            else:
                pua_to_sound[key] = {"sound": sound_label, "pcd": pcd}
        print(f"  pcd={pcd}  sound={sound_label!r:25s}  count={len(cps)}")
        time.sleep(args.delay)

    out = {
        "_doc": "AKS 한국학중앙연구원 한국역사정보통합시스템 구결자 PUA 매핑",
        "_source": "http://yoksa.aks.ac.kr/jsp/hh/gukyul.jsp",
        "_fetched_at": time.strftime("%Y-%m-%d"),
        "_total_pua": len(pua_to_sound),
        "_total_sounds": len(sound_to_pua),
        "_skipped_categories": skipped,
        "pua_to_sound": pua_to_sound,
        "sound_to_pua": sound_to_pua,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    print(f"\n저장: {args.out}")
    print(f"  총 PUA: {len(pua_to_sound)}")
    print(f"  총 음가: {len(sound_to_pua)}")
    print(f"  미식별 카테고리: {len(skipped)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
