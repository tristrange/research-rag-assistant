# Research RAG Assistant

A local-first Retrieval-Augmented Generation (RAG) system for querying academic PDFs.

The project extracts and chunks PDF text, generates local embeddings, stores them in PostgreSQL with pgvector, retrieves relevant passages, and uses a local LLM to answer questions with source metadata.

## Stack

- Python
- uv
- FastAPI
- Ollama
- Qwen3 8B
- nomic-embed-text
- PostgreSQL + pgvector
- SQLAlchemy
- PyMuPDF
- sentence-transformers

## Current pipeline

```text
PDF
→ text extraction
→ chunking
→ embeddings
→ pgvector
→ semantic retrieval
→ reranking
→ local LLM
→ answer + sources
```

## Setup

Install dependencies:

```bash
uv sync
```

Start PostgreSQL:

```bash
docker compose up -d
```

Initialize the database:

```bash
uv run python -m scripts.init_db
```

Pull the local models:

```bash
ollama pull qwen3:8b
ollama pull nomic-embed-text
```

Place a paper at:

```text
data/sample.pdf
```

Index it (running this again replaces the chunks for `sample.pdf`):

```bash
uv run python -m scripts.index_pdf
```

Documents are currently identified by filename. Reindexing replaces only that
filename's chunks, including removing stale chunks if the PDF becomes shorter or
has no extractable text. Extraction, embedding, or database failures preserve the
previous index. Use distinct filenames for distinct papers.

Chunking prefers sentence boundaries and falls back to whitespace for long
sentences. It keeps the original page text and metadata, with a hard character
limit; exceptionally long tokens may still be split. Overlap is adjusted to
boundaries rather than being an exact number of characters. This reduces partial
numbers and detached sentence fragments, but does not guarantee correct retrieval
or answers. Sentence detection is a lightweight punctuation heuristic, not a full
parser for scientific prose.

After updating the chunker, rerun `uv run python -m scripts.index_pdf` to replace
the stored chunks and embeddings. Existing indexes do not change automatically.
Then rerun the retrieval and answer evaluations below; older reports describe the
old chunk boundaries and should not be treated as measurements of the new index.

Start the API:

```bash
uv run uvicorn app.main:app --reload --reload-dir app
```

## Example

```bash
curl -X POST http://127.0.0.1:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question":"What is the main contribution of the paper?"}' \
  | jq
```

## Retrieval evaluation

The retrieval pipeline is evaluated on a manually labelled set of research-paper questions.

Hit@k is the fraction of questions with at least one expected page among the first k chunks. Relevance is currently labelled at page level.

Current best configuration:

- chunk size: `500`
- overlap: `100`
- top-k: `3`

Results:

| Metric | Score |
|---|---:|
| Hit@1 | 0.75 |
| Hit@3 | 0.92 |
| Hit@5 | 0.92 |
| MRR | 0.82 |

### Compare reranking

Use the same indexed paper and the shared development questions in
`scripts/retrieval_cases.py`:

```bash
uv run python -m scripts.compare_reranking
```

The defaults compare vector search returning 3 chunks with vector search returning
10 candidates followed by reranking down to 3, matching the assistant's current
retrieval settings. Each strategy is warmed once before measurement, then evaluated
three times per question with alternating execution order. Timings include query
embedding and database retrieval, plus cross-encoder inference for the reranked
strategy; model loading and answer generation are excluded.

The output includes Hit@1, Hit@k, MRR@k (zero when no relevant result is in the top k),
mean/median latency, candidate hit rate, and per-question rank changes and excerpts.
Relevance requires both the expected document and a labelled page. An improvement
or regression refers to mean reciprocal rank, not a judgement of the generated answer.

Full JSON reports are saved under `evaluation-results/`, which is ignored by Git
because reports contain PDF passages. They record the questions, all measured runs,
separate retrieval/reranking timings, settings, model names, package versions, and a
fingerprint of the indexed text and vectors. The command rejects missing documents,
duplicate chunk identities, and an index that changes during the run. It does not
modify the index.

Options:

```bash
uv run python -m scripts.compare_reranking --top-k 3 --candidates 10 --repetitions 3
```

`--document` changes the indexed filename of the **same evaluation paper**; it does
not supply labels for a different paper. `--output` chooses a JSON file; existing
files are not overwritten. After experimenting with `compare_chunking`, run
`scripts.index_pdf` again to restore the documented 500/100 configuration before
comparing against these results.

### Measured comparison (2026-09-14)

Local run on macOS arm64, Python 3.14.7, sentence-transformers 6.0.1, and torch 2.14.0:
12 development questions, 3 measured repetitions, 141 chunks (500 characters, 100
overlap), `nomic-embed-text` embeddings, and `BAAI/bge-reranker-base` reranking.

| Strategy | Hit@1 | Hit@3 | MRR@3 | Mean latency | Median latency |
|---|---:|---:|---:|---:|---:|
| Vector top 3 | 0.750 | 0.917 | 0.819 | 32.9 ms | 26.4 ms |
| Retrieve 10, rerank to 3 | 0.750 | 0.917 | 0.819 | 197.9 ms | 194.2 ms |

