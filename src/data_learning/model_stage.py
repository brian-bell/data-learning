from __future__ import annotations

import argparse
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from data_learning.common import (
    DEFAULT_MODELED_DIR,
    DEFAULT_VALIDATED_PATH,
    date_to_key,
    ensure_directory,
    json_loads_if_needed,
    path_arg,
)

FACT_COLUMNS = [
    "submission_key",
    "paper_id",
    "version_number",
    "paper_key",
    "date_key",
    "is_first_submission",
    "is_latest_version",
]

PAPER_COLUMNS = [
    "paper_key",
    "paper_id",
    "title",
    "abstract",
    "doi",
    "journal_ref",
    "comments",
    "license",
    "valid_from",
    "valid_to",
    "is_current",
]

DATE_COLUMNS = [
    "date_key",
    "full_date",
    "year",
    "quarter",
    "month",
    "month_name",
    "day_of_week",
    "day_name",
    "is_weekend",
]

def build_date_dimension(start_date: date | None, end_date: date | None) -> pd.DataFrame:
    if start_date is None or end_date is None:
        return pd.DataFrame(columns=DATE_COLUMNS)

    date_rows = []
    current_date = start_date
    while current_date <= end_date:
        date_rows.append(
            {
                "date_key": date_to_key(current_date),
                "full_date": current_date.isoformat(),
                "year": current_date.year,
                "quarter": ((current_date.month - 1) // 3) + 1,
                "month": current_date.month,
                "month_name": current_date.strftime("%B"),
                "day_of_week": current_date.weekday(),
                "day_name": current_date.strftime("%A"),
                "is_weekend": current_date.weekday() >= 5,
            }
        )
        current_date += timedelta(days=1)

    return pd.DataFrame(date_rows, columns=DATE_COLUMNS)


def build_paper_dimension(records: list[dict[str, Any]]) -> tuple[pd.DataFrame, dict[str, int]]:
    paper_rows: list[dict[str, Any]] = []
    paper_keys: dict[str, int] = {}

    for paper_key, row in enumerate(sorted(records, key=lambda item: item["id"]), start=1):
        paper_id = row["id"]
        if paper_id in paper_keys:
            raise ValueError(f"duplicate paper id: {paper_id}")

        versions = json_loads_if_needed(row["versions"])
        if not versions:
            raise ValueError(f"paper {paper_id} has no versions")

        first_submission_date = date.fromisoformat(versions[0]["created_date"])
        paper_keys[paper_id] = paper_key
        paper_rows.append(
            {
                "paper_key": paper_key,
                "paper_id": paper_id,
                "title": row.get("title"),
                "abstract": row.get("abstract"),
                "doi": row.get("doi"),
                "journal_ref": row.get("journal_ref"),
                "comments": row.get("comments"),
                "license": row.get("license"),
                "valid_from": first_submission_date.isoformat(),
                "valid_to": None,
                "is_current": True,
            }
        )

    return pd.DataFrame(paper_rows, columns=PAPER_COLUMNS), paper_keys


def build_fact_and_dates(validated_frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    records = validated_frame.to_dict(orient="records")
    paper_frame, paper_keys = build_paper_dimension(records)
    fact_rows: list[dict[str, Any]] = []
    min_submission_date: date | None = None
    max_submission_date: date | None = None
    submission_key = 1

    # The fact table grain is one submission event per paper-version. Keeping the fact at that
    # event grain makes version history explicit without forcing query-time array parsing.
    for row in records:
        versions = json_loads_if_needed(row["versions"])
        if not versions:
            raise ValueError(f"paper {row['id']} has no versions")
        latest_version_number = max(version["version_number"] for version in versions)

        for version in versions:
            created_date = date.fromisoformat(version["created_date"])
            date_key = date_to_key(created_date)
            min_submission_date = created_date if min_submission_date is None else min(min_submission_date, created_date)
            max_submission_date = created_date if max_submission_date is None else max(max_submission_date, created_date)
            fact_rows.append(
                {
                    "submission_key": submission_key,
                    "paper_id": row["id"],
                    "version_number": version["version_number"],
                    # The natural arXiv id stays on the fact for readability, but the surrogate
                    # key gives us a stable join target for dimensional modeling and later SCD work.
                    "paper_key": paper_keys[row["id"]],
                    "date_key": date_key,
                    "is_first_submission": version["version_number"] == 1,
                    "is_latest_version": version["version_number"] == latest_version_number,
                }
            )
            submission_key += 1

    fact_frame = pd.DataFrame(fact_rows, columns=FACT_COLUMNS)
    # This stays a star schema instead of snowflaking further because the learning goal here is
    # straightforward analytical joins over a small set of conformed dimensions, not extra
    # normalization depth that would add joins without clarifying the query model.
    date_frame = build_date_dimension(min_submission_date, max_submission_date)
    return fact_frame, date_frame, paper_frame


def write_modeled_outputs(
    fact_frame: pd.DataFrame,
    date_frame: pd.DataFrame,
    paper_frame: pd.DataFrame,
    output_dir: Path,
) -> dict[str, Path]:
    ensure_directory(output_dir)
    fact_path = output_dir / "fact_submissions.parquet"
    date_path = output_dir / "dim_dates.parquet"
    paper_path = output_dir / "dim_papers.parquet"
    fact_frame.to_parquet(fact_path, index=False)
    date_frame.to_parquet(date_path, index=False)
    paper_frame.to_parquet(paper_path, index=False)
    return {
        "fact_submissions": fact_path,
        "dim_dates": date_path,
        "dim_papers": paper_path,
    }


def run_model(input_path: Path, output_dir: Path) -> dict[str, Any]:
    validated_frame = pd.read_parquet(input_path)
    fact_frame, date_frame, paper_frame = build_fact_and_dates(validated_frame)
    outputs = write_modeled_outputs(
        fact_frame=fact_frame,
        date_frame=date_frame,
        paper_frame=paper_frame,
        output_dir=output_dir,
    )
    return {
        "fact_rows": len(fact_frame),
        "date_rows": len(date_frame),
        "paper_rows": len(paper_frame),
        "outputs": outputs,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build core star schema tables from validated data.")
    parser.add_argument("--input", type=path_arg, default=DEFAULT_VALIDATED_PATH, help="Path to the validated Parquet input.")
    parser.add_argument("--output-dir", type=path_arg, default=DEFAULT_MODELED_DIR, help="Directory for modeled Parquet outputs.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_model(input_path=args.input, output_dir=args.output_dir)
    print(
        f"Created {result['fact_rows']} fact rows, {result['date_rows']} date rows, "
        f"and {result['paper_rows']} paper rows "
        f"under {args.output_dir}"
    )
    return 0
