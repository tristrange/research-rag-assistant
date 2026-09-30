# Question coverage and exact evidence

The v13 verifier selected its own list of question requirements. In the earlier
Qwen3.5 non-thinking control, it accepted an effect summary for “At what dose did
treatment delay weight loss in the cited Smith study?” The reference title gave
the effect but no dose. The verifier omitted dose from its requirements, so code
had nothing to reject. The original comparison and raw report remain unchanged.

## v21 contract

The verifier keeps the original concise requirement assessments, attribution rules,
and claim checks. It must additionally return a `requested_answer` check whose
`question_excerpt` copies the entire original question, allowing whitespace
normalization. A supported full-question check and every supported claim verdict
must link to exact evidence IDs. A missing or rewritten full-question check,
unsupported requirement, rejected claim, or unsupported full-question check
prevents rendering the answer.

The separate full-question gate prevents the model's requirement list from being
the sole completeness check. It does not mechanically identify an omitted
qualifier: the model must still assess the complete question correctly. Exact
question copying and evidence links provide auditable structure, not proof of
semantic support.

For every claim, the application builds an evidence catalogue from all exact
sentence spans in that claim's cited passages. Each ID belongs to a particular
claim and source. This includes adjacent population and attribution sentences,
even when the draft selected only the result sentence. Uncited retrieved passages
are excluded. The schema restricts IDs and the full-question excerpt; runtime
validation checks them again. Supported requested-answer checks and claim verdicts
need nonempty, unique, known IDs.
A claim verdict cannot borrow another claim's evidence. Traces retain the
catalogue alongside the verdict for inspection.

The v21 verifier restores the original v18 schema and prompt, with medium
verifier reasoning, a 300-second timeout, and 4,096 output tokens. The v20 flat
generation grammar failed on its first `supported_requested_population` case
with `OllamaOutputLimitError` before any complete verdict (0/5); that grammar is
abandoned. v21 keeps nonempty evidence IDs for positive approvals mandatory in
the schema and runtime validation. No acceptance check changed; only the GPT-OSS
sampling default is updated in the current code candidate.