Reranking added approximately 170 ms of inference per query. One question improved
from rank 3 to 1, one worsened from rank 1 to 3, and ten were unchanged. Candidate
Hit@10 was also 0.917: the missed discussion-summary question had no labelled page
among the candidates, so reranking could not recover it.

These results do not show an aggregate page-level ranking gain on this small
development set. They also do not establish answer quality: for the conclusion
question, the baseline's matching page contained a bibliography passage, while
reranking selected the actual conclusion. Passage-level relevance labels and new
held-out questions are needed before drawing a broader conclusion about reranking.
Latency is specific to this local run. The assistant's retrieval defaults are unchanged.

## Status

Still in development. Initial passage-level and answer-quality evaluation is available.
Next steps include reviewing the reference labels and judge scores, testing more papers,
improving multi-document support, and adding a small frontend.

## Answer-quality evaluation

See the [17 September local evaluation](docs/evaluation-2026-09-17.md) for a completed
20-question run, its configuration, and a manual review of the observed failures.

Run the complete question → retrieval → generation pipeline, then score each answer:

```bash
uv run python -m scripts.evaluate_answers
```

This requires PostgreSQL, Ollama with `nomic-embed-text` and `qwen3:8b`, the reranker
(downloaded on first use if not cached), and the original paper at `data/sample.pdf`.
The paper is *Pre-clinical cancer cachexia causes glucose hypermetabolism prior to
overt weight loss*, DOI `10.1016/j.molmet.2026.102422`. Its SHA-256 must match the
labelled version, and the index must contain only this paper because the
unanswerability labels apply to this corpus.

The 20 cases in `scripts/answer_quality_cases.py` contain 16 answerable questions with
reference answers and evidence quotes, plus four unanswerable questions. They are
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

The default `reranked` strategy uses the assistant's existing top-10 → top-3 pipeline.
The `vector` strategy retrieves the top 3 directly. Both use the same prompt and
answer-generation function. Reference answers and labels go only to the judge.
The FastAPI endpoint continues to use reranking.

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

Semantic scores and abstention classification use schema-constrained JSON from
**the same Qwen model that generated the answer**, at temperature 0 and with
`think: false`. Answer generation retains the model's default thinking behavior.
Ollama supports this switch for Qwen3; see its
[thinking documentation](https://docs.ollama.com/capabilities/thinking).
This judge can
be biased or wrong: inspect the saved explanations and passages. Invalid judge output
fails the run. Correct refusals do not inflate answerable-case quality scores.
Unavailable metric groups in selected-case runs are reported as `null`.
The `abstained` flag describes whether the answer declined to respond, independently
of whether the reference contains an answer. Correctness and completeness separately
penalize refusing an answerable question.

The initial local trial exposed both kinds of failure: a chunk beginning partway
through a percentage led to an incorrect body-mass answer, and the judge credited
another answer with a numerical detail present only in the reference. These examples
are why both the exact-evidence diagnostic and manual review are needed.

Before generating benchmark answers, the judge grades six synthetic examples with
known expectations: a correct answer, a missing number, a contradiction, an
answerable refusal, an unanswerable refusal, and an unsupported claim. The report
records its scores and which checks passed. A failed check stops the run with
`calibration_failed` and no aggregate metrics. Transport or invalid-output errors
produce a `failed` report. Passing this small calibration does **not** establish
judge accuracy or remove the need for human review.

A fresh full run makes 46 model calls (six calibration calls plus 40 benchmark
calls) and can take several minutes. Calibration may warm the local model; there
is no dedicated timing warmup. Answer timing includes retrieval, generation, and
any model loading; judge timing is separate. Generation uses its existing
model-default sampling, so results can vary.
Use the retrieval comparison for warmed latency measurements.

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
match; incompatible or malformed reports are rejected. Model names do not pin
Ollama model weights: keep the installed models unchanged between attempts.
Reports from the old schema (version 1), or older evaluations without recorded
thinking settings, cannot be resumed; start a new run for them. Changing the judge
prompt or thinking settings also requires a fresh evaluation. The 120-second
request timeout is unchanged; disabling judge thinking is not a guarantee against
timeouts on every machine.
`--output PATH` chooses a filename; existing reports are never overwritten.

## Tests

Run the regression tests without Ollama or PostgreSQL:

```bash
uv run python -m unittest discover -s tests -v
```

These tests use SQLite and stubbed extraction, embeddings, and reranking to check
index replacement and rollback, evaluation metrics and cutoffs, timing boundaries,
warmup exclusion, document matching, index validation, and reranker ordering.
Answer-evaluation tests additionally cover evidence labels, strict judge validation,
abstention scoring, reference isolation, report preservation, and both generation paths.

## Type checking

Install development dependencies with `uv sync`, then check all application code,
scripts, tests, and the package entry point:

```bash
uv run mypy
```

Strict checking uses shared typed dictionaries for pages, chunks, answers, and
evaluation cases. Ollama response types describe the expected JSON structure;
the ordinary chat response types do not add runtime validation. The evaluation judge's
JSON output is validated with Pydantic. PyMuPDF's incomplete annotations are skipped,
and missing pgvector stubs are tolerated in the checker configuration.
