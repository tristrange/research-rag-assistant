## Scope

<!-- What changes, and what is deliberately out of scope? -->

## Behavior

<!-- Describe user-visible or operational behavior before and after. Write "No behavior change" when applicable. -->

## Evidence

<!-- Link reports or summarize measurements. Distinguish development cases from independent validation. For performance changes, include model, settings and corpus provenance; do not cite a baseline without a matching local run. -->

## Tests

- [ ] `uv run --locked ruff check .`
- [ ] `uv run --locked ruff format --check .`
- [ ] `RAG_DATABASE_URL=sqlite:///:memory: HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run --locked python -m unittest discover -s tests -v`
- [ ] `node --test tests/test_ui_rendering.js`
- [ ] `uv run --locked mypy`
- [ ] Relevant browser, PostgreSQL, live-model or evaluation check, or an explanation of why it was not run

## Provenance

<!-- For extraction, chunking, embedding, model, prompt, evaluation or benchmark changes: record model/settings, corpus or index fingerprint and report path. Write "Not applicable" for changes that do not affect those inputs. -->

## Rollback

<!-- How to revert safely, including any index or data migration or compatibility steps. -->
