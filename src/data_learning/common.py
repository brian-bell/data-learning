from __future__ import annotations

import json
from datetime import date, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

DEFAULT_RAW_INPUT_PATH = Path("data/arxiv-metadata-oai-snapshot.json")
DEFAULT_VALIDATED_PATH = Path("data/raw/arxiv_validated.parquet")
DEFAULT_MODELED_DIR = Path("data/modeled")
DEFAULT_OUTPUT_DIR = Path("data/output")


def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def ensure_parent_directory(path: Path) -> None:
    ensure_directory(path.parent)


def dump_json(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=True)


def parse_version_number(value: Any) -> int | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    if normalized.startswith("v"):
        normalized = normalized[1:]
    if not normalized.isdigit():
        return None
    return int(normalized)


def parse_created_date(value: Any) -> date | None:
    if not isinstance(value, str):
        return None

    try:
        return parsedate_to_datetime(value).date()
    except (TypeError, ValueError, IndexError, OverflowError):
        pass

    iso_candidate = value.strip().replace("Z", "+00:00")
    for parser in (datetime.fromisoformat, date.fromisoformat):
        try:
            parsed = parser(iso_candidate)
            if isinstance(parsed, datetime):
                return parsed.date()
            return parsed
        except ValueError:
            continue
    return None


def date_to_key(value: date) -> int:
    return int(value.strftime("%Y%m%d"))


def json_loads_if_needed(value: Any) -> Any:
    if isinstance(value, str):
        return json.loads(value)
    return value


def path_arg(value: str) -> Path:
    return Path(value).expanduser()
