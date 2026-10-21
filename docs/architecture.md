# Local architecture

The supported local product is a FastAPI application, a PostgreSQL/pgvector
index, and Ollama on one machine. FastAPI serves the browser files directly;
there is no frontend build or separate browser server. The normal API path uses
verified answering. Evaluation and internal plain-generation paths are separate.

```mermaid
flowchart LR
    PDF["Local PDF"] --> Extract["PyMuPDF: text + page numbers"]
    Extract --> Chunk["Sentence-aware chunks + section metadata"]
    Chunk --> ChunkEmbed["Chunk embeddings: Ollama nomic-embed-text"]
    ChunkEmbed --> Store["Atomic filename replacement"]
    Store --> DB[("PostgreSQL + pgvector")]

    UI["Browser: question + search scope"] --> API["FastAPI: POST /query"]
    API --> QueryEmbed["Question embedding: Ollama nomic-embed-text"]
    QueryEmbed --> Search["Read-only cosine search"]
    Search -->|read| DB
    DB --> Rank["Local BGE cross-encoder reranker"]
    Rank --> Ground["Ollama: draft + evidence verification"]
    Ground --> Result["Answer or refusal + sources + claim evidence"]
    Result --> API
    API --> UI
```

Both embedding nodes use the same embedding model and validation contract.
Ingestion calls `embed_texts()` for batches; a request-owned `QuestionEmbedding`
calls `embed_text()` once and reuses its vector across searches. Only ingestion
proceeds to index replacement; asking a question reads the stored chunks without
changing the corpus.

## Ingestion and stored data

[`app.ingestion.indexing`](../app/ingestion/indexing.py) owns extraction, chunking,
embedding and atomic replacement. [`scripts.index_pdf`](../scripts/index_pdf.py)
handles terminal arguments, progress output and error messages, and delegates to
the shared application function. The workflow extracts text with PyMuPDF and
retains the PDF's one-based page number. The chunker preserves document, page,
chunk index and recognized section. Its normal target is 500 characters with
100-character overlap, preferring sentence and whitespace boundaries. It does
not perform OCR; scanned PDFs without text are outside local v1.

Chunks are embedded with `nomic-embed-text` in batches of at most 16, using one
HTTP client owned and closed by the indexing operation. The provider validates
the exact response count and every finite 768-value vector before returning a
batch; input order pairs each vector with its chunk. No parallel inference or
automatic retry is introduced. Question embedding keeps the single-text API.
PostgreSQL stores each chunk's text,
metadata and 768-dimensional vector in the `chunks` table. Extraction, chunking
and all embeddings finish before a transaction replaces only rows for that
exact filename. A failed embedding or save preserves the old index. A PDF with
no extractable chunks removes that filename's old rows. Distinct papers need
distinct filenames. Changing extraction, chunking or embeddings requires
reindexing before evaluating the new corpus.

`document_indexes` records each saved PDF checksum and its extraction, chunking
and embedding profile in the same transaction as its chunks. Legacy rows retain
unknown provenance until reindexed. Retrieval checks the selected scope against
the current embedding model name/dimensions before inference, then again under
a shared PostgreSQL transaction advisory lock before vector ranking. Replacements
and removals take the exclusive lock; inference holds no index lock. A unique
index enforces each document/page/chunk location. See the README for migration
recovery and the limits of name-based embedding compatibility.

The CLI reports real stages and completed embedding counts. `Indexed …` follows
the successful commit; completing embeddings alone does not establish a saved
index. PDFs remain local and are ignored by Git.

## Retrieval and answering

[`app.rag`](../app/rag.py) embeds the question, uses pgvector cosine distance to
retrieve vector candidates, then reranks them with the locally loaded
`BAAI/bge-reranker-base` cross-encoder. Normal verified targeted searches retrieve
twenty candidates and retain five reranked passages plus the highest vector-ranked
passage from a document/page absent from those five, within the six-source limit
and without neighbor expansion. If no new page is available, use the highest
vector-ranked unselected passage. This preserves a second selection signal for
cohort and timing details.
With an explicit cutoff, one slot is reserved within that cutoff; a one-source
cutoff or a candidate pool no larger than the cutoff uses ordinary reranking.
Plain answering, vector-only retrieval,
overviews and the opt-in vector-reserve strategy retain their three-passage
defaults. Other reranked paths still retrieve ten candidates. See the
[qualifier retrieval follow-up](qualifier-retrieval.md) for development checks
and limitations.
Each request owns one lazy question embedding, reused across overview section
probes and each-paper searches. Document/section filters, candidate limits and
cosine ordering still run independently for each search. Every search rechecks
index compatibility, including when the vector is already available. The vector
is discarded with the request; identical later questions are embedded again.

