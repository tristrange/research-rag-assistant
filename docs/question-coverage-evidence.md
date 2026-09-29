# Question coverage and exact evidence

The v13 verifier selected its own list of question requirements. In the earlier
Qwen3.5 non-thinking control, it accepted an effect summary for “At what dose did
treatment delay weight loss in the cited Smith study?” The reference title gave
the effect but no dose. The verifier omitted dose from its requirements, so code
had nothing to reject. The original comparison and raw report remain unchanged.

## v18 contract

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

The original verifier prompt, field order, and 300-character reason budget are
preserved, with instructions for the new fields appended. Earlier attempts to
replace this with a large fixed checklist or a new requirement format failed
live controls. The final approach keeps those semantic assessments intact while
adding the whole-question and exact-evidence guards.

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
development diagnostics also audited requested-category labels, but those labels
are not part of the final verifier contract. A label can expose an omission without
establishing whether the model assessed its scope correctly. The sole
intentional deterministic exception is a current-study claim citing a references
section. Added pairs test a supported dose and duration against titles that omit
them. Expected answers are not supplied to the verifier.

The initial runs used all 21 synthetic controls once per model, sequentially.
The v15/v16 revisions first used seven targeted controls covering observed
failures and matched positive answers. The v17 revision first checked the
shared-population pair; v18 checked that pair and the matched dose pair before
expanding to the full set. Qwen3.5 uses
thinking disabled in both stages; GPT-OSS retains low drafting and medium verifier
reasoning. Both use temperature zero, 12,288 context tokens, 4,096 output tokens,
and initially a 180-second per-call timeout. The full v18 GPT-OSS run uses its
existing 300-second application default, with a fresh protocol and report. These
are development checks, not a new 16-question benchmark or independent validation. Reports preserve exact model
outputs, evidence catalogues, fingerprints, settings and timings. Original and
failed outputs are not overwritten or retried.

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
RAG_GROUNDING_SAMPLING='{"temperature":0}' \
RAG_GROUNDING_TIMEOUT_SECONDS=300 RAG_GROUNDING_OUTPUT_TOKENS=4096 \
uv run python -m scripts.check_grounding \
  --output evaluation-results/question-coverage-gpt-oss-new.json
```

Each invocation needs a fresh output path. Before rerunning the 16 saved
questions, freeze a new schema-3 comparison protocol for this implementation;
the historical protocols cannot be reused by replacing their hashes.

## Initial v14 development results

The first literal-contract runs on 2026-09-29 did not meet the rollout gate.
Qwen3.5 9B completed all 21 controls, passing 18/21. It incorrectly accepted
three unsupported cases: `unsupported_shared_population`, `mixed_attribution`,
and `missing_comparison`. Its five prespecified integrated cases passed 5/5,
including refusal when a requested dose was absent. Those five cases do not
override the control failures.

GPT-OSS 20B's 21-control run timed out on its first case at the 180-second
per-call limit, with zero completed controls. Its integrated run correctly
refused the missing-dose case, then timed out during verification of the
supported-dose case. The run therefore did not complete its five-case packet.

Both models used temperature zero, 12,288 context tokens, 4,096 output tokens,
and a 180-second call timeout. Qwen3.5 used thinking disabled for drafting and
verification; GPT-OSS used low drafting and medium verifier reasoning. The
grounding prompt fingerprints were `409b0794…de04090` for Qwen3.5 and
`c388a6a4…fd87f48` for GPT-OSS; the integrated reports share probe fingerprint
`d69e86e8…891fe42`. In Qwen's integrated run, the four verifier calls completed
with 859–1,091 generated tokens and about 79–104 seconds of total model-call time per
call, excluding draft calls. This is material latency for the verified path.

These are inspected development trials, not independent validation or grounds
for model promotion. The original reports, including failed runs, remain
preserved under `evaluation-results/qualifier-evidence-20260929/` in the main
checkout. No raw passages are reproduced here.

A schema-in-prompt-only diagnostic reduced Qwen response times to 29–35 seconds
but still accepted the mixed-attribution control. A subsequent v15 seven-case
trial added assessments before decisions and explicit scope rules. It passed
3/7: the three unsafe approvals remained, and the supported-dose control was
incorrectly refused because unasked fields were emitted as unsupported objects.
Those reports are preserved as diagnostics; they are not replaced by later runs.
The v16 flat statuses and separate bindings removed that mixed-type choice,
but the subsequent controls still failed.

## Revised development checks

The v16 seven-case Qwen trial passed 5/7 by accept/refuse outcome. Mixed
attribution was rejected, but shared-population and missing-comparison cases
were still incorrectly accepted. All 63 qualifier statuses were `not_requested`,
including explicit dose and study requests. These results do not establish that
the fixed checklist is being used correctly. This prompted the additional
requested-category criterion in the runner; it is a development refinement,
not a criterion prespecified before these diagnostics. Original reports remain
unchanged. No Qwen model promotion is supported by these checks.

The v16 GPT-OSS targeted trial also accepted the shared-population claim. The
fixed checklist therefore did not resolve the scope error on either model. The
v17 revision returned to concise, question-specific requirements while retaining
the mandatory full-question and exact-evidence checks. Its failed results are
recorded below.

GPT-OSS completed the v16 targeted packet with 6/7 accept/refuse outcomes and
all minimum requested categories present in a subsequent audit. Its sole unsafe
approval was the shared-population control; calls took 58–112 seconds. Qwen's
seven outputs contained none of the 16 minimum category checks across the packet,
so it passed 0/7 under that subsequent audit. The audit is saved separately from
the original reports and is explicitly a development refinement.

The fresh v13 verifier from `main` rejected the unsupported shared-population
claim and accepted its supported counterpart in 30.5 and 31.4 seconds. This
confirms the observed revisions need to preserve that assessment. The baseline
requirement statuses were positive, but its overall and claim reasons correctly
identified the missing population support and rejected the answer. The v17
critical pair did not meet the gate: it accepted the unsupported claim, and its
supported counterpart omitted categories under the development audit.

A separate v17 high-reasoning diagnostic used a 300-second call timeout with the
same 4,096-token output cap. It exhausted that output budget on the first control,
so no complete verdict was obtained. The failed report is retained; this is not
evidence for adopting higher reasoning effort or increasing the output cap.

## v18 development results

The four critical GPT-OSS controls passed 4/4 with complete, evidence-valid
verdicts: the unsupported shared-population claim and missing-dose answer were
rejected, while their supported counterparts were accepted. Calls took 53.5–102.3
seconds at the 180-second timeout. These are fresh development trials on inspected
inputs; the full control set and integrated checks are still pending.
