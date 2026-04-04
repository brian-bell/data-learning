from __future__ import annotations

import pandas as pd

from data_learning.store_stage import run_store


def test_run_store_writes_csv_and_parquet_outputs(tmp_path):
    input_path = tmp_path / "fact_submissions.parquet"
    output_dir = tmp_path / "output"

    fact_frame = pd.DataFrame(
        [
            {
                "submission_key": 1,
                "paper_id": "0000001",
                "version_number": 1,
                "paper_key": 1,
                "date_key": 20200101,
                "is_first_submission": True,
                "is_latest_version": True,
            }
        ]
    )
    fact_frame.to_parquet(input_path, index=False)

    result = run_store(input_path=input_path, output_dir=output_dir)

    csv_path = output_dir / "csv" / "fact_submissions.csv"
    parquet_path = output_dir / "parquet" / "fact_submissions.parquet"

    assert result["row_count"] == 1
    assert csv_path.exists()
    assert parquet_path.exists()
    assert len(pd.read_csv(csv_path)) == 1
    assert len(pd.read_parquet(parquet_path)) == 1
