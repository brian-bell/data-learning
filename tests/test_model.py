from __future__ import annotations

import pytest
import pandas as pd

from data_learning.ingest_stage import normalize_record
from data_learning.model_stage import DATE_COLUMNS, FACT_COLUMNS, build_fact_and_dates, normalize_versions, run_model

from tests.helpers import make_arxiv_record


def test_run_model_builds_fact_submissions_and_dim_dates(tmp_path):
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

    assert result["fact_rows"] == 3
    assert fact_frame.columns.tolist() == FACT_COLUMNS
    assert date_frame.columns.tolist() == DATE_COLUMNS
    assert fact_frame["is_first_submission"].tolist() == [True, False, True]
    assert fact_frame["is_latest_version"].tolist() == [False, True, True]
    assert date_frame["date_key"].tolist() == [20200101, 20210101, 20210202]


def test_build_fact_and_dates_raises_on_empty_versions():
    frame = pd.DataFrame([{"id": "0000001", "versions": "[]"}])
    with pytest.raises(ValueError, match="no versions"):
        build_fact_and_dates(frame)


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
