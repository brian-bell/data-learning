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
    parse_created_date,
    parse_version_number,
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

PAPER_COLUMNS = [
    "paper_key",
    "paper_id",
    "title",
    "abstract",
    "doi",
    "journal_ref",
    "comments",
    "license",
    "is_current",
    "valid_from",
    "valid_to",
]


def normalize_versions(value: Any) -> list[dict[str, Any]]:
    raw_versions = json_loads_if_needed(value)
    if raw_versions is None:
        return []

    versions = list(raw_versions)
    normalized_versions: list[dict[str, Any]] = []
    for version in versions:
        if not isinstance(version, dict):
            raise ValueError(f"invalid version payload: {version!r}")

        if "version_number" in version and "created_date" in version:
            version_number = version["version_number"]
            created_date = version["created_date"]
        else:
            version_number = parse_version_number(version.get("version"))
            created = parse_created_date(version.get("created"))
            if version_number is None or created is None:
                raise ValueError(f"invalid version payload: {version!r}")
            created_date = created.isoformat()

        normalized_versions.append(
            {
                "version_number": version_number,
                "created_date": created_date,
            }
        )

    normalized_versions.sort(key=lambda item: item["version_number"])
    return normalized_versions


def _build_date_dimension(start_date: date, end_date: date) -> pd.DataFrame:
    date_rows: list[dict[str, Any]] = []
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


def _extract_paper_rows(validated_frame: pd.DataFrame) -> tuple[list[dict[str, Any]], list[date]]:
    paper_rows: list[dict[str, Any]] = []
    first_submission_dates: list[date] = []
    seen_paper_ids: set[str] = set()

    for row in validated_frame.to_dict(orient="records"):
        paper_id = row["id"]
        if paper_id in seen_paper_ids:
            raise ValueError(f"duplicate paper id in validated input: {paper_id}")
        seen_paper_ids.add(paper_id)

        versions = normalize_versions(row["versions"])
        if not versions:
            raise ValueError(f"paper {paper_id} has no versions")

        first_submission_date = date.fromisoformat(versions[0]["created_date"])
        first_submission_dates.append(first_submission_date)
        paper_rows.append(
            {
                "paper_id": paper_id,
                "title": row["title"],
                "abstract": row["abstract"],
                "doi": row["doi"],
                "journal_ref": row["journal_ref"],
                "comments": row["comments"],
                "license": row["license"],
                "is_current": True,
                "valid_from": first_submission_date.isoformat(),
                "valid_to": None,
                "versions": versions,
            }
        )

    return paper_rows, first_submission_dates


def build_star_schema(validated_frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    paper_rows, first_submission_dates = _extract_paper_rows(validated_frame)
    if not paper_rows:
        empty_fact = pd.DataFrame(columns=FACT_COLUMNS)
        empty_dates = pd.DataFrame(columns=DATE_COLUMNS)
        empty_papers = pd.DataFrame(columns=PAPER_COLUMNS)
        return empty_fact, empty_dates, empty_papers

    sorted_papers = sorted(paper_rows, key=lambda row: row["paper_id"])
    paper_key_by_id: dict[str, int] = {}
    dim_paper_rows: list[dict[str, Any]] = []
    all_submission_dates = list(first_submission_dates)

    # This stage models a star schema so the fact table stays narrow and analytic joins stay simple.
    # Snowflaking categories/authors into more dimensions happens later when that scope is requested.
    for paper_key, paper in enumerate(sorted_papers, start=1):
        paper_key_by_id[paper["paper_id"]] = paper_key
        dim_paper_rows.append(
            {
                # The surrogate key gives the warehouse a stable join target even if source metadata
                # changes later; the natural arXiv id is still retained for traceability.
                "paper_key": paper_key,
                "paper_id": paper["paper_id"],
                "title": paper["title"],
                "abstract": paper["abstract"],
                "doi": paper["doi"],
                "journal_ref": paper["journal_ref"],
                "comments": paper["comments"],
                "license": paper["license"],
                "is_current": paper["is_current"],
                "valid_from": paper["valid_from"],
                "valid_to": paper["valid_to"],
            }
        )

    fact_rows: list[dict[str, Any]] = []
    submission_key = 1
    for paper in paper_rows:
        latest_version_number = max(version["version_number"] for version in paper["versions"])
        for version in paper["versions"]:
            created_date = date.fromisoformat(version["created_date"])
            all_submission_dates.append(created_date)
            fact_rows.append(
                {
                    # The fact grain is one row per paper-version submission event.
                    "submission_key": submission_key,
                    "paper_id": paper["paper_id"],
                    "version_number": version["version_number"],
                    "paper_key": paper_key_by_id[paper["paper_id"]],
                    "date_key": date_to_key(created_date),
                    "is_first_submission": version["version_number"] == 1,
                    "is_latest_version": version["version_number"] == latest_version_number,
                }
            )
            submission_key += 1

    fact_frame = pd.DataFrame(fact_rows, columns=FACT_COLUMNS)
    date_frame = _build_date_dimension(min(all_submission_dates), max(all_submission_dates))
    paper_frame = pd.DataFrame(dim_paper_rows, columns=PAPER_COLUMNS)
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
    fact_frame, date_frame, paper_frame = build_star_schema(validated_frame)
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
    parser = argparse.ArgumentParser(description="Build the core star schema tables from validated data.")
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
