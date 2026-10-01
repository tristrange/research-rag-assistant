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
