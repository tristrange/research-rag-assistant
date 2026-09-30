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

Create local credentials and start PostgreSQL. The private `.env` file is ignored
by Git; source it in each new terminal before running the API or scripts:

```bash
if [ ! -e .env ]; then
  umask 077
  RAG_DB_PASSWORD=$(openssl rand -hex 24)
  printf 'RAG_DB_PASSWORD=%s\nRAG_DATABASE_URL=postgresql+psycopg://rag:%s@localhost:5432/rag\n' \
    "$RAG_DB_PASSWORD" "$RAG_DB_PASSWORD" > .env
fi
set -a
. ./.env
set +a
docker compose up -d
```

For an existing PostgreSQL volume created with the old `rag` password, rotate
the role once after starting the container (a new volume needs no rotation):

```bash
docker compose exec -T db psql -U rag -d rag <<SQL
ALTER ROLE rag WITH PASSWORD '${RAG_DB_PASSWORD}';
SQL
```

Compose now publishes PostgreSQL only on `127.0.0.1`. The application is still
intended for local use; do not expose its API or Ollama to other devices without
adding authentication and deployment-specific access controls.

Initialize the database:

```bash
uv run python -m scripts.init_db
```

Pull the local models:

```bash
ollama pull gpt-oss:20b
ollama pull qwen3:8b
ollama pull nomic-embed-text
```

Place your PDFs under `data/` and index each by path:

```bash
uv run python -m scripts.index_pdf data/my-paper.pdf
```

Omitting the path retains the `data/sample.pdf` development example. Local PDFs
are ignored by Git. The [corpus notes](docs/benchmark-corpus.md) record attribution,
licenses, historical PDF copies and an Emma Frank coauthored benchmark.

Section recognition supports standalone numbered publisher headings such as
`2 | Materials and Methods`, including PDF whitespace. Reindex affected PDFs to
replace previously stored section labels; no schema migration is needed. The
[evaluator and section regression report](docs/section-refusal-regressions.md)
records validation against the housing-temperature paper.

Documents are currently identified by filename. Reindexing replaces only that
filename's chunks, including removing stale chunks if the PDF becomes shorter or
has no extractable text. Extraction, embedding, or database failures preserve the
previous index. Use distinct filenames for distinct papers.

List the indexed filenames before choosing a paper:

```bash
curl http://127.0.0.1:8000/documents | jq
```

Pass one of those exact filenames as `document` to restrict retrieval and
citations to that paper:

```bash
curl -X POST http://127.0.0.1:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question":"What were the main findings?","document":"my-paper.pdf"}' \
  | jq
```

Omitting `document` keeps corpus-wide retrieval of the top matching passages;
it does not guarantee coverage of every indexed paper. For a findings overview
of **each** indexed paper, use `scope: "each"` without `document`:

```bash
curl -X POST http://127.0.0.1:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question":"What were the main findings?","scope":"each"}' \
  | jq
```

This overview mode retrieves passages from each paper independently, preferring its
conclusion, then abstract, discussion, and results sections, with a document-wide
fallback when those section labels are unavailable. It runs a separate
answer call per paper and can take several minutes, especially in verified mode.
Each answer is labelled with its paper. It is still based on selected passages,
not a complete reading of every PDF. An insufficient-evidence answer means the
retrieved passages did not establish the requested finding, not that the paper
has none.

For a specific question, such as a method or protocol, use `scope: "each_query"`.
It still answers separately for every indexed paper, but searches each complete
paper for passages relevant to the question instead of prioritizing summaries:

```bash
curl -X POST http://127.0.0.1:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question":"How was glucose tolerance measured?","scope":"each_query"}' \
  | jq
```

An unknown filename yields an insufficient-evidence answer with no sources; an
empty or path-like filename is rejected. Document identity is still the basename, so two PDFs with the same
filename cannot be indexed separately, even if they live in different folders.

Chunking prefers sentence boundaries and falls back to whitespace for long
sentences. It keeps the original page text and metadata, with a hard character
limit; exceptionally long tokens may still be split. Overlap is adjusted to
boundaries rather than being an exact number of characters. This reduces partial
numbers and detached sentence fragments, but does not guarantee correct retrieval
or answers. Sentence detection is a lightweight punctuation heuristic, not a full
parser for scientific prose.

