# Project guidance

This is a local-first FastAPI RAG assistant for academic PDFs. Application code is
in `app/`, command-line workflows in `scripts/`, regression tests in `tests/`, and
evaluation protocols and findings in `docs/`. Use `README.md` for setup and
current commands rather than copying its full instructions here.

## Checks

- Install dependencies with `uv sync --locked`. After changing dependencies,
  run `uv lock`, then `uv sync --locked`; use `uv run --locked` for commands.
- Run linting and formatting checks with `uv run --locked ruff check .` and
  `uv run --locked ruff format --check .`; apply fixes with
  `uv run --locked ruff check --fix .` and `uv run --locked ruff format .`.
- Run relevant regression tests with
  `uv run --locked python -m unittest discover -s tests -v`.
- Run strict type checking with `uv run --locked mypy` after Python changes.
- Unit tests use local stubs and SQLite. Targeted live verifier checks need
  Ollama; end-to-end evaluations also need PostgreSQL. Run the relevant live
  checks when a change affects those paths.

## Repository workflow

- Start each change from an up-to-date `main` on a short-lived branch and open one
  pull request per concern. Do not merge with failing checks.
- The repository owner configures branch rules in GitHub settings to require a
  pull request and the `Python, UI and types`, `PostgreSQL contracts` and
  `CodeQL` checks. These settings are not enforced by files in this repository;
  verify the names against the actual check runs after workflow changes.
- Dependabot updates `uv` dependencies and GitHub Actions weekly. Keep `uv.lock`
  synchronized, review major updates separately, and treat changes to models,
  prompts, evaluation settings or corpus provenance as semantic changes that
  need their own evidence.

## Status and evidence

- `docs/status.md` is the current status authority. Keep historical reports and
  dated findings unchanged; link to them rather than rewriting them.
- Update `docs/status.md` only for a validated transition or a factual correction
  supported by the current repository state: a completed reserved check, a merged
  behavior change with evidence, a measured baseline, a resolved blocker, or a
  correction of an outdated factual statement. A correction must not overstate
  quality or turn development evidence into validation.
- Do not claim release readiness or general answer accuracy from green CI,
  development replays, or a passing synthetic regression. See the status decision
  log for the current position.

## Evidence and evaluation

- Obtain explicit user approval before sending private PDF content, paper excerpts
  or derived passages to an external model or service. Local processing is the
  default; do not assume a hosted model is permitted.
- Keep findings from the paper being queried distinct from findings in its
  references. Claims need support from the cited passage and correct attribution.
  A supported negative result can answer a yes/no question; missing evidence
  cannot establish a negative result.
- Keep source PDFs in `data/` and raw evaluation reports in
  `evaluation-results/`; both are Git-ignored and may contain copyrighted text.
  Document findings without committing raw passages or reports.
- Use fresh report paths for new trials. Preserve failed and original runs, record
  model/settings and corpus fingerprints, and distinguish inspected development
  cases from independent validation. A replay is a new generation trial.
- Reindex after extraction, chunking, or embedding changes before evaluating the
  new corpus. Do not compare an old report to a changed index as if inputs matched.
- Use the [pipeline performance baseline](docs/performance-baselines.md) procedure
  for stage-level timing; keep warm-up samples, failures and provenance, and do not
  cite a baseline until a matching local run exists.
