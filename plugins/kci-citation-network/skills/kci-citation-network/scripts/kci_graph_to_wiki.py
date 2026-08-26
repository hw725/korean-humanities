#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
kci_graph_to_wiki.py — kci_citation_collect.py 산출(nodes/edges)을 Obsidian 논문 노트로.

각 논문마다 노트 1개를 만들고, 같은 집합 내에서 인용한 논문을 [[위키링크]]로 연결한다.
Obsidian Graph View에서 인용 네트워크가 그려진다(Zotero Citation-Network 도구의 한문학판).

용법:
  python kci_graph_to_wiki.py --in-dir out/kys \
      --vault "<your-vault-root>" \
      --folder "wiki/인용망/운양김윤식"

규칙:
  - 자동 생성 구역은 <!-- KCI-AUTO --> ... <!-- /KCI-AUTO --> 사이. 그 아래 수동 메모는 재실행해도 보존.
  - 위키 폴더 경로는 vault 규칙을 따른다(한글 폴더 허용).
  - 노트 basename = 저자·제목 슬러그. 링크는 [[basename]].
  - references/·writing/ 등 자동생성 보호 폴더에는 쓰지 않는다(대상은 wiki/ 하위).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

# CJK 텍스트 계약 E3: Windows 콘솔 기본 cp949에서 한글·한자 출력이
# UnicodeEncodeError로 죽는 것을 막는다 (환경변수에 의존하지 않는 방어선).
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

AUTO_START = "<!-- KCI-AUTO -->"
AUTO_END = "<!-- /KCI-AUTO -->"


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s or "")


def slugify(title: str, kci_id: str) -> str:
    t = nfc(title).strip()
    if not t:
        return kci_id
    t = re.sub(r"[<>:\"/\\|?*\x00-\x1f\[\]#^]", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return (t[:70].strip() or kci_id)


def read_jsonl(p: Path) -> list[dict]:
    if not p.exists():
        return []
    return [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]


def preserve_manual(note_path: Path) -> str:
    """기존 노트에서 자동구역 밖(수동 메모)만 살려 반환."""
    if not note_path.exists():
        return ""
    text = note_path.read_text(encoding="utf-8")
    if AUTO_END in text:
        return text.split(AUTO_END, 1)[1].lstrip("\n")
    return ""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="KCI 인용망 → Obsidian 노트")
    ap.add_argument("--in-dir", type=Path, required=True, help="kci_citation_collect 산출 폴더")
    ap.add_argument("--vault", type=Path, required=True, help="vault 루트")
    ap.add_argument("--folder", default="wiki/인용망", help="vault 내 대상 폴더(한글 허용)")
    ap.add_argument("--tag", action="append", default=None, help="추가 태그")
    ap.add_argument("--min-degree", type=int, default=1,
                    help="집합 내 (인용+피인용) 차수 이 값 미만 노드는 노트 생략")
    ap.add_argument("--seeds-only", action="store_true",
                    help="씨앗 논문만 노드로(피인용된 외부 KCI 논문은 제외) — 깨끗한 코어 인용망")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    nodes = {n["kci_id"]: n for n in read_jsonl(args.in_dir / "nodes.jsonl")}
    edges = read_jsonl(args.in_dir / "edges.jsonl")
    if not nodes:
        sys.exit(f"[에러] nodes.jsonl 비어있음: {args.in_dir}")

    setids = {k for k, n in nodes.items() if n.get("seed")} if args.seeds_only else set(nodes)
    # 집합 내부 엣지만
    out_edges = defaultdict(list)   # src -> [dst]
    in_edges = defaultdict(list)    # dst -> [src]
    for e in edges:
        s, d = e["src"], e["dst"]
        if s in setids and d in setids and s != d:
            out_edges[s].append(d)
            in_edges[d].append(s)

    # 차수
    degree = {k: len(set(out_edges[k])) + len(set(in_edges[k])) for k in setids}
    targets = [k for k in setids if degree.get(k, 0) >= args.min_degree or nodes[k].get("seed")]

    # 슬러그(파일명) 결정 — 링크 대상
    slug = {k: slugify(nodes[k].get("title", ""), k) for k in setids}
    # 슬러그 충돌 방지
    used = {}
    for k in targets:
        base = slug[k]
        if base in used and used[base] != k:
            slug[k] = f"{base} ({k[-4:]})"
        used[slug[k]] = k

    folder = args.vault / args.folder
    tags = ["kci", "인용망", "논문"] + (args.tag or [])
    written = 0
    for k in targets:
        n = nodes[k]
        title = nfc(n.get("title", "")) or k
        cites = sorted(set(out_edges[k]), key=lambda d: nodes[d].get("year", ""))
        cited_by = sorted(set(in_edges[k]), key=lambda s: nodes[s].get("year", ""))

        is_seed = bool(n.get("seed"))
        node_tags = tags + (["씨앗논문"] if is_seed else ["피인용외부"])
        fm = [
            "---",
            f'title: "{title}"',
            "type: paper",
            f"kci_id: {k}",
            f"seed: {str(is_seed).lower()}",
            f'year: "{n.get("year","")}"',
            f'journal: "{nfc(n.get("journal",""))}"',
            f"source_url: https://www.kci.go.kr/kciportal/ci/sereArticleSearch/ciSereArtiView.kci?sereArticleSearchBean.artiId={k}",
            "tags: [" + ", ".join(node_tags) + "]",
            "---",
            "",
        ]
        body = [AUTO_START,
                f"# {title}",
                "",
                f"> KCI {n.get('year','')} · {nfc(n.get('journal',''))} · `{k}`",
                ""]
        body.append(f"## 인용 ({len(cites)})")
        if cites:
            for d in cites:
                body.append(f"- [[{slug[d]}]] ({nodes[d].get('year','')})")
        else:
            body.append("- _(집합 내 인용 없음)_")
        body.append("")
        body.append(f"## 피인용 ({len(cited_by)})")
        if cited_by:
            for s in cited_by:
                body.append(f"- [[{slug[s]}]] ({nodes[s].get('year','')})")
        else:
            body.append("- _(집합 내 피인용 없음)_")
        body += ["", AUTO_END, ""]

        manual = preserve_manual(folder / f"{slug[k]}.md")
        content = "\n".join(fm) + "\n".join(body)
        if manual:
            content += "\n" + manual
        else:
            content += "\n## 메모\n\n"

        if args.dry_run:
            written += 1
            continue
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{slug[k]}.md").write_text(content, encoding="utf-8")
        written += 1

    print(f"노드 {len(nodes)}, 노트 대상 {len(targets)} (min-degree={args.min_degree}), "
          f"{'작성예정' if args.dry_run else '작성'} {written}")
    print(f"집합 내부 인용 엣지: {sum(len(set(v)) for v in out_edges.values())}")
    if not args.dry_run:
        print(f"→ {folder}")
        print("Obsidian에서 이 폴더로 Graph View 필터(path:) 걸면 인용망이 보입니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