Indexing rejects PDFs with more than 500 pages, 100,000 extracted characters on
one page, 2,000,000 extracted characters in total, or 10,000 chunks. These limits keep an
unusual PDF from monopolizing local processing; a rejected import leaves the
existing index unchanged.

After updating the chunker, rerun `uv run python -m scripts.index_pdf` to replace
the stored chunks and embeddings. Existing indexes do not change automatically.
Then rerun the retrieval and answer evaluations below; older reports describe the
old chunk boundaries and should not be treated as measurements of the new index.

Section metadata is recognized from standalone headings during chunking and carried
across pages. Chunks and expanded windows do not cross recognized section boundaries.
Sources expose a `section` field; unrecognized sections are `unknown`. These labels
are hints: discussion/results passages may still cite other studies, and PDF reading
order or unconventional headings can prevent reliable classification. References
remain retrievable for questions explicitly about cited literature.

After upgrading an existing database, run both commands in order:

```bash
uv run python -m scripts.init_db
uv run python -m scripts.index_pdf
```

Initialization adds the section column idempotently and marks existing rows `unknown`.
Reindexing replaces them with section-aware chunks and embeddings. The answer prompt
requires evidence of attribution to the current study, but cannot guarantee that the
model follows it. See the [attribution evaluation](docs/source-attribution-evaluation.md).

Start the API:

```bash
uv run uvicorn app.main:app --host 127.0.0.1 --reload --reload-dir app
```

