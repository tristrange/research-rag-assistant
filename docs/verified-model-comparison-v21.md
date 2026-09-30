# Verified-answer comparison, v21

**Status: development comparison complete (2026-09-30).** The schema-3 protocol
was committed before fresh calls as `fbcd34b`, on application baseline
`912f76f` (merged PR #37). All three 16-case generation arms and calibrated
saved-answer grading arms completed. The two fresh Qwen control sets failed
semantic expectations, so their paper arms are diagnostic. GPT-OSS reused its
matching v21 preflight control report; this is not a fresh control repetition.
No default model changes or v1 acceptance follow from this comparison. Thomas
and Emma's human review remains deferred.

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
Both Qwen control sets are fresh, with 21 fixtures each; one fixture in each
was rejected deterministically before a verifier call, so each set made 20 actual
model calls. Do not reuse prior Qwen controls. The GPT-OSS report is a preflight
result, not a new or independent trial. Keep semantic verdict completeness separate from expected accept/refuse
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

After inspecting the generation records, grade each completed arm once. This
loop stops on the first grading failure; use fresh output paths for a new trial:

```bash
for RAG_REPLAY_ARM in qwen3-8b qwen3.5-9b gpt-oss-20b; do
  RAG_JUDGE_MODEL=qwen3:8b uv run python -m scripts.evaluate_grounding_replays \
    "evaluation-results/verified-model-comparison-v21/$RAG_REPLAY_ARM/sample.json" \
    "evaluation-results/verified-model-comparison-v21/$RAG_REPLAY_ARM/housing.json" \
    "evaluation-results/verified-model-comparison-v21/$RAG_REPLAY_ARM/mitochondrial.json" \
    "evaluation-results/verified-model-comparison-v21/$RAG_REPLAY_ARM/activin.json" \
    --manifest benchmarks/v1-development-review.json \
    --protocol benchmarks/verified-model-comparison-v21.json \
    --source-root "$RAG_SOURCE_ROOT" \
    --generation-record "evaluation-results/verified-model-comparison-v21/$RAG_REPLAY_ARM/run.json" \
    --output "evaluation-results/verified-model-comparison-v21/$RAG_REPLAY_ARM-judged.json" \
    || break
done
```

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

### Synthetic controls

Each set covers 21 fixtures: 20 model verifier calls and one intentional
current-study/reference rejection by deterministic validation. Every model
verdict was complete and structurally evidence-valid. That establishes valid
output and evidence-ID provenance, not semantic correctness.

| Configuration | Expected outcomes matched | Unsafe approvals | False refusals | Control provenance |
| --- | ---: | ---: | ---: | --- |
| Qwen3 | 17/21 | 4 | 0 | Fresh |
| Qwen3.5 | 19/21 | 0 | 2 | Fresh |
| GPT-OSS | 21/21 | 0 | 0 | Reused exact-profile v21 preflight from PR #37 |

Qwen3 incorrectly accepted `unsupported_shared_population`,
`mislabelled_attribution`, `unsupported_embellishment`, and
`missing_comparison`. Qwen3.5 falsely refused `supported_cited_work`, overlooking
an explicit mouse qualifier, and `title_without_unasked_dimensions`, failing to
bind the adjacent author and title. Both sets had accepted positive controls
and complete verdicts, permitting diagnostic paper generation under the frozen
gate. Neither Qwen configuration is eligible for promotion from these controls.
GPT-OSS's passing controls did not prevent its unsupported paper answer below.

The fresh Qwen control calls all ended with `done_reason=stop`, without transport
or output-budget failures. Their observed ranges were 10.5–63.0 seconds for
Qwen3 and 17.6–69.2 seconds for Qwen3.5. The reused GPT-OSS controls are not
included in fresh comparison timing.

### Inspection of all 48 final answers

Assistant inspection covered every final answer, actual cited passages, and
relevant draft/verifier/repair trace across all 12 four-case reports. Categories
are mutually exclusive and sum to 16 per model. A supported off-target answer
states an evidenced fact about a different requested measurement or intervention;
it is still an unsuccessful answer. An unsupported final answer includes an
assertion not established by its cited evidence. Safe context refusals concern
paper-level answerable labels whose saved passages do not establish the whole
requested answer. Correct labeled-unanswerable refusals remain evidence-relative,
not proof of paper-wide absence. These are inspected development results, not
independent human validation.

| Audited outcome | Qwen3 | Qwen3.5 | GPT-OSS |
| --- | ---: | ---: | ---: |
| Complete supported answer | 6 | 9 | 8 |
| Unsupported final answer | 2 | 0 | 1 |
| Supported fact, off target | 2 | 1 | 0 |
| Correct refusal, labeled unanswerable | 3 | 4 | 4 |
| Safe refusal, incomplete saved context | 1 | 2 | 3 |
| Avoidable refusal, evidence available | 2 | 0 | 0 |
| Incomplete but otherwise supported answer | 0 | 0 | 0 |
| **Total** | **16** | **16** | **16** |

The following paired outcomes use short names for those categories. Each row
uses the same question and source bundle across all three models; no retrieval
was performed in these trials.

| Frozen case ID | Qwen3 | Qwen3.5 | GPT-OSS |
| --- | --- | --- | --- |
| `c26-body-mass-loss` | Supported | Supported | Supported |
| `glucose-tolerance-protocol` | Avoidable refusal | Supported | Supported |
| `cited-rosiglitazone` | Avoidable refusal | Supported | Supported |
| `own-rosiglitazone-dose` | Correct refusal | Correct refusal | Correct refusal |
| `housing-fat-loss` | Off target | Supported | Unsupported |
| `housing-bat-atp` | Unsupported | Off target | Context refusal |
| `housing-grip-runs` | Supported | Supported | Supported |
| `housing-female-response` | Correct refusal | Correct refusal | Correct refusal |
| `cytosolic-mtdna` | Unsupported | Context refusal | Context refusal |
| `muscle-csa-sexes` | Supported | Supported | Supported |
| `food-intake-negative` | Supported | Supported | Supported |
| `rab5c-inhibitor-mouse-dose` | Off target | Correct refusal | Correct refusal |
| `activin-long-regimen` | Supported | Supported | Supported |
| `activin-human-myotubes` | Supported | Supported | Supported |
| `activin-liver-tg-duration` | Context refusal | Context refusal | Context refusal |
| `activin-female-gtt` | Correct refusal | Correct refusal | Correct refusal |

The paired failures show why a model switch alone is insufficient:

- **Measurement binding:** Qwen3 gives the supported 24% regional adipose-weight
  decrease when asked for total fat mass, omitting the 35% total result available
  in the saved abstract. GPT-OSS instead asserts a 24% decrease in **total** fat
  mass, misbinding the regional value to the requested outcome. Its first draft
  had invalid claim/citation keys; the repair kept the semantic error and the
  verifier accepted it. Qwen3.5 answers the total-fat question correctly.
- **Related outcomes:** Qwen3 asserts an ATP-level result supported only by an
  ATPase-activity passage. Qwen3.5 accurately reports the SERCA ATPase result,
  but that does not answer the ATP-concentration question. GPT-OSS refuses at
  draft stage. This saved bundle lacks the requested ATP-level finding.
- **Missing comparison and added comparator:** Qwen3's cytosolic-mtDNA answer
  omits the requested Mfn1/Mfn2 contrast and adds a control comparison that the
  cited passage attaches to total mtDNA. Qwen3.5's verifier identifies the
  missing comparison; a separate evidence-ID ownership error also rejects the
  draft, followed by a refusal on repair. GPT-OSS refuses initially. Neither
  refusal establishes absence from the full paper.
- **Avoidable structural refusals:** Qwen3's glucose-protocol and cited-title
  drafts contain supported requested facts, but verification repeatedly assigns
  an evidence ID owned by a different claim. Identical quoted text has separate
  per-claim IDs. Those failures survive the bounded repair and cause refusals.
- **Intervention substitution:** Qwen3 reports an evidenced sodium-salicylate
  dose for a question about a Rab5C-specific inhibitor. The dose is supported
  for that different intervention; it does not establish the requested answer.
- **Refusal mechanism matters:** In the liver-TG case, Qwen3's verifier twice
  semantically approves unsupported duration/population claims; an evidence-ID
  ownership failure causes the final refusal. Qwen3.5 refuses at draft stage.
  GPT-OSS's verifier rejects an unsupported chow-fed qualifier and the missing
  long-term answer in its draft's cited passages, then the repair refuses. The
  saved bundle contains numeric effects but lacks all required connecting
  qualifiers. GPT-OSS's female-GTT refusal follows malformed JSON and repair,
  with no verifier verdict; it does not demonstrate female-scope recognition.

The existing single repair was used in 5 Qwen3 cases, 2 Qwen3.5 cases and 3
GPT-OSS cases. Initial GPT-OSS schema failures occurred in the fat and female-GTT
cases. All final case records completed; malformed drafts remain in the traces.
No generation call timed out or hit its output budget, and no manual retries,
settings changes, regenerated answers, or fallback models were used.

### Fixed-judge diagnostics

After every generation arm finished, the unchanged `qwen3:8b` judge, thinking
false and temperature zero, graded the saved answers. Each grading arm passed
all 13 calibration fixtures before scoring its 16 answers. All grading calls
completed without transport or output-budget errors. Calibration is a synthetic
sanity check, not proof of judge accuracy or independence from Qwen-family bias.

| Metric against frozen labels | Qwen3 | Qwen3.5 | GPT-OSS |
| --- | ---: | ---: | ---: |
| Composite passes, all 16 cases | 7/16 | 11/16 | 10/16 |
| Correctness, normalized over 12 answerable cases | 66.7% | 75.0% | 70.8% |
| Completeness, same denominator | 66.7% | 79.2% | 70.8% |
| Citation support, same denominator | 83.3% | 91.7% | 100.0% |
| Exact labeled evidence hit, answerable cases | 8/12 | 8/12 | 8/12 |
| Refusals on 4 labeled-unanswerable cases | 3/4 | 4/4 | 4/4 |
| Refusals on 12 paper-labeled-answerable cases | 3/12 | 2/12 | 3/12 |

Do not interpret these numbers as audited factual-support rates. In particular:

- The judge gives GPT-OSS's incorrect total-fat claim citation support 2/2,
  explaining its aggregate 100% support score despite an unsupported final
  assertion. It also gives Qwen3's incomplete cytosolic-mtDNA answer 2/2 on all
  three factual scores, overlooking the missing contrast and added comparator.
- It marks all three grip and long-regimen answers factually complete and
  supported, but their composite passes fail the exact labeled-quote hit.
  Equivalent evidence or facts split across passages still support those answers.
- It describes Qwen3.5's ATPase result and Qwen3's sodium-salicylate dose as
  invented, although the cited passages support those narrower statements.
  The audit classifies both as off-target answers instead. Qwen3's regional-fat
  statement is likewise supported even though it does not answer total fat mass.
- Safe context refusals receive zero correctness/completeness against paper-level
  answerable labels. These differ from Qwen3's two avoidable refusals, where the
  requested evidence is available. Refusal citation scores do not test a factual
  claim and can inflate an aggregate support rate.

The judge evaluates the whole returned source bundle; the audit separately
checks actual inline citations. The unchanged labels, contexts and scores are
preserved; no retrospective relabeling or judge tuning was used to improve rates.

### Observed time

Per-answer generation includes model loading, draft, verification and repair;
it excludes retrieval and judging. Each configuration has 16 sequential trials.
There were 39, 30 and 29 generation model calls respectively.

| Observed seconds | Qwen3 | Qwen3.5 | GPT-OSS |
| --- | ---: | ---: | ---: |
| Mean generation per question | 68.0 | 54.4 | 81.1 |
| Median generation per question | 48.3 | 64.4 | 91.2 |
| Minimum–maximum generation per question | 8.9–186.6 | 4.5–107.7 | 6.9–179.0 |
| Sum of 16 generation times | 1,087.9 | 869.7 | 1,298.0 |
| Mean saved-answer grading per question, excluding calibration | 7.6 | 7.5 | 6.1 |
| Grading-arm elapsed time, including calibration | 229.2 | 215.2 | 193.2 |

Some exact refusals are scored deterministically without judge calls, reducing
mean grading time. Qwen3.5 has a lower observed mean generation time than Qwen3
but a higher median. Unequal refusals and repairs, different configurations,
fixed arm order and model loading prevent steady-state speed, statistical
superiority or parameter-specific causal conclusions. This run shows completion
under these profiles, not why the historical thinking runs timed out.

### Provenance and checks

The ignored experiment directory is
`evaluation-results/verified-models-v21-20260930/` in the main checkout. Its
`freeze-v2.json` SHA-256 is
`dc7567fa115c9e5ce699cdd9bfd3697db6eae675599865fec813e64a8ee02108`.
It pins 69 input/code/observer files, runtime/model metadata and the reused
GPT-OSS controls before fresh calls. The final integrity check found no changes
to those frozen files. All 12 replay hashes still match the digests recorded at
generation completion and bound by the grader. Audit files also bind their
respective replay hashes. `experiment.json` records completion and hashes for
all generation and grading arms. Raw calls, failed drafts and original source
reports stay ignored; no PDF passages or raw reports are committed.

| Artifact | Retained SHA-256 |
| --- | --- |
| `qwen3-8b-controls.json` | `ddd6f283cb197dddecea57826e28f1213ccfe7371eecac58d59db4e4023c5563` |
| `qwen35-9b-controls.json` | `9a1eb4476face012c27effdb20a294bf60df41140019d444c9d190e11d90e003` |
| Reused `qualifier-evidence-20260930/gpt-oss-v21-default-controls.json` | `9cc27ff00e076e6418d42bac0590315846e9170f04747e9afac0cc4de59a7d06` |
| `qwen3-8b-recorded/run.json` | `da0b3cc5a87e27f0ac92dde3ee76a2d905c280b00bddd3de39ec32db75e8b574` |
| `qwen35-9b-recorded/run.json` | `8e755a7154383eb58889abe37c29bc4491c6bf3391b9665943786bef0ae9b00c` |
| `gpt-oss-20b-recorded/run.json` | `bd2d72c00f4c33affffc859616c3a4516560ef56000f86d82980ad0dd62a8d3f` |
| `qwen3-8b-judged.json` | `392105b3db93d03cca7c88d07035dd07b2313d9b0b711757c41a76f4c8986f7b` |
| `qwen35-9b-judged.json` | `03e33964b8d74195d5d9b2d1b6df989c420571f1f4d90b7e4b9f46ec3252e2c6` |
| `gpt-oss-20b-judged.json` | `5852bd297df00658a25f8537ed4f3519ccda2c48ed5170f9ae6e1a701bb18210` |

The relevant replay/protocol regression suite passed 25 tests. This PR adds a
frozen protocol and reporting only; application code, defaults, corpus and the
human-review packet remain unchanged. A later implementation change needs a
new protocol and fresh reports rather than updating these study artifacts.

## Decision and next step

Qwen3.5 shows the most complete supported answers in this small inspected set,
but its two positive-control false refusals and off-target ATP answer prevent
promotion. GPT-OSS remains the existing default; its passing synthetic preflight
is insufficient to treat its answers as verified facts, as the fat-mass error
shows. The study does not establish an overall winning model or finish v1.

The next bounded implementation step should reduce avoidable multi-claim
refusals by improving evidence-ID mapping, with regression cases for the
supported glucose protocol and cited title. Add paired positive/negative controls
for measurement substitution (total versus regional fat; ATP concentration versus
ATPase activity) before another frozen comparison. These need to test whole
question coverage as well as citation support, without weakening evidence checks.
Then address the documented context gaps through a separate retrieval milestone
and resume Thomas and Emma's review before claiming v1 readiness. Cloud-provider
support remains deferred until the existing local v1 plan is complete.
