from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from data_learning.common import (
    DEFAULT_RAW_INPUT_PATH,
    DEFAULT_VALIDATED_PATH,
    dump_json,
    ensure_parent_directory,
    parse_created_date,
    parse_version_number,
    path_arg,
)

OUTPUT_COLUMNS = [
    "id",
    "submitter",
    "title",
    "authors_parsed",
    "categories",
    "versions",
    "abstract",
    "doi",
    "journal_ref",
    "comments",
    "license",
    "update_date",
]

REQUIRED_FIELDS = ("id", "title", "authors_parsed", "categories", "versions")


def normalize_record(record: dict[str, Any]) -> dict[str, Any] | None:
    for field in REQUIRED_FIELDS:
        if field not in record or record[field] in (None, "", []):
            return None

    categories = record.get("categories")
    if not isinstance(categories, str) or not categories.strip():
        return None

    authors_parsed = record.get("authors_parsed")
    if not isinstance(authors_parsed, list) or not authors_parsed:
        return None

    versions = record.get("versions")
    if not isinstance(versions, list) or not versions:
        return None

    normalized_versions: list[dict[str, Any]] = []
    for version in versions:
        if not isinstance(version, dict):
            return None

        version_number = parse_version_number(version.get("version"))
        created_date = parse_created_date(version.get("created"))
        if version_number is None or created_date is None:
            return None

        normalized_versions.append(
            {
                "version": version.get("version"),
                "version_number": version_number,
                "created_date": created_date.isoformat(),
            }
        )

    normalized_versions.sort(key=lambda item: item["version_number"])

    return {
        "id": record.get("id"),
        "submitter": record.get("submitter"),
        "title": record.get("title"),
        "authors_parsed": dump_json(authors_parsed),
        "categories": categories.strip(),
        "versions": dump_json(normalized_versions),
        "abstract": record.get("abstract"),
        "doi": record.get("doi"),
        "journal_ref": record.get("journal-ref"),
        "comments": record.get("comments"),
        "license": record.get("license"),
        "update_date": record.get("update_date"),
    }


def collect_validated_rows(input_path: Path, limit: int) -> tuple[list[dict[str, Any]], dict[str, int]]:
    rows: list[dict[str, Any]] = []
    total_read = 0
    dropped_records = 0

    with input_path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue

            total_read += 1
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                dropped_records += 1
                continue

            normalized = normalize_record(parsed)
            if normalized is None:
                dropped_records += 1
                continue

            rows.append(normalized)
            if len(rows) >= limit:
                break

    stats = {
        "total_read": total_read,
        "valid_records": len(rows),
        "dropped_records": dropped_records,
    }
    return rows, stats


def write_validated_parquet(rows: list[dict[str, Any]], output_path: Path) -> None:
    ensure_parent_directory(output_path)
    dataframe = pd.DataFrame(rows, columns=OUTPUT_COLUMNS)
    dataframe.to_parquet(output_path, index=False)


def run_ingest(input_path: Path, output_path: Path, limit: int = 100) -> dict[str, int]:
    rows, stats = collect_validated_rows(input_path=input_path, limit=limit)
    write_validated_parquet(rows=rows, output_path=output_path)
    return stats


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate arXiv JSONL input and write Parquet output.")
    parser.add_argument("--input", type=path_arg, default=DEFAULT_RAW_INPUT_PATH, help="Path to the raw JSONL file.")
    parser.add_argument("--output", type=path_arg, default=DEFAULT_VALIDATED_PATH, help="Path to the validated Parquet output.")
    parser.add_argument("--limit", type=int, default=100, help="Number of valid records to process.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    stats = run_ingest(input_path=args.input, output_path=args.output, limit=args.limit)
    print(
        f"Validated {stats['valid_records']} records "
        f"(read={stats['total_read']}, dropped={stats['dropped_records']}) "
        f"-> {args.output}"
    )
    return 0
