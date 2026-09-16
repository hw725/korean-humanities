#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
kci_citation_collect.py — KCI 참고문헌 서비스로 논문 인용 네트워크(엣지) 수집.

OpenAlex는 한국 인문학 인용을 커버하지 못한다(referenced_works=0). 대신 한국연구재단
KCI 참고문헌 서비스 `refInfo/openApiM320List`(★ 접두사 M — D272/D321은 부분/OA전용)를
쓰면 논문당 전체 참고문헌과 `REFE_BIBL_ARTI_ID`(참조가 KCI 논문일 때 그 논문 ID = 정확
직접인용 조인 키)를 얻는다. 실측: 한문학 참조의 약 25%가 KCI 논문으로 정확 연결.

용법:
  # KCI 검색어로 씨앗 논문 모으고 인용망 수집
  python kci_citation_collect.py --query "운양 김윤식" --max 40 --out-dir out/kys
  # artiId 목록 파일(줄당 ART#########)로
  python kci_citation_collect.py --arti-ids ids.txt --out-dir out/kys
  # 스노볼: 인용된 KCI 논문도 노드로 1홉 확장 (깊이는 --max-depth, 기본 1)
  python kci_citation_collect.py --query "운양 김윤식" --max 40 --snowball --out-dir out/kys

산출(out-dir):
  nodes.jsonl  — {kci_id,title,year,journal,seed}
  edges.jsonl  — {src,dst,dst_title,dst_year}  (src가 dst를 직접 인용, 둘 다 KCI 논문)
  refs.jsonl   — 논문별 전체 참조(텍스트 참조 포함, REFE_BIBL_ARTI_ID 유무)
  collect.seen — 처리한 artiId 체크포인트(재실행 resume)

키 해석 순서 (절대 로그 출력 안 함):
  1. 환경변수 KCI_DATA_GO_KR_KEY_DECODING (없으면 _ENCODING)
  2. --env로 지정한 .env 파일 (기본: cwd의 .env)
API 트래픽 개발계정 5,000/일 — 100건↑는 체크포인트로 나눠 실행 권장.

