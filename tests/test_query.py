from __future__ import annotations

import pandas as pd

from data_learning.query_stage import run_query, yearly_submission_counts


def test_yearly_submission_counts_queries_parquet_files(tmp_path):
    fact_path = tmp_path / "fact_submissions.parquet"
    date_path = tmp_path / "dim_dates.parquet"

    pd.DataFrame(
        [
            {"submission_key": 1, "paper_id": "a", "version_number": 1, "date_key": 20200101, "is_first_submission": True, "is_latest_version": True},
            {"submission_key": 2, "paper_id": "b", "version_number": 1, "date_key": 20200101, "is_first_submission": True, "is_latest_version": True},
            {"submission_key": 3, "paper_id": "c", "version_number": 1, "date_key": 20210101, "is_first_submission": True, "is_latest_version": True},
        ]
    ).to_parquet(fact_path, index=False)

    pd.DataFrame(
        [
            {"date_key": 20200101, "full_date": "2020-01-01", "year": 2020, "quarter": 1, "month": 1, "month_name": "January", "day_of_week": 2, "day_name": "Wednesday", "is_weekend": False},
            {"date_key": 20210101, "full_date": "2021-01-01", "year": 2021, "quarter": 1, "month": 1, "month_name": "January", "day_of_week": 4, "day_name": "Friday", "is_weekend": False},
        ]
    ).to_parquet(date_path, index=False)

    rows = yearly_submission_counts(fact_path=fact_path, date_dim_path=date_path)
    rendered = run_query(fact_path=fact_path, date_dim_path=date_path)

    assert rows == [(2020, 2), (2021, 1)]
    assert rendered.splitlines() == ["year\tsubmission_count", "2020\t2", "2021\t1"]
