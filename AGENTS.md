# AGENTS.md

## Purpose

This repository is a local learning project for a staged data-engineering pipeline over arXiv metadata. The current implementation is the narrow tracer bullet for issue `#3`, not the full Phase 1 spec.

When making changes, preserve that distinction unless the user explicitly asks to expand scope.

## Current implementation boundaries

- Implemented:
  - packaging and editable install support
  - `src/ingest.py`
  - `src/model.py`
  - `src/store.py`
  - `src/query.py`
  - shared logic under `src/data_learning/`
  - stage tests and one end-to-end CLI smoke test
- Not implemented yet:
  - full ingestion validation/reporting
  - `dim_papers`
  - authors/categories dimensions and bridge tables
  - SCD Type 2 logic
  - Avro output and benchmarks
  - dashboard/UI

Do not quietly introduce later-scope features while touching the tracer bullet.

## Working conventions

- Python version target: `>=3.9`
- Package install: `./.venv/bin/pip install -e .`
- Test command:

```bash
PYTHONPYCACHEPREFIX=/tmp/data-learning-pyc ./.venv/bin/pytest -q
```

- The macOS environment may block default bytecode cache writes outside the workspace. If needed, keep using `PYTHONPYCACHEPREFIX=/tmp/data-learning-pyc`.
- Data files under `data/` are not tracked. Assume tests should use temp fixtures, not the real Kaggle dataset.

## Code expectations

- Keep the CLI entrypoints in `src/` thin; put reusable behavior in `src/data_learning/`.
- Favor explicit path arguments and deterministic outputs so tests can run against temp directories.
- Preserve the current tracer-bullet fact schema unless the user explicitly requests the next modeling issue:
  - `submission_key`
  - `paper_id`
  - `version_number`
  - `date_key`
  - `is_first_submission`
  - `is_latest_version`

## When updating docs

- Keep `README.md` aligned to what is actually implemented today.
- If new issues expand scope, update both `README.md` and this file so future agents do not assume unfinished Phase 1 features already exist.
