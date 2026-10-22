# Documentation

Start with the [project overview and quickstart](../README.md). The guides below
describe current usage; dated studies preserve the configurations and limitations
of earlier development experiments.

**Current status:** [Project status](status.md) records the current commit,
engineering gates, latest review evidence, blockers, decision log and next
experiment.

## Use and understand the assistant

- [Local usage](local-usage.md): indexing, library maintenance, API scopes, evidence,
  service failures and the local security boundary.
- [Configuration](configuration.md): model roles, environment variables, sampling
  profiles, timeouts and output budgets.
- [Architecture](architecture.md): components, ingestion, retrieval, grounding and
  transaction boundaries.

## Development and installation

- [Development checks](development.md): Python/JavaScript tests, browser smoke tests,
  typing, synthetic model controls and CI.
- [Fresh-install checks](install-smoke-test.md): isolated installation and the
  recorded live startup check.
- [PostgreSQL contracts](postgres-contract-tests.md): disposable database setup and
  integration-test coverage.

## Evaluation and validation

- [Project status](status.md): current commit, engineering gates, latest review
  evidence, blockers, decision log and next experiment.
- [Retrieval evaluation](retrieval-evaluation.md): comparison commands, page-level
  metrics and the dated baseline measurement.
- [Answer-quality evaluation](answer-evaluation.md): benchmark commands, strategies,
  model-judge calibration, score limits and resuming reports.
- [Report format](evaluation-report-format.md): schemas, provenance and compatibility.
- [Pipeline performance baselines](performance-baselines.md): stage-level timing,
  warm-up policy, provenance and the baseline-pending status.
- [Benchmark corpus](benchmark-corpus.md): paper acquisition, attribution, licensing
  and isolated evaluation inputs. PDFs and raw reports remain local and ignored.
- [Local v1 readiness](v1-readiness.md): detailed readiness criteria, historical
  review record, optional human review and the release stopping rule. Current
  status is recorded in [project status](status.md).
- [Local v1 fresh-question check](local-v1-fresh-check.md): frozen configuration,
  fresh question reservation, AI review mode and exact stopping criteria.

## Engineering studies

These are development evidence, not independent quality certification. Historical
model names, settings and outcomes remain as recorded; they do not override the
[current configuration](configuration.md).

**Model and inference comparisons**

- [Initial answer evaluation](evaluation-2026-09-17.md)
- [Housing-paper model comparison](housing-model-comparison.md)
- [Verified-model comparison](verified-model-comparison.md)
- [v21 verified-model comparison](verified-model-comparison-v21.md)
- [Ollama inference settings](ollama-inference-settings.md)
- [Embedding batching measurement](embedding-batching.md)

**Retrieval and context experiments**

- [Neighboring context](neighbor-context-evaluation.md)
- [Retrieval evidence coverage](retrieval-evidence-coverage.md)
- [Verified context comparison](verified-context-comparison.md)
- [Unexpanded third-paper evaluation](unexpanded-verified-third-paper.md)
- [Vector reserve](vector-reserve-evaluation.md)
- [Activin vector-reserve validation](activin-vector-reserve-validation.md)
- [Reviewed answer coverage follow-up](reviewed-answer-quality.md)
- [Activin context coverage investigation](activin-context-coverage.md)

**Grounding and attribution investigations**

- [Source attribution](source-attribution-evaluation.md)
- [Verified claims](verified-claims-evaluation.md)
- [Section/refusal regressions](section-refusal-regressions.md)
- [Grounding refusal diagnostics](grounding-refusal-diagnostics.md)
- [Question coverage and evidence](question-coverage-evidence.md)
- [Shared verifier evidence](shared-evidence-verification.md)
- [Draft source selection](draft-source-selection.md)
