# Three-model verified-answer comparison

## Frozen protocol

Compare `qwen3:8b`, `qwen3.5:9b`, and `gpt-oss:20b` in that order, using
application baseline `96264a7`. Reuse the 16 inspected development questions and
exact saved passages identified by `benchmarks/v1-development-review.json`.
Verify all four report hashes before running. Keep extraction, retrieval, labels,
prompts, deterministic evidence checks, repair limits, and rendering unchanged.
There is no retrieval, reindexing, or change to the user's normal library.

| Draft and verifier model | Ollama weight digest | Draft thinking | Verifier thinking |
| --- | --- | --- | --- |
| `qwen3:8b` | `500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41` | `true` | `true` |
| `qwen3.5:9b` | `6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7` | `true` | `true` |
| `gpt-oss:20b` | `17052f91a42e97930aa6e28a6c6c06a983e6a58dbb00434885a0cf5313e376f7` | `low` | `medium` |

Ollama is `0.34.4`. Its `/api/show` metadata confirms these thinking controls.
Qwen weights are Q4_K_M; GPT-OSS is MXFP4. These are practical configuration
comparisons, not isolated parameter-count effects. Thinking budgets differ across
families. Temperature is zero; context/output limits remain 12,288/4,096 tokens.
Other model defaults remain as installed and are retained in local metadata.

Run all 18 existing synthetic verifier controls once per model before paper
answers. Record semantic verdict completeness separately from deterministic
rejections: rejecting malformed output is safe behavior, but does not establish
correct semantic reasoning. A failed control disqualifies default promotion;
paper runs can still be diagnostic if the configuration returns valid outputs.
If transport or compatibility fails, preserve the failed report and record the
incomplete arm. Do not change settings or selectively retry completed cases.

Generate the four paper replays per model using `scripts.replay_grounding` and
fresh report paths, then move to the next model. Select the four IDs in each
manifest entry explicitly. The replay preserves the source report's case order;
all models must receive the same ordered case and passage payloads. Preserve
original answers, refusals, exceptions, and traces. The pipeline's existing one
bounded repair remains enabled for every model.

After all generation, score saved answers with fixed `qwen3:8b`, thinking disabled,
temperature zero, and unchanged judge prompts. Require existing judge calibration
before publishing scores. Do not send arm/model identities to the judge. Never
regenerate an answer to recover a grading failure. Calibration, model judging,
and assistant inspection are development diagnostics, not independent human review.
Qwen judging Qwen-family answers may have bias; inspect disagreements.

Compare case-level factual support, citation/attribution accuracy, requested
qualifiers, completeness, correct unanswerable refusals, answerable false refusals,
malformed responses and errors. Inspect every answer and relevant trace against
its passages. Automated citation support grades the entire returned bundle,
not specifically each inline citation; inspect the actual cited evidence too.
Do not select a winner from composite pass rate alone: an exact label split over
chunks or alternative valid evidence can fail its retrieval component.

Record generation latency separately from judge latency. Generation includes
model loading and repair, but excludes retrieval. Fixed model order and one trial
per question do not support steady-state speed or statistical superiority claims.
Report exact counts, paired outcomes and limits. No default changes in this PR.
The 16-case human packet stays intact and pending; this run does not complete
human review, independent validation, or local v1.

## Reproduction

The protocol was committed before live controls as `d7d8a05`; per-candidate
fingerprints and weights were committed before paper generation as `78276b0` in
`benchmarks/verified-model-comparison.json`. These fingerprints include model and
thinking settings, so they intentionally differ while the grounding code stays
unchanged. The original selection manifest continues to identify the saved
passages and development labels.

From the repository root with the original ignored source reports present, run
one model at a time. For example, the sample-paper Qwen3.5 replay is:

