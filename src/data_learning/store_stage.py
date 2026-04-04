from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import pandas as pd

from data_learning.common import DEFAULT_MODELED_DIR, DEFAULT_OUTPUT_DIR, ensure_directory, path_arg

DEFAULT_FACT_INPUT_PATH = DEFAULT_MODELED_DIR / "fact_submissions.parquet"


def write_fact_outputs(fact_frame: pd.DataFrame, output_dir: Path) -> dict[str, Path]:
    csv_dir = output_dir / "csv"
    parquet_dir = output_dir / "parquet"
    ensure_directory(csv_dir)
    ensure_directory(parquet_dir)

    csv_path = csv_dir / "fact_submissions.csv"
    parquet_path = parquet_dir / "fact_submissions.parquet"

    fact_frame.to_csv(csv_path, index=False)
    fact_frame.to_parquet(parquet_path, index=False)
    return {
        "csv": csv_path,
        "parquet": parquet_path,
    }


def run_store(input_path: Path, output_dir: Path) -> dict[str, Any]:
    fact_frame = pd.read_parquet(input_path)
    outputs = write_fact_outputs(fact_frame=fact_frame, output_dir=output_dir)
    return {
        "row_count": len(fact_frame),
        "outputs": outputs,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Write minimal fact output in CSV and Parquet formats.")
    parser.add_argument("--input", type=path_arg, default=DEFAULT_FACT_INPUT_PATH, help="Path to the fact_submissions Parquet input.")
    parser.add_argument("--output-dir", type=path_arg, default=DEFAULT_OUTPUT_DIR, help="Directory for output files.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_store(input_path=args.input, output_dir=args.output_dir)
    print(f"Wrote {result['row_count']} fact rows to {args.output_dir}")
    return 0
