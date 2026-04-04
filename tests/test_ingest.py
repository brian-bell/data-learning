from __future__ import annotations

import logging

import pandas as pd
import pytest

from data_learning.ingest_stage import OUTPUT_COLUMNS, run_ingest

from tests.helpers import make_arxiv_record, write_jsonl


def test_run_ingest_writes_validated_parquet_and_logs_drop_reasons(tmp_path, caplog):
    input_path = tmp_path / "raw.jsonl"
    output_path = tmp_path / "validated.parquet"

    valid_a = make_arxiv_record(1, version_count=1, year=2020)
    valid_b = make_arxiv_record(2, version_count=2, year=2021)
    missing_categories = make_arxiv_record(3)
    missing_categories["categories"] = ""

    caplog.set_level(logging.INFO)
    write_jsonl(
        input_path,
        [valid_a, valid_b, missing_categories],
        extra_lines=["not-json"],
    )

    stats = run_ingest(input_path=input_path, output_path=output_path)

    frame = pd.read_parquet(output_path)
    assert stats["total_read"] == 4
    assert stats["valid_records"] == 2
    assert stats["dropped_records"] == 2
    assert stats["drop_reasons"] == {
        "invalid_json": 1,
        "missing_categories": 1,
    }
    assert stats["elapsed_seconds"] >= 0
    assert frame.columns.tolist() == OUTPUT_COLUMNS
    assert frame["id"].tolist() == [valid_a["id"], valid_b["id"]]
    assert [list(author) for author in frame.iloc[0]["authors_parsed"]] == valid_a["authors_parsed"]
    assert list(frame.iloc[1]["versions"]) == valid_b["versions"]
    assert "Drop reasons:" in caplog.text
    assert "Sample dropped records:" in caplog.text


@pytest.mark.parametrize(
    ("mutator", "expected_reason"),
    [
        (lambda record: record.pop("id"), "missing_id"),
        (lambda record: record.pop("title"), "missing_title"),
        (lambda record: record.pop("authors_parsed"), "missing_authors_parsed"),
        (lambda record: record.pop("categories"), "missing_categories"),
        (lambda record: record.pop("versions"), "missing_versions"),
        (lambda record: record.__setitem__("authors_parsed", []), "missing_authors_parsed"),
        (lambda record: record.__setitem__("authors_parsed", "Bell, Brian"), "invalid_authors_parsed"),
        (lambda record: record.__setitem__("categories", "   "), "invalid_categories"),
        (lambda record: record.__setitem__("versions", []), "missing_versions"),
        (lambda record: record.__setitem__("versions", "v1"), "invalid_versions"),
        (lambda record: record.__setitem__("versions", [{"version": "v1", "created": "not-a-date"}]), "invalid_version_created"),
    ],
)
def test_run_ingest_rejects_invalid_records_with_specific_reason(tmp_path, mutator, expected_reason):
    input_path = tmp_path / "raw.jsonl"
    output_path = tmp_path / "validated.parquet"

    record = make_arxiv_record(1)
    mutator(record)
    write_jsonl(input_path, [record])

    stats = run_ingest(input_path=input_path, output_path=output_path)

    frame = pd.read_parquet(output_path)
    assert frame.empty
    assert stats["valid_records"] == 0
    assert stats["dropped_records"] == 1
    assert stats["drop_reasons"] == {expected_reason: 1}


def test_run_ingest_stops_after_limit_valid_records(tmp_path):
    input_path = tmp_path / "raw.jsonl"
    output_path = tmp_path / "validated.parquet"

    records = [make_arxiv_record(index, version_count=1, year=2020) for index in range(1, 6)]
    write_jsonl(input_path, records)

    stats = run_ingest(input_path=input_path, output_path=output_path, limit=3)

    frame = pd.read_parquet(output_path)
    assert stats["valid_records"] == 3
    assert stats["total_read"] == 3
    assert len(frame) == 3


def test_run_ingest_writes_multiple_batches(tmp_path):
    input_path = tmp_path / "raw.jsonl"
    output_path = tmp_path / "validated.parquet"

    records = [make_arxiv_record(index, version_count=1, year=2020) for index in range(1, 6)]
    write_jsonl(input_path, records)

    stats = run_ingest(input_path=input_path, output_path=output_path, batch_size=2)

    frame = pd.read_parquet(output_path)
    assert stats["valid_records"] == 5
    assert frame["id"].tolist() == [record["id"] for record in records]
