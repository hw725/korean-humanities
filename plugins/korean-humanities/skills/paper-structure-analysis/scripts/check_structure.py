#!/usr/bin/env python3
"""구조분석 트리 JSON과 노트를 검사한다(paper-structure-analysis §5).

    python check_structure.py tree <tree.json> --text <text.md>
    python check_structure.py page <note.md> --text <text.md> [--tree <tree.json>]

오류가 있으면 한 줄씩 찍고 종료 코드 1, 없으면 「오류 0」과 종료 코드 0. 표준 라이브러리만 쓴다.
노트 형식의 정본은 ../references/page-format.md — REQUIRED_KEYS·SECTIONS는 그 문서와 맞춘다.
"""
import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

REQUIRED_KEYS = ("title", "description", "source_path", "structure_tree", "structure_generator", "sources", "created")
SECTIONS = ("서지 정보", "한눈에 보는 논증", "논증 지도", "논증 흐름도", "근거의 구성",
            "결론의 지탱 구조와 빈틈", "학술 대화", "기존 위키와의 연결", "원문 인용", "검증 메타데이터")
PAGE_MARK = re.compile(r"<!--\s*page\s+(\d+)\s*-->")
QUOTE_PAGE = re.compile(r"\(PDF p\.(\d+)\)\s*$")


def read(path):
    return Path(path).read_text(encoding="utf-8")


IMAGE_LINK = re.compile(r"!\[[^\]]*\]\([^)]*\)")
NOISE = str.maketrans("", "", "-­*")  # 줄끝 하이픈·소프트 하이픈·마크다운 강조


def squash(s):
    """인용 대조용: 유니코드 정규화 뒤 공백·이미지 링크·줄끝 하이픈·강조 표시를 지운다.

    추출본은 문장 한가운데 그림 링크를 끼우거나 줄끝에서 낱말을 하이픈으로 끊고, 서명 괄호 『』를 글꼴의
    사용자 정의 영역(PUA) 글자로 내놓는다(2026-10-22 실측) — 인용은 지면 그대로 옮긴 것이 맞으므로 이 차이로
    오류를 내지 않는다.
    """
    s = IMAGE_LINK.sub("", unicodedata.normalize("NFC", s))
    return "".join(c for c in "".join(s.split()).translate(NOISE) if not "" <= c <= "")


def text_pages(text):
    """`<!-- page N -->` 표지로 쪽별 본문을 나눈다. {쪽: 본문}."""
    pages, cur, buf = {}, None, []
    for line in text.splitlines():
        m = PAGE_MARK.search(line)
        if m:
            if cur is not None:
                pages[cur] = pages.get(cur, "") + "\n".join(buf)
            cur, buf = int(m.group(1)), [PAGE_MARK.sub("", line)]
        else:
            buf.append(line)
    if cur is not None:
        pages[cur] = pages.get(cur, "") + "\n".join(buf)
    return pages


def flatten(nodes, depth=0, parent=None):
    for n in nodes:
        yield n, depth, parent
        yield from flatten(n.get("nodes") or [], depth + 1, n)


def check_tree(tree_path, text):
    errs = []
    try:
        data = json.loads(read(tree_path))
    except (OSError, ValueError) as e:
        return [f"트리를 읽을 수 없음: {e}"], []
    struct = data.get("structure") if isinstance(data, dict) else None
    if not isinstance(struct, list) or not struct:
        return ["트리에 structure 목록이 없거나 비었음"], []
    last = max(text_pages(text) or {0: ""})
    nodes = list(flatten(struct))
    for i, (n, _, parent) in enumerate(nodes):
        tag = f"노드 {i} 「{str(n.get('title', ''))[:30]}」"
        if not str(n.get("title", "")).strip():
            errs.append(f"{tag}: 제목이 비었음")
        if n.get("node_id") != f"{i:04d}":
            errs.append(f"{tag}: node_id {n.get('node_id')!r} — 순회 순서상 {i:04d}이어야 함")
        s, e = n.get("start_index"), n.get("end_index")
        if not (isinstance(s, int) and isinstance(e, int)):
            errs.append(f"{tag}: start_index·end_index가 정수가 아님")
            continue
        if s > e:
            errs.append(f"{tag}: 시작 쪽 {s} > 끝 쪽 {e}")
        if last and not (1 <= s and e <= last):
            errs.append(f"{tag}: 쪽 범위 {s}～{e}가 text의 1～{last} 밖")
        # 상위 노드의 end_index 는 하위 노드를 덮지 않아도 된다 — 상위 노드 범위를 「첫 하위 노드 앞 도입부」로 적는
        # 트리 관례가 있다(2026-10-22 실측: 기존 트리 145개 중 다수). 시작이 상위보다 앞서는 것만 오류로 본다.
        if parent is not None and isinstance(parent.get("start_index"), int) and s < parent["start_index"]:
            errs.append(f"{tag}: 시작 쪽 {s}이 상위 노드 시작 {parent['start_index']}보다 앞")
    for group in [struct] + [n.get("nodes") or [] for n, _, _ in nodes]:
        starts = [x.get("start_index") for x in group if isinstance(x.get("start_index"), int)]
        if any(b < a for a, b in zip(starts, starts[1:])):
            errs.append(f"형제 노드 시작 쪽이 거꾸로 감: {starts}")
    return errs, nodes


