# Pipeline performance baselines

This is optional development tooling for measuring where one answer spends its
time. It is not an answer-quality evaluation, a latency guarantee, or a release
gate. Run it from the repository root against the same isolated corpus and model
configuration you intend to compare.

**Baseline status:** pending. This change adds the measurement contract and CLI;
it does not include a measured baseline. Do not cite a performance number until a
report has been produced on the hardware, models and corpus being discussed.

## Inputs

The case manifest is local JSON. Questions stay in the manifest and are not copied
into the report. Each `document` must be the exact filename already present in the
indexed library.

```json
{
  "schema_version": 1,
  "answer_mode": "verified",
  "cases": [
    {
      "id": "cachexia-body-mass",
      "question": "Did body mass change before overt weight loss?",
      "document": "sample.pdf"
    }
  ]
}
```

`answer_mode` is `verified` by default; use `plain` for the free-text path. Case
IDs must be unique. Documents must be bare `.pdf` filenames, not paths. The runner
checks that every document is indexed before collecting samples.

The runner needs PostgreSQL, Ollama with the embedding and answer models, and the
reranker model. The first reranker use may download model files. The answer mode
determines whether `qwen3:8b` or `gpt-oss:20b` is exercised; the verified path also
produces grounding diagnostics.

## Command

Use a fresh output path under `evaluation-results/`, which is Git-ignored:

```bash
uv run python -m scripts.benchmark_pipeline \
  --cases benchmark-cases.json \
  --output evaluation-results/pipeline-baseline-20261021.json \
  --runs 5 --warmup 1
```

The output path is reserved before any search or model call and is never
overwritten. Once the initial report exists, a sample failure or a later
runtime/index change updates it with a failed status rather than replacing an
earlier trial. A setup failure before that point leaves only the empty reserved
file.

## What is measured

Each case gets one warm-up by default and five measured runs. Warm-up samples are
retained with `phase: "warmup"` but excluded from summaries. Measured samples are
marked `phase: "measured"`.

The answer path records monotonic wall-clock time for these stages:

- `embedding`: query embedding construction (or validation of a supplied embedding)
- `vector_search`: candidate retrieval, including overview fallbacks
- `rerank`: reranking and any vector-reserve selection
- `context`: source/chunk construction or context expansion
- `generation`: the answer or grounding call, including verification

Verified runs also copy each `VerificationTrace` into the sample. Its stages appear
in `stages` with a `grounding_` prefix, and the raw trace records remain under
`verification`. Grounding stages are nested inside `generation`; do not sum every
stage as if the stages were disjoint.

Every sample also records its total duration, Ollama model calls, token counts when
the provider reports them, the failed stage if an exception escaped a stage, and
the exception type. Exceptions are retained as failed samples so a run is not
silently reduced to its successes. Error messages are deliberately not stored.

Summaries report count, mean, median, nearest-rank p90, minimum, maximum and
population standard deviation. They are written per case and for all measured
complete samples. A stage that did not run is omitted rather than treated as zero.

## Provenance and redaction

The report uses schema version `pipeline-performance-v1` and records:

- commit SHA, UTC start/finish timestamps
- operating system, machine architecture, Python and Pydantic versions
- SHA-256 of the exact manifest bytes and a hash of the effective settings
- answer mode, retrieval settings, reranker model and warm-up declaration
- Ollama runtime and model digests before and after the run
- corpus/index fingerprint before and after the run
- process peak resident memory where the platform exposes it

A runtime or corpus change makes the trial fail because its samples are no longer
comparable. The report contains no questions, prompts, passages, answer text or
free-form model output. Keep manifests and reports local anyway: manifests contain
questions and generated reports can still reveal development activity.

## Interpretation limits

Timing is specific to the machine, model server state, corpus, cache state and
software commit. A warm-up inside one process does not guarantee that Ollama or the
operating system has the same cache state on another run. `reranker_cache` records
only whether the run declared a warm-up; it is not a cache measurement.

Peak RSS is a whole-process maximum, not a per-stage allocation measurement. The
`generation` stage for verified answers includes grounding and verification work,
so use the nested grounding traces when those costs matter.

Reindex after extraction, chunking or embedding changes before collecting a new
baseline. Compare reports only when their corpus fingerprints, runtime identities,
settings, answer mode and relevant hardware state match. This runner is a local
diagnostic and does not replace the [answer-quality evaluation](answer-evaluation.md)
or the [retrieval evaluation](retrieval-evaluation.md).
