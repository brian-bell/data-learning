from __future__ import annotations

import argparse
from datetime import date
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


def build_fact_and_dates(validated_frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    fact_rows: list[dict[str, Any]] = []
    unique_dates: dict[int, date] = {}
    submission_key = 1

    for row in validated_frame.to_dict(orient="records"):
        versions = normalize_versions(row["versions"])
        if not versions:
            raise ValueError(f"paper {row['id']} has no versions")
        latest_version_number = max(version["version_number"] for version in versions)

        for version in versions:
            created_date = date.fromisoformat(version["created_date"])
            date_key = date_to_key(created_date)
            unique_dates[date_key] = created_date
            fact_rows.append(
                {
                    "submission_key": submission_key,
                    "paper_id": row["id"],
                    "version_number": version["version_number"],
                    "date_key": date_key,
                    "is_first_submission": version["version_number"] == 1,
                    "is_latest_version": version["version_number"] == latest_version_number,
                }
            )
            submission_key += 1

    fact_frame = pd.DataFrame(fact_rows, columns=FACT_COLUMNS)

    date_rows = []
    for date_key, full_date in sorted(unique_dates.items()):
        date_rows.append(
            {
                "date_key": date_key,
                "full_date": full_date.isoformat(),
                "year": full_date.year,
                "quarter": ((full_date.month - 1) // 3) + 1,
                "month": full_date.month,
                "month_name": full_date.strftime("%B"),
                "day_of_week": full_date.weekday(),
                "day_name": full_date.strftime("%A"),
                "is_weekend": full_date.weekday() >= 5,
            }
        )

    date_frame = pd.DataFrame(date_rows, columns=DATE_COLUMNS)
    return fact_frame, date_frame


def write_modeled_outputs(fact_frame: pd.DataFrame, date_frame: pd.DataFrame, output_dir: Path) -> dict[str, Path]:
    ensure_directory(output_dir)
    fact_path = output_dir / "fact_submissions.parquet"
    date_path = output_dir / "dim_dates.parquet"
    fact_frame.to_parquet(fact_path, index=False)
    date_frame.to_parquet(date_path, index=False)
    return {
        "fact_submissions": fact_path,
        "dim_dates": date_path,
    }


def run_model(input_path: Path, output_dir: Path) -> dict[str, Any]:
    validated_frame = pd.read_parquet(input_path)
    fact_frame, date_frame = build_fact_and_dates(validated_frame)
    outputs = write_modeled_outputs(fact_frame=fact_frame, date_frame=date_frame, output_dir=output_dir)
    return {
        "fact_rows": len(fact_frame),
        "date_rows": len(date_frame),
        "outputs": outputs,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build minimal fact and date dimensions from validated data.")
    parser.add_argument("--input", type=path_arg, default=DEFAULT_VALIDATED_PATH, help="Path to the validated Parquet input.")
    parser.add_argument("--output-dir", type=path_arg, default=DEFAULT_MODELED_DIR, help="Directory for modeled Parquet outputs.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_model(input_path=args.input, output_dir=args.output_dir)
    print(
        f"Created {result['fact_rows']} fact rows and {result['date_rows']} date rows "
        f"under {args.output_dir}"
    )
    return 0