```bash
RAG_GROUNDING_MODEL=qwen3.5:9b RAG_DRAFT_THINK=true RAG_VERIFIER_THINK=true \
uv run python -m scripts.check_grounding \
  --output evaluation-results/qwen35-controls-new.json

RAG_GROUNDING_MODEL=qwen3.5:9b RAG_DRAFT_THINK=true RAG_VERIFIER_THINK=true \
uv run python -m scripts.replay_grounding \
  evaluation-results/v1-review-sample-20260928.json \
  --case c26-body-mass-loss --case glucose-tolerance-protocol \
  --case cited-rosiglitazone --case own-rosiglitazone-dose \
  --output evaluation-results/qwen35-sample-new.json
```

Repeat the replay for the other three papers using the matching source paths and
four case IDs from the selection manifest. Use `qwen3:8b` with `true`/`true`, or
`gpt-oss:20b` with `low`/`medium`, for the other arms. Verify local weight digests
against the protocol before and after each arm. Never overwrite a source or replay.

The generation commands above repeat individual trials. For grading the retained
Qwen3.5 arm from this comparison, use its completed replays and orchestration
record together:

```bash
RAG_JUDGE_MODEL=qwen3:8b uv run python -m scripts.evaluate_grounding_replays \
  evaluation-results/compare-qwen35-9b-sample-20260929.json \
  evaluation-results/compare-qwen35-9b-housing-20260929.json \
  evaluation-results/compare-qwen35-9b-mitochondrial-20260929.json \
  evaluation-results/compare-qwen35-9b-activin-20260929.json \
  --generation-record evaluation-results/verified-model-comparison-20260929-run.json \
  --output evaluation-results/qwen35-judged-new.json
```

The grader rejects modified source-report bytes, questions, labels, passages,
budgets, candidate settings or prompt fingerprints, and incomplete/duplicate
paper sets. It checks source hashes rather than connecting to a database.
`--source-root` can point to the checkout holding the original ignored reports.
Each grading attempt uses a fresh output path; grading failures preserve saved
answers. A new grading attempt is not a new generation trial and must still be
reported rather than selectively replacing an unfavorable grade.

Generation identities are attested by the retained local orchestration record:
its runner checks each model digest before every paper replay and after each arm.
The grader binds that record by hash, requires its successful replay entries and
matching model/runtime, and verifies the installed judge digest/runtime before
and after grading. Replay JSON alone does not attest model weights. New complete
comparisons need a corresponding identity-checked orchestration record; individual
manual replays should not be presented as weight-pinned comparisons without it.
The exact local runner and logs are retained beside the ignored raw reports.

## Prespecified revised configuration after control timeouts

The initial Qwen3 thinking-enabled control run completed 17 checks (15 passes,
two semantic failures), then timed out on `missing_comparison` at the existing
300-second request limit. Qwen3.5 timed out on its first positive control at the
same limit. Both original reports are retained; neither Qwen paper arm was run
under that initial configuration. These are incomplete control runs, not zero
answer-quality scores or evidence about every possible configuration of either model.

Before any paper answers, freeze a revised phase in
`benchmarks/verified-model-comparison-direct.json`: Qwen3 and Qwen3.5 drafting and
verification use `false`/`false`; GPT-OSS retains `low`/`medium`. All other budgets,
code, weights, cases and saved passages remain fixed. Boolean-false calls use the
application's existing 120-second timeout; GPT-OSS named thinking uses 300 seconds.
The control failure motivates a configuration change, not a hidden retry. Treat
this as a new development experiment, preserve the initial failures, and report
both phases. No prompt or evidence-policy changes are allowed.

Reuse GPT-OSS's first unchanged control and paper trials from the initial phase;
they have not yet run at this freeze. After that baseline arm, run all 18 controls
and the four first paper replays for Qwen3 with thinking disabled, then Qwen3.5.
Retain every result, even if controls fail. Incomplete controls still stop that
paper arm; completed semantic failures allow diagnostic paper runs but disqualify
default promotion. There are no repeated completed paper questions within an arm.
Generation order differs from the original plan, further limiting latency claims.
Use the revised protocol explicitly when grading these configurations:
`--protocol benchmarks/verified-model-comparison-direct.json`.
