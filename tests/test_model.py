from __future__ import annotations

import pytest
import pandas as pd

from data_learning.ingest_stage import normalize_record
from data_learning.model_stage import (
    DATE_COLUMNS,
    FACT_COLUMNS,
    PAPER_COLUMNS,
    build_fact_and_dates,
    normalize_versions,
    run_model,
)

from tests.helpers import make_arxiv_record


def test_run_model_builds_core_star_schema_tables(tmp_path):
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
    expected_dates = pd.date_range("2020-01-01", "2021-02-02", freq="D")

    assert result["fact_rows"] == 3
    assert result["paper_rows"] == 2
    assert result["date_rows"] == len(expected_dates)
    assert set(result["outputs"]) == {"fact_submissions", "dim_dates", "dim_papers"}
    assert fact_frame.columns.tolist() == FACT_COLUMNS
    assert date_frame.columns.tolist() == DATE_COLUMNS
    assert paper_frame.columns.tolist() == PAPER_COLUMNS
    assert fact_frame["paper_key"].tolist() == [1, 1, 2]
    assert fact_frame["is_first_submission"].tolist() == [True, False, True]
    assert fact_frame["is_latest_version"].tolist() == [False, True, True]
    assert date_frame["date_key"].tolist()[0] == 20200101
    assert date_frame["date_key"].tolist()[-1] == 20210202
    assert paper_frame.to_dict(orient="records") == [
        {
            "paper_key": 1,
            "paper_id": "0000001",
            "title": "Paper 1",
            "abstract": "Abstract for paper 1",
            "doi": None,
            "journal_ref": None,
            "comments": None,
            "license": "CC0",
            "valid_from": "2020-01-01",
            "valid_to": None,
            "is_current": True,
        },
        {
            "paper_key": 2,
            "paper_id": "0000002",
            "title": "Paper 2",
            "abstract": "Abstract for paper 2",
            "doi": None,
            "journal_ref": None,
            "comments": None,
            "license": "CC0",
            "valid_from": "2021-01-01",
            "valid_to": None,
            "is_current": True,
        },
    ]


def test_build_fact_and_dates_raises_on_empty_versions():
    frame = pd.DataFrame([{"id": "0000001", "versions": "[]"}])
    with pytest.raises(ValueError, match="no versions"):
        build_fact_and_dates(frame)


def test_build_fact_and_dates_uses_valid_dimension_keys():
    frame = pd.DataFrame(
        [
            normalize_record(make_arxiv_record(2, version_count=3, year=2020))[0],
            normalize_record(make_arxiv_record(1, version_count=1, year=2021))[0],
        ]
    )

    fact_frame, date_frame, paper_frame = build_fact_and_dates(frame)

    assert len(fact_frame) == 4
    assert len(paper_frame) == 2
    assert len(fact_frame) >= len(paper_frame)
    assert set(fact_frame["paper_key"]) == set(paper_frame["paper_key"])
    assert set(fact_frame["date_key"]).issubset(set(date_frame["date_key"]))
    assert fact_frame["version_number"].tolist() == [1, 2, 3, 1]
    assert fact_frame["paper_key"].tolist() == [2, 2, 2, 1]
    assert fact_frame["is_first_submission"].tolist() == [True, False, False, True]
    assert fact_frame["is_latest_version"].tolist() == [False, False, True, True]


def test_build_fact_and_dates_rejects_pathological_date_span():
    frame = pd.DataFrame(
        [
            {
                "id": "0000001",
                "title": "Paper 1",
                "abstract": "Abstract for paper 1",
                "doi": None,
                "journal_ref": None,
                "comments": None,
                "license": "CC0",
                "versions": [
                    {"version_number": 1, "created_date": "2020-01-01"},
                ],
            },
            {
                "id": "0000002",
                "title": "Paper 2",
                "abstract": "Abstract for paper 2",
                "doi": None,
                "journal_ref": None,
                "comments": None,
                "license": "CC0",
                "versions": [
                    {"version_number": 1, "created_date": "9999-12-31"},
                ],
            },
        ]
    )

    with pytest.raises(ValueError, match="submission date range is too large"):
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
