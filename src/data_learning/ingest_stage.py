from __future__ import annotations

import argparse
import json
import logging
import time
from collections import Counter
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from data_learning.common import (
    DEFAULT_RAW_INPUT_PATH,
    DEFAULT_VALIDATED_PATH,
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
DEFAULT_BATCH_SIZE = 10_000
DROP_SAMPLE_LIMIT = 5

LOGGER = logging.getLogger(__name__)

VALIDATED_SCHEMA = pa.schema(
    [
        pa.field("id", pa.string()),
        pa.field("submitter", pa.string()),
        pa.field("title", pa.string()),
        pa.field("authors_parsed", pa.list_(pa.list_(pa.string()))),
        pa.field("categories", pa.string()),
        pa.field(
            "versions",
            pa.list_(
                pa.struct(
                    [
                        pa.field("version", pa.string()),
                        pa.field("created", pa.string()),
                    ]
                )
            ),
        ),
        pa.field("abstract", pa.string()),
        pa.field("doi", pa.string()),
        pa.field("journal_ref", pa.string()),
        pa.field("comments", pa.string()),
        pa.field("license", pa.string()),
        pa.field("update_date", pa.string()),
    ]
)


def normalize_record(record: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    if not isinstance(record, dict):
        return None, "invalid_record_type"

    for field in REQUIRED_FIELDS:
        if field not in record or record[field] in (None, "", []):
            return None, f"missing_{field}"

    categories = record.get("categories")
    if not isinstance(categories, str) or not categories.strip():
        return None, "invalid_categories"

    authors_parsed = record.get("authors_parsed")
    if not isinstance(authors_parsed, list) or not authors_parsed:
        return None, "invalid_authors_parsed"

    normalized_authors: list[list[str]] = []
    for author in authors_parsed:
        if not isinstance(author, (list, tuple)) or not author:
            return None, "invalid_authors_parsed"
        normalized_authors.append(
            [None if value is None else str(value) for value in author]
        )

    versions = record.get("versions")
    if not isinstance(versions, list) or not versions:
        return None, "invalid_versions"

    normalized_versions: list[dict[str, str | None]] = []
    for version in versions:
        if not isinstance(version, dict):
            return None, "invalid_versions"

        raw_version = version.get("version")
        raw_created = version.get("created")
        if parse_version_number(raw_version) is None:
            return None, "invalid_versions"
        if parse_created_date(raw_created) is None:
            return None, "invalid_version_created"

        normalized_versions.append(
            {
                "version": str(raw_version),
                "created": str(raw_created),
            }
        )

    normalized_versions.sort(key=lambda item: parse_version_number(item["version"]) or 0)

    return (
        {
            "id": str(record.get("id")),
            "submitter": record.get("submitter"),
            "title": str(record.get("title")),
            "authors_parsed": normalized_authors,
            "categories": categories.strip(),
            "versions": normalized_versions,
            "abstract": record.get("abstract"),
            "doi": record.get("doi"),
            "journal_ref": record.get("journal-ref"),
            "comments": record.get("comments"),
            "license": record.get("license"),
            "update_date": record.get("update_date"),
        },
        None,
    )


def _write_batch(writer: pq.ParquetWriter, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    batch_rows = [{column: row.get(column) for column in OUTPUT_COLUMNS} for row in rows]
    table = pa.Table.from_pylist(batch_rows, schema=VALIDATED_SCHEMA)
    writer.write_table(table)


def _log_summary(
    *,
    input_path: Path,
    output_path: Path,
    total_read: int,
    valid_records: int,
    dropped_records: int,
    drop_reasons: Counter[str],
    drop_samples: list[dict[str, Any]],
    elapsed_seconds: float,
) -> None:
    LOGGER.info(
        "Ingested %s -> %s in %.2fs (read=%d, valid=%d, dropped=%d)",
        input_path,
        output_path,
        elapsed_seconds,
        total_read,
        valid_records,
        dropped_records,
    )
    LOGGER.info("Drop reasons: %s", dict(sorted(drop_reasons.items())))
    if drop_samples:
        LOGGER.info("Sample dropped records: %s", drop_samples)


def run_ingest(
    input_path: Path,
    output_path: Path,
    limit: int | None = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> dict[str, Any]:
    ensure_parent_directory(output_path)
    started_at = time.perf_counter()
    drop_reasons: Counter[str] = Counter()
    drop_samples: list[dict[str, Any]] = []
    buffered_rows: list[dict[str, Any]] = []
    total_read = 0
    valid_records = 0

    # This stage reads a bounded snapshot, so a batch scan is the right fit here.
    # A streaming variant would handle unbounded new submissions through a long-lived consumer.
    # In Lambda terms this is only the batch layer; a Kappa design would replay both history and
    # new submissions through one streaming path instead of splitting batch and speed paths.
    with input_path.open("r", encoding="utf-8") as handle, pq.ParquetWriter(
        output_path,
        VALIDATED_SCHEMA,
    ) as writer:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue

            total_read += 1
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                reason = "invalid_json"
                drop_reasons[reason] += 1
                if len(drop_samples) < DROP_SAMPLE_LIMIT:
                    drop_samples.append({"line": line_number, "reason": reason})
                continue

            normalized, reason = normalize_record(parsed)
            if normalized is None:
                drop_reasons[reason or "invalid_record"] += 1
                if len(drop_samples) < DROP_SAMPLE_LIMIT:
                    sample = {"line": line_number, "reason": reason or "invalid_record"}
                    if isinstance(parsed, dict):
                        sample["id"] = parsed.get("id")
                    drop_samples.append(sample)
                continue

            buffered_rows.append(normalized)
            valid_records += 1

            # Batched writes keep memory bounded while still giving this batch job predictable,
            # rerunnable output semantics. That simplicity is the batch version of exactly-once.
            if len(buffered_rows) >= batch_size:
                _write_batch(writer, buffered_rows)
                buffered_rows.clear()

            if limit is not None and valid_records >= limit:
                break

        _write_batch(writer, buffered_rows)

    elapsed_seconds = time.perf_counter() - started_at
    dropped_records = total_read - valid_records
    _log_summary(
        input_path=input_path,
        output_path=output_path,
        total_read=total_read,
        valid_records=valid_records,
        dropped_records=dropped_records,
        drop_reasons=drop_reasons,
        drop_samples=drop_samples,
        elapsed_seconds=elapsed_seconds,
    )
    return {
        "total_read": total_read,
        "valid_records": valid_records,
        "dropped_records": dropped_records,
        "drop_reasons": dict(sorted(drop_reasons.items())),
        "elapsed_seconds": elapsed_seconds,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate arXiv JSONL input and write Parquet output.")
    parser.add_argument("--input", type=path_arg, default=DEFAULT_RAW_INPUT_PATH, help="Path to the raw JSONL file.")
    parser.add_argument("--output", type=path_arg, default=DEFAULT_VALIDATED_PATH, help="Path to the validated Parquet output.")
    parser.add_argument("--limit", type=int, default=None, help="Optional cap on valid records to process.")
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = build_parser().parse_args(argv)
    stats = run_ingest(input_path=args.input, output_path=args.output, limit=args.limit)
    print(
        f"Validated {stats['valid_records']} records "
        f"(read={stats['total_read']}, dropped={stats['dropped_records']}, elapsed={stats['elapsed_seconds']:.2f}s) "
        f"-> {args.output}"
    )
    return 0
