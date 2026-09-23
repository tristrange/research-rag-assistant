# Project guidance

This is a local-first FastAPI RAG assistant for academic PDFs. Application code is
in `app/`, command-line workflows in `scripts/`, regression tests in `tests/`, and
evaluation protocols and findings in `docs/`. Use `README.md` for setup and
current commands rather than copying its full instructions here.

## Checks

- Install dependencies with `uv sync`.
- Run relevant regression tests with `uv run python -m unittest discover -s tests -v`.
- Run strict type checking with `uv run mypy` after Python changes.
- Unit tests use local stubs and SQLite. Targeted live verifier checks need
  Ollama; end-to-end evaluations also need PostgreSQL. Run the relevant live
  checks when a change affects those paths.

## Evidence and evaluation

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