The reranker downloads weights from Hugging Face on first use and caches them;
an installed Ollama model does not include the reranker weights.

| Browser scope | Retrieval behavior |
| --- | --- |
| One filename | Search only that paper. |
| Across papers | Retrieve top matches from the library; not every paper is guaranteed to appear. |
| Each paper, targeted search | Retrieve and answer separately for every indexed filename. |
| Each paper, overview | Per paper, try conclusion, abstract, discussion, then results sections; fall back to ordinary search if none has candidates. Merge selected overlapping context. |

Each-paper answering is sequential and can take longer. It labels separate
answers by filename and remaps accepted citation indexes into the combined
source list. Neighbor expansion and the experimental strategy that appends an
extra vector candidate remain opt-in; normal verified targeted searches instead
reserve a vector slot inside their source limit.

[`app.grounding`](../app/grounding.py) asks the configured grounding model for a
structured draft with claims, attribution and citations. The default is
`gpt-oss:20b`: first-draft reasoning low, repair and verification reasoning medium.
Repair reuses the configured verifier reasoning and timeout profile. Runtime
validation checks schema and source references. Draft and repair citations select
only source IDs; the application constructs exact evidence excerpts from those
passages. A separate model call selects excerpt IDs and checks claim support,
attribution and coverage of the whole question. The final excerpts also undergo
an isolated full-question proof check. Rendered locations and public claim
evidence include only the approved selections, not unused draft sources. See
[source selection](draft-source-selection.md) for the contract and development check. A
deterministic [duration check](duration-evidence.md) also compares explicit
numeric durations with each claim's verifier-selected quotes. Missing duration
support rejects the claim even when the model approves it. A
rejected draft has at most one repair attempt followed by another check. A
failed evidence check produces the standard insufficient-evidence refusal.
Transport failures, timeouts and output exhaustion are service errors rather
than evidence refusals. [`app.config`](../app/config.py) resolves one immutable
`SETTINGS` snapshot at startup, including model profiles, sampling and per-stage
timeouts. Database, embedding/chat adapters, grounding and diagnostics derive
their settings from it. Compatibility exports preserve evaluation/report imports;
reloading environment variables requires restarting the application.

“Verified” describes these software/model checks, not independent factual truth.
The verifier can miss an unsupported claim or reject a correct answer. It does
not compare runtime questions to stored benchmark answers. Qwen3 8B's evaluation
judge runs in offline evaluation scripts, not in the normal verified query path.

The response contains `answer`, `sources` and `claim_evidence`. The additive
`outcome` field records verified answering or insufficient evidence; each-paper
responses report `partial` when only some
papers were answered. Plain generation with retrieved context leaves the
outcome unknown. The browser uses this field for readiness and retry guidance,
without classifying model prose or claiming independent answer quality.
`sources` is all retrieved context. `claim_evidence` contains only final accepted
claims with
their attribution and verifier-selected excerpts; citation indexes refer to
`sources`. Refusals expose no accepted claim evidence. Browser page links open
the matching retrieved context; inspect that context and the original PDF.

## Grounding module contract

[`app.grounding`](../app/grounding.py) is one module today, but it carries five
separate responsibilities: Pydantic contracts, prompt construction, semantic and
structural validation, evidence selection, and orchestration. The extraction
follow-up splits those into `grounding_models`, `grounding_prompts`,
`grounding_validation` and `grounding_evidence`, leaving `app.grounding` as the
facade and orchestrator. The contract below is what that split must preserve.

**Public entry points and exports.** These names stay importable from
`app.grounding`, so evaluation scripts and the query path do not change:

| Caller | Imports | Role |
| --- | --- | --- |
| [`app.rag`](../app/rag.py) | `INSUFFICIENT_EVIDENCE`, `grounded_answer` | request path, each-paper aggregation |
| [`app.answer_evaluation`](../app/answer_evaluation.py) | `INSUFFICIENT_EVIDENCE` | refusal classification |
| [`scripts.check_grounding`](../scripts/check_grounding.py) | constants, models, `build_verifier_evidence`, `generate_verification_json`, `validate_verification_structure`, `verify_draft`, `grounding_fingerprint` | live adversarial checks |
| [`scripts.evaluate_answers`](../scripts/evaluate_answers.py) | stage constants, `grounding_fingerprint` | evaluation run records |
| [`scripts.replay_grounding`](../scripts/replay_grounding.py) | `GROUNDING_MODEL`, `grounded_answer` | replay trials |
| [`scripts.check_prompt_injection`](../scripts/check_prompt_injection.py) | `grounded_answer` | prompt-injection probes |

