# Verified-answer comparison, v21

**Status: methods drafted; comparison work is pending.** The schema-3 protocol is
`benchmarks/verified-model-comparison-v21.json`. This is a new development
comparison after PR #37 (`912f76f`), not a rewrite of the prior comparison or its
reports. A matching GPT-OSS control report already exists and is reused as
preflight; fresh Qwen controls, all paper generations, and grading remain pending.

## Scope and frozen inputs

Compare `qwen3:8b`, `qwen3.5:9b`, and `gpt-oss:20b`, in that order, on the same
16 saved questions, passages, and labels selected by
`benchmarks/v1-development-review.json`. Use the original ignored source reports
from the main checkout. Do not retrieve again, reindex, or rewrite questions,
passages, labels, or expected answers. Do not put gold answers in candidate
draft or verifier prompts; the fixed judge may use the saved references for
factual grading after all candidate generation is complete. These are inspected
development data; Thomas and Emma's human review remains deferred.

The schema-3 protocol freezes the review-set hash (which binds the manifest's
source-report hashes), current grounding and evaluator fingerprints, Ollama
version, installed model digests, judge identity, and each candidate's settings.
The recorder verifies those values and captures each replay digest when generation
finishes. Record the protocol, wrapper settings, and raw-call observer freeze in
the local ignored experiment record before fresh model calls. Do not change
runtime code, prompts, or the protocol during the experiment. Use fresh reports
and replay directories for new calls; preserve failed runs and never retry a
completed case.

| Draft and verifier | Draft / verifier reasoning | Sampling | Per-call timeout | Output tokens |
| --- | --- | --- | ---: | ---: |
| `qwen3:8b` | `false` / `false` | temperature 0 | 120 s | 4,096 |
| `qwen3.5:9b` | `false` / `false` | temperature 0 | 120 s | 4,096 |
| `gpt-oss:20b` | `low` / `medium` | temperature 1, `top_p` 1 | 300 s | 4,096 |

All arms use 12,288 context tokens. Ollama is 0.34.4; the protocol records the
installed digest for each model. These are configuration comparisons, not an
isolated test of model family or reasoning level. The different model weights,
reasoning modes, and sampling settings prevent causal claims about any one
parameter.

## Run order and control gate

Run one arm at a time in this order: Qwen3 controls, then its paper arm if
eligible; Qwen3.5 controls, then its paper arm if eligible; GPT-OSS using the
exact-profile v21 full-control report below, then its paper arm if eligible.
Both Qwen control sets are fresh, 21 calls each; do not reuse prior Qwen
controls. The GPT-OSS report is a preflight result, not a new or independent
trial. Keep semantic verdict completeness separate from expected accept/refuse
behavior. One current-study/reference control is intentionally rejected by
deterministic validation; it is not a model reasoning result. The other controls
require complete, schema-valid, evidence-valid verdicts.

An incomplete verdict, transport or compatibility failure, or a run with no
accepted positive control stops that model's paper arm. Preserve its report and
continue with the next model. A complete semantic failure may be followed by a
diagnostic paper arm if at least one positive control was accepted, but that
model is disqualified from promotion. Do not convert an error or malformed
verdict into a passing refusal. The existing single bounded repair remains
enabled; it is part of the recorded run and must not be invoked as a manual
retry.

Example control commands (use the exact candidate values also frozen in the
protocol):

```bash
RAG_GROUNDING_MODEL=qwen3:8b \
RAG_DRAFT_THINK=false RAG_VERIFIER_THINK=false \
RAG_GROUNDING_SAMPLING='{"temperature":0}' \
RAG_GROUNDING_TIMEOUT_SECONDS=120 RAG_GROUNDING_OUTPUT_TOKENS=4096 \
uv run python -m scripts.check_grounding \
  --output evaluation-results/verified-model-comparison-v21/qwen3-8b-controls.json

RAG_GROUNDING_MODEL=qwen3.5:9b \
RAG_DRAFT_THINK=false RAG_VERIFIER_THINK=false \
RAG_GROUNDING_SAMPLING='{"temperature":0}' \
RAG_GROUNDING_TIMEOUT_SECONDS=120 RAG_GROUNDING_OUTPUT_TOKENS=4096 \
uv run python -m scripts.check_grounding \
  --output evaluation-results/verified-model-comparison-v21/qwen35-9b-controls.json
```

The scripts use the application's fixed 12,288-token context. Inspect each
control report before deciding whether its paper arm may proceed. Complete
semantic failures permit diagnostic generation, but never promotion.

## Paper generation and grading

For each eligible model, record all 16 saved cases with
`scripts.record_grounding_replays`, using the frozen manifest and schema-3
protocol. Run the arms in the stated order with a fresh output directory for
each. The wrapper receives that arm's frozen model, thinking, sampling, timeout,
and output settings; the example uses a source root that contains the original
ignored reports. It checks source reports, model/runtime identity and
fingerprints, and records completion-time replay digests. It preserves outputs
on failure and stops without retries. No retrieval or reindexing occurs.

