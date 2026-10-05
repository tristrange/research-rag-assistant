# PDF embedding batching

PDF ingestion now sends at most 16 chunk texts per Ollama `/api/embed` request
and owns one HTTP client for the operation. The
[Ollama API](https://docs.ollama.com/api/embed) accepts an array of texts.
The single-question request remains unchanged. Every response must contain
exactly one finite 768-value vector per input, in input order. All batches finish
before index replacement; a malformed or failed later batch preserves the
saved chunks and provenance. Progress counts only fully completed batches.

## Local development measurement, 2026-10-05

Use eight evenly spaced chunk locations from each of the four existing PDFs:
32 texts prepared with indexing's 500-character target and 100-character
overlap. Warm the model first, then time two rounds with reversed mode order:
single/pooled/batched, then batched/pooled/single. Include client creation and
closing in each timed run. The model was `nomic-embed-text`, digest
`0a109f422b47e3a30ba2b10eca18548e944e8a23073ee3f3e947efcf3c45e59f`,
with Ollama 0.35.1 on an Apple Silicon Mac.

| Mode | Requests for 32 chunks | Median elapsed time |
| --- | ---: | ---: |
| Previous single-text requests | 32 | 0.786 s |
| One client, one text per request | 32 | 0.494 s |
| One client, batches of 16 | 2 | 0.458 s |

Connection reuse accounted for most of the measured gain. Both optimized modes
returned exactly the same vectors as single-text requests in both rounds.
Top-three cosine rankings also matched for three questions across the full
32-chunk set and each paper separately: 15 probes per round. This was a
read-only vector comparison; it performed no indexing or answer generation.

The fresh ignored report `embedding-batching-20261005T140958994574Z.json` records
PDF hashes, selected-text hash, processing profile, model/runtime snapshot and
individual timings. The earlier `embedding-batching-20261005T140732725037Z.json`
used the chunking helper's larger defaults; it is preserved separately and is
not the basis for this table.

This small warm-model measurement does not establish cold-start, full-PDF or
answer latency. Existing compatible indexes need no migration or reindex for
this transport optimization. Model, dimensions, extraction and chunking remain
unchanged. Changing those inputs still requires reindexing and new evaluation.