`grounded_answer(question, sources, *, trace=None, claim_evidence=None) -> str`
is the only answering entry point. It returns the rendered answer or
`INSUFFICIENT_EVIDENCE`; it never returns partial claims. It clears and fills
`claim_evidence` in place with approved claims only, and appends stage records to
`trace` when given. Transport failures, timeouts and output exhaustion propagate
as service errors; malformed or rejected model content becomes a refusal after
at most one repair attempt.

```text
grounded_answer
├── _bounded_draft_schema
├── generate_draft_json ──────────────► app.llm.generate_json (draft profile)
├── GroundedDraft.model_validate
├── _verify_draft_with_feedback
│   ├── _validate_draft
│   ├── build_verifier_evidence
│   ├── build_verifier_prompt ────────► _bounded_verifier_schema
│   ├── generate_verification_json ───► app.llm.generate_json (verifier profile)
│   ├── VerificationResult.model_validate
│   ├── _validate_verification ───────► validate_verification_structure
│   │   ├── _validate_question_identifiers
│   │   └── grounding_durations.validate_duration_evidence
│   ├── _record_accepted_evidence
│   └── generate_approved_proof_json ─► ApprovedProof
├── _record_accepted_evidence
└── _render_claims
```

**Frozen behaviour.** `GROUNDING_CONTRACT_VERSION` (`claim-grounding-v41`), the
prompt bytes built from equivalent inputs, the serialized response and claim
evidence shape, the refusal text and the exception classes above are the
contract. The stage fingerprint from `grounding_fingerprint()` binds evaluation
resumes to these definitions.

[`tests/test_grounding_contracts.py`](../tests/test_grounding_contracts.py)
replays synthetic, license-safe cases from
`tests/fixtures/grounding_contracts/cases.json` against this contract: supported
positive and negative answers, missing-evidence refusal, malformed verifier JSON,
unknown source IDs, a reference entry claimed as this document's own work, a
claimed duration absent from approved evidence, verifier evidence outside the
cited sources, and output-limit propagation. Each real model call's prompt and
schema are pinned by SHA-256 digest at the single `generate_json` boundary in
`tests/fixtures/grounding_contracts/call_digests.json`, including the generated
proof prompt, so editing a prompt, its schema, or the stage wiring fails the
suite. Refusal answers are asserted as literal text rather than through the
exported constant, so rewording a refusal fails it too. Existing unit tests keep
the per-stage detail and multi-paper citation remapping.

## Maintenance and boundaries

[`scripts.manage_library`](../scripts/manage_library.py) lists filenames and
stored chunk/distinct-indexed-page counts. Removal previews by default and needs
`--yes` to apply an exact-filename transaction. It preserves original PDFs. The
browser's **Refresh papers** rebuilds its selection list after index changes.

`GET /status` checks database/schema access, Ollama connectivity and installed
answer/embedding model tags. It performs no inference, indexing, downloads or
paper-text reads. It does not check the reranker cache or prove that a question
will succeed. Question progress is elapsed browser wait time, not backend stage
reporting or an estimated finish time.

FastAPI enforces loopback clients and local Host headers. PostgreSQL's Compose
port is bound to loopback, and its password comes from the ignored private
`.env`, loaded before starting scripts or the API. Ollama also remains local.
There are no accounts or permissions for multiple users; public deployment is
deferred. One API-process lock rejects overlapping queries with HTTP 429. It is
not a shared lock across multiple worker processes.

PDFs, questions and model output are untrusted data. Prompts distinguish source
content from instructions, structured output and quote checks constrain answers,
and the browser inserts excerpts as text. These defenses do not guarantee that
prompt injection or semantic verification errors are impossible. The model has
no application tools to execute commands or mutate the library. Credentials
are not included in prompts. See the [local security boundary](local-usage.md#local-security-boundary).

Regression CI covers local logic with stubs and SQLite. The
[fresh-install smoke test](install-smoke-test.md) additionally checks live
database/model/browser wiring. Neither substitutes for the deferred human
review and reserved final quality checks in [v1 readiness](v1-readiness.md).
