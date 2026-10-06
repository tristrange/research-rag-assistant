# Development checks

Run from the repository root. `uv sync --locked` installs the development
dependencies. The supported local target is Apple Silicon macOS, Python 3.14
and Node.js 24 for JavaScript tests. See [fresh-install checks](install-smoke-test.md)
for isolated setup and the separate live startup procedure.

## Service-independent regressions

```bash
RAG_DATABASE_URL=sqlite:///:memory: HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  uv run --locked python -m unittest discover -s tests -v
node --test tests/test_ui_rendering.js
uv run --locked mypy
```

Python tests use SQLite and stubs for extraction, embeddings, reranking and model
responses. They cover index replacement/rollback, retrieval, grounding, evaluation
contracts and API boundaries. JavaScript tests use a simulated DOM. Strict mypy
covers application code, scripts and Python tests. No PDFs or running model/database
services are required. Missing Hugging Face models are not downloaded by these tests.

## Real-browser smoke tests

Install the separate browser binary, then run the opt-in suite:

```bash
uv run --locked python -m playwright install chromium
RAG_DATABASE_URL=sqlite:///:memory: HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  uv run --locked python -m unittest discover -s tests/browser -v
```

The suite serves the real FastAPI app, HTML and assets on an unused loopback port,
with synthetic backend results. It checks scoped submission, emphasis rendering,
literal HTML safety, evidence/citation links, copy-button output, refusal/partial
guidance, paper refresh and service-error retry. One flow uses a narrow viewport.
The Clipboard API is stubbed so the host clipboard stays unchanged. The test server
and browser contexts are closed afterward.

This is a Chromium integration smoke check, not Safari compatibility testing,
a visual layout audit or answer-quality evaluation. Ordinary Python/Node tests
do not need browser binaries.

## PostgreSQL contracts

The opt-in integration suite skips without `RAG_TEST_POSTGRES_URL` and creates
isolated test databases. Follow the [disposable Docker instructions](postgres-contract-tests.md)
for controller permissions and the test command. Do not point experiments at a
personal paper index or delete its volume.

## Grounding and injection controls

These checks **do call Ollama**. They use synthetic controls rather than papers:

```bash
uv run python -m scripts.check_grounding --output evaluation-results/grounding-controls.json
uv run python -m scripts.check_prompt_injection
uv run python -m scripts.check_prompt_injection --mode plain
```

Use repeated `--case CONTROL_ID` flags with `scripts.check_grounding` for selected
controls. Always use a fresh output path; preserve failures. The injection probe
tests one attack pattern, not all possible attacks. Passing model controls does
not establish answer reliability or replace human review.

## CI and quality boundaries

The `Regression checks` workflow installs locked dependencies on a fresh macOS
runner and executes Python, Node, Chromium and mypy checks. A separate Ubuntu
job runs PostgreSQL contracts against a disposable pgvector service. CodeQL checks
the repository through GitHub's code-scanning workflow. Dependency/browser installation
needs network access; model inference is not part of regression CI.

Green CI establishes those checks passed, not scientific answer quality or release
approval. See [evaluation](answer-evaluation.md) and [v1 readiness](v1-readiness.md).
