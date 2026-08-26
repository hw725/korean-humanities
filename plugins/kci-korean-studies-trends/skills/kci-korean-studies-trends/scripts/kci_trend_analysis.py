#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
kci_trend_analysis.py - KCI JSONL corpus trend summaries.

Usage:
  python scripts/kci_trend_analysis.py --corpus intermediate_results/kci_2025_corpus.jsonl --year 2025
  python scripts/kci_trend_analysis.py --corpus intermediate_results/kci_2020_2024_corpus.jsonl --use-citations --window-label 2020-2024
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
import unicodedata
import sys

# CJK Text Contract 1-b: Windows cp949 콘솔에서 한글 출력이 UnicodeEncodeError로 죽는 것 차단
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable, Optional


# [korean-humanities trends 벤더링본] 개인 경로 기본값 제거 —
# 작업 루트는 KCI_TRENDS_DIR 환경변수(없으면 cwd의 kci-trends/), 프로파일은 스킬 동봉본.
import os
DEFAULT_PIPELINE = Path(os.environ.get("KCI_TRENDS_DIR", "kci-trends"))
DEFAULT_PROFILE = Path(__file__).resolve().parent.parent / "assets" / "kci_korean_studies_journals.json"
DEFAULT_OUT_DIR = DEFAULT_PIPELINE
DEFAULT_REPORT = DEFAULT_OUT_DIR / "kci_trend_report.md"



def _is_cjk_token_char(ch: str) -> bool:
    """토큰 구성 문자 — 한글(음절+옛한글 자모)·한자(확장 B+ 포함)·ASCII 영숫자.

    [local divergence] upstream의 [가-힣A-Za-z0-9一-鿿] 클래스는 옛한글 첫가끝과
    한자 확장 A/B를 놓쳐 전근대 문헌 제목의 핵심어가 통째로 사라졌다(CJK 계약 R1).
    문자클래스 대신 코드포인트 판별 — stdlib 유지.
    """
    o = ord(ch)
    if ch.isascii():
        return ch.isalnum()
    return (0xAC00 <= o <= 0xD7A3 or 0x1100 <= o <= 0x11FF or 0x3130 <= o <= 0x318F
            or 0xA960 <= o <= 0xA97F or 0xD7B0 <= o <= 0xD7FF
            or 0x3400 <= o <= 0x9FFF or 0xF900 <= o <= 0xFAFF or 0x20000 <= o <= 0x2FA1F)


def _token_runs(text: str, min_len: int = 2) -> list[str]:
    out, buf = [], []
    for ch in text:
        if _is_cjk_token_char(ch):
            buf.append(ch)
        elif buf:
            if len(buf) >= min_len:
                out.append("".join(buf))
            buf = []
    if len(buf) >= min_len:
        out.append("".join(buf))
    return out


STOPWORDS = {
    "연구", "고찰", "분석", "검토", "중심", "대한", "통해", "양상", "의미", "방안", "현황", "과제",
    "한국", "조선", "시대", "관련", "기반", "활용", "자료", "문제", "특징", "재론", "비교", "논의",
    "중심으로", "나타난", "대하여", "관한", "위한", "양상과", "구조와", "연구의", "일고찰", "새로운",
    "변화", "성격", "인식", "활동", "표현", "사용", "제시", "구현", "전개", "형성", "통한", "따른",
    "사례를", "관점에서", "관하여", "정비와", "구성과", "실제", "방법", "내용", "수록", "검토를",
    "통하여", "비판적", "가능성과", "맥락과", "방향", "탐색", "기대와", "전망",
    "article", "study", "korean", "analysis", "research", "review", "based", "using",
}

FIELD_LABELS = {
    "hanmun": "한문학",
    "hanmun_education": "한문교육",
    "korean_literature": "국문학·고전문학",
    "korean_language": "국어학",
    "korean_history": "한국사",
    "history_education": "역사교육",
    "korean_studies": "한국학 종합",
    "unclassified": "미분류",
}


def clean_text(value: object) -> str:
    if value is None:
        return ""
    value = unicodedata.normalize("NFC", str(value))
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def load_jsonl(path: Path) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise ValueError(f"{path}:{line_no} JSON decode failed: {e}") from e
    return records