[korean-humanities suite 벤더링본] 원본: <corpus-pipeline>/scripts/kci_citation_collect.py.
로컬 분기: 키 해석에 환경변수 우선 추가, 기본 .env 경로를 파이프라인 상대에서
cwd 상대로 변경(스킬 단독 배포에서 <corpus-pipeline> 부재 가정). 로직 변경 없음.
"""
from __future__ import annotations

import argparse
import os
import json
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

# CJK 텍스트 계약 E3: Windows 콘솔 기본 cp949에서 한글·한자 출력이
# UnicodeEncodeError로 죽는 것을 막는다 (환경변수에 의존하지 않는 방어선).
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

DEFAULT_ENV = Path(".env")  # cwd 기준 — 환경변수가 있으면 파일은 아예 안 읽는다
M320 = "http://apis.data.go.kr/B552540/KCIOpenApi/refInfo/openApiM320List"
UA = {"User-Agent": "kci_citation_collect/1.0 personal research"}
_ARTI_RE = None


def load_key(env_path: Path) -> str:
    # 1순위: 환경변수 (스킬 단독 배포·CI에서 .env 없이 동작)
    env_key = os.environ.get("KCI_DATA_GO_KR_KEY_DECODING") or os.environ.get("KCI_DATA_GO_KR_KEY_ENCODING")
    if env_key:
        return env_key.strip()
    if not env_path.exists():
        sys.exit(f"[에러] 환경변수 KCI_DATA_GO_KR_KEY_DECODING 미설정이고 .env도 없음: {env_path}")
    kv = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            kv[k.strip()] = v.strip()
    key = kv.get("KCI_DATA_GO_KR_KEY_DECODING") or kv.get("KCI_DATA_GO_KR_KEY_ENCODING")
    if not key:
        sys.exit("[에러] .env에 KCI_DATA_GO_KR_KEY_DECODING 없음")
    return key


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s or "")


class KciApiError(RuntimeError):
    """KCI API가 성공 응답을 주지 않았다. 이 논문은 완료로 기록하지 않는다."""


def fetch_refs(key: str, arti_id: str, sleep: float, retries: int = 3) -> list[dict]:
    """openApiM320List로 논문 한 편의 전체 참고문헌을 페이지네이션하여 반환."""
    refs: list[dict] = []
    page = 1
    while True:
        q = {"serviceKey": key, "pageNo": str(page), "recordCnt": "100", "artiId": arti_id}
        url = M320 + "?" + urllib.parse.urlencode(q)
        raw = None
        for attempt in range(retries):
            try:
                req = urllib.request.Request(url, headers=UA)
                with urllib.request.urlopen(req, timeout=40) as r:
                    raw = r.read().decode("utf-8", errors="replace")
                break
            except (urllib.error.URLError, TimeoutError) as e:
                if attempt == retries - 1:
                    raise
                time.sleep(1.5 * (attempt + 1))
        # 오류를 「참고문헌 0건」으로 삼키지 않는다. 예전 판은 파싱 실패·빈 응답에서
        # break로 빠져 빈 리스트를 성공처럼 돌려줬고, 호출부가 그 논문을 완료로 기록해
        # **키·네트워크를 고친 뒤 재개해도 영원히 건너뛰었다**
        # (2026-09-15 Codex 교차검증 Important 4). 실패는 예외로 올려 호출부가 미완료로 남긴다.
        try:
            root = ET.fromstring(raw)
        except ET.ParseError as e:
            raise KciApiError(
                f"{arti_id} p{page}: XML 파싱 실패 — 응답 앞부분 {raw[:120]!r}") from e
        code = (root.findtext(".//resultCode") or "").strip()
        msg = (root.findtext(".//resultMsg") or "").strip()
        if code and code not in ("00", "0"):
            raise KciApiError(f"{arti_id} p{page}: API 오류 resultCode={code} resultMsg={msg!r}")
        items = root.findall(".//item")
        if not items:
            if page == 1:
                break  # 참고문헌이 실제로 0건 — 정상
            # 2페이지 이후가 비었다는 것은 앞서 totalCount가 더 있다고 했다는 뜻이다.
            raise KciApiError(f"{arti_id} p{page}: 페이지가 비었으나 앞 페이지는 더 있다고 보고했다")
        for it in items:
            g = lambda t: nfc((it.findtext(t) or "").strip())
            refs.append({
                "refe_bibl_id": g("REFE_BIBL_ID"),
                "dst": g("REFE_BIBL_ARTI_ID"),      # 참조가 KCI 논문이면 그 artiId (정확 조인 키)
                "author": g("SEAR_CRET_NM") or g("CRET_NM"),
                "title": g("SEAR_TITL") or g("TITL"),
                "year": g("PUBI_YR"),
                "journal": g("DATA_NATE"),
                "type_cd": g("REFE_BIBL_TYPE_CD"),
                "doi": g("DOI"),
            })
        total = int(root.findtext(".//totalCount") or "0")
        if len(items) < 100 or page * 100 >= total:
            break
        page += 1
        time.sleep(sleep)
    return refs


def resolve_seeds_by_query(query: str, max_n: int, since: Optional[int], until: Optional[int],
                           sleep: float) -> list[dict]:
    """kci_ingest.py의 KCI 검색을 재사용해 씨앗 artiId+제목+연도 확보.

    씨앗 검색은 동봉된 kci_search.py(같은 디렉터리, stdlib 전용)가 기본이다 —
    별도 설치·API 키 없이 동작한다. KCI_INGEST_DIR 환경변수가 있으면 그쪽의
    전체 수집기(kci_ingest.py)를 우선 쓴다(개인 파이프라인 통합용).
    """
    here = Path(__file__).resolve().parent
    ingest_dir = os.environ.get("KCI_INGEST_DIR")
    if ingest_dir and (Path(ingest_dir) / "kci_ingest.py").is_file():
        sys.path.insert(0, str(Path(ingest_dir)))
        from kci_ingest import HTTPClient, search_kci  # type: ignore
    else:
        sys.path.insert(0, str(here))
        try:
            from kci_search import HTTPClient, search_kci  # type: ignore
        except Exception as e:
            sys.exit(f"[에러] 동봉 kci_search 임포트 실패({e}) — 스킬 scripts/ 구성이 손상됐습니다.")
    client = HTTPClient(sleep_seconds=sleep, respect_robots=False)
    arts = search_kci(client, query, max_n, since, "KEYALL", until=until)
    out = []
    for a in arts[:max_n]:
        out.append({"kci_id": a.kci_id, "title": nfc(a.title), "year": a.year,
                    "journal": nfc(a.journal)})
    return out


def read_jsonl_safe(path: Path) -> list[dict]:
    """jsonl을 읽되 없거나 깨진 줄은 건너뛴다(재실행 복원용)."""
    if not path.exists():
        return []
    out: list[dict] = []
    for ln in path.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            obj = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            out.append(obj)
    return out


def load_seen(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {ln.strip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()}


def append_jsonl(path: Path, obj: dict) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="KCI 참고문헌 인용 네트워크 수집기")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--query", help="KCI 검색어(씨앗 논문 자동 수집)")
    src.add_argument("--arti-ids", type=Path, help="artiId 목록 파일(줄당 ART#########)")
    ap.add_argument("--max", type=int, default=40, help="--query 시 씨앗 최대 수")
    ap.add_argument("--since", type=int, help="발행연도 하한")
    ap.add_argument("--until", type=int, help="발행연도 상한")
    ap.add_argument("--snowball", action="store_true",
                    help="인용된 KCI 논문을 노드로 확장 (기본 1홉 — --max-depth로 조정)")
    ap.add_argument("--max-depth", type=int, default=1,
                    help="--snowball 확장 깊이. 씨앗이 0, 씨앗의 참고문헌이 1. "
                         "기본 1 = 문서가 말하는 1홉. 0이면 확장하지 않는다")
    ap.add_argument("--out-dir", type=Path, help="산출 디렉터리 (--preview가 아니면 필수)")
    ap.add_argument("--env", type=Path, default=DEFAULT_ENV)
    ap.add_argument("--sleep", type=float, default=0.25, help="API 요청 간 sleep 초")
    ap.add_argument("--preview", action="store_true",
                    help="씨앗 후보만 TSV로 출력하고 종료 — 동명이인·무관 논문 확인용 (수집 안 함, 키 불필요)")
    args = ap.parse_args(argv)

    # --preview: 씨앗 후보만 보여주고 종료 (SKILL.md §0의 "제목 보여주고 확인" 공식 수단)
    if args.preview:
        if not args.query:
            sys.exit("[에러] --preview는 --query와 함께 쓴다")
        seeds = resolve_seeds_by_query(args.query, args.max, args.since, args.until, args.sleep)
        print("# 씨앗 후보 — 무관·동명이인 행을 지우고 --arti-ids 파일로 저장해 수집하라")
        print("# kci_id	title	year	journal")
        for s_ in seeds:
            print(f"{s_['kci_id']}	{s_['title']}	{s_['year']}	{s_['journal']}")
        return 0

    if not args.out_dir:
        sys.exit("[에러] --out-dir이 필요하다 (--preview 모드가 아니면)")
    key = load_key(args.env)
    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    nodes_p, edges_p, refs_p, seen_p = (out / "nodes.jsonl", out / "edges.jsonl",
                                        out / "refs.jsonl", out / "collect.seen")

    # 씨앗 확보
    if args.query:
        seeds = resolve_seeds_by_query(args.query, args.max, args.since, args.until, args.sleep)
    else:
        seeds = []
        for ln in args.arti_ids.read_text(encoding="utf-8").splitlines():
            ln = ln.strip()
            if not ln.startswith("ART"):
                continue
            # "ARTID" 또는 "ARTID<탭>제목<탭>연도<탭>저널" 허용
            parts = ln.split("\t")
            seeds.append({"kci_id": parts[0].strip(),
                          "title": nfc(parts[1].strip()) if len(parts) > 1 else "",
                          "year": parts[2].strip() if len(parts) > 2 else "",
                          "journal": nfc(parts[3].strip()) if len(parts) > 3 else ""})

    seen = load_seen(seen_p)
    # 재실행 복원: 기존 nodes.jsonl을 먼저 읽어 들인다. 예전 판은 빈 사전에서 시작해
    # 씨앗만 등록하고 마지막에 nodes.jsonl을 통째로 덮어써서, 재실행하면 **지난번에
    # 발견한 피인용 노드가 전부 사라졌다.** 엣지는 남지만 그래프 변환기가 노드 집합
    # 밖이라며 연결을 버린다(2026-09-15 Codex 교차검증 Important 3).
    node_meta: dict[str, dict] = {}          # kci_id -> {title,year,journal,seed}
    restored = 0
    for rec in read_jsonl_safe(nodes_p):
        kid = rec.get("kci_id")
        if kid:
            node_meta[kid] = {k: v for k, v in rec.items() if k != "kci_id"}
            restored += 1
    for s in seeds:
        # 씨앗은 언제나 seed=True로 올린다(지난 실행에서 피인용 노드로 먼저 들어왔을 수 있다).
        node_meta[s["kci_id"]] = {**node_meta.get(s["kci_id"], {}), **s, "seed": True}

    print("=" * 66)
    snow = f"snowball=깊이 {args.max_depth}" if args.snowball else "snowball=off"
    print(f"씨앗 {len(seeds)}편, {snow}, out={out}")
    print(f"이미 처리(resume): {len(seen)}편, 복원한 기존 노드: {restored}")
    print("=" * 66)

    # 큐는 (kci_id, depth). 씨앗이 0, 씨앗의 참고문헌이 1이다. 예전 판은 깊이를 들고
    # 다니지 않아 새로 찾은 노드를 조건 없이 큐에 넣었고, 문서가 말한 「1홉 확장」과 달리
    # A→B→C→D…로 **깊이 제한 없이 퍼졌다**(2026-09-15 Codex 교차검증 Important 7).
    queue: list[tuple[str, int]] = [(s["kci_id"], 0) for s in seeds]
    edge_pairs: set[tuple] = set()
    processed = 0
    tot_ref = tot_link = 0
    depth_capped = 0
    failed = 0

    while queue:
        aid, depth = queue.pop(0)
        if aid in seen:
            continue
        try:
            refs = fetch_refs(key, aid, args.sleep)
        except Exception as e:
            # 완료(seen)로 기록하지 않는다 — 다음 실행이 이 논문을 다시 시도한다.
            print(f"  {aid} 실패(미완료로 남김): {type(e).__name__}: {e}")
            failed += 1
            continue
        n_link = sum(1 for r in refs if r["dst"])
        tot_ref += len(refs); tot_link += n_link
        meta = node_meta.get(aid, {"title": "", "year": "", "journal": "", "seed": False})
        print(f"[{processed+1}] {aid}  refs={len(refs):>3} KCI링크={n_link:>3}  {meta.get('title','')[:30]}")
        # refs 저장
        append_jsonl(refs_p, {"src": aid, "refs": refs})
        # 엣지 + (snowball) 새 노드
        for r in refs:
            dst = r["dst"]
            if not dst or dst == aid:
                continue
            if (aid, dst) not in edge_pairs:
                edge_pairs.add((aid, dst))
                append_jsonl(edges_p, {"src": aid, "dst": dst,
                                       "dst_title": r["title"], "dst_year": r["year"]})
            if dst not in node_meta:
                node_meta[dst] = {"title": r["title"], "year": r["year"],
                                  "journal": r["journal"], "seed": False}
                if args.snowball:
                    # 씨앗이 깊이 0, 씨앗의 참고문헌이 1. max-depth 1 = 「1홉 확장」이므로
                    # 깊이 1까지는 그 논문의 참고문헌도 캔다(경계 포함).
                    if depth + 1 <= args.max_depth:
                        queue.append((dst, depth + 1))
                    else:
                        # 노드·엣지로는 남기되 이 노드의 참고문헌은 더 캐지 않는다.
                        depth_capped += 1
        with seen_p.open("a", encoding="utf-8") as f:
            f.write(aid + "\n")
        seen.add(aid)
        processed += 1
        time.sleep(args.sleep)

    # 노드 저장(최종 메타)
    nodes_p.write_text("", encoding="utf-8")
    for kid, m in node_meta.items():
        append_jsonl(nodes_p, {"kci_id": kid, **m})

    print("=" * 66)
    print(f"처리 {processed}편, 노드 {len(node_meta)}, 엣지 {len(edge_pairs)}")
    if depth_capped:
        print(f"깊이 상한({args.max_depth})에서 확장 중단한 노드 {depth_capped}개 — "
              f"노드·엣지로는 남아 있다. 더 캐려면 --max-depth를 올린다")
    if failed:
        print(f"실패 {failed}편 — 완료로 기록하지 않았다. 같은 명령을 다시 돌리면 그 논문부터 재시도한다")
    if tot_ref:
        print(f"참조 {tot_ref}건 중 KCI 직접인용 {tot_link}건 ({tot_link/tot_ref*100:.1f}%)")
    print(f"→ {nodes_p}\n→ {edges_p}\n→ {refs_p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