Open [http://127.0.0.1:8000/](http://127.0.0.1:8000/) for the browser interface.
It lists the indexed PDFs, lets you search one paper, top matches across the
library, or every paper separately in overview or targeted-search mode. It uses
experimental verified answers. Page references that match a returned
source link to its retrieved passages, grouped by document and page. These links
help with inspection but do not verify a claim. The passages below an answer are
the retrieved context; they are not necessarily passages the answer cited. The
page uses the same `/documents` and `/query` endpoints as the command-line
examples below, and needs no separate frontend install or build step.

## Local security boundary

PDF text is untrusted. A paper can contain instructions directed at an assistant;
if retrieved, those instructions may influence a generated answer. The browser and
`/query` endpoint use verified answers only: they require source-specific quotes
and a separate claim check. This cannot prove that a PDF is authentic or make
prompt injection impossible. Review a PDF and its provenance before indexing it,
and inspect cited passages before relying on an answer. The plain generator remains
available only to local evaluation scripts for comparisons, not through the API.

The API accepts questions up to 2,000 characters and runs one query at a time;
an overlapping query receives HTTP 429. The app rejects non-loopback clients and
unexpected Host headers, including a basic DNS-rebinding route into localhost.
It has no user authentication, so keep Uvicorn, PostgreSQL, and Ollama on loopback.
If you later want access from other devices, add authentication and per-client
limits before changing this boundary. A local reverse proxy can make a remote
client appear to be on loopback, so the application check is not authentication.
The browser inserts model and PDF text as text, not HTML.
The `/docs` page is served locally without third-party scripts and links to the
current OpenAPI schema at `/openapi.json`.

Run the synthetic prompt-injection probe against your installed Ollama models:

```bash
uv run python -m scripts.check_prompt_injection
uv run python -m scripts.check_prompt_injection --mode plain
```

The probe tests one attack pattern, not all possible injections. A failing plain
probe demonstrates why the API does not offer plain mode.

## Local model settings

Set these environment variables before starting the API or evaluation process:

| Variable | Default | Role |
|---|---|---|
| `RAG_GENERATOR_MODEL` | `qwen3:8b` | Plain generation in local evaluation scripts |
| `RAG_GROUNDING_MODEL` | `gpt-oss:20b` | Verified drafting and verification |
| `RAG_JUDGE_MODEL` | `qwen3:8b` | Evaluation and judge calibration |
| `RAG_DRAFT_THINK` | `true` for Qwen3/Qwen3.5; otherwise `low` | Verified draft reasoning |
| `RAG_VERIFIER_THINK` | `true` for Qwen3/Qwen3.5; otherwise `medium` | Verified reasoning |
| `RAG_GROUNDING_SAMPLING` | `{}` (automatic profile below) | JSON sampling overrides shared by verified drafting, repair and verification |
| `RAG_GROUNDING_TIMEOUT_SECONDS` | 120 without explicit thinking; 300 with thinking | Per-call HTTP timeout override, greater than 0 and at most 600 seconds |
| `RAG_GROUNDING_OUTPUT_TOKENS` | `4096` | Per-call output budget, including reasoning; 1–8192 tokens |
| `RAG_DB_PASSWORD` | Required by Compose | Local PostgreSQL password |
| `RAG_DATABASE_URL` | No usable password by default; set via private `.env` | Index connection |

The API uses `RAG_GROUNDING_MODEL`; local plain-mode evaluation uses
`RAG_GENERATOR_MODEL` independently.
Reasoning values accept `true`, `false`, `low`, `medium`, or `high`; choose values
supported by the selected model. These settings do not change the embedding model
or require reindexing. Models must already be installed in Ollama; there is no
automatic download or fallback. Blank settings fail at startup. Restart the process
after changing settings. Model comparisons should keep the judge fixed and inspect
actual evidence, not rely only on aggregate model grades.

With Qwen3 or Qwen3.5, thinking flags must be Boolean. If either stage thinks,
the shared sampling profile uses temperature 0.6 for Qwen3 or 1.0 for Qwen3.5,
top_p 0.95, top_k 20, min_p 0, repeat_penalty 1, and presence_penalty 0 for
Qwen3 or 1.5 for Qwen3.5. These follow their general-thinking guidance.
When both stages disable thinking, temperature stays at the previously tested
zero baseline. GPT-OSS uses temperature 1.0 and top_p 1.0, following its
[recommended sampling](https://github.com/openai/gpt-oss#recommended-sampling-parameters).
Other grounding models retain temperature zero. Selecting Qwen
alone enables its thinking profile; use both `THINK=false` variables for the
faster non-thinking configuration.

Sampling accepts numeric `temperature` (0–2), `top_p` (greater than 0, at most 1),
integer `top_k` (1–1000), `min_p` (0–1), `presence_penalty` (0–2), and
`repeat_penalty` (greater than 0, at most 2). Explicit values override the selected
profile; omitted values inherit it, including when the JSON is `{}` or specifies
only a filter. Filters omitted from the selected profile retain the installed
model's defaults. Explicit temperature zero is available for controlled
experiments; it overrides the recommended Qwen thinking and GPT-OSS profiles. Unknown keys, invalid
types, non-finite numbers, and out-of-range values fail at startup.
These overrides affect verified calls only; the evaluation judge stays at
temperature zero with thinking disabled. Context remains 12,288 tokens.
For tested settings, commands, and limitations, see the
[inference-settings follow-up](docs/ollama-inference-settings.md).

## Verified answer mode (experimental)

The API's verified mode is experimental. In the latest 24-question development run it
answered 17 of 18 answerable questions and correctly refused all six unanswerable
questions. One answerable question still received a false refusal. These results
come from one paper used during development; they are not a reliability guarantee.
See the [evaluation report](docs/verified-claims-evaluation.md) for the full results
and the retained failures from earlier versions. Plain remains available only to
local evaluation scripts.

Omit `answer_mode` to use claim-level grounding, or set it explicitly to `verified`:

```bash
curl -X POST http://127.0.0.1:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question":"What did the cited study report?","answer_mode":"verified"}'
```

The model drafts concise claims and selects exact excerpts from a source-specific
quote catalogue. Code rejects invalid IDs, quotes outside that catalogue, and current-study claims citing a references section.
A second model call checks each claim's full support, attribution, and relevance.
It must assess the full original question separately from its list of essential
requested findings and qualifiers. Supported checks and claim verdicts
must reference application-owned exact excerpts from their cited passages. Code
validates question excerpts, evidence IDs, and claim ownership before accepting the
answer. Unasked study attributes are not required. A supported negative answer
can satisfy a yes/no question; missing outcome evidence cannot establish a
negative result.
A rejected draft may be corrected once using validation feedback; the corrected
draft must pass all the same checks. Only an entirely approved answer is rendered; document/page labels come from stored
source metadata. Invalid or rejected output becomes a fixed insufficient-evidence
response. Model connection errors still propagate as errors, not evidence refusals.

The response shape remains `answer` and `sources`; sources are the retrieved bundle,
not a list filtered to cited passages. Quote matches establish textual presence, not
semantic support, and the same local model acts as drafter and verifier. This mode
can reject valid answers or miss subtle unsupported claims. The API and browser
use `verified`; `answer_mode: "plain"` is rejected by the API. Local evaluation
scripts retain plain generation for controlled comparisons. Neighbor expansion
also remains opt-in through the evaluation CLI. The
[question coverage contract](docs/question-coverage-evidence.md) explains the fixed
whole-question and exact-evidence checks, control results, and their limits. The
[refusal diagnostics](docs/grounding-refusal-diagnostics.md) distinguish initial
draft refusals from verifier errors and record the targeted checks.
The [v21 local-model comparison](docs/verified-model-comparison-v21.md) compares
Qwen3, Qwen3.5 and GPT-OSS on the same 16 saved question-and-passage bundles.
It records citation audits, control failures and remaining evidence gaps;
these development results do not change the default model or complete human review.

```bash
uv run python -m scripts.check_grounding --output evaluation-results/grounding-controls.json
uv run python -m scripts.evaluate_answers --strategy expanded --answer-mode verified
```

Use `--case CONTROL_ID` (repeatable) with `scripts.check_grounding` to rerun
specific verifier controls; each run needs a fresh output path. The
[Activin follow-up](docs/activin-vector-reserve-validation.md#fixed-source-follow-up-2026-09-27)
records paired controls for a population qualifier in a two-duration answer.

Verified mode uses `gpt-oss:20b` with low reasoning for drafting, medium reasoning
for verification, temperature 1.0 and top_p 1.0. Install it with `ollama pull gpt-oss:20b` before trying this
mode. Plain evaluation and the evaluation judge continue to use `qwen3:8b`.
Verified requests default to a 12,288-token context window, a 4,096-token output limit
(including reasoning), and a 300-second timeout per call. Evaluation records the answer mode, sampling overrides, effective per-stage timeouts, both
model configurations, and the grounding prompt/schema contract fingerprint. Resume
requires matching settings; older reports require a fresh run. See the
[verified-claims evaluation](docs/verified-claims-evaluation.md) for observed results
and limitations.

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
files are not overwritten. If you change the chunking configuration, reindex the
paper before comparing against these results.

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

The local assistant has verified answering, passage-level and answer-quality
evaluation, and a browser interface for one-paper or library-wide questions.
The [local v1 readiness plan](docs/v1-readiness.md) defines the remaining quality,
evidence-display, usability, and release milestones. Its first step is a bounded
human review of 16 development cases; preparing the packet does not complete
that review or approve a release.

## Answer-quality evaluation

The [first comparison on the second paper](docs/housing-model-comparison.md)
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

See [corpus acquisition and evaluation protocol](docs/benchmark-corpus.md) for the
license, download, isolated database setup and evaluation-set lifecycle. `--validate-only`
checks the PDF and labels without calling models or accessing the database. Remove
that flag to run an evaluation against an index containing only the selected paper.


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
[development evaluation](docs/vector-reserve-evaluation.md)
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

The [evidence-coverage comparison](docs/retrieval-evidence-coverage.md) traces a
reranking miss and compares three versus six seeds across both development papers.
The subsequent [verified-answer comparison](docs/verified-context-comparison.md)
completed 68 answers: wider context recovered some answers but introduced a
cited-study refusal and higher latency, so expansion remains opt-in.
The [third-paper unexpanded verified evaluation](docs/unexpanded-verified-third-paper.md)
used a separate CC BY paper and the normal three-passage retrieval path. It
answered seven of eight answerable questions and refused both unanswerable ones;
one false refusal came from missing complementary retrieved evidence. The small,
assistant-labelled set is provisional and does not change the API defaults.
The retrieval-only runner reproduces the coverage check without generating answers:

```bash
uv run python -m scripts.compare_evidence_coverage \
  --output evaluation-results/coverage-sample.json
```

The default `reranked` strategy uses the assistant's existing top-10 → top-3 pipeline.
The `vector` strategy retrieves the top 3 directly. Both use the same prompt and
answer-generation function. Reference answers and labels go only to the judge.
The FastAPI endpoint continues to use reranking without expansion. Expansion stays
opt-in because the previous trial improved retrieval but introduced an unsupported
drug-treatment answer. See the [neighboring-context evaluation](docs/neighbor-context-evaluation.md)
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
match; incompatible or malformed reports are rejected. Model names do not pin
Ollama model weights: keep the installed models unchanged between attempts.
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

## Tests

Run the regression tests without Ollama or PostgreSQL:

```bash
uv run python -m unittest discover -s tests -v
```

If Node.js is installed, check the browser answer and source rendering separately:

```bash
node --test tests/test_ui_rendering.js
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
