#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Merge KCI field shards into a single year corpus.

The field list is intentionally explicit so newly separated fields are not
silently dropped from full-year corpora.
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import sys

# CJK Text Contract 1-b: Windows cp949 콘솔에서 한글 출력이 UnicodeEncodeError로 죽는 것 차단
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

from pathlib import Path

from kci_trend_analysis import apply_profile_overrides, load_profile


import os
DEFAULT_PIPELINE = Path(os.environ.get("KCI_TRENDS_DIR", "kci-trends"))
DEFAULT_FIELDS = [
    "hanmun",
    "hanmun_education",
    "korean_literature",
    "korean_language",
    "korean_history",
    "history_education",
    "korean_studies",
]


def read_jsonl(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError as e:
                raise ValueError(f"{path}:{line_no} JSON decode failed: {e}") from e
            if isinstance(data, dict):
                rows.append(data)
    return rows


def record_key(record: dict[str, object]) -> str:
    for key in ("kci_id", "url", "doi"):
        value = str(record.get(key) or "").strip()
        if value:
            return f"{key}:{value}"
    title = str(record.get("title") or "").strip()
    journal = str(record.get("journal") or "").strip()
    year = str(record.get("year") or "").strip()
    return f"title:{year}:{journal}:{title}"


def record_field(record: dict[str, object]) -> str:
    profile = record.get("journal_profile") or {}
    if isinstance(profile, dict):
        field = str(profile.get("field") or "").strip()
        if field:
            return field
    return str(record.get("field") or "unclassified").strip() or "unclassified"


def write_jsonl_atomic(path: Path, records: list[dict[str, object]]) -> Path | None:
    path.parent.mkdir(parents=True, exist_ok=True)
    backup_path: Path | None = None
    if path.exists():
        stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_path = path.with_name(f"{path.stem}.bak-{stamp}{path.suffix}")
        path.replace(backup_path)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8", newline="\n") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    tmp_path.replace(path)
    return backup_path


def append_log(path: Path, event: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge KCI year field shards into one corpus")
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--pipeline-root", type=Path, default=DEFAULT_PIPELINE)
    parser.add_argument("--field", action="append", dest="fields",
                        help="Field shard to include. Defaults to all Korean studies fields.")
    parser.add_argument("--out", type=Path,
                        help="Output corpus path. Default: intermediate_results/kci_<year>_corpus.jsonl")
    parser.add_argument("--completeness", type=Path,
                        help="Completeness JSON path. Default: intermediate_results/kci_<year>_completeness.json")
    parser.add_argument("--base-corpus", type=Path,
                        help="Existing full corpus to seed before adding shards. Useful when only a newly added field shard exists.")
    parser.add_argument("--profile", type=Path,
                        help="Journal profile to reapply before writing. Default: config/kci_korean_studies_journals.json")
    parser.add_argument("--allow-missing", action="store_true",
                        help="Allow writing a corpus even when one or more requested field shards are missing.")
    args = parser.parse_args()

    pipeline_root = args.pipeline_root.resolve()
    intermediate = pipeline_root / "intermediate_results"
    fields = args.fields or DEFAULT_FIELDS
    out_path = args.out or intermediate / f"kci_{args.year}_corpus.jsonl"
    completeness_path = args.completeness or intermediate / f"kci_{args.year}_completeness.json"
    profile_path = args.profile or pipeline_root / "config" / "kci_korean_studies_journals.json"

    merged: list[dict[str, object]] = []
    seen: set[str] = set()
    shard_counts: dict[str, int] = {}
    duplicate_counts: collections.Counter[str] = collections.Counter()
    missing_shards: list[str] = []

    if args.base_corpus:
        for row in read_jsonl(args.base_corpus):
            key = record_key(row)
            if key in seen:
                duplicate_counts["base_corpus"] += 1
                continue
            merged.append(row)
            seen.add(key)

    for field in fields:
        shard = intermediate / f"kci_{args.year}_{field}_corpus.jsonl"
        rows = read_jsonl(shard)
        if not rows:
            missing_shards.append(field)
        shard_counts[field] = len(rows)
        for row in rows:
            key = record_key(row)
            if key in seen:
                duplicate_counts[field] += 1
                continue
            merged.append(row)
            seen.add(key)

    if missing_shards and not args.allow_missing and not args.base_corpus:
        missing = ", ".join(missing_shards)
        raise SystemExit(
            f"Refusing to overwrite full corpus because field shards are missing: {missing}. "
            "Collect all shards first, or pass --base-corpus with an existing full corpus."
        )

    if profile_path.exists():
        merged = apply_profile_overrides(merged, load_profile(profile_path))

    field_counts = collections.Counter(record_field(row) for row in merged)
    journal_counts = collections.Counter(str(row.get("journal") or "").strip() for row in merged)
    backup_path = write_jsonl_atomic(out_path, merged)

    completeness = {
        "year": args.year,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "corpus": str(out_path),
        "backup": str(backup_path) if backup_path else None,
        "base_corpus": str(args.base_corpus) if args.base_corpus else None,
        "profile": str(profile_path) if profile_path.exists() else None,
        "requested_shards": fields,
        "fields_present": sorted(field_counts),
        "total_records": len(merged),
        "shard_counts": shard_counts,
        "field_counts": dict(sorted(field_counts.items())),
        "journal_count": len([key for key in journal_counts if key]),
        "duplicate_counts": dict(duplicate_counts),
        "missing_shards": missing_shards,
    }
    completeness_path.write_text(json.dumps(completeness, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    append_log(
        pipeline_root / ".queue" / "kci-corpus-merge.jsonl",
        {
            "ts": dt.datetime.now(dt.timezone.utc).isoformat(),
            "event": "merge_year_corpus",
            "year": args.year,
            "corpus": str(out_path),
            "backup": str(backup_path) if backup_path else None,
            "total_records": len(merged),
            "requested_shards": fields,
            "fields_present": sorted(field_counts),
            "missing_shards": missing_shards,
        },
    )

    print(f"corpus: {out_path}")
    print(f"records: {len(merged)}")
    print(f"backup: {backup_path}" if backup_path else "backup: none")
    print(f"missing shards: {', '.join(missing_shards) if missing_shards else 'none'}")
    for field, count in sorted(field_counts.items()):
        print(f"{field}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
