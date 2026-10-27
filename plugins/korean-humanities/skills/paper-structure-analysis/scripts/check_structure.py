#!/usr/bin/env python3
"""구조분석 트리 JSON과 노트를 검사한다(paper-structure-analysis §5).

    python check_structure.py tree <tree.json> --text <text.md>
    python check_structure.py page <note.md> --text <text.md> [--tree <tree.json>]
    python check_structure.py stamp <tree.json> --text <text.md>   # 트리에 추출본 쪽별 해시를 찍는다(파일을 고쳐 씀)

오류가 있으면 한 줄씩 찍고 종료 코드 1, 없으면 「오류 0」과 종료 코드 0. 표준 라이브러리 밖으로는
`regex` 하나를 쓴다(CJK 문자클래스 — CJK 계약 R1, ../requirements.txt).
노트 형식의 정본은 ../references/page-format.md — REQUIRED_KEYS·SECTIONS는 그 문서와 맞춘다.
"""
import argparse
import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path

import regex

REQUIRED_KEYS = ("title", "description", "source_path", "structure_tree", "structure_generator", "sources", "created")
SECTIONS = ("서지 정보", "한눈에 보는 논증", "논증 지도", "논증 흐름도", "근거의 구성",
            "결론의 지탱 구조와 빈틈", "학술 대화", "기존 위키와의 연결", "원문 인용", "검증 메타데이터")
PAGE_MARK = re.compile(r"<!--\s*page\s+(\d+)\s*-->")
QUOTE_PAGE = re.compile(r"\(PDF p\.(\d+)\)\s*$")
HANGUL = regex.compile(r"\p{Hangul}")
KANA = regex.compile(r"[\p{Hiragana}\p{Katakana}]")
LETTER = regex.compile(r"[\p{Hangul}\p{Hiragana}\p{Katakana}\p{Han}A-Za-z]")


def summary_not_korean(s):
    """요약은 한국어로 쓴다(제목만 원문 그대로). 한글 없이 글자만 있거나 가나가 한글보다 많으면 한국어가 아니다.

    2026-10-27: 같은 세션이 만든 일본어 논문 트리도 요약 언어가 갈렸다 — 지침이 언어를 정하지 않아서였다.
    한자·원어 인용이 섞인 한국어 문장과 「[1]～[196].」처럼 글자가 없는 요약은 통과한다.
    """
    h = len(HANGUL.findall(s))
    return bool(LETTER.search(s)) and (h == 0 or len(KANA.findall(s)) > h)


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


TITLE_NOISE = regex.compile(r"[\s\p{P}\p{S}_]+")
TITLE_PROBE = 14  # 제목 앞 14글자로 대조 — vault-pipeline tree-check.mjs 와 같은 기준


def norm_title(s):
    """제목 대조용: NFKC·소문자, 공백·문장부호·기호를 지운다(Ⅱ→ii, 전각→반각)."""
    return TITLE_NOISE.sub("", unicodedata.normalize("NFKC", str(s)).lower())


def title_errors(tag, n, npages):
    """제목이 시작 쪽(±1)에 있는가(2026-10-28 learn-from-materials 체리픽 ① — 제목 지면 증거).

    다른 쪽에만 있으면 쪽 오배치라 늘 오류다(vault 158편 실측 17노드). 지면에 없으면 「표제·초록」「주 묶음」처럼
    지면 제목 없는 구간을 설명으로 붙인 노드이므로(같은 실측 306노드) `"synthetic": "사유"`가 있을 때만 통과한다.
    """
    syn = n.get("synthetic")
    if syn is not None:
        return [] if str(syn).strip() else [f"{tag}: synthetic 사유가 비었음"]
    key = norm_title(n.get("title", ""))[:TITLE_PROBE]
    s = n.get("start_index")
    if not key or not npages:
        return []
    if any(key in npages.get(p, "") for p in (s - 1, s, s + 1)):
        return []
    elsewhere = [p for p, t in sorted(npages.items()) if key in t]
    if elsewhere:
        return [f"{tag}: 제목이 시작 쪽 {s}(±1)이 아니라 p.{elsewhere[0]}에 있음 — 쪽 오배치"]
    return [f"{tag}: 제목이 지면에 없음 — 지면 제목 그대로 쓰거나, 제목 없는 구간이면 \"synthetic\": \"사유\""]


def page_set(spec):
    """uncovered 키 「3」「15-24」 → 쪽 집합. 못 읽으면 빈 집합."""
    m = re.fullmatch(r"\s*(\d+)\s*(?:[-～~]\s*(\d+))?\s*", str(spec))
    if not m:
        return set()
    a = int(m.group(1))
    return set(range(a, int(m.group(2) or a) + 1))


