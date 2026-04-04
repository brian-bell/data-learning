# Stage 2 Star Schema

This note explains the current Stage 2 modeling design implemented in [`src/data_learning/model_stage.py`](/Users/brian/dev/data-learning/src/data_learning/model_stage.py).

The repository now writes three modeled Parquet tables under `data/modeled/`:

- `fact_submissions.parquet`
- `dim_dates.parquet`
- `dim_papers.parquet`

This is the core star schema from issue `#5`. It is intentionally narrower than the full Phase 1 spec: bridge tables and SCD Type 2 behavior are still out of scope.

## Schema overview

### `fact_submissions`

This is the central fact table.

Current grain:

- one row per paper-version submission event

Current columns:

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
- but the extra rows reflect real submission events, which is the more useful analytical shape for this project

### `dim_papers`

This dimension has one row per unique `paper_id`.

Current columns:

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
- `valid_from`, `valid_to`, and `is_current` are present now as placeholders for later SCD work
- for issue `#5`, every paper row is current, `valid_to` is null, and `valid_from` is the first submission date

Tradeoff:

- this is not a full historical dimension yet
- but it keeps the schema compatible with the next modeling issue without pretending SCD Type 2 is already implemented

### `dim_dates`

This is a calendar dimension keyed by `date_key` in `YYYYMMDD` form.

Current columns:

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

## Known limits of the current implementation

What is intentionally not implemented yet:

- SCD Type 2 behavior in `dim_papers`
- author and category dimensions
- bridge tables for paper-author and paper-category relationships
- later storage-format and dashboard work from later stages

That boundary matters because the current code should describe the implemented core star schema accurately without implying the rest of Phase 1 already exists.
