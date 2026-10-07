# Answer-quality evaluation

This is optional development tooling. The browser does not require stored
reference answers or the evaluation judge. Run commands from the repository root
after loading `.env`; install the default judge with `ollama pull qwen3:8b`.
Use fresh output paths and isolated single-paper benchmark indexes. See the
[corpus protocol](benchmark-corpus.md) before starting a run.

New reports preserve accepted claim evidence, per-call inference timings, and
Ollama model/runtime identities. See the [report format and legacy compatibility](evaluation-report-format.md)
for what each field means and how resume handles older reports.

The [first comparison on the second paper](housing-model-comparison.md)
compares Qwen3 8B, GPT-OSS 20B and Qwen3 Coder 30B with identical retrieved evidence.
GPT-OSS refused where both Qwen models gave unsupported answers, but grader and
section-metadata defects limit the automated scores. No default was changed.


The default below is the historical sample-paper development benchmark. For a
separate paper, supply a versioned JSON manifest and its local PDF:

```bash
uv run python -m scripts.evaluate_answers \
  --benchmark benchmarks/housing-temperature-2025.json \
  --pdf data/housing-temperature.pdf --validate-only
```

See [corpus acquisition and evaluation protocol](benchmark-corpus.md) for the
license, download, isolated database setup and evaluation-set lifecycle. `--validate-only`
checks the PDF and labels without calling models or accessing the database. Remove
that flag to run an evaluation against an index containing only the selected paper.


See the [17 September local evaluation](evaluation-2026-09-17.md) for a completed
20-question run, its configuration, and a manual review of the observed failures.

Run the complete question → retrieval → generation pipeline, then score each answer.
The CLI defaults to **plain** generation; pass `--answer-mode verified` to evaluate
the browser's claim-checking path, which also requires `gpt-oss:20b`:

```bash
uv run python -m scripts.evaluate_answers
```

This default plain-mode run requires PostgreSQL, Ollama with `nomic-embed-text`
and `qwen3:8b`, the reranker
(downloaded on first use if not cached), and the original paper at `data/sample.pdf`.
The paper is *Pre-clinical cancer cachexia causes glucose hypermetabolism prior to
overt weight loss*, DOI `10.1016/j.molmet.2026.102422`. Its SHA-256 must match the
labelled version, and the index must contain only this paper because the
unanswerability labels apply to this corpus.

The 24 cases in `scripts/answer_quality_cases.py` contain 18 answerable questions with
reference answers and evidence quotes, plus six unanswerable questions. Four
attribution cases distinguish cited treatment studies from the current paper. They are
assistant-authored, exploratory labels on the same paper used for retrieval tuning,
with overlapping topics. Review them before using the results to make claims about
general answer quality; this is not an independently reviewed benchmark.

For a quick trial, select one answerable and one unanswerable question:

```bash
uv run python -m scripts.evaluate_answers \
  --case c26-body-mass-loss --case female-mice
```

To compare without reranking, run a separate report:

```bash
uv run python -m scripts.evaluate_answers --strategy vector
```

To evaluate reranked passages with neighboring context:

```bash
uv run python -m scripts.evaluate_answers --strategy expanded
```

To test the opt-in vector-reserve strategy, use `--strategy vector_reserve`.
It keeps three reranked chunks and appends the highest vector-ranked candidate
not already selected; `--top-k` must be below ten. Its
[development evaluation](vector-reserve-evaluation.md)
does not change the normal API retrieval default.

`expanded` keeps six of the top ten reranked passages by default, then adds the
two preceding and two following chunks on each passage's document and page.
Overlapping windows are merged, repeated text at chunk boundaries is removed,
and the rendered context (including source labels) is capped at 6,000 characters.
Budgeting retains whole passages rather than cutting through a numerical result.
Returned sources contain exactly the passages provided to the model. For a merged
window, `chunk_index` identifies its first included chunk; document and page remain
unchanged. Neighboring text is context, not independently ranked evidence.

Use `--top-k 3` to reproduce the previous expanded cutoff, or choose another cutoff
from 1 to 10. The effective cutoff, strategy, neighbor radius, context budget and
generator prompt fingerprint are recorded in reports. Resume preserves the saved
cutoff; an explicitly different `--top-k` is rejected. Older reports without the
required settings need a fresh run.

