# Stage 2 Star Schema

This note describes the Stage 2 dimensional model implemented in [`src/data_learning/model_stage.py`](/Users/brian/dev/data-learning/src/data_learning/model_stage.py).

The current modeled schema centers on three tables:

- `fact_submissions.parquet`
- `dim_dates.parquet`
- `dim_papers.parquet`

Together they form a compact star schema for analytical work over arXiv submission history. The model is intentionally narrower than a fuller warehouse-style design: bridge tables and full SCD Type 2 behavior are not part of the current implementation.

## Schema overview

### `fact_submissions`

This is the central fact table.

Grain:

- one row per paper-version submission event

Columns:

- `submission_key`
- `paper_id`
- `version_number`
- `paper_key`
- `date_key`
- `is_first_submission`
- `is_latest_version`

Why this grain:

- the raw arXiv data already expresses version history as repeated version entries per paper
- one row per paper-version keeps that submission history explicit
- analytical queries such as "how many updates happened" or "which submissions were latest" become simple filters and counts

Tradeoff:

- this creates more fact rows than a one-row-per-paper model
- but the extra rows reflect real submission events, which is the more useful analytical shape for this dataset and query pattern

### `dim_papers`

This dimension has one row per unique `paper_id`.

Columns:

- `paper_key`
- `paper_id`
- `title`
- `abstract`
- `doi`
- `journal_ref`
- `comments`
- `license`
- `valid_from`
- `valid_to`
- `is_current`

Implementation choice:

- `paper_key` is a surrogate key assigned deterministically from sorted `paper_id` values
- `valid_from`, `valid_to`, and `is_current` are present to support historical dimension patterns
- in the current implementation, each paper has one current row, `valid_to` is null, and `valid_from` is the first submission date

Tradeoff:

- this is not a full historical dimension yet
- but it keeps the schema compatible with future historical-dimension work without pretending SCD Type 2 is already implemented

### `dim_dates`

This is a calendar dimension keyed by `date_key` in `YYYYMMDD` form.

Columns:

- `date_key`
- `full_date`
- `year`
- `quarter`
- `month`
- `month_name`
- `day_of_week`
- `day_name`
- `is_weekend`

Implementation choice:

- the dimension is generated for every calendar day from the earliest submission date to the latest submission date, inclusive
- it is not limited to dates that appear directly in the fact table

Tradeoff:

- this writes more rows than a sparse "observed dates only" table
- but it makes the date dimension behave like a real analytic calendar dimension and supports simpler joins and future reporting

## Why a star schema here

Stage 2 uses a star schema rather than a snowflake design.

Reasons:

- the main queries are analytical and join-driven, not OLTP updates
- denormalized dimensions are easier to understand in a learning project
- a star schema keeps the relationship between events and dimensions visible without extra join depth

Tradeoff:

- a snowflake model could reduce some duplication inside dimensions
- but it would add complexity without improving the current query patterns or learning goals

## Surrogate keys versus natural keys

The model keeps both:

- `paper_id` as the natural arXiv identifier
- `paper_key` as the warehouse-style surrogate key

Why both exist:

- `paper_id` is readable and maps directly back to the source data
- `paper_key` gives the model a stable dimension join key
- surrogate keys are the standard pattern once dimensions may need historical versioning

Tradeoff:

- keeping both keys adds one more column to the fact table
- but it avoids repainting the schema later when SCD logic is added

## Determinism and testability

The current implementation favors deterministic outputs:

- `paper_key` assignment is based on sorted `paper_id`
- all modeled outputs are written from explicit input and output paths
- tests can build temporary fixtures and assert exact row values

This is a good fit for a local batch pipeline because reruns should produce the same outputs from the same validated input.

## Scope limits

Some dimensional-modeling capabilities are intentionally outside the current schema:

- SCD Type 2 behavior in `dim_papers`
- author and category dimensions
- bridge tables for paper-author and paper-category relationships
- later storage-format and dashboard work from later stages

That boundary matters because this document is meant to describe the current model accurately without implying a broader warehouse design that is not yet present.
