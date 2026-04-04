# data-learning

Minimal tracer-bullet data pipeline for learning data engineering concepts with the arXiv metadata dataset.

This repository currently implements issue `#3`: a thin end-to-end slice that proves the local pipeline shape works before the fuller Phase 1 project is built out.

## Current scope

The implemented pipeline processes a small sample of the raw arXiv JSONL snapshot through four stages:

1. `ingest`: read JSONL, keep the first 100 valid records, and write validated Parquet
2. `model`: build the core Stage 2 star schema tables `fact_submissions`, `dim_dates`, and `dim_papers`
3. `store`: write `fact_submissions` to CSV and Parquet outputs
4. `query`: run one DuckDB query for submission counts by year

This is intentionally narrower than the full Phase 1 spec. It does not yet include full validation/logging, bridge tables, SCD Type 2 behavior, Avro output, benchmarks, or the Streamlit dashboard.

## Project layout

```text
data-learning/
├── pyproject.toml
├── setup.py
├── README.md
├── AGENTS.md
├── src/
│   ├── ingest.py
│   ├── model.py
│   ├── store.py
│   ├── query.py
│   └── data_learning/
├── data/
│   ├── raw/
│   ├── modeled/
│   └── output/
└── tests/
```

## Requirements

- Python `3.9+`
- Local copy of the arXiv Kaggle snapshot in JSONL form

Default raw input path:

```text
data/arxiv-metadata-oai-snapshot.json
```

## Download the dataset with Kaggle CLI

The intended source for this project is the Kaggle arXiv dataset:

```text
Cornell-University/arxiv
```

If you want the file locally as `data/arxiv-metadata-oai-snapshot.json`, the Kaggle CLI is the easiest path.

### 1. Install the Kaggle CLI

You can install it inside this project's virtual environment:

```bash
./.venv/bin/pip install kaggle
```

Or, if you have activated the environment already:

```bash
pip install kaggle
```

### 2. Create a Kaggle API token

1. Sign in to Kaggle
2. Open your account settings at `https://www.kaggle.com/settings`
3. In the API section, create a new token
4. Kaggle will download a file named `kaggle.json`

### 3. Put `kaggle.json` where the CLI expects it

On macOS:

```bash
mkdir -p ~/.kaggle
mv ~/Downloads/kaggle.json ~/.kaggle/kaggle.json
chmod 600 ~/.kaggle/kaggle.json
```

The `chmod 600` step matters because the Kaggle CLI expects your API token file to be private.

### 4. Download the arXiv dataset

From the repo root:

```bash
mkdir -p data
./.venv/bin/kaggle datasets download -d Cornell-University/arxiv -p data
```

That command downloads a zip file into `data/`.

### 5. Unzip it

```bash
unzip data/arxiv.zip -d data
```

After extraction, you should have:

```text
data/arxiv-metadata-oai-snapshot.json
```

### 6. Verify the file exists

```bash
ls -lh data/arxiv-metadata-oai-snapshot.json
```

## Python on macOS

If you are new to Python, the main thing to know is that you should treat each project as having its own isolated Python environment.

For this repo, the recommended approach is:

1. Make sure `python3` exists and is at least version `3.9`
2. Create a local virtual environment in `.venv`
3. Install this project's dependencies into that `.venv`
4. Run all project commands with that environment

Check your current Python:

```bash
python3 --version
which python3
```

If your machine does not have `python3`, or if the version is older than `3.9`, install a newer Python first. For beginners, the simplest paths are:

- install Python from `python.org`, or
- install Python with Homebrew and use that `python3`

## Why use a virtual environment?

Yes, you should use a virtual environment for this project.

A virtual environment:

- keeps this repo's packages separate from your system Python
- avoids version conflicts with other Python projects
- makes it easy to delete and recreate your local setup if something gets messy

In this repo, the virtual environment lives in:

```text
.venv/
```

That folder is local to the project and is not meant to be committed.

## Setup

From the repo root, create a virtual environment and install the project:

```bash
python3 -m venv .venv
./.venv/bin/pip install --upgrade pip setuptools wheel
./.venv/bin/pip install -e .
```

What those commands do:

- `python3 -m venv .venv` creates an isolated Python environment in this folder
- `./.venv/bin/pip install --upgrade ...` updates packaging tools inside that environment
- `./.venv/bin/pip install -e .` installs this repo in editable mode, so local code changes are immediately used without reinstalling every time

## Two ways to run commands

You can use this project in either of these styles.

### Option A: Run tools directly from `.venv`

This is the most explicit and beginner-friendly option because every command clearly uses the project's Python:

```bash
./.venv/bin/python --version
./.venv/bin/pytest -q
```

This README mostly uses that style.

### Option B: Activate the virtual environment

You can also activate the environment for your current shell session:

```bash
source .venv/bin/activate
```

After activation, commands like `python`, `pip`, and `pytest` automatically point at the local environment:

```bash
python --version
pip install -e .
pytest -q
```

When you are done, leave the environment with:

```bash
deactivate
```

If you are not comfortable with shell state yet, use Option A and call binaries via `./.venv/bin/...`.

## Running the pipeline

Run each stage manually in sequence from the repository root.

Before running the pipeline, make sure the raw arXiv JSONL snapshot exists at:

```text
data/arxiv-metadata-oai-snapshot.json
```

If your file lives somewhere else, pass a different path with `--input`.

### 1. Ingest

```bash
./.venv/bin/python src/ingest.py \
  --input data/arxiv-metadata-oai-snapshot.json \
  --output data/raw/arxiv_validated.parquet \
  --limit 100
```

### 2. Model

```bash
./.venv/bin/python src/model.py \
  --input data/raw/arxiv_validated.parquet \
  --output-dir data/modeled
```

### 3. Store

```bash
./.venv/bin/python src/store.py \
  --input data/modeled/fact_submissions.parquet \
  --output-dir data/output
```

### 4. Query

```bash
./.venv/bin/python src/query.py \
  --fact-path data/output/parquet/fact_submissions.parquet \
  --date-dim-path data/modeled/dim_dates.parquet
```

Expected query output is a tab-separated table:

```text
year    submission_count
...
```

## Outputs

The current tracer bullet writes:

- `data/raw/arxiv_validated.parquet`
- `data/modeled/fact_submissions.parquet`
- `data/modeled/dim_dates.parquet`
- `data/modeled/dim_papers.parquet`
- `data/output/csv/fact_submissions.csv`
- `data/output/parquet/fact_submissions.parquet`

## Testing

Run the test suite with:

```bash
PYTHONPYCACHEPREFIX=/tmp/data-learning-pyc ./.venv/bin/pytest -q
```

The tests cover stage behavior plus a CLI smoke test for the full ingest -> model -> store -> query flow.

If you activated the virtual environment first, the shorter equivalent is:

```bash
pytest -q
```

## Common beginner workflow

If you just want a safe, repeatable local workflow on macOS, use this:

```bash
python3 -m venv .venv
./.venv/bin/pip install --upgrade pip setuptools wheel
./.venv/bin/pip install -e .
./.venv/bin/pytest -q
./.venv/bin/python src/ingest.py --help
```

That sequence confirms:

- Python is working
- the virtual environment exists
- dependencies installed correctly
- tests pass
- the project CLI is runnable

## Troubleshooting

- If `python3` is missing, install Python first, then rerun the setup commands.
- If `pip install -e .` fails, make sure you are running it from the repository root.
- If command names like `pytest` are not found, either activate `.venv` or use the full path like `./.venv/bin/pytest`.
- If you want to completely reset your local Python environment, delete `.venv/` and recreate it with the setup commands above.

## Notes

- `data/` contents are ignored by git; only placeholder `.gitkeep` files are tracked.
- The code uses CLI defaults for repo-local paths, but every stage also accepts explicit file arguments for tests and ad hoc runs.