def split_frontmatter(page):
    if not page.startswith("---"):
        return None, page
    end = page.find("\n---", 3)
    if end < 0:
        return None, page
    return page[3:end], page[end + 4:]


def strip_code(body):
    """코드 블록·인라인 코드를 지운 본문(표기 검사용)."""
    body = re.sub(r"```.*?```", "", body, flags=re.S)
    return re.sub(r"`[^`\n]*`", "", body)


def sections(body):
    """## 절 제목 → 그 절 본문."""
    out, cur = {}, None
    for line in body.splitlines():
        if line.startswith("## "):
            cur = line[3:].strip()
            out[cur] = []
        elif cur is not None:
            out[cur].append(line)
    return {k: "\n".join(v) for k, v in out.items()}


def check_page(page_path, text, tree_path=None):
    errs = []
    page = read(page_path)
    fm, body = split_frontmatter(page)
    if fm is None:
        errs.append("프런트매터(--- … ---)가 없음")
    else:
        keys = {m.group(1) for m in re.finditer(r"^([A-Za-z_]+)\s*:", fm, re.M)}
        errs += [f"프런트매터 필수 키 없음: {k}" for k in REQUIRED_KEYS if k not in keys]
    if not re.search(r"^# \S", body, re.M):
        errs.append("# 제목 줄이 없음")
    found = [line[3:].strip() for line in body.splitlines() if line.startswith("## ")]
    missing = [s for s in SECTIONS if s not in found]
    errs += [f"절 없음: ## {s}" for s in missing]
    if not missing:
        order = [s for s in found if s in SECTIONS]
        if order != list(SECTIONS):
            errs.append(f"절 순서가 다름: {order}")
    sec = sections(body)

    if tree_path:
        terr, nodes = check_tree(tree_path, text)
        if terr:
            errs.append(f"트리 오류 {len(terr)}건 — tree 검사부터 통과시킬 것")
        rows = [ln for ln in sec.get("논증 지도", "").splitlines() if ln.strip().startswith("|")]
        data_rows = [ln for ln in rows[2:] if not re.fullmatch(r"\|[\s:|-]*\|?", ln.strip())]
        if nodes and len(data_rows) != len(nodes):
            errs.append(f"논증 지도 행 {len(data_rows)}개 ≠ 트리 노드 {len(nodes)}개(바로잡았으면 트리도 맞춘다)")

    pages = text_pages(text)
    whole = squash(text)
    quotes = []
    for block in re.split(r"\n\s*\n", sec.get("원문 인용", "")):
        lines = [ln[1:].strip() for ln in block.splitlines() if ln.startswith(">")]
        if lines:
            quotes.append(lines[0])
    if not quotes:
        errs.append("원문 인용이 없음")
    for q in quotes:
        m = QUOTE_PAGE.search(q)
        if not m:
            errs.append(f"인용 끝에 (PDF p.N)이 없음: {q[:40]}")
            continue
        core = squash(QUOTE_PAGE.sub("", q).strip().strip("“”\"'"))
        if not core:
            continue
        if core not in whole:
            errs.append(f"인용이 text에 글자 그대로 없음: {q[:40]}")
        elif pages:
            n = int(m.group(1))
            near = squash(pages.get(n, "") + pages.get(n + 1, ""))
            if core not in near:
                errs.append(f"인용이 적힌 쪽 p.{n}(～다음 쪽)에 없음: {q[:40]}")

    plain = strip_code(body)
    for i, line in enumerate(plain.splitlines(), 1):
        if line.lstrip().startswith(">"):
            continue  # 원문 인용 안은 원문 표기 그대로
        if '"' in line or "'" in line:
            errs.append(f"직선 따옴표(본문 {i}줄): {line.strip()[:40]}")
        if "~" in line:
            errs.append(f"ASCII 물결표(본문 {i}줄 — 전각 ～): {line.strip()[:40]}")

    blocks = re.findall(r"```mermaid\n(.*?)```", body, flags=re.S)
    if len(blocks) != 1:
        errs.append(f"mermaid 블록이 {len(blocks)}개(1개여야 함)")
    for blk in blocks:
        if not re.match(r"\s*flowchart\s+TD", blk):
            errs.append("mermaid가 flowchart TD로 시작하지 않음")
        for ln in blk.splitlines():
            if re.search(r"\w\[(?![\"\[])", ln):
                errs.append(f"mermaid 라벨이 [\"...\"]로 감싸이지 않음: {ln.strip()[:40]}")
            if re.search(r"--\s+[^>|\s-]", ln) and "-->|" not in ln:
                errs.append(f"mermaid 간선 라벨은 -->|라벨| 형식: {ln.strip()[:40]}")
    return errs


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("tree", help="트리 JSON 검사")
    t.add_argument("tree")
    t.add_argument("--text", required=True)
    p = sub.add_parser("page", help="구조분석 노트 검사")
    p.add_argument("page")
    p.add_argument("--text", required=True)
    p.add_argument("--tree")
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    text = read(a.text)
    if a.cmd == "tree":
        errs = check_tree(a.tree, text)[0]
    else:
        errs = check_page(a.page, text, a.tree)
    for e in errs:
        print(f"오류: {e}")
    print(f"오류 {len(errs)}")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
