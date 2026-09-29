# Three-model verified-answer comparison

## Initial frozen protocol

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

The application overrides both installed Qwen temperatures to zero for these JSON
calls. This is a shared operational protocol, not the vendors' recommended thinking
configuration. [Qwen3's model card](https://huggingface.co/Qwen/Qwen3-8B#best-practices)
recommends temperature 0.6 for thinking and warns that greedy decoding can cause
repetition. [Qwen3.5's model card](https://huggingface.co/Qwen/Qwen3.5-9B#best-practices)
recommends temperature 1.0 for general thinking tasks. This is a plausible contributor
to long generation, not proof of why the recorded calls timed out. A future experiment
should freeze model-specific sampling settings and suitable timeout/output budgets
before testing them; preserve this zero-temperature run and its failures. The thinking
results here do not establish each model's speed or quality under recommended settings.

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

The current protocol manifests use schema 2, added during PR review to freeze the
evaluator fingerprint and require completion-time replay digests. The historical
trials used schema 1. A changed evaluator fingerprint is rejected before grading;
matching judge weights alone does not establish identical grading instructions.

For a **new** trial, start from the repository root with the original ignored source
reports present. Run one model at a time. For example:

```bash
RAG_GROUNDING_MODEL=qwen3.5:9b RAG_DRAFT_THINK=false RAG_VERIFIER_THINK=false \
uv run python -m scripts.check_grounding \
  --output evaluation-results/qwen35-controls-new.json

RAG_GROUNDING_MODEL=qwen3.5:9b RAG_DRAFT_THINK=false RAG_VERIFIER_THINK=false \
uv run python -m scripts.record_grounding_replays \
  --protocol benchmarks/verified-model-comparison-direct.json \
  --output-dir evaluation-results/qwen35-recorded-new

RAG_JUDGE_MODEL=qwen3:8b uv run python -m scripts.evaluate_grounding_replays \
  evaluation-results/qwen35-recorded-new/sample.json \
  evaluation-results/qwen35-recorded-new/housing.json \
  evaluation-results/qwen35-recorded-new/mitochondrial.json \
  evaluation-results/qwen35-recorded-new/activin.json \
  --protocol benchmarks/verified-model-comparison-direct.json \
  --generation-record evaluation-results/qwen35-recorded-new/run.json \
  --output evaluation-results/qwen35-judged-new.json
```

Inspect the controls before starting paper generation. Stop an arm if controls are
incomplete or no positive control is accepted; completed semantic failures permit
only diagnostic paper runs and disqualify default promotion. The recording wrapper
runs the paper arm, not the controls. It checks the frozen source/model/configuration,
uses a fresh directory, pins candidate thinking settings in each subprocess, hashes
each replay as that generation process exits, and checkpoints the run record. Failures
preserve outputs and stop without retries. Model/runtime identity is checked before
and after each replay. Use `qwen3:8b` with `false`/`false`, or `gpt-oss:20b` with
`low`/`medium`, for new trials of the other arms, always with fresh paths.

The grader rejects modified source-report bytes, questions, labels, passages, answer
bytes, budgets, candidate settings, grounding/evaluator fingerprints, and incomplete
or duplicate paper sets. Answer digests must match the successful generation steps,
not merely hashes computed while loading files for grading. It also checks installed
judge identity/runtime before and after grading. These are integrity checks against
a trusted local run record, not cryptographic signatures of the model's execution.
`--source-root` can point to the checkout holding the original ignored reports.
Every grading attempt uses a fresh output path and preserves saved answers on failure.

### Legacy experiment provenance

The retained September 29 generation records checked model identities and return
codes but did **not** capture replay digests when generation finished. Their scoring
reports hashed replay bytes at grading time; all three also recorded the same evaluator
fingerprint, `b9c68934238f422d44debca5ab4cc7f1668e961edbad49f93cbfe0a2ec0a3e73`.
These grade-time hashes and matching fingerprints are verifiable, but cannot establish
completion-time byte integrity retroactively. The result tables below therefore
remain **legacy development observations**, with this weaker provenance limitation.

Do not backfill hashes into those run records or overwrite their reports. The schema-2
grader rejects them because their completion digests are absent. Regrading those legacy
files with the current strict tool is intentionally unsupported; new compliant trials
require new generation through the wrapper. No new trial or grading was performed to
address these review comments, and the original measurements are unchanged. The exact
legacy runners, logs, records and scoring reports remain retained with the hashes below.

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

Reuse GPT-OSS's first unchanged control and paper trials from the initial phase.
Its controls had started at the revision freeze; its paper trials had not. After
that baseline arm, run all 18 controls
and the four first paper replays for Qwen3 with thinking disabled, then Qwen3.5.
Retain every result, even if controls fail. Incomplete controls still stop that
paper arm; completed semantic failures allow diagnostic paper runs but disqualify
default promotion. There are no repeated completed paper questions within an arm.
Generation order differs from the original plan, further limiting latency claims.
Use the revised protocol explicitly when grading these configurations:
`--protocol benchmarks/verified-model-comparison-direct.json`.


## Passage audit before candidate answer inspection

A separate assistant audit checked all 16 original question/passages bundles before
inspecting the new candidate answers. This is a development diagnostic, not paper-wide
verification or the pending human review. Keep original labels unchanged for paired
machine scores, and report these interpretation limits alongside them:

- `housing-grip-runs` splits the two requested facts across passages;
  `activin-long-regimen` has equivalent evidence outside the exact labeled quote.
  Their exact-evidence misses do not establish missing support.
- `housing-bat-atp` lacks the requested ATP concentration finding; SERCA ATPase
  activity is a different outcome. A refusal is safe relative to this bundle but
  fails an answerable end-to-end question.
- `cytosolic-mtdna` supports the Fis1/Drp1 finding but lacks the requested Mfn1/Mfn2
  comparison. A full refusal loses usable evidence; a complete reference-matching
  answer would include an unsupported clause.
- `activin-liver-tg-duration` contains both numeric effects, but does not establish
  every treatment-duration and chow-fed qualifier linking them. Exact quote hits
  alone do not establish the full reference answer.
- The four unanswerable cases support evidence-relative refusal. Their returned
  passages do not independently prove every paper-wide absence or male-only
  population explanation contained in the assistant-authored reference labels.

The other nine answerable bundles establish their requested facts, including the
rosiglitazone result as the title of a cited publication, with appropriate attribution.


## First-trial development results

All three revised configurations completed the same 16 questions, without transport
errors. The separate assistant audit inspected every final answer, actual cited chunk,
and draft/verifier/repair trace. Counts describe support from those retrieved passages,
not certification of the full papers or reference labels.

| Outcome | GPT-OSS 20B | Qwen3 8B, no thinking | Qwen3.5 9B, no thinking |
| --- | ---: | ---: | ---: |
| Synthetic controls passed / completed | 18/18 | 12/18 | 17/18 |
| Complete substantive answers with full retrieved support | 8 | 7 | 9 |
| Answers with clear unsupported final claims or qualifiers | 1 | 5 | 0 |
| Correct refusals on the four labeled-unanswerable cases | 4 | 1 | 4 |
| Safe refusals on answerable cases with incomplete context | 2 | 0 | 3 |
| Avoidable refusal despite complete available evidence | 1 | 0 | 0 |
| Supported but off-target answers | 0 | 2 | 0 |
| Incomplete comparison answer | 0 | 1 | 0 |
| Cases using the bounded repair | 5 | 0 | 3 |
| Cases with draft-schema validation errors | 3 | 0 | 0 |
| Median generation seconds, all 16 cases | 39.0 | 36.2 | 44.8 |
| Mean generation seconds, all 16 cases | 41.5 | 37.6 | 38.7 |

The seven answer/refusal categories sum to 16 per arm. Controls include deterministic
rejections: GPT-OSS had 16 complete semantic verdicts and two deterministic rejections;
each Qwen had 17 complete semantic verdicts and one deterministic rejection. These are
not 18 independent successful model reasoning decisions. Qwen3 failed six negative
controls (two attribution controls, shared population, embellishment, mixed attribution,
and missing comparison); Qwen3.5 accepted an effect summary despite a requested missing dose.

Qwen3.5 answered all nine questions whose bundles fully establish the requested facts.
It refused four presumed-unanswerable requests and three answerable requests with
incomplete evidence. This is the strongest observed support/usefulness balance here.
It is a promising development candidate, not an approved default: its missing-dose
control failed, some component verifier explanations were wrong, and zero unsupported
final answers on this small inspected sample does not establish general reliability.

GPT-OSS prevented a mistaken 24% total-fat-mass draft but repair then refused despite
available 35% evidence. It also accepted the liver-TG numeric comparison with two
unestablished population/duration bindings. Qwen3 merged separate cited publications,
substituted ATPase activity for ATP levels, imported female populations from questions,
and misbound treatment durations. Its salicylate dose and regional-fat-weight answers
were sourced but answered different questions. Its partial mtDNA answer additionally
inferred a control comparator not explicitly established for that measured outcome.

Some accepted structured quote fragments omit supporting qualifiers or even quote a
different sentence; the full cited chunks establish the supported final facts. Exact
span presence alone is not a complete claim-support test. GPT-OSS had one composite
claim with unsupported context; Qwen3 had eight clear unsupported claim units across
five answers, plus the mtDNA comparator caveat. Unsupported here means the cited
retrieval does not establish the assertion, not that the full scientific paper proves
it false. No output numerical value was fabricated from nowhere; the failures often
attach real numbers or findings to the wrong outcome, population, or publication.

Latency includes loading, verification, and repairs, excludes retrieval and judging,
and mixes answers with fast refusals. One sequential trial per case, different thinking
settings and model defaults, and unequal refusal counts prevent a steady-state speed
ranking. The small median differences do not justify choosing a model on speed alone.

Keep application defaults unchanged. The next bounded improvement should strengthen
verifier evidence for requested outcome/population/duration/attribution requirements,
then address the missing retrieval context. Preserve the 16-case human packet for
Thomas and Emma; this comparison does not complete their review or the v1 milestone.


## Paired case audit

“Sourced/off-target” means an explicit fact is present in the cited chunk but does not
answer the requested finding. “Unsafe context” means at least one final assertion or
attribution is unestablished by the retrieved evidence. Refusals are evidence-relative;
“incomplete context” does not imply the full paper lacks the answer.

| Case | GPT-OSS | Qwen3, no thinking | Qwen3.5, no thinking |
| --- | --- | --- | --- |
| `c26-body-mass-loss` | Supported | Supported | Supported |
| `glucose-tolerance-protocol` | Supported | Supported | Supported |
| `cited-rosiglitazone` | Supported | Unsafe attribution/absence | Supported |
| `own-rosiglitazone-dose` | Correct refusal | Correct refusal | Correct refusal |
| `housing-fat-loss` | Avoidable refusal | Sourced/off-target | Supported |
| `housing-bat-atp` | Incomplete-context refusal | Unsafe outcome substitution | Incomplete-context refusal |
| `housing-grip-runs` | Supported | Supported | Supported |
| `housing-female-response` | Correct refusal | Unsafe population | Correct refusal |
| `cytosolic-mtdna` | Incomplete-context refusal | Partial; comparator caveat | Incomplete-context refusal |
| `muscle-csa-sexes` | Supported | Supported | Supported |
| `food-intake-negative` | Supported | Supported | Supported |
| `rab5c-inhibitor-mouse-dose` | Correct refusal | Sourced/off-target drug | Correct refusal |
| `activin-long-regimen` | Supported | Supported | Supported |
| `activin-human-myotubes` | Supported | Supported | Supported |
| `activin-liver-tg-duration` | Unsafe qualifiers | Unsafe qualifiers/off-target | Incomplete-context refusal |
| `activin-female-gtt` | Correct refusal | Unsafe population | Correct refusal |


## Fixed-judge diagnostics

All three scoring reports completed all 16 saved cases. Each attempt passed all
13 existing calibration fixtures with `qwen3:8b`, thinking disabled. The unchanged
evaluator scores exact fixed refusals deterministically; other answers use the fixed
model. Grades below retain the original assistant-authored reference labels.
Correctness, completeness, citation support and exact-evidence hit rate are normalized
means over the 12 labeled-answerable cases; composite pass rate includes all 16.

| Automated diagnostic | GPT-OSS | Qwen3, no thinking | Qwen3.5, no thinking |
| --- | ---: | ---: | ---: |
| Correctness / completeness | 75.0% / 75.0% | 87.5% / 87.5% | 75.0% / 75.0% |
| Citation support | 100.0% | 79.2% | 100.0% |
| Exact-evidence hit rate | 66.7% | 66.7% | 66.7% |
| Composite passes | 11/16 | 7/16 | 11/16 |
| Refusals on labeled-answerable questions | 3/12 | 0/12 | 3/12 |
| Refusals on labeled-unanswerable questions | 4/4 | 1/4 | 4/4 |

The automated GPT-OSS/Qwen3.5 tie masks their fat-loss/liver-TG difference. The judge
awarded GPT-OSS's overqualified liver answer full citation support and also accepted
Qwen3's merged-publication/absence claims. Conversely, it gave Qwen3's sourced regional
fat-weight statement zero citation support, conflating its off-target response with
unsupported content. Exact-label misses also fail the fully supported grip-run and
long-regimen answers for every model. Neither correctness means nor composite pass
rates alone establish the recommended configuration. Calibration success did not
prevent these real-case judging errors; same-family judge bias remains a limitation.

## Retained local evidence

The following artifacts remain under ignored `evaluation-results/`. SHA-256 values
bind the final bytes. Each graded report contains the hashes of its four replay inputs
and generation record; those legacy records attest the installed weight/runtime checks but lack completion-time
replay digests, as described above.
The source-report hashes remain in the original selection manifest. The local driver
scripts and logs are retained for inspection, without committing raw paper passages.

| Artifact filename | SHA-256 |
| --- | --- |
| `compare-qwen3-8b-controls-20260929.json` | `ae0c0a145fc71e399461629f48362c8f69932f2b789dd876afeca1baed18d819` |
| `compare-qwen35-9b-controls-20260929.json` | `1aacb7532a4c7ff504d2b7d37be780bce7956fc4340ba0c753068a4a023a3192` |
| `compare-gpt-oss-20b-controls-20260929.json` | `74ea6fc6d91861f59715b6fc20455bd8662fbaa0da7294928e02fb6cd2e1e15e` |
| `compare-qwen3-8b-direct-controls-20260929.json` | `ffb19599697125fae580e9d9c4e9d395d78c782a03c6abbf419501e793fc03a0` |
| `compare-qwen35-9b-direct-controls-20260929.json` | `faa45a30c0fcd0eba1d905409b256c7b6de674571df180001ba9050e74ef3545` |
| `verified-model-comparison-20260929-run.json` | `b68fccc670dc937d18d9953d7f8d37c0ee8991604bd23a2930c1810f7f3da7d6` |
| `verified-model-comparison-direct-20260929-run.json` | `e814cb4ce15c8cec0da9100745d7cfaf60b83d0ffaede09c0f494a317aeb2a2f` |
| `compare-gpt-oss-20b-judged-20260929.json` | `f64854c34bce1c5bab79485e5f11fa002c11977fd04d950edbf784553fcc73c8` |
| `compare-qwen3-8b-direct-judged-20260929.json` | `ce65b6230296d3bb5a71ca1f45ff7ace6b2fb0eceac1452810839772a0784145` |
| `compare-qwen35-9b-direct-judged-20260929.json` | `9e1ff582b0eb47080cd28db325635cd1aabffa9d52376b95ba46dabb9b6deb4d` |
| `verified-model-comparison-grading-20260929-run.json` | `13511ca31cea4ce6ac441467fa3274cbac563c12f2a5b55980d1ec2f8b87838b` |
| `verified-model-comparison-assistant-audit-20260929.json` | `b586a0faece7da3f19ed12a4d73370f2d47e55fe9e89bbc3f6d24207344fbc42` |
| `run-verified-comparison-20260929.py` | `4d53c44d7431bb33a236f864609536caa23ac2526c387ba1271de85e9ce605ef` |
| `run-verified-comparison-direct-20260929.py` | `0f261b47a4c7d22017476c14942d48eaa6f5ce9563eb090a9a36dbd654163b97` |
| `grade-verified-comparison-20260929.py` | `4a1facbfde6e64706be3eda586150750503996d71a9a9f7c4c51f1871c4afb0b` |
