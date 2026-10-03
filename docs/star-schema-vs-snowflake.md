# Star Schema vs Snowflake

This note compares the two common dimensional-modeling shapes and explains why the current Stage 2 implementation uses a star schema.

It is a companion to [`docs/star-schema.md`](./star-schema.md), which describes the concrete tables implemented in this repository.

## Short version

- use a star schema when the priority is simple analytical queries, understandable joins, and predictable reporting behavior
- use a snowflake schema when the priority is stricter normalization inside dimensions and dimension reuse matters more than query simplicity

For this project, the star schema is the better fit.

## What a star schema means

In a star schema:

- the fact table sits in the center
- dimensions connect directly to the fact table
- dimension tables are relatively denormalized

In this repository, the current shape is:

- `fact_submissions`
- `dim_dates`
- `dim_papers`

That is a star because the modeled tables are intended to join directly to the fact table rather than through additional sub-dimensions.

## What a snowflake schema means

In a snowflake schema:

- the fact table still sits at the center
- some dimensions are normalized into additional tables
- the query path from fact to business attributes usually requires more joins

In a fuller arXiv model, a snowflake design might split data further into shapes like:

- `dim_papers` -> publisher or license sub-dimensions
- category tables broken into group and subcategory lookup tables
- author name components broken into additional lookup tables

That design is more normalized, but it also pushes more join logic into every analytical query.

## Tradeoffs

### Star schema advantages

- simpler SQL for reporting and exploration
- fewer joins for common analytical queries
- easier for new contributors to understand
- better fit for BI-style workflows where facts are filtered and aggregated repeatedly
- dimensions can carry friendly attributes directly without repeated lookup hops

### Star schema costs

- more duplicated attribute data inside dimensions
- dimension tables may be wider
- some updates can require touching more than one row if attributes are repeated

### Snowflake advantages

- less redundancy inside dimensions
- stricter normalization of hierarchical or reusable reference data
- can make sense when dimension maintenance is the main concern
- can help when the same normalized reference entities need to be governed consistently across many models

### Snowflake costs

- more joins in nearly every analytical query
- more cognitive overhead for readers of the model
- more places for foreign-key issues or missing joins to show up
- can make a small learning project feel more complex than the reporting needs justify

## Query use cases

### Good fit for a star schema

Star schemas work well when the main questions look like:

- how many submissions happened by year or month
- which papers have multiple versions
- how many first submissions versus updates are there
- how do submission counts change over time

These are fact-first questions. They usually filter or group the fact table and join directly to a small number of descriptive dimensions.

### Better fit for a snowflake schema

Snowflake schemas are more attractive when the main questions depend on reusable hierarchies or heavily shared reference data, for example:

- many models need one canonical category-group hierarchy
- the same normalized author, institution, or license entities are maintained centrally
- dimension maintenance and governance are more important than ad hoc query readability

That is not the current situation in this repository.

## Why this repo uses a star schema

The current Stage 2 choice is deliberate.

Reasons:

- the project is about learning dimensional modeling, not maximizing normalization depth
- the current query layer is simple and analytical
- the implemented dimensions are small and easy to reason about directly
- the current scope does not yet include the richer dimension network where snowflaking would even become a serious option
- the model should stay readable for tests, docs, and local inspection

Put differently: the extra complexity of a snowflake model would be paid immediately, while most of its benefits would remain theoretical in this repo's current scope.

## Concrete examples in this project

### Example: `dim_dates`

Star-oriented choice:

- keep all calendar attributes on `dim_dates`

Why:

- queries can group by `year`, `quarter`, `month_name`, or `day_name` without additional joins

Snowflake alternative:

- split date parts into separate tables or separate hierarchical lookups

Why that is not useful here:

- it would complicate every query without reducing meaningful operational cost

### Example: `dim_papers`

Star-oriented choice:

- keep paper metadata directly on `dim_papers`

Why:

- paper-level descriptive attributes are naturally consumed together
- analysts usually want title, abstract, DOI, comments, and license together when they inspect a paper dimension row

Snowflake alternative:

- split some descriptive fields into separate reference tables

Why that is not useful here:

- there is no current need to normalize those fields into reusable shared dimensions

## When this decision might change

A future issue might justify more snowflaking if the project grows to include:

- category hierarchies used across multiple fact tables
- reusable author or institution dimensions with their own maintenance workflows
- broader warehouse-style governance requirements
- reporting patterns where dimension normalization clearly reduces duplication without hurting usability too much

If that happens, the right move would be to introduce those changes intentionally and document the new query tradeoffs, not to snowflake the model opportunistically during unrelated work.

## Practical recommendation for this repo

For the current repository:

- keep `fact_submissions` as the central event table
- keep `dim_dates` and `dim_papers` directly joinable from the fact table
- add future dimensions and bridge tables in a star-oriented shape unless there is a clear, concrete reason to normalize further

That keeps the model aligned with the current learning goals, test design, and query workload.
