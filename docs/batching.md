# Ingest Batching

This note explains the batching pattern used by Stage 1 ingestion in [`src/data_learning/ingest_stage.py`](/Users/brian/dev/data-learning/src/data_learning/ingest_stage.py).

## Read path

Input is read one line at a time from the JSONL snapshot:

- the file handle is opened once
- each non-empty line is parsed with `json.loads(...)`
- each parsed record is validated immediately

This means reads are streamed. The ingest stage does not load the full source file into memory.

## Write path

Writes are batched separately from reads.

For each valid record:

1. the normalized record is appended to `buffered_rows`
2. once `len(buffered_rows) >= batch_size`, the batch is written to the open `pyarrow.parquet.ParquetWriter`
3. the in-memory buffer is cleared

At end of file, the remaining partial batch is written once more.

## Current batch size

The current default write batch size is `10_000` rows, defined as `DEFAULT_BATCH_SIZE` in [`src/data_learning/ingest_stage.py`](/Users/brian/dev/data-learning/src/data_learning/ingest_stage.py).

That means:

- full batches are written in chunks of 10,000 valid rows
- the final flush is whatever remains, from 1 to 9,999 rows
- if `--limit` is used, the last batch may be smaller than the default size

## Why this helps

This pattern keeps memory bounded compared with collecting every validated row before writing output.

It also preserves the simple semantics of a batch job:

- one bounded input snapshot
- one deterministic output file
- reruns can rewrite the target from the beginning

That is much simpler than a streaming system where the code has to reason about duplicate events, checkpoint recovery, and idempotent event-by-event writes.

## Memory tradeoff

The code is memory-safe relative to the full dataset, but it is not memory-free.

Peak memory for the write side is driven by:

- `batch_size`
- average size of each normalized record
- temporary conversion overhead when `buffered_rows` is converted into a PyArrow table

So a larger batch improves write amortization, but it also increases peak memory use. If records become much larger, reducing `batch_size` lowers the memory ceiling.

## Why reading line by line is not enough by itself

Streaming reads only solve half of the problem.

Even if input is parsed one line at a time, memory can still grow too large if validated rows are accumulated without a write flush. The separate write buffer is what keeps output-side memory bounded.

## Future hardening options

If Stage 1 needs tighter operational controls later, reasonable next steps would be:

- make `batch_size` configurable from the CLI
- benchmark different batch sizes on the full dataset
- track approximate buffer size in bytes instead of only row count