def load_profile(path: Path) -> list[dict[str, object]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    journals = data.get("journals", [])
    return [item for item in journals if isinstance(item, dict)]


def field_label(field: str) -> str:
    return FIELD_LABELS.get(field, field)


def match_key(value: object) -> str:
    value = unicodedata.normalize("NFC", clean_text(value))
    value = re.sub(r"\s*[\(\（][^\)\）]+[\)\）]\s*", "", value)
    return re.sub(r"[\s\W_]+", "", value, flags=re.UNICODE).lower()


def sere_id_key(value: object) -> str:
    return re.sub(r"\D+", "", clean_text(value))


def profile_alias_keys(item: dict[str, object]) -> set[str]:
    values: list[object] = [
        item.get("name"),
        item.get("workbook_title"),
        item.get("publisher"),
    ]
    aliases = item.get("aliases") or []
    if isinstance(aliases, list):
        values.extend(aliases)
    return {match_key(value) for value in values if match_key(value)}


def build_profile_indexes(profile: list[dict[str, object]]) -> tuple[dict[str, dict[str, object]], dict[str, dict[str, object]]]:
    by_sere: dict[str, dict[str, object]] = {}
    by_name: dict[str, dict[str, object]] = {}
    for item in profile:
        sere_id = sere_id_key(item.get("kci_sere_id"))
        if sere_id:
            by_sere[sere_id] = item
        for key in profile_alias_keys(item):
            by_name.setdefault(key, item)
    return by_sere, by_name


def apply_profile_overrides(
    records: list[dict[str, object]],
    profile: list[dict[str, object]],
) -> list[dict[str, object]]:
    by_sere, by_name = build_profile_indexes(profile)
    out: list[dict[str, object]] = []
    for record in records:
        updated = dict(record)
        embedded = updated.get("journal_profile")
        if not isinstance(embedded, dict):
            embedded = {}
        match = None
        sere_id = sere_id_key(updated.get("sere_id"))
        if sere_id:
            match = by_sere.get(sere_id)
        if match is None:
            for value in (embedded.get("workbook_title"), embedded.get("name"), updated.get("journal")):
                key = match_key(value)
                if key in by_name:
                    match = by_name[key]
                    break
        if match is not None:
            updated["journal_profile"] = {**embedded, **match}
        else:
            updated["journal_profile"] = embedded
        out.append(updated)
    return out


def dedupe_records(records: Iterable[dict[str, object]]) -> list[dict[str, object]]:
    seen: set[str] = set()
    out: list[dict[str, object]] = []
    for record in records:
        kci_id = clean_text(record.get("kci_id"))
        if not kci_id or kci_id in seen:
            continue
        seen.add(kci_id)
        out.append(record)
    return out


def profile_value(record: dict[str, object], key: str, default: str = "") -> str:
    profile = record.get("journal_profile")
    if isinstance(profile, dict):
        value = profile.get(key)
        if value is not None:
            return clean_text(value)
    return default


def record_field(record: dict[str, object]) -> str:
    return profile_value(record, "field", "unclassified")


def record_category(record: dict[str, object]) -> str:
    return profile_value(record, "source_category", "미분류")


def record_subfield(record: dict[str, object]) -> str:
    return profile_value(record, "source_subfield", "미분류")


def record_workbook_title(record: dict[str, object]) -> str:
    return profile_value(record, "workbook_title", clean_text(record.get("journal")))


def split_keywords(value: object) -> list[str]:
    if isinstance(value, list):
        raw = [clean_text(v) for v in value]
    else:
        raw = re.split(r"[,;，；ㆍ·/]", clean_text(value))
    return [item for item in raw if item and len(item) >= 2]


def tokenize(text: str) -> list[str]:
    text = unicodedata.normalize("NFC", clean_text(text)).lower()
    tokens = _token_runs(text, min_len=2)
    out: list[str] = []
    for token in tokens:
        if token in STOPWORDS:
            continue
        if token.isdigit():
            continue
        out.append(token)
    return out


def article_terms(record: dict[str, object]) -> list[str]:
    terms: list[str] = []
    for keyword in split_keywords(record.get("keywords")):
        normalized = clean_text(keyword).lower()
        if normalized and normalized not in STOPWORDS:
            terms.append(normalized)
    terms.extend(tokenize(clean_text(record.get("title"))))
    return terms


def citation_count(record: dict[str, object]) -> int:
    value = record.get("citation_count")
    if isinstance(value, int):
        return value
    match = re.search(r"\d+", clean_text(value))
    return int(match.group(0)) if match else 0


def score_record(record: dict[str, object], field_terms: Counter[str], use_citations: bool) -> int:
    terms = set(article_terms(record))
    term_score = sum(field_terms.get(term, 0) for term in terms)
    metadata_score = 0
    if split_keywords(record.get("keywords")):
        metadata_score += 5
    if clean_text(record.get("abstract")):
        metadata_score += 5
    if use_citations:
        metadata_score += citation_count(record) * 10
    return term_score + metadata_score


def representative_candidates(
    field_records: list[dict[str, object]],
    field_terms: Counter[str],
    use_citations: bool,
    limit: int,
    max_per_journal: int,
) -> list[dict[str, object]]:
    scored = sorted(
        field_records,
        key=lambda r: (score_record(r, field_terms, use_citations), citation_count(r), clean_text(r.get("title"))),
        reverse=True,
    )
    selected: list[dict[str, object]] = []
    selected_ids: set[str] = set()
    journal_counts: Counter[str] = Counter()
    for record in scored:
        journal = record_workbook_title(record)
        if max_per_journal > 0 and journal_counts[journal] >= max_per_journal:
            continue
        selected.append(record)
        selected_ids.add(clean_text(record.get("kci_id")))
        journal_counts[journal] += 1
        if len(selected) >= limit:
            return selected
    for record in scored:
        kci_id = clean_text(record.get("kci_id"))
        if kci_id in selected_ids:
            continue
        selected.append(record)
        selected_ids.add(kci_id)
        if len(selected) >= limit:
            break
    return selected


def row_for_record(
    record: dict[str, object],
    field: str,
    rank: int,
    field_terms: Counter[str],
    use_citations: bool,
) -> dict[str, object]:
    return {
        "field": field,
        "field_label": field_label(field),
        "rank": rank,
        "score": score_record(record, field_terms, use_citations),
        "citation_count": citation_count(record),
        "kci_id": clean_text(record.get("kci_id")),
        "year": clean_text(record.get("year")),
        "journal": record_workbook_title(record),
        "title": clean_text(record.get("title")),
        "authors": "; ".join(clean_text(a) for a in record.get("authors", []) if clean_text(a)),
        "doi": clean_text(record.get("doi")),
        "kci_url": clean_text(record.get("url")),
    }


def build_topic_groups(
    records: list[dict[str, object]],
    field_term_counts: dict[str, Counter[str]],
    use_citations: bool,
    topics_per_field: int,
    papers_per_topic: int,
    min_topic_count: int,
) -> list[dict[str, object]]:
    groups: list[dict[str, object]] = []
    by_field = group_records(records, key=record_field)
    for field, field_records in sorted(by_field.items()):
        candidates: list[dict[str, object]] = []
        seeds = [
            term for term, count in field_term_counts[field].most_common(80)
            if count >= min_topic_count and term not in STOPWORDS
        ]
        for seed in seeds:
            matching = [record for record in field_records if seed in set(article_terms(record))]
            if len(matching) < min_topic_count:
                continue
            matching_ids = {clean_text(record.get("kci_id")) for record in matching}

            co_terms: Counter[str] = Counter()
            journals: Counter[str] = Counter()
            citation_sum = 0
            for record in matching:
                journals[record_workbook_title(record)] += 1
                citation_sum += citation_count(record)
                for term in set(article_terms(record)):
                    if term != seed and term not in STOPWORDS:
                        co_terms[term] += 1

            label_terms = [seed, *[term for term, _count in co_terms.most_common(4)]]
            label = " · ".join(label_terms[:4])
            topic_score = len(matching) * 10 + len(journals) * 3
            if use_citations:
                topic_score += citation_sum * 5

            selected = representative_candidates(
                matching,
                field_term_counts[field],
                use_citations=use_citations,
                limit=papers_per_topic,
                max_per_journal=2,
            )
            candidates.append({
                "field": field,
                "field_label": field_label(field),
                "seed": seed,
                "label": label,
                "article_count": len(matching),
                "journal_count": len(journals),
                "citation_sum": citation_sum,
                "score": topic_score,
                "record_ids": matching_ids,
                "terms": [{"term": term, "count": count} for term, count in co_terms.most_common(20)],
                "papers": [
                    row_for_record(record, field, rank, field_term_counts[field], use_citations)
                    for rank, record in enumerate(selected, start=1)
                ],
            })

        candidates.sort(key=lambda group: (int(group["score"]), int(group["article_count"]), str(group["label"])), reverse=True)
        selected_groups: list[dict[str, object]] = []
        for group in candidates:
            group_ids = set(group["record_ids"])
            too_similar = False
            for selected in selected_groups:
                selected_ids = set(selected["record_ids"])
                intersection = len(group_ids & selected_ids)
                union = len(group_ids | selected_ids) or 1
                if intersection / union >= 0.45:
                    too_similar = True
                    break
            if too_similar:
                continue
            selected_groups.append(group)
            if len(selected_groups) >= topics_per_field:
                break
        for group in selected_groups:
            group.pop("record_ids", None)
        groups.extend(selected_groups)
    groups.sort(key=lambda group: (str(group["field"]), -int(group["score"]), str(group["label"])))
    return groups


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_topic_evidence(
    path: Path,
    records: list[dict[str, object]],
    field_term_counts: dict[str, Counter[str]],
    terms_per_field: int = 40,
    evidence_per_term: int = 8,
) -> None:
    wanted = {
        field: {term for term, _count in counts.most_common(terms_per_field)}
        for field, counts in field_term_counts.items()
    }
    evidence: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for record in records:
        field = record_field(record)
        if field not in wanted:
            continue
        terms = set(article_terms(record)) & wanted[field]
        for term in terms:
            key = (field, term)
            if len(evidence[key]) >= evidence_per_term:
                continue
            evidence[key].append({
                "kci_id": clean_text(record.get("kci_id")),
                "title": clean_text(record.get("title")),
                "journal": record_workbook_title(record),
                "year": clean_text(record.get("year")),
                "url": clean_text(record.get("url")),
            })

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for field, counts in sorted(field_term_counts.items()):
            for term, count in counts.most_common(terms_per_field):
                f.write(json.dumps({
                    "field": field,
                    "field_label": field_label(field),
                    "term": term,
                    "count": count,
                    "evidence": evidence.get((field, term), []),
                }, ensure_ascii=False) + "\n")


def build_outputs(
    records: list[dict[str, object]],
    profile: list[dict[str, object]],
    out_dir: Path,
    report_path: Path,
    year: Optional[int],
    use_citations: bool,
    window_label: str,
    top_n_terms: int,
    representative_per_field: int,
    max_per_journal_representatives: int,
    topics_per_field: int,
    papers_per_topic: int,
    min_topic_count: int,
    selected_fields: Optional[set[str]],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    field_counts = Counter(record_field(r) for r in records)
    category_counts = Counter(record_category(r) for r in records)
    subfield_counts = Counter((record_category(r), record_subfield(r)) for r in records)
    journal_counts = Counter(record_workbook_title(r) for r in records)

    profile_titles = [clean_text(j.get("workbook_title") or j.get("name")) for j in profile]
    missing_titles = [title for title in profile_titles if title and title not in journal_counts]

    term_counts: Counter[tuple[str, str]] = Counter()
    field_term_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for record in records:
        field = record_field(record)
        for term in article_terms(record):
            term_counts[(field, term)] += 1
            field_term_counts[field][term] += 1

    journal_rows = [
        {
            "journal": journal,
            "count": count,
        }
        for journal, count in journal_counts.most_common()
    ]
    field_rows = [
        {
            "field": field,
            "field_label": field_label(field),
            "count": count,
        }
        for field, count in field_counts.most_common()
    ]
    category_rows = [
        {
            "category": category,
            "count": count,
        }
        for category, count in category_counts.most_common()
    ]
    subfield_rows = [
        {
            "category": category,
            "subfield": subfield,
            "count": count,
        }
        for (category, subfield), count in subfield_counts.most_common()
    ]
    term_rows = [
        {
            "field": field,
            "field_label": field_label(field),
            "term": term,
            "count": count,
        }
        for (field, term), count in term_counts.most_common()
    ]

    representative_rows: list[dict[str, object]] = []
    for field, field_records in group_records(records, key=record_field).items():
        selected = representative_candidates(
            field_records,
            field_term_counts[field],
            use_citations=use_citations,
            limit=representative_per_field,
            max_per_journal=max_per_journal_representatives,
        )
        for rank, record in enumerate(selected, start=1):
            representative_rows.append(row_for_record(record, field, rank, field_term_counts[field], use_citations))

    topic_groups = build_topic_groups(
        records,
        field_term_counts,
        use_citations=use_citations,
        topics_per_field=topics_per_field,
        papers_per_topic=papers_per_topic,
        min_topic_count=min_topic_count,
    )

    write_csv(out_dir / f"kci_{window_label}_journal_counts.csv", journal_rows, ["journal", "count"])
    write_csv(out_dir / f"kci_{window_label}_field_counts.csv", field_rows, ["field", "field_label", "count"])
    write_csv(out_dir / f"kci_{window_label}_category_counts.csv", category_rows, ["category", "count"])
    write_csv(out_dir / f"kci_{window_label}_subfield_counts.csv", subfield_rows, ["category", "subfield", "count"])
    write_csv(out_dir / f"kci_{window_label}_topic_terms.csv", term_rows[:500], ["field", "field_label", "term", "count"])
    write_csv(
        out_dir / f"kci_{window_label}_representative_candidates.csv",
        representative_rows,
        ["field", "field_label", "rank", "score", "citation_count", "kci_id", "year", "journal", "title", "authors", "doi", "kci_url"],
    )
    topic_group_rows = [
        {
            "field": group["field"],
            "field_label": group["field_label"],
            "seed": group["seed"],
            "label": group["label"],
            "article_count": group["article_count"],
            "journal_count": group["journal_count"],
            "citation_sum": group["citation_sum"],
            "score": group["score"],
            "paper_kci_ids": "; ".join(str(paper["kci_id"]) for paper in group["papers"]),
        }
        for group in topic_groups
    ]
    write_csv(
        out_dir / f"kci_{window_label}_topic_groups.csv",
        topic_group_rows,
        ["field", "field_label", "seed", "label", "article_count", "journal_count", "citation_sum", "score", "paper_kci_ids"],
    )

    write_topic_evidence(out_dir / f"kci_{window_label}_topic_evidence.jsonl", records, field_term_counts)

    topic_json = {
        "window": window_label,
        "year": year,
        "use_citations": use_citations,
        "selected_fields": sorted(selected_fields) if selected_fields else None,
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "total_articles": len(records),
        "field_terms": {
            field: [{"term": term, "count": count} for term, count in counts.most_common(40)]
            for field, counts in field_term_counts.items()
        },
        "topic_groups": topic_groups,
        "missing_profile_journals": missing_titles,
    }
    (out_dir / f"kci_{window_label}_topic_clusters.json").write_text(
        json.dumps(topic_json, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    report_path.write_text(
        render_report(
            records=records,
            window_label=window_label,
            year=year,
            use_citations=use_citations,
            field_rows=field_rows,
            category_rows=category_rows,
            subfield_rows=subfield_rows,
            journal_rows=journal_rows,
            field_term_counts=field_term_counts,
            representative_rows=representative_rows,
            topic_groups=topic_groups,
            missing_titles=missing_titles,
            top_n_terms=top_n_terms,
            profile_count=len(profile),
            selected_fields=selected_fields,
        ),
        encoding="utf-8",
    )


def group_records(records: list[dict[str, object]], key) -> dict[str, list[dict[str, object]]]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for record in records:
        grouped[key(record)].append(record)
    return dict(grouped)


def render_report(
    records: list[dict[str, object]],
    window_label: str,
    year: Optional[int],
    use_citations: bool,
    field_rows: list[dict[str, object]],
    category_rows: list[dict[str, object]],
    subfield_rows: list[dict[str, object]],
    journal_rows: list[dict[str, object]],
    field_term_counts: dict[str, Counter[str]],
    representative_rows: list[dict[str, object]],
    topic_groups: list[dict[str, object]],
    missing_titles: list[str],
    top_n_terms: int,
    profile_count: int,
    selected_fields: Optional[set[str]],
) -> str:
    title_year = str(year) if year else window_label
    scope_label = "한국학"
    if selected_fields:
        scope_label = "·".join(field_label(field) for field in sorted(selected_fields))
    lines = [
        "---",
        "type: research-report",
        "source_db: KCI",
        f"corpus_window: {json.dumps(window_label, ensure_ascii=False)}",
        f"generated: {dt.date.today().isoformat()}",
        "verification_layer: Layer 2",
        "verification_scope: abstract-only",
        "status: pending-review",
        "---",
        "",
        f"# {title_year} KCI {scope_label} 동향 전수조사",
        "",
        "## 조사 범위",
        "",
        f"- 대상 논문 수: {len(records)}",
        f"- 대상 학술지: 엑셀 기반 KCI 프로필 {profile_count}종",
        "- 근거 자료: KCI 서지정보, 초록, 키워드",
        "- 본문 PDF 확인 전이므로 개별 논문 내용 판단은 Layer 2 abstract-only로 제한",
        "- 보고서의 주제어·대표 논문은 코퍼스 기반 후보이며, 본문 독해 전 확정 판단으로 쓰지 않음",
    ]
    if use_citations:
        lines.append("- 조사시점 기준 2년 전 이하 연도이므로 대표 후보 산정에 KCI 피인용 수를 보조 지표로 사용")
    else:
        lines.append("- 조사시점 기준 피인용 누적이 부족한 최근 연도이므로 KCI 피인용 수는 대표성 판단에 사용하지 않음")

    lines.extend(["", "## 분야별 논문 수", ""])
    for row in field_rows:
        lines.append(f"- {row['field_label']} (`{row['field']}`): {row['count']}건")

    lines.extend(["", "## 원자료 분야별 논문 수", ""])
    for row in category_rows:
        lines.append(f"- {row['category']}: {row['count']}건")

    lines.extend(["", "## 세부분야 상위", ""])
    for row in subfield_rows[:20]:
        lines.append(f"- {row['category']} / {row['subfield']}: {row['count']}건")

    lines.extend(["", "## 학술지별 논문 수 상위", ""])
    for row in journal_rows[:20]:
        lines.append(f"- {row['journal']}: {row['count']}건")

    lines.extend(["", "## 분야별 빈출 주제어 후보", ""])
    for field, counts in sorted(field_term_counts.items()):
        top_terms = ", ".join(f"{term}({count})" for term, count in counts.most_common(top_n_terms))
        lines.append(f"- {field_label(field)} (`{field}`): {top_terms}")

    lines.extend(["", "## 주제별 묶음", ""])
    grouped_topics = group_records(topic_groups, key=lambda r: str(r["field"]))
    for field, groups in sorted(grouped_topics.items()):
        lines.append(f"### {field_label(field)} (`{field}`)")
        for group in groups:
            lines.append(
                f"#### {group['label']} "
                f"({group['article_count']}건, {group['journal_count']}개 학술지)"
            )
            for paper in group["papers"]:
                citation_note = f", 피인용 {paper['citation_count']}" if use_citations else ""
                lines.append(
                    f"- {paper['title']} — {paper['authors']} / {paper['journal']} "
                    f"({paper['year']}, KCI {paper['kci_id']}{citation_note})"
                )

    lines.extend(["", "## 대표 논문 후보", ""])
    grouped = group_records(representative_rows, key=lambda r: str(r["field"]))
    for field, rows in sorted(grouped.items()):
        lines.append(f"### {field_label(field)} (`{field}`)")
        for row in rows:
            citation_note = f", 피인용 {row['citation_count']}" if use_citations else ""
            lines.append(
                f"- {row['rank']}. {row['title']} — {row['authors']} / {row['journal']} "
                f"({row['year']}, KCI {row['kci_id']}{citation_note})"
            )

    if missing_titles:
        lines.extend(["", "## 0건 또는 미수집 후보", ""])
        lines.append("아래 학술지는 이번 코퍼스에 2025년 논문이 잡히지 않았습니다. 실제 0건인지 KCI 검색 제한인지 별도 확인이 필요합니다.")
        for title in missing_titles:
            lines.append(f"- {title}")

    lines.extend([
        "",
        "## 후속 작업",
        "",
        "- 5년치 또는 10년치 코퍼스에서는 `--use-citations`를 켜고 KCI 피인용 누적을 보조 지표로 사용",
        "- PDF 확보 논문은 Layer 1로 승격 후 본문 논점 기준 재분류",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="KCI JSONL corpus trend summaries")
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--year", type=int)
    parser.add_argument("--field", action="append",
                        help="분석 field 필터. 예: hanmun, hanmun_education, korean_history, history_education. 여러 번 지정 가능")
    parser.add_argument("--window-label", default="")
    parser.add_argument("--top-n-terms", type=int, default=20)
    parser.add_argument("--representative-per-field", type=int, default=0,
                        help="field별 대표 논문 후보 수. 0이면 전체 보고서 10개, 전공별 보고서 30개")
    parser.add_argument("--max-per-journal-representatives", type=int, default=2,
                        help="대표 후보가 한 학술지에 과도하게 몰리지 않도록 1차 선별에서 적용할 상한. 부족하면 나머지는 채움")
    parser.add_argument("--topics-per-field", type=int, default=0,
                        help="field별 주제 묶음 수. 0이면 전체 보고서 6개, 전공별 보고서 12개")
    parser.add_argument("--papers-per-topic", type=int, default=0,
                        help="주제 묶음별 논문 후보 수. 0이면 전체 보고서 3개, 전공별 보고서 6개")
    parser.add_argument("--min-topic-count", type=int, default=3,
                        help="주제 seed가 되기 위한 최소 논문 수")
    parser.add_argument("--citation-lag-years", type=int, default=2,
                        help="조사시점 기준 몇 년 전 논문부터 피인용 지표를 반영할지. 기본 2년")
    parser.add_argument("--use-citations", action="store_true", help="연도와 무관하게 피인용 지표를 강제로 사용")
    parser.add_argument("--no-citations", action="store_true", help="연도와 무관하게 피인용 지표를 사용하지 않음")
    args = parser.parse_args()

    records = dedupe_records(load_jsonl(args.corpus))
    profile = load_profile(args.profile)
    records = apply_profile_overrides(records, profile)
    if args.year:
        records = [record for record in records if clean_text(record.get("year")) == str(args.year)]
    selected_fields = set(args.field or []) or None
    if selected_fields:
        records = [record for record in records if record_field(record) in selected_fields]
        profile = [item for item in profile if clean_text(item.get("field")) in selected_fields]
    detailed_field_report = bool(selected_fields and len(selected_fields) == 1)
    representative_per_field = args.representative_per_field or (30 if detailed_field_report else 10)
    topics_per_field = args.topics_per_field or (12 if detailed_field_report else 6)
    papers_per_topic = args.papers_per_topic or (6 if detailed_field_report else 3)
    window_label = args.window_label or (str(args.year) if args.year else args.corpus.stem)
    citation_cutoff = dt.date.today().year - args.citation_lag_years
    use_citations = args.use_citations or bool(args.year and args.year <= citation_cutoff)
    if args.no_citations:
        use_citations = False
    build_outputs(
        records=records,
        profile=profile,
        out_dir=args.out_dir,
        report_path=args.report,
        year=args.year,
        use_citations=use_citations,
        window_label=window_label,
        top_n_terms=args.top_n_terms,
        representative_per_field=representative_per_field,
        max_per_journal_representatives=args.max_per_journal_representatives,
        topics_per_field=topics_per_field,
        papers_per_topic=papers_per_topic,
        min_topic_count=args.min_topic_count,
        selected_fields=selected_fields,
    )
    print(json.dumps({
        "corpus": str(args.corpus),
        "records": len(records),
        "out_dir": str(args.out_dir),
        "report": str(args.report),
        "citation_cutoff_year": citation_cutoff,
        "use_citations": use_citations,
        "selected_fields": sorted(selected_fields) if selected_fields else None,
        "representative_per_field": representative_per_field,
        "topics_per_field": topics_per_field,
        "papers_per_topic": papers_per_topic,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
