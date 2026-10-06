# Local usage

Follow the [quickstart](../README.md#quickstart) first. Run commands from the
repository root after loading your private `.env`:

```bash
set -a
. ./.env
set +a
```

## Library management

```bash
uv run python -m scripts.index_pdf data/my-paper.pdf
uv run python -m scripts.manage_library list
uv run python -m scripts.manage_library provenance my-paper.pdf
```

Indexing identifies documents by filename. Use distinct filenames for distinct
papers and quote paths containing spaces. Reindexing replaces that filename's
chunks and provenance atomically; failures preserve its previous index. A PDF
with no extractable text removes its old chunks. The CLI prints `Indexed …` only
after saving commits, not merely when embeddings finish.

The provenance command shows the indexed PDF checksum, embedding model and
dimensions, extraction versions and chunk settings. Compatibility checks use
embedding model names and dimensions, not weight digests. Reindex if you replace
embedding weights under the same name. Queries do not reread the source PDF to
detect edits; reindex after changing a PDF, extraction or chunking. Changing only
the answer model does not require reindexing.

List counts describe stored chunks and pages with chunks, not all PDF pages.
PDF imports are limited to 500 pages, 100,000 extracted characters per page,
2,000,000 total characters and 10,000 chunks.

Preview removal, then explicitly apply it:

```bash
uv run python -m scripts.manage_library remove my-paper.pdf
uv run python -m scripts.manage_library remove my-paper.pdf --yes
```

Removal takes an exact filename, not a path or wildcard. It preserves the
original PDF and other indexed papers. Click **Refresh papers** in the browser
after adding, replacing or removing papers. Replacing the corpus also changes
evaluation inputs; preserve earlier reports and use fresh ones.

## Search scopes and API

FastAPI serves the UI directly. Open `/docs` for local API documentation and
`/openapi.json` for the schema. The API exposes verified answering only;
`answer_mode: "plain"` is rejected.

| Browser scope | Query fields | Behavior |
| --- | --- | --- |
| Across papers (top matches) | `scope: "relevant"` (default), no document | Retrieves top matches; may omit papers. |
| One selected paper | `document: "my-paper.pdf"` | Searches only that exact indexed filename. |
| Each paper (overview) | `scope: "each"`, no document | Answers separately, preferring conclusion, abstract, discussion and results sections. |
| Each paper (targeted search) | `scope: "each_query"`, no document | Answers separately using question-matched passages from each paper. |

Each-paper scopes can take several minutes. Overview falls back to document-wide
retrieval if preferred sections are unavailable. Section labels are extraction
hints; a results or discussion passage may still describe cited literature.

With the API running, list filenames and ask a focused question:

```bash
curl http://127.0.0.1:8000/documents
curl -X POST http://127.0.0.1:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question":"What methods were used in the study?","document":"my-paper.pdf"}'
```

For a library overview:

```bash
curl -X POST http://127.0.0.1:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question":"What were the main findings?","scope":"each"}'
```

An unknown filename yields an insufficient-evidence response with no sources;
empty or path-like filenames are rejected. Each-paper scopes cannot also select
one document.

## Reading a response

`answer` is the displayed answer or refusal. `sources` contains **all retrieved
passages**, including passages that may not support an accepted claim.
`claim_evidence` contains the final accepted claims, attribution and exact excerpts
selected by the verifier. Each citation's zero-based `source_index` refers to
`sources`; `quote` retains catalogue whitespace normalization. Refused answers
contain no accepted claim evidence.

Expand **Evidence used for this answer** in the browser, then follow its page link
to the matching retrieved passage. Inspect the original PDF too. A page link or
matching quote does not establish factual correctness or semantic support.

`outcome` describes the response: `answered`, `insufficient_evidence`, or `partial`
when some papers were answered and others refused. Older/internal plain results
may have no outcome. An insufficient-evidence response can reflect a retrieval
gap; it does not show that the paper lacks a result. Service errors are failed
requests and return no answer. The browser timer measures elapsed wait time,
not a backend stage or estimated completion.

## Troubleshooting

The page checks services on load; use **Check services** to repeat the check:

```bash
curl http://127.0.0.1:8000/status
```

This read-only endpoint always returns HTTP 200 with `available` and individual
`checks`. It probes database/schema access, Ollama connectivity and installed
answer/embedding model tags. It does not run inference, inspect paper contents,
check the reranker cache or establish sufficient memory or answer quality.
If paper loading failed, click **Refresh papers** after fixing the dependency.

Service errors use `{"detail":{"code":"…","message":"…"}}` and omit SQL,
credentials, exception text and upstream response bodies. Failed requests release
the query lock so you can retry.

| HTTP status | Error code | Next action |
| --- | --- | --- |
| 409 | `index_incompatible` | Run `scripts.init_db`, then reindex selected PDFs with `scripts.index_pdf <PDF path>`. |
| 503 | `database_error` | Start PostgreSQL, load `.env`, and run `uv run python -m scripts.init_db`. |
| 503 | `model_unavailable` | Open Ollama or run `ollama serve`. |
| 503 | `model_not_found` | Check `RAG_GROUNDING_MODEL` and install it with `ollama pull`. |
| 503 | `embedding_model_not_found` | Run `ollama pull nomic-embed-text`. |
| 504 | `model_timeout` | Narrow the question; see [timeouts](configuration.md). Embedding timeouts do not use the grounding timeout setting. |
| 502 | `model_output_limit` | Narrow the question or review `RAG_GROUNDING_OUTPUT_TOKENS`. |
| 502 | `model_service_error` / `model_invalid_response` | Check Ollama logs, model compatibility and available memory, then retry. |
| 503 | `dependency_error` | Check other dependency requests, including model downloads. |
| 429 | Another query is running | Wait for that question to finish, then retry. |

**Address already in use:** stop the server you started in its terminal with
Ctrl+C, or choose an unused API port with `--port 8001` and open that address.
For a database port conflict, inspect the existing database rather than starting
another on port 5432. An existing Docker volume retains its database credentials;
creating a new `.env` does not change them. Keep the matching private credentials
or use a separate database/port for experiments. Preserve personal volumes.

## Local security boundary

The unauthenticated app targets one user on one machine. Keep Uvicorn, PostgreSQL
and Ollama on loopback. The API rejects non-loopback clients and unexpected Host
headers; a reverse proxy can hide a remote client's address, so this is not user
authentication. Public hosting needs separate access controls and is outside local v1.

Questions are limited to 2,000 characters. One API-process lock rejects concurrent
questions; it is not a shared lock across multiple worker processes. Model/PDF text
is inserted as text in the browser, and the local API docs load no third-party scripts.

PDF text is untrusted and may contain prompt-injection attempts. Structured
claims, exact quote validation and model verification constrain answers but cannot
guarantee safety or correctness. The model has no application tools to execute
commands or mutate the library. Review PDF provenance and inspect supporting text.
See [architecture](architecture.md) and the [synthetic probe](development.md#grounding-and-injection-controls).