The [evidence-coverage comparison](retrieval-evidence-coverage.md) traces a
reranking miss and compares three versus six seeds across both development papers.
The subsequent [verified-answer comparison](verified-context-comparison.md)
completed 68 answers: wider context recovered some answers but introduced a
cited-study refusal and higher latency, so expansion remains opt-in.
The [third-paper unexpanded verified evaluation](unexpanded-verified-third-paper.md)
used a separate CC BY paper and the normal three-passage retrieval path. It
answered seven of eight answerable questions and refused both unanswerable ones;
one false refusal came from missing complementary retrieved evidence. The small,
assistant-labelled set is provisional and does not change the API defaults.
The retrieval-only runner reproduces the coverage check without generating answers:

```bash
uv run python -m scripts.compare_evidence_coverage \
  --output evaluation-results/coverage-sample.json
```

For a focused retrieval diagnosis, select a question and widen the inspected
candidate pool without generating an answer:

```bash
uv run python -m scripts.compare_evidence_coverage \
  --benchmark benchmarks/activin-receptor-2025.json \
  --pdf data/activin-receptor-2025.pdf \
  --case activin-liver-tg-duration --candidates 30 --repetitions 1 \
  --output evaluation-results/activin-qualifier-coverage.json
```

This coverage command can use your existing multi-paper library. Retrieval and
PDF-text validation are scoped to the benchmark's exact filename; the saved
fingerprint covers the full library, and any library change fails the run.
Repeat `--case` to select more answerable questions. Unknown, duplicate or
unanswerable selections are rejected. `--candidates` accepts 1–100 and must be
at least the larger cutoff; the existing defaults remain ten candidates and
three-versus-six seeds. The report saves all candidates, reranked order and the
actual selection. It performs one warmup plus the requested measured repetitions,
calling embeddings and the reranker but no answer generator or judge.

Both numeric labels can match while a required population or diet qualifier is
missing. Quote coverage is a retrieval diagnostic, not answer correctness; inspect
the complete evidence chain. See the [Activin context investigation](activin-context-coverage.md).
These scoped-library changes apply to the coverage command; other benchmark
runners retain their documented isolation requirements.

The default `reranked` strategy retrieves ten candidates and retains three for
plain answering or six for verified answering, without neighbor expansion. The
`vector` and `vector_reserve` strategies retain their three-passage defaults.
Use `--top-k 3` to reproduce the older verified cutoff; resumed reports preserve
their recorded cutoff. The [coverage follow-up](reviewed-answer-quality.md) records
the six-passage development trial and known gaps. Reference answers and labels go
only to the judge.
The FastAPI endpoint continues to use reranking without expansion. Expansion stays
opt-in because the previous trial improved retrieval but introduced an unsupported
drug-treatment answer. See the [neighboring-context evaluation](neighbor-context-evaluation.md)
for results, inspected failures, and the rollout decision.

### Scores and limitations

| Metric | Meaning |
|---|---|
| Correctness / completeness / citation support | Judge scores from 0–2, averaged and divided by 2 across answerable cases only. Support checks the returned source bundle, not inline citation attribution. |
| Evidence hit rate | Fraction of answerable cases with at least one labelled quote fully present in a returned chunk on the correct document/page. |
| Mean evidence recall | Average fraction of each answerable case's labelled quotes found in returned chunks. |
| Abstention accuracy | Fraction of all cases where answering versus declining matches the paper's answerability label, using the judge's classification. |
| Unanswerable abstention rate | Fraction of unanswerable cases where the judge classifies the response as a refusal without guessing. |
| Answerable false abstention rate | Fraction of answerable cases where the assistant declined. Lower is better. |
| Pass rate | All three judge scores equal 2, expected abstention behavior, and at least one evidence match for answerable cases. |

Quotes are validated against the PDF before running, independently of chunk boundaries.
Evidence matching normalizes line breaks and hyphenation but requires the whole quote
in one returned chunk; it can miss split or alternative supporting passages. Indexed
text must belong to the PDF; duplicate chunk identities and a changed index are rejected.
The evaluator never reindexes the paper.

