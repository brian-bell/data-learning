from __future__ import annotations

import pandas as pd

from data_learning.ingest_stage import OUTPUT_COLUMNS, run_ingest

from tests.helpers import make_arxiv_record, write_jsonl


def test_run_ingest_writes_validated_parquet_and_skips_bad_rows(tmp_path):
    input_path = tmp_path / "raw.jsonl"
    output_path = tmp_path / "validated.parquet"

    valid_a = make_arxiv_record(1, version_count=1, year=2020)
    valid_b = make_arxiv_record(2, version_count=2, year=2021)
    missing_categories = make_arxiv_record(3)
    missing_categories["categories"] = ""

    write_jsonl(
        input_path,
        [valid_a, valid_b, missing_categories],
        extra_lines=["not-json"],
    )

    stats = run_ingest(input_path=input_path, output_path=output_path, limit=10)

    frame = pd.read_parquet(output_path)
    assert stats == {"total_read": 4, "valid_records": 2, "dropped_records": 2}
    assert frame.columns.tolist() == OUTPUT_COLUMNS
    assert frame["id"].tolist() == [valid_a["id"], valid_b["id"]]


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
