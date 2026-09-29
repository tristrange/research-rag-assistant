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
