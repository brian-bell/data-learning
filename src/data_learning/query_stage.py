from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

import duckdb

from data_learning.common import DEFAULT_MODELED_DIR, DEFAULT_OUTPUT_DIR, path_arg

DEFAULT_FACT_PATH = DEFAULT_OUTPUT_DIR / "parquet" / "fact_submissions.parquet"
DEFAULT_DATE_DIM_PATH = DEFAULT_MODELED_DIR / "dim_dates.parquet"


def sql_path_literal(path: Path) -> str:
    return str(path).replace("'", "''")


def yearly_submission_counts(fact_path: Path, date_dim_path: Path) -> list[tuple[int, int]]:
    connection = duckdb.connect()
    try:
        query = f"""
            SELECT d.year, COUNT(*) AS submission_count
            FROM read_parquet('{sql_path_literal(fact_path)}') AS f
            JOIN read_parquet('{sql_path_literal(date_dim_path)}') AS d
              ON f.date_key = d.date_key
            GROUP BY d.year
            ORDER BY d.year
        """
        rows = connection.execute(query).fetchall()
    finally:
        connection.close()
    return [(int(year), int(count)) for year, count in rows]


def format_results(rows: Iterable[tuple[int, int]]) -> str:
    lines = ["year\tsubmission_count"]
    lines.extend(f"{year}\t{count}" for year, count in rows)
    return "\n".join(lines)


def run_query(fact_path: Path, date_dim_path: Path) -> str:
    rows = yearly_submission_counts(fact_path=fact_path, date_dim_path=date_dim_path)
    return format_results(rows)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Query fact_submissions Parquet output with DuckDB.")
    parser.add_argument("--fact-path", type=path_arg, default=DEFAULT_FACT_PATH, help="Path to fact_submissions Parquet output.")
    parser.add_argument("--date-dim-path", type=path_arg, default=DEFAULT_DATE_DIM_PATH, help="Path to dim_dates Parquet table.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    print(run_query(fact_path=args.fact_path, date_dim_path=args.date_dim_path))
    return 0