def coverage_errors(data, nodes, last):
    """모든 노드의 쪽 범위를 합쳐 1～마지막 쪽에 빈 쪽이 있는가(체리픽 ② — 쪽 커버리지 감사).

    상위 노드 범위가 하위를 덮지 않는 관례가 있어 최상위만이 아니라 전 노드를 합친다. 빈 쪽은 최상위
    `"uncovered": {"쪽 또는 범위": "사유"}`에 사유가 있으면 통과한다(158편 중 18편 — 앞표지·끝 참고문헌 쪽).
    """
    if not last:
        return []
    covered = set()
    for n, _, _ in nodes:
        s, e = n.get("start_index"), n.get("end_index")
        if isinstance(s, int) and isinstance(e, int) and s <= e:
            covered |= set(range(s, e + 1))
    declared = set()
    unc = data.get("uncovered") if isinstance(data.get("uncovered"), dict) else {}
    for k, why in unc.items():
        if str(why).strip():
            declared |= page_set(k)
    gaps = sorted(set(range(1, last + 1)) - covered - declared)
    if not gaps:
        return []
    return [f"트리가 덮지 않는 쪽 {gaps[:12]}{'…' if len(gaps) > 12 else ''} — 노드를 더하거나 "
            f"최상위 \"uncovered\": {{\"쪽\": \"사유\"}}에 적는다"]


def page_hashes(text):
    """쪽별 본문 해시(sha256 앞 12자리). 공백 차이는 무시한다 — 줄바꿈만 바뀐 재추출로 재대조를 부르지 않게."""
    return {str(k): hashlib.sha256("".join(v.split()).encode("utf-8")).hexdigest()[:12]
            for k, v in sorted(text_pages(text).items())}


def stamp_tree(data, text):
    """트리에 추출본 쪽별 해시를 찍는다(2026-10-28 learn-from-materials 체리픽 — 증분 갱신의 의존표).

    노드의 쪽 범위가 곧 「이 노드는 이 쪽들에 기대고 있다」는 의존표다. 추출본을 다시 만들면 바뀐 쪽에 걸린 노드만
    다시 읽고 대조하면 되고, 나머지 노드·노트 문장은 그대로 둔다. 대조를 마치면 다시 찍는다.
    """
    data["page_sha"] = page_hashes(text)
    return data


def stamp_errors(data, nodes, text):
    """찍어 둔 쪽 해시와 지금 추출본이 다르면 바뀐·더해진·사라진 쪽과 그 쪽에 걸린 노드를 짚는다."""
    old = data.get("page_sha")
    if not isinstance(old, dict):
        return []
    new = page_hashes(text)
    changed = sorted(int(k) for k in set(old) | set(new) if old.get(k) != new.get(k) and str(k).isdigit())
    if not changed:
        return []
    hit = [str(n.get("title", ""))[:20] for n, _, _ in nodes
           if isinstance(n.get("start_index"), int) and isinstance(n.get("end_index"), int)
           and any(n["start_index"] <= p <= n["end_index"] for p in changed)]
    return [f"추출본 p.{changed[:12]} 바뀜(찍은 뒤) — 걸린 노드 {hit[:8]}만 다시 읽고 대조한 뒤 stamp 로 다시 찍는다"]


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
    tpages = text_pages(text)
    last = max(tpages or {0: ""})
    npages = {k: norm_title(v) for k, v in tpages.items()}
    nodes = list(flatten(struct))
    for i, (n, _, parent) in enumerate(nodes):
        tag = f"노드 {i} 「{str(n.get('title', ''))[:30]}」"
        if not str(n.get("title", "")).strip():
            errs.append(f"{tag}: 제목이 비었음")
        if summary_not_korean(str(n.get("summary") or "")):
            errs.append(f"{tag}: 요약이 한국어가 아님 — 제목은 원문 그대로, 요약은 한국어로 쓴다")
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
        errs += title_errors(tag, n, npages)
    errs += coverage_errors(data, nodes, last)
    errs += stamp_errors(data, nodes, text)
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

    # 근거 층(2026-10-28 learn-from-materials 체리픽, answer-protocol): 노트 문장은 기본이 원문 근거다. 원문 밖에서 확인한
    # 사실은 [외부 확인: 출처]로 출처를 대고, 원문에 없는 모델 보충은 노트에 쓰지 않는다(대화에서만 말한다).
    for m in re.finditer(r"\[외부 확인([^\]]*)\]", body):
        if not re.match(r"\s*:\s*\S", m.group(1)):
            errs.append(f"[외부 확인]에 출처가 없음 — [외부 확인: 출처] 형식: {m.group(0)[:40]}")
    if "[모델 보충" in body:
        errs.append("노트에 [모델 보충]이 있음 — 원문에 없는 보충은 노트에 쓰지 않는다")

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
    s = sub.add_parser("stamp", help="트리에 추출본 쪽별 해시를 찍는다")
    s.add_argument("tree")
    s.add_argument("--text", required=True)
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    text = read(a.text)
    if a.cmd == "stamp":
        data = json.loads(read(a.tree))
        Path(a.tree).write_text(json.dumps(stamp_tree(data, text), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"쪽 {len(data['page_sha'])}개 해시를 찍음: {a.tree}")
        return 0
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
