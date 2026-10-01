# Fresh-install checks

Local v1 targets macOS with Apple Silicon. Run the installation and regression
checks in a fresh clone with no `.venv`, `.env`, PDFs or evaluation reports.
Dependency installation needs internet access. These checks use synthetic text,
SQLite and stubbed models; they never index or remove a real paper.

## Installation and service-independent regressions

With uv and Node.js 24 installed, clone the candidate branch into a new directory,
then run from its root:

```bash
uv python install
uv sync --locked
RAG_DATABASE_URL='sqlite:///:memory:' HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  uv run --locked python -m unittest discover -s tests -v
node --test tests/test_ui_rendering.js
uv run --locked mypy
git diff --exit-code -- pyproject.toml uv.lock
```

The lockfile check must pass without rewriting dependencies. The Python tests
exercise imports of the complete FastAPI application, its loopback-only browser
and API routes, synthetic PDF extraction, SQLite indexing/replacement/rollback,
and stubbed retrieval and verification. Node tests check browser behavior without
a browser build step. Model weights and external database services are not used.

The `Regression checks` workflow repeats these checks for every pull request and
`main` push, with Python from `.python-version`, pinned uv, Node.js 24 and actions
pinned to commit hashes. Its macOS runner matches the supported local platform;
it does not establish support for Linux or Windows. Cache reuse speeds package
installation, but each job creates its own virtual environment.

## Live startup check before release

A passing regression run does not complete the live fresh-install milestone.
In the fresh clone, follow the README setup using Docker/Compose and Ollama:

1. Create and load the private `.env` and start a **new, isolated** PostgreSQL
   database. If the existing database uses port 5432, choose a different local
   port and database/Compose project. Do not delete or reuse a personal volume.
2. Initialize the schema, install the configured models, and index a PDF you are
   permitted to use. Confirm `scripts.manage_library list` shows that filename.
3. Start the API on an unused loopback port and open its browser page. Check
   services, refresh papers, select that paper, and ask a routine question.
4. Check the answer, selected claim evidence and page references against the
   source PDF. Copy the displayed answer. Ask an unanswerable question and check
   that it refuses. This is a startup check, not the reserved final quality set.
5. Preview index removal. If applying it, remove only the synthetic/test paper;
   confirm the source PDF remains and **Refresh papers** updates the dropdown.

Record the candidate commit, OS/architecture, Python/uv/Node versions, exact
commands, model tags/settings, and pass/failure results in a new local report
under ignored `evaluation-results/`. Preserve failures. Do not record passwords
or commit PDFs, excerpts, private credentials, or raw reports. Model tags alone
do not pin weights. Human review and the separately reserved final validation
questions remain necessary before tagging v1.

## Recorded startup check: 2026-10-01

Application commit `0b654537cd8bf629f235c291bf781b1722e6c509` completed this check
in a fresh worktree and virtual environment on Apple Silicon macOS, Python
3.14.7 and uv 0.12.21. A generated two-page PDF contained known synthetic
seedling-height results and a missing-price control. A disposable
`pgvector/pgvector:pg17` container used loopback port 55432, with the API on
loopback port 8011. New private credentials were used; no personal database,
PDF library or volume was reused.

| Check | Observed result |
| --- | --- |
| Locked dependency installation | Passed; `pyproject.toml` and `uv.lock` unchanged. |
| Schema initialization and live embedding/indexing | Passed; two chunks across two pages. |
| `/status`, paper list and browser selection | Passed; all service checks available and the test filename selectable. |
| Routine verified question | Returned both expected heights with day-14 qualifiers and a page-1 citation in 1:00. |
| Evidence and source inspection | Selected excerpts supported both values; clicking the page reference opened surrounding context. |
| Copy answer | Success feedback and clipboard text matched the displayed answer and citation. |
| Missing-price question | Standard insufficient-evidence refusal in 0:19; no accepted claim evidence displayed. |
| Removal preview and apply | Preview preserved the index; apply removed only the test paper's rows and preserved the PDF hash. |
| Refresh after removal | Removed selection reset, empty-library message displayed, querying disabled. |
| Cleanup | Test API stopped; only the disposable test container and its anonymous volume removed. |

This exercised the normal verified path using `gpt-oss:20b`, low draft and
medium verifier reasoning, the default sampling/output budget, live
`nomic-embed-text` embeddings and the BGE reranker. No prompt, retrieval or model
settings were changed. The first question included model/reranker startup costs;
these two timings are observations, not a performance benchmark.

The package cache, installed Ollama models and reranker cache were reused, so
this does not test a cold download of all model weights. The PDF was synthetic
and inspected by the assistant; it establishes working wiring, not scientific
answer quality or completion of human review. These cases must not be reused as
reserved final validation questions.

Local evidence remains in ignored `evaluation-results/`: `live-startup-20261001.json`,
`live-browser-20261001.json`, `live-config-20261001.json`, `api-startup.log` and
`live-answer-20261001.jpg`. Records include the fixture hash, Ollama model
digests, runtime settings, grounding fingerprint, returned text, observed
browser state and cleanup result. The synthetic PDF and private `.env` remain
local. No raw report, PDF or credential is part of this documentation PR.
