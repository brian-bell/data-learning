from __future__ import annotations

from datetime import date

import pytest
import pandas as pd

from data_learning.ingest_stage import normalize_record
from data_learning.model_stage import DATE_COLUMNS, FACT_COLUMNS, PAPER_COLUMNS, build_star_schema, normalize_versions, run_model

from tests.helpers import make_arxiv_record


def test_run_model_builds_core_star_schema_outputs(tmp_path):
    input_path = tmp_path / "validated.parquet"
    output_dir = tmp_path / "modeled"

    records = [
        normalize_record(make_arxiv_record(1, version_count=2, year=2020))[0],
        normalize_record(make_arxiv_record(2, version_count=1, year=2021))[0],
    ]

    pd.DataFrame(records).to_parquet(input_path, index=False)

    result = run_model(input_path=input_path, output_dir=output_dir)

    fact_frame = pd.read_parquet(output_dir / "fact_submissions.parquet")
    date_frame = pd.read_parquet(output_dir / "dim_dates.parquet")
    paper_frame = pd.read_parquet(output_dir / "dim_papers.parquet")

    assert result["fact_rows"] == 3
    assert result["paper_rows"] == 2
    assert fact_frame.columns.tolist() == FACT_COLUMNS
    assert date_frame.columns.tolist() == DATE_COLUMNS
    assert paper_frame.columns.tolist() == PAPER_COLUMNS
    assert fact_frame["is_first_submission"].tolist() == [True, False, True]
    assert fact_frame["is_latest_version"].tolist() == [False, True, True]
    assert fact_frame["paper_key"].tolist() == [1, 1, 2]
    assert date_frame.iloc[0]["date_key"] == 20200101
    assert date_frame.iloc[-1]["date_key"] == 20210202
    assert len(date_frame) == (date(2021, 2, 2) - date(2020, 1, 1)).days + 1
    assert paper_frame[["paper_key", "paper_id"]].to_dict(orient="records") == [
        {"paper_key": 1, "paper_id": "0000001"},
        {"paper_key": 2, "paper_id": "0000002"},
    ]
    assert paper_frame["is_current"].tolist() == [True, True]
    assert paper_frame["valid_from"].tolist() == ["2020-01-01", "2021-01-01"]
    assert paper_frame["valid_to"].isna().all()
    assert set(fact_frame["date_key"]).issubset(set(date_frame["date_key"]))
    assert set(fact_frame["paper_key"]).issubset(set(paper_frame["paper_key"]))


def test_build_star_schema_raises_on_empty_versions():
    frame = pd.DataFrame([{"id": "0000001", "versions": "[]"}])
    with pytest.raises(ValueError, match="no versions"):
        build_star_schema(frame)


def test_build_star_schema_raises_on_duplicate_paper_ids():
    record, _ = normalize_record(make_arxiv_record(1, version_count=1, year=2020))
    assert record is not None
    frame = pd.DataFrame([record, record])

    with pytest.raises(ValueError, match="duplicate paper id"):
        build_star_schema(frame)


def test_build_star_schema_preserves_version_numbering_and_date_completeness():
    records = [
        normalize_record(make_arxiv_record(7, version_count=3, year=2020))[0],
    ]
    frame = pd.DataFrame(records)

    fact_frame, date_frame, paper_frame = build_star_schema(frame)

    assert fact_frame["version_number"].tolist() == [1, 2, 3]
    assert fact_frame["paper_key"].tolist() == [1, 1, 1]
    assert len(fact_frame) >= len(paper_frame)
    assert date_frame.iloc[0]["date_key"] == 20200101
    assert date_frame.iloc[-1]["date_key"] == 20220303
    assert len(date_frame) == 793


def test_normalize_versions_accepts_raw_ingest_payload():
    raw_versions = [
        {"version": "v2", "created": "Tue, 02 Feb 2021 00:00:00 GMT"},
        {"version": "v1", "created": "Wed, 01 Jan 2020 00:00:00 GMT"},
    ]

    normalized = normalize_versions(raw_versions)

    assert normalized == [
        {"version_number": 1, "created_date": "2020-01-01"},
        {"version_number": 2, "created_date": "2021-02-02"},
    ]