Evaluation uses `RAG_JUDGE_MODEL` (default `qwen3:8b`) with temperature zero and
thinking disabled. For noncanonical answers, it makes two schema-constrained calls:

1. Classify refusal behavior using only the question and answer. Reference answers,
   answerability labels and retrieved passages are absent from this call. Partial
   answers and refusals followed by guesses are not counted as abstentions.
2. Grade factual quality using the reference and returned passages. Expected
   evidence quotes are omitted, so they cannot be mistaken for retrieved evidence.

The first decision owns the final `abstained` flag. Code assigns zero correctness
and completeness when an answerable question was refused, even if the grading
call awards full credit. Source support remains independently graded, including
any factual explanation attached to a refusal. Unanswerable refusals do not
receive automatic full credit if they contain unsupported explanatory claims.
Both calls can still be wrong; inspect their explanations and passages. Invalid
output fails the run. Judge timing includes both calls. Unavailable metric groups
in selected-case runs are reported as `null`.

The initial local trial exposed both kinds of failure: a chunk beginning partway
through a percentage led to an incorrect body-mass answer, and the judge credited
another answer with a numerical detail present only in the reference. These examples
are why both the exact-evidence diagnostic and manual review are needed.

Before generating benchmark answers, calibration version 2 exercises thirteen
synthetic controls through the same two-stage evaluator. They cover correct and
partial answers, contradictions, missing evidence, short and explanatory refusals,
refusals followed by guesses, and negative findings that must count as answers.
The report records the scores and checks. A failed check stops the run with
`calibration_failed` and no aggregate metrics. Transport or invalid-output errors
produce a `failed` report. Passing this small calibration does **not** establish
judge accuracy or remove the need for human review.

Each noncanonical calibration control uses two model calls; the exact fact-free
refusal controls are scored directly. Each plain benchmark case normally adds one
generation call and two evaluation calls; exact fact-free refusals skip the two
evaluation calls. Verified generation may use additional calls. Calibration may
warm the local model; there is no dedicated timing warmup. Answer timing includes
retrieval, generation and model loading; judge timing is separate. Model-default
sampling can vary between runs. Use the retrieval comparison for warmed latency
measurements.

Reports in the Git-ignored `evaluation-results/` directory include questions, answers,
sources, judge explanations, timings, paper/corpus/case fingerprints, model names,
settings, and package versions. Generated answers, sources, and generation timing
are saved **before judging**, then completed scores are saved separately. Failure
or interruption leaves a report with completed results and any pending answer,
but no aggregate scores. Checkpoints are replaced atomically.

Resume a failed or interrupted run into a new report:

```bash
uv run python -m scripts.evaluate_answers \
  --resume evaluation-results/answers-original.json \
  --output evaluation-results/answers-resumed.json
```

Resume keeps the original report, skips completed cases, and reuses a saved pending
answer instead of regenerating it. Calibration runs again before work continues.
The source paper, corpus, cases, model names, settings, and evaluator version must
match; incompatible or malformed reports are rejected. New reports also record
Ollama weight digests and runtime versions, and resume rechecks previously known
identities. Missing metadata in older reports remains unknown; keep installed
models unchanged when resuming those reports.
Reports from the old schema (version 1), or older evaluations without recorded
thinking settings or the generator prompt fingerprint, cannot be resumed; start
a new run for them. Changing either prompt or thinking settings also requires a
fresh evaluation. Without a grounding timeout override, requests without explicit reasoning retain the 120-second timeout;
explicit reasoning uses 300 seconds. Changed sampling, output budgets, or timeouts also require fresh evaluation.
An exhausted output budget fails the call; it is not counted as an evidence refusal or silently retried.
Disabling judge thinking is not a guarantee
against timeouts on every machine.

The canonical application refusal and a small explicit set of fact-free refusal
sentences are scored directly: each counts as abstention, with
zero correctness/completeness on answerable cases and full credit on unanswerable
cases. Other responses use the two-stage evaluator described above. Evaluator
version 9 and the combined prompt/exact-refusal fingerprint prevent resuming reports under older
grading rules; historical reports remain readable and are not rewritten.
`--output PATH` chooses a filename; existing reports are never overwritten.