```bash
# Set RAG_SOURCE_ROOT to the main checkout containing the frozen ignored reports.
RAG_SOURCE_ROOT=/path/to/main-checkout

RAG_GROUNDING_MODEL=qwen3:8b RAG_DRAFT_THINK=false RAG_VERIFIER_THINK=false \
RAG_GROUNDING_SAMPLING='{"temperature":0}' \
RAG_GROUNDING_TIMEOUT_SECONDS=120 RAG_GROUNDING_OUTPUT_TOKENS=4096 \
uv run python -m scripts.record_grounding_replays \
  --manifest benchmarks/v1-development-review.json \
  --protocol benchmarks/verified-model-comparison-v21.json \
  --source-root "$RAG_SOURCE_ROOT" \
  --output-dir evaluation-results/verified-model-comparison-v21/qwen3-8b

RAG_GROUNDING_MODEL=qwen3.5:9b RAG_DRAFT_THINK=false RAG_VERIFIER_THINK=false \
RAG_GROUNDING_SAMPLING='{"temperature":0}' \
RAG_GROUNDING_TIMEOUT_SECONDS=120 RAG_GROUNDING_OUTPUT_TOKENS=4096 \
uv run python -m scripts.record_grounding_replays \
  --manifest benchmarks/v1-development-review.json \
  --protocol benchmarks/verified-model-comparison-v21.json \
  --source-root "$RAG_SOURCE_ROOT" \
  --output-dir evaluation-results/verified-model-comparison-v21/qwen3.5-9b

RAG_GROUNDING_MODEL=gpt-oss:20b RAG_DRAFT_THINK=low RAG_VERIFIER_THINK=medium \
RAG_GROUNDING_SAMPLING='{"temperature":1,"top_p":1}' \
RAG_GROUNDING_TIMEOUT_SECONDS=300 RAG_GROUNDING_OUTPUT_TOKENS=4096 \
uv run python -m scripts.record_grounding_replays \
  --manifest benchmarks/v1-development-review.json \
  --protocol benchmarks/verified-model-comparison-v21.json \
  --source-root "$RAG_SOURCE_ROOT" \
  --output-dir evaluation-results/verified-model-comparison-v21/gpt-oss-20b
```

Finish generation for every arm before grading any answers. Then score the saved
replays with fixed `qwen3:8b` judging, thinking disabled, and temperature zero.
Use the frozen judge prompt and protocol. Require the grader's judge calibration
to pass before publishing scores; the grading command runs calibration and must
stop if it fails. If calibration or a grading arm fails, stop the remaining
grading, preserve saved answers, and never regenerate them. Do not send model or
arm identities to the judge. Grading is a diagnostic against the unchanged
development labels, not an independent check of the answers.

Inspect every final answer and its actual citations and draft/verifier/repair
trace against the saved passages. Report whether the cited evidence establishes
the requested facts, qualifiers, and attribution. Record correct refusals,
false refusals on answerable cases, unsupported or off-target claims, malformed
outputs, errors, and any repair. Label scores alone are insufficient: exact
quote or chunk-label matches can miss valid evidence elsewhere in the saved
context, while a bundle can lack enough context to establish every phrase in an
assistant-written reference answer.

The prior comparison documents specific interpretation limits that remain
relevant; preserve the labels but explain them when reporting outcomes:

| Frozen case group | Limitation to report |
| --- | --- |
| `housing-grip-runs`, `activin-long-regimen` | Requested facts are split across passages, or equivalent support falls outside the exact labeled quote. A label miss alone does not establish missing support. |
| `housing-bat-atp` | The saved bundle lacks the requested ATP concentration result; SERCA ATPase activity is a different outcome. A refusal is safe against these passages but can still miss an answerable paper-level question. |
| `cytosolic-mtdna` | The bundle supports the Fis1/Drp1 result but not the requested Mfn1/Mfn2 comparison. Do not treat a full reference answer as wholly grounded in the saved context. |
| `activin-liver-tg-duration` | Numeric effects are present, but the bundle does not establish every requested duration and chow-fed qualifier connecting them. |
| Four labeled-unanswerable cases | The saved passages support evidence-relative refusal; they do not independently prove paper-wide absence or every population explanation in the reference labels. |

Report generation latency separately from grading latency. Generation time
includes model loading, verifier work, and any bounded repair, and excludes
retrieval. One sequential trial per question, fixed model order, different
reasoning settings, and unequal refusal counts cannot establish steady-state
speed or statistical superiority. Do not choose a winner from aggregate pass
rate alone. No model is promoted by this comparison; it does not complete the
deferred human review or establish v1 readiness.

## Results

The GPT-OSS v21 preflight report at
`evaluation-results/qualifier-evidence-20260930/gpt-oss-v21-default-controls.json`
passed 21/21 expected outcomes under the frozen GPT-OSS fingerprint, model
digest, and Ollama runtime. It contains 20 complete, evidence-valid model
verdicts and one expected deterministic rejection without a verifier call. Its
SHA-256 is `9cc27ff00e076e6418d42bac0590315846e9170f04747e9afac0cc4de59a7d06`.
The new protocol's local freeze binds this report and its runtime metadata. Reuse
it only as the GPT-OSS control preflight; do not describe it as a fresh repetition
or independent validation.

The Qwen3 and Qwen3.5 controls, the three paper arms, and all grading results are
pending. For each arm, record the control completion and expected-outcome counts,
complete semantic verdicts, errors and transport failures, then the status of its
16-case paper run. Generate every eligible arm before grading. After all
generation finishes, report case-level findings and paired differences, judge
calibration, generation and grading latency separately, and the manual
citation/trace audit. Keep diagnostic model-judge scores distinct from that
inspection and preserve the label/context limitations above. No human review or
model promotion is implied by a completed machine comparison.
