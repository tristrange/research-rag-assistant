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

Index it:

```bash
uv run python -m scripts.index_pdf
```

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

Current best configuration:

- chunk size: `500`
- overlap: `100`
- top-k: `3`

Results:

| Metric | Score |
|---|---:|
| Recall@1 | 0.75 |
| Recall@3 | 0.92 |
| Recall@5 | 0.92 |
| MRR | 0.82 |

## Status

Still in development. Next steps include evaluating reranking, improving multi-document support, and adding a small frontend.
