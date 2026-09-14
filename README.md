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

Still in development. Next steps include passage-level and answer-quality evaluation,
improving multi-document support, and adding a small frontend.

## Tests

Run the regression tests without Ollama or PostgreSQL:

```bash
uv run python -m unittest discover -s tests -v
```

These tests use SQLite and stubbed extraction, embeddings, and reranking to check
index replacement and rollback, evaluation metrics and cutoffs, timing boundaries,
warmup exclusion, document matching, index validation, and reranker ordering.

## Type checking

Install development dependencies with `uv sync`, then check all application code,
scripts, tests, and the package entry point:

```bash
uv run mypy
```

Strict checking uses shared typed dictionaries for pages, chunks, answers, and
evaluation cases. Ollama response types describe the expected JSON structure;
they do not add runtime validation. PyMuPDF's incomplete annotations are skipped,
and missing pgvector stubs are tolerated in the checker configuration.
