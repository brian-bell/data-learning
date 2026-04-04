from __future__ import annotations

import json
from datetime import datetime
from email.utils import format_datetime
from pathlib import Path
from typing import Any

from tests.conftest import ROOT


def make_arxiv_record(identifier: int, *, version_count: int = 1, year: int = 2020) -> dict[str, Any]:
    versions = []
    for index in range(version_count):
        month = (index % 12) + 1
        day = (index % 28) + 1
        versions.append(
            {
                "version": f"v{index + 1}",
                "created": format_datetime(datetime(year + index, month, day)),
            }
        )

    return {
        "id": f"{identifier:07d}",
        "submitter": f"submitter-{identifier}",
        "title": f"Paper {identifier}",
        "authors_parsed": [["Bell", "Brian", ""]],
        "categories": "cs.AI cs.LG",
        "versions": versions,
        "abstract": f"Abstract for paper {identifier}",
        "doi": None,
        "journal-ref": None,
        "comments": None,
        "license": "CC0",
        "update_date": f"{year:04d}-01-01",
    }


def write_jsonl(path: Path, records: list[dict[str, Any]], extra_lines: list[str] | None = None) -> None:
    lines = [json.dumps(record) for record in records]
    if extra_lines:
        lines.extend(extra_lines)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
