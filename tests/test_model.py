from __future__ import annotations

import pytest
import pandas as pd

from data_learning.ingest_stage import normalize_record
from data_learning.model_stage import (
    DATE_COLUMNS,
    DIM_PAPERS_COLUMNS,
    FACT_COLUMNS,
    build_fact_and_dates,
    normalize_versions,
    run_model,
)

from tests.helpers import make_arxiv_record


def _make_validated_parquet(tmp_path, records):
    input_path = tmp_path / "validated.parquet"
    pd.DataFrame(records).to_parquet(input_path, index=False)
    return input_path


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
    papers_frame = pd.read_parquet(output_dir / "dim_papers.parquet")

    assert result["fact_rows"] == 3
    assert result["paper_rows"] == 2
    assert fact_frame.columns.tolist() == FACT_COLUMNS
    assert date_frame.columns.tolist() == DATE_COLUMNS
    assert papers_frame.columns.tolist() == DIM_PAPERS_COLUMNS
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


def test_dim_papers_has_one_row_per_unique_paper(tmp_path):
    records = [
        normalize_record(make_arxiv_record(1, version_count=3, year=2019))[0],
        normalize_record(make_arxiv_record(2, version_count=1, year=2021))[0],
        normalize_record(make_arxiv_record(3, version_count=2, year=2022))[0],
    ]
    input_path = _make_validated_parquet(tmp_path, records)
    result = run_model(input_path=input_path, output_dir=tmp_path / "modeled")

    papers_frame = pd.read_parquet(tmp_path / "modeled" / "dim_papers.parquet")

    assert result["paper_rows"] == 3
    # Surrogate keys are sequential integers starting at 1
    assert papers_frame["paper_key"].tolist() == [1, 2, 3]
    # Natural keys match the paper ids from the input
    assert papers_frame["paper_id"].tolist() == ["0000001", "0000002", "0000003"]
    # SCD placeholder columns: is_current=True, valid_to=None for all rows
    assert papers_frame["is_current"].all()
    assert papers_frame["valid_to"].isna().all()
    # valid_from is the ISO date of each paper's first version
    assert papers_frame["valid_from"].tolist() == ["2019-01-01", "2021-01-01", "2022-01-01"]


def test_fact_foreign_key_integrity(tmp_path):
    records = [
        normalize_record(make_arxiv_record(1, version_count=2, year=2020))[0],
        normalize_record(make_arxiv_record(2, version_count=1, year=2021))[0],
    ]
    input_path = _make_validated_parquet(tmp_path, records)
    run_model(input_path=input_path, output_dir=tmp_path / "modeled")

    fact_frame = pd.read_parquet(tmp_path / "modeled" / "fact_submissions.parquet")
    date_frame = pd.read_parquet(tmp_path / "modeled" / "dim_dates.parquet")
    papers_frame = pd.read_parquet(tmp_path / "modeled" / "dim_papers.parquet")

    # Every date_key in the fact table must exist in dim_dates
    assert set(fact_frame["date_key"]).issubset(set(date_frame["date_key"]))
    # Every paper_key in the fact table must exist in dim_papers
    assert set(fact_frame["paper_key"]).issubset(set(papers_frame["paper_key"]))


def test_fact_row_count_geq_paper_count(tmp_path):
    # Each paper contributes at least one fact row (its first version), so
    # fact rows must be >= dim_papers rows.
    records = [
        normalize_record(make_arxiv_record(i, version_count=i, year=2020))[0]
        for i in range(1, 5)
    ]
    input_path = _make_validated_parquet(tmp_path, records)
    result = run_model(input_path=input_path, output_dir=tmp_path / "modeled")

    assert result["fact_rows"] >= result["paper_rows"]


def test_dim_dates_covers_all_submission_dates(tmp_path):
    # dim_dates must contain a row for every date that appears in the fact table.
    records = [
        normalize_record(make_arxiv_record(1, version_count=2, year=2018))[0],
        normalize_record(make_arxiv_record(2, version_count=3, year=2022))[0],
    ]
    input_path = _make_validated_parquet(tmp_path, records)
    run_model(input_path=input_path, output_dir=tmp_path / "modeled")

    fact_frame = pd.read_parquet(tmp_path / "modeled" / "fact_submissions.parquet")
    date_frame = pd.read_parquet(tmp_path / "modeled" / "dim_dates.parquet")

    fact_date_keys = set(fact_frame["date_key"])
    dim_date_keys = set(date_frame["date_key"])
    assert fact_date_keys == dim_date_keys


def test_correct_version_numbering(tmp_path):
    records = [
        normalize_record(make_arxiv_record(1, version_count=3, year=2020))[0],
    ]
    input_path = _make_validated_parquet(tmp_path, records)
    run_model(input_path=input_path, output_dir=tmp_path / "modeled")

    fact_frame = pd.read_parquet(tmp_path / "modeled" / "fact_submissions.parquet")
    paper_rows = fact_frame[fact_frame["paper_id"] == "0000001"].sort_values("version_number")

    assert paper_rows["version_number"].tolist() == [1, 2, 3]
    assert paper_rows["is_first_submission"].tolist() == [True, False, False]
    assert paper_rows["is_latest_version"].tolist() == [False, False, True]
