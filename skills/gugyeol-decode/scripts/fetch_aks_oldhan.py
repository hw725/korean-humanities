#!/usr/bin/env python3
"""
한국학중앙연구원 (AKS) 한국역사정보통합시스템 옛한글 lookup → PUA 매핑 캐시

URL: http://yoksa.aks.ac.kr/jsp/hh/oldhan.jsp
페이지 구조: 22개 코드 (01-22) + 99(기타)

사용:
  python scripts/fetch_aks_oldhan.py [--out reference/aks_oldhan_pua.json]
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

BASE = "http://yoksa.aks.ac.kr/jsp/hh/oldhan"
HEADERS = {"User-Agent": "Mozilla/5.0 gugyeol-decode/1.0"}


def fetch_top() -> list[tuple[str, str]]:
    """카테고리 코드 + 라벨 (대표 글자) 추출."""
    req = urllib.request.Request(f"{BASE}/oldhanTop.jsp", headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as resp:
        html = resp.read().decode("utf-8", errors="replace")
    pat = re.compile(r"goList\('(\d+)'\)\"\s*>([^<]*)</a>")
    return pat.findall(html)


def fetch_category(pcd: str) -> list[int]:
    """단일 카테고리의 PUA codepoint 리스트."""
    data = urllib.parse.urlencode({"pcd": pcd}).encode()
    req = urllib.request.Request(
        f"{BASE}/oldhanBottom.jsp", data=data, headers=HEADERS, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as e:
        print(f"  WARN: pcd={pcd} fetch failed: {e}", file=sys.stderr)
        return []
    cps = []
    seen = set()
    for ch in html:
        cp = ord(ch)
        if 0xE000 <= cp <= 0xF8FF and cp not in seen:
            cps.append(cp)
            seen.add(cp)
    return cps


def main() -> int:
    parser = argparse.ArgumentParser(description="AKS 옛한글 PUA 매핑 캐시 구축")
    parser.add_argument("--out", type=Path,
                        default=Path(__file__).parent.parent / "reference" / "aks_oldhan_pua.json")
    parser.add_argument("--delay", type=float, default=0.3)
    args = parser.parse_args()

    print("AKS 옛한글 카테고리 목록 가져오는 중...")
    categories = fetch_top()
    print(f"  {len(categories)}개 카테고리 발견")

    pua_to_label: dict[str, dict] = {}
    label_to_pua: dict[str, list[int]] = {}

    for pcd, label in categories:
        label_clean = label.strip() or f"<empty_pcd_{pcd}>"
        cps = fetch_category(pcd)
        label_to_pua[label_clean] = cps
        for cp in cps:
            key = f"U+{cp:04X}"
            existing = pua_to_label.get(key)
            if existing:
                existing.setdefault("alt_labels", []).append(label_clean)
            else:
                pua_to_label[key] = {"label": label_clean, "pcd": pcd}
        print(f"  pcd={pcd}  label={label_clean!r:30s}  count={len(cps)}")
        time.sleep(args.delay)

    out = {
        "_doc": "AKS 한국역사정보통합시스템 옛한글 PUA 매핑",
        "_source": "http://yoksa.aks.ac.kr/jsp/hh/oldhan.jsp",
        "_fetched_at": time.strftime("%Y-%m-%d"),
        "_total_pua": len(pua_to_label),
        "_total_labels": len(label_to_pua),
        "_note": "label은 카테고리 대표 글자 또는 범위 (예: 'ㄱ-가' 등). 정확한 음가 매핑은 각 PUA 글자의 시각 판독 필요.",
        "pua_to_label": pua_to_label,
        "label_to_pua": label_to_pua,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    print(f"\n저장: {args.out}")
    print(f"  총 PUA: {len(pua_to_label)}")
    print(f"  총 카테고리: {len(label_to_pua)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
