from __future__ import annotations

import subprocess
import sys

import pandas as pd

from tests.helpers import ROOT, make_arxiv_record, write_jsonl


def test_pipeline_runs_end_to_end_via_cli(tmp_path):
    raw_input = tmp_path / "raw.jsonl"
    validated_path = tmp_path / "raw" / "arxiv_validated.parquet"
    modeled_dir = tmp_path / "modeled"
    output_dir = tmp_path / "output"

    records = [make_arxiv_record(index, version_count=1, year=2020 + (index % 2)) for index in range(1, 106)]
    write_jsonl(raw_input, records)

    commands = [
        [
            sys.executable,
            str(ROOT / "src" / "ingest.py"),
            "--input",
            str(raw_input),
            "--output",
            str(validated_path),
            "--limit",
            "100",
        ],
        [
            sys.executable,
            str(ROOT / "src" / "model.py"),
            "--input",
            str(validated_path),
            "--output-dir",
            str(modeled_dir),
        ],
        [
            sys.executable,
            str(ROOT / "src" / "store.py"),
            "--input",
            str(modeled_dir / "fact_submissions.parquet"),
            "--output-dir",
            str(output_dir),
        ],
        [
            sys.executable,
            str(ROOT / "src" / "query.py"),
            "--fact-path",
            str(output_dir / "parquet" / "fact_submissions.parquet"),
            "--date-dim-path",
            str(modeled_dir / "dim_dates.parquet"),
        ],
    ]

    completed = []
    for command in commands:
        completed.append(
            subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
            )
        )

    validated_frame = pd.read_parquet(validated_path)
    assert len(validated_frame) == 100
    assert (modeled_dir / "dim_papers.parquet").exists()
    assert len(validated_frame) == 100
    assert (output_dir / "csv" / "fact_submissions.csv").exists()
    assert (output_dir / "parquet" / "fact_submissions.parquet").exists()
    assert "year\tsubmission_count" in completed[-1].stdout