The v21 GPT-OSS profile uses `temperature: 1` and `top_p: 1`, the recommended
sampling values in the [official gpt-oss guidance](https://github.com/openai/gpt-oss#recommended-sampling-parameters).
The installed Ollama model also reports temperature 1. Earlier trials explicitly
overrode temperature to 0. Since this profile changes both sampling parameters,
its result cannot establish temperature's effect by itself. The current code
candidate now configures this profile as the sampling default. The PR remains a
draft pending the full control and integrated runs. The default model, verifier
reasoning, output budget, context, and timeout remain unchanged.

The draft and verifier still use the configured local model in separate calls.
There is at most one repair and no added model round trip. Transport and
output-budget failures propagate rather than becoming safe refusals. A supported
negative result remains answerable; merely measuring an outcome cannot establish
no effect. No default model, extraction, retrieval, embedding, or corpus setting
changes, so no reindexing is needed.

## Limits

These checks establish complete output structure and exact textual provenance,
not semantic entailment. The model can still misclassify a requested qualifier
as unasked, bind an excerpt to the wrong population or time period, or approve an
excerpt that does not answer the question. Exact evidence makes those decisions
auditable; it does not make them infallible. Independent human review and a fresh
paired replay are still needed before a model-promotion decision.

The 16-case development packet remains inspected development data. Thomas and
Emma's review is deferred, and this change does not complete that milestone or
establish v1 readiness.

## Control protocol

The live control runner now requires a complete, structurally valid and
evidence-linked verifier response for every semantic control, including negative
cases. A malformed rejection cannot count as a passing negative. The v16/v17
development diagnostics also audited requested-category labels; those labels
remain outside the verifier contract. The sole intentional deterministic
exception is a current-study claim citing a references section. Added pairs
test a supported dose and duration against titles that omit them. Expected answers are not supplied to the verifier.

The initial runs used all 21 synthetic controls once per model, sequentially.
The v15/v16 revisions first used seven targeted controls covering observed
failures and matched positive answers. The v17 revision first checked the
shared-population pair; v18 checked that pair and the matched dose pair before
expanding to the full set. Qwen3.5 uses
thinking disabled in both stages; GPT-OSS retains low drafting and medium verifier
reasoning. Historical controls used temperature zero and 12,288 context tokens.
The initial controls used 4,096 output tokens and a 180-second per-call timeout.
The full v18 GPT-OSS run used its 300-second application timeout; a separate
capacity diagnostic used 6,144 output tokens. The current GPT-OSS candidate uses
medium verifier reasoning, a 300-second timeout, 4,096 output tokens, and the
recommended sampling profile. These are development checks, not a new 16-question
benchmark or independent validation. Reports preserve exact model outputs,
evidence catalogues, fingerprints, settings and timings. Original and failed
outputs are not overwritten or retried.

Raw artifacts are ignored under
`evaluation-results/qualifier-evidence-20260929/` in the main checkout. A local
manifest records installed model digests, Ollama 0.34.4 and file hashes.

```bash
RAG_GROUNDING_MODEL=qwen3.5:9b \
RAG_DRAFT_THINK=false RAG_VERIFIER_THINK=false \
RAG_GROUNDING_SAMPLING='{"temperature":0}' \
RAG_GROUNDING_TIMEOUT_SECONDS=180 RAG_GROUNDING_OUTPUT_TOKENS=4096 \
uv run python -m scripts.check_grounding \
  --output evaluation-results/question-coverage-qwen35-new.json

RAG_GROUNDING_MODEL=gpt-oss:20b \
RAG_DRAFT_THINK=low RAG_VERIFIER_THINK=medium \
RAG_GROUNDING_SAMPLING='{"temperature":1,"top_p":1}' \
RAG_GROUNDING_TIMEOUT_SECONDS=300 RAG_GROUNDING_OUTPUT_TOKENS=4096 \
uv run python -m scripts.check_grounding \
  --output evaluation-results/question-coverage-gpt-oss-new.json
```

Each invocation needs a fresh output path. Before rerunning the 16 saved
questions, freeze a new schema-3 comparison protocol for this implementation;
the historical protocols cannot be reused by replacing their hashes.

## Development evidence

All results below are inspected development trials on fixed synthetic controls, not independent validation. A completed verdict means the response was structurally complete and evidence-valid; an output-limit or timeout failure is not a refusal or a pass. Reports preserve original attempts, and no result below supports promoting a model or declaring v1 ready.

| Revision / run | Result | What it established or failed to establish |
|---|---|---|
| v14 literal contract, Qwen3.5 9B | 18/21; three unsafe approvals | Accepted unsupported shared-population, mixed-attribution, and missing-comparison cases. Its five integrated cases passed 5/5, including the missing-dose refusal, but that does not offset the control failures. |
| v14 literal contract, GPT-OSS 20B | 0 complete controls | Timed out on the first control at 180 seconds. In the integrated packet it refused the missing-dose case, then timed out verifying the supported-dose case. |
| v15 targeted Qwen3.5 | 3/7 | The three unsafe approvals remained; it also refused the supported-dose control after emitting unasked fields as unsupported requirements. |
| v16 targeted Qwen3.5 | 5/7 outcome; 0/7 under later category audit | It rejected mixed attribution but still accepted shared-population and missing-comparison. A separate post-hoc audit found all 63 qualifier statuses `not_requested` and none of 16 minimum requested-category checks across the seven outputs. The audit was a development refinement, not a prespecified gate. |
| v16 targeted GPT-OSS | 6/7 | It accepted the unsupported shared-population case. All minimum requested categories were present in a later post-hoc audit; the unsafe scope approval remained. |
| v17 critical pair and high-reasoning diagnostic | Critical pair failed; high-reasoning run incomplete | The critical pair accepted the unsupported shared-population claim, and its supported counterpart omitted categories under the development audit. A separate 300-second, 4,096-token high-reasoning attempt exhausted the output budget on its first control before a complete verdict. |
| v18 critical GPT-OSS, 4 controls | 4/4 | Rejected unsupported shared-population and missing-dose cases, and accepted the matched supported counterparts. Complete, evidence-valid verdicts; 53.5–102.3 seconds per call at a 180-second timeout. |
| v18 full GPT-OSS, 4,096 output tokens | 2/21 complete | The first two controls passed. The third, `supported_requested_population`, hit the output limit before a verdict. The five-case integrated packet was therefore not run. This used the 300-second application timeout. |
| v18 capacity-targeted GPT-OSS, 6,144 output tokens | 2/2 | The supported requested-population and unsupported shared-population controls both produced complete expected verdicts at 300 seconds. This was a frozen capacity diagnostic, not a full control run. |
| v18 full GPT-OSS capacity follow-up, 6,144 output tokens | 2/21 complete | The first two controls completed; the second took 243 seconds. The next control again exhausted the output budget before a verdict. No integrated packet followed. Increasing the output cap did not complete the full run. |
| v18 targeted Qwen3.5 non-thinking, 9 controls | 8/9 | It rejected the missing-dose, missing-duration, shared-population, mixed-attribution, and missing-comparison cases and accepted the matched dose, duration, and population positives. It falsely refused the supported title-only case because it judged the adjacent author and result sentences insufficient to establish title attribution; the original v14 Qwen run accepted that case. |
| v18 GPT-OSS low-verifier-reasoning, 10 controls | 8/10 | It falsely refused `supported_requested_dose` and `supported_requested_duration` after confusing attribution labels with source scope. |
| v19 GPT-OSS low-verifier-reasoning, same 10 controls | 8/10 | The supported-duration refusal was fixed, but `supported_requested_dose` was still falsely refused and `unsupported_shared_population` was incorrectly accepted. Do not adopt low verifier reasoning. The attribution-mapping diagnostic was abandoned. |
| v20 GPT-OSS medium-verifier, flat grammar | 0 complete | The first `supported_requested_population` case failed with `OllamaOutputLimitError`. The 2,802-character grammar was abandoned; the v18 schema measured 4,004 characters on that case. |
| v21 GPT-OSS, recommended sampling profile, targeted 10 | 10/10 | All ten controls returned complete, schema-valid and evidence-valid expected verdicts. Calls took 48.2–157.9 seconds. This supports the profile as a code candidate, not independent validation. |
| v21 GPT-OSS, automatic-default full 21 | Running; no result recorded here | A fresh run uses the code candidate's automatic defaults without sampling, reasoning, budget, or timeout overrides. Its protocol fingerprint matches the targeted profile (`bd3bec30157ac6655268239ded6d08598c368bf7d3ef8cea0b0324711993a6c1`). The five-case integrated packet remains gated on this run. |

The 16-question human review packet has been reviewed by neither Thomas nor Emma; their review is deferred. These trials do not complete that milestone or establish v1 readiness. No model promotion is supported.

Reports, raw transport captures, and passages stay in the ignored `evaluation-results/qualifier-evidence-20260929/` and `evaluation-results/qualifier-evidence-20260930/` directories in the main checkout. The v21 records are dated 2026-09-30. No raw passages are reproduced here. The v14–v21 attempts were single-run development checks on inspected inputs; subsequent audits are explicitly labeled post-hoc. The 16-question packet is separate and has not been used here as independent validation.
