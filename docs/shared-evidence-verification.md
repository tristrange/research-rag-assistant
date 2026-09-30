# Shared evidence and measurement checks, v22–v24

Status: bounded implementation complete and ready for review; v24 GPT-OSS paper
validation is incomplete. Model promotion and v1 acceptance remain deferred.

## Change

Two claims citing the same retrieved source previously received duplicate copies
of its exact evidence spans with different claim-owned IDs. A verifier selecting
the first copy for the second claim was rejected even though both claims cited
the same source. This caused avoidable glucose-protocol and cited-title refusals
in the v21 development comparison.

The v22 catalogue gives each span one ID per source, in source catalogue order.
It lists every claim allowed to use that source. Each claim also receives its
eligible IDs in the prompt; the generation schema binds its claim index and IDs,
and runtime validation independently rejects evidence from an uncited source.
Identical wording in distinct sources retains distinct IDs. Source eligibility
establishes provenance, not semantic support for a claim.

Draft and verifier instructions explicitly distinguish the measured outcome from
its numerical effect. A regional tissue-weight percentage cannot establish total
fat mass; ATPase activity cannot establish ATP concentration. An accurate statement
about a different outcome must still fail question relevance and coverage.
No outcome is inferred by keyword matching or numerical postprocessing.

The single bounded repair, exact quote matching, attribution rules, model defaults,
retrieval and evaluation judge remain unchanged. No reindex
is needed. The new grounding fingerprint prevents resuming old reports under this
contract. Historical v21 protocols and artifacts are preserved.

## Prespecified development checks

Run Qwen3.5 9B first with thinking disabled, temperature zero, 120-second per-call
timeout; then GPT-OSS 20B with low draft and medium verifier reasoning, temperature
1 and top_p 1, 300-second timeout. Both use 12,288 context and 4,096 output tokens.
Installed digests, runtime, settings and fingerprints are frozen in
`benchmarks/shared-evidence-v22-protocol.json` before live calls. Qwen3 is not an
answer candidate in these checks. The judge is recorded for recorder compatibility
but is not called; this is a targeted development regression check, not a new
model-performance comparison.

For each model, run one positive two-claim check with disjoint cited sources to
check the per-claim grammar. Then run all 30 synthetic controls once (29 model
verifier calls and one intentional deterministic rejection). The nine additions
cover supported and substituted measurements, accurate off-target answers, and
two-claim methods/title answers sharing a source. Require complete schema- and
evidence-valid verdicts; malformed rejection is not a passing semantic refusal.

An incomplete disjoint-source or control verdict, transport failure, compatibility
failure or no accepted positive control stops that model's paper arm. Complete
semantic failures permit diagnostic generation but must be reported. Preserve
failed output and continue the next model without manual retries or settings
changes. Do not promote either model from these checks.

For eligible arms, replay only the four saved questions and source bundles in
`benchmarks/shared-evidence-regressions.json`: glucose protocol, cited title,
total fat mass and BAT ATP concentration. Keep original labels and saved passages;
no new retrieval or reference answers enter candidate prompts. The expected audit
is supported methods/title answers, total-fat support from its actual cited
measurement, and refusal where the supplied context lacks the ATP result. An
accurate ATPase response alone does not satisfy the ATP question.

Inspect every final answer and relevant trace against its actual citations.
Completion alone is insufficient: classify supported answer, unsupported assertion,
off-target answer, avoidable refusal or safe refusal against incomplete context.
These known development cases and assistant inspection do not replace Thomas and
Emma's deferred human review or independent final validation.

Use fresh ignored report directories and freeze observer, scripts, protocol,
source-report hashes and runtime metadata locally before calls. Record replay
hashes at completion. Never update an earlier experiment's protocol or reports.

## Reproduction

The v22 reproduction requires application revision `6228f68`, matching its frozen
protocol. Use fresh report paths.
The source root must contain the original ignored reports named by the selection.
These commands use the same candidate settings as the recorded checks:

```bash
RAG_GROUNDING_MODEL=qwen3.5:9b RAG_DRAFT_THINK=false RAG_VERIFIER_THINK=false \
RAG_GROUNDING_SAMPLING='{"temperature":0}' \
RAG_GROUNDING_TIMEOUT_SECONDS=120 RAG_GROUNDING_OUTPUT_TOKENS=4096 \
uv run python -m scripts.check_grounding \
  --output evaluation-results/shared-evidence-qwen35-new.json

RAG_GROUNDING_MODEL=gpt-oss:20b RAG_DRAFT_THINK=low RAG_VERIFIER_THINK=medium \
RAG_GROUNDING_SAMPLING='{"temperature":1,"top_p":1}' \
RAG_GROUNDING_TIMEOUT_SECONDS=300 RAG_GROUNDING_OUTPUT_TOKENS=4096 \
uv run python -m scripts.check_grounding \
  --output evaluation-results/shared-evidence-gpt-oss-new.json
```

For eligible arms, replay the four-case selection with the candidate environment
above. For example, the GPT-OSS paper check is:

```bash
RAG_GROUNDING_MODEL=gpt-oss:20b RAG_DRAFT_THINK=low RAG_VERIFIER_THINK=medium \
RAG_GROUNDING_SAMPLING='{"temperature":1,"top_p":1}' \
RAG_GROUNDING_TIMEOUT_SECONDS=300 RAG_GROUNDING_OUTPUT_TOKENS=4096 \
uv run python -m scripts.record_grounding_replays \
  --manifest benchmarks/shared-evidence-regressions.json \
  --protocol benchmarks/shared-evidence-v22-protocol.json \
  --source-root /path/to/main-checkout \
  --output-dir evaluation-results/shared-evidence-gpt-oss-recorded-new
```

The additional disjoint-source preflight script, input and report are retained
in the ignored experiment directory. Reproducing that exact preflight requires
access to these local artifacts; it is not available from a fresh checkout alone. Every future trial needs fresh output paths;
changed application code or settings require a new protocol, not edited historical
fingerprints. Report complete semantic failures even when diagnostic paper generation
is allowed, and inspect actual final citations rather than counting completion.

## Results

The implementation and prespecified live protocol were committed before calls as
`6228f68`, based on merged PR #38 (`0791cef`). Unit tests passed 277/277 and strict
mypy passed all 61 files. Static reviews found no source-boundary or control-runner
defect. Model behavior still requires the separate live evidence below.

Qwen3.5's disjoint-source positive preflight passed with complete per-claim evidence
bindings. The full control set completed 27/30 expected outcomes: all 29 model
verdicts were structurally complete and evidence-ID valid, plus the intentional
deterministic rejection. All seven measurement controls passed. The shared-source
methods control passed; the shared-source cited-title control was refused because the verifier demanded an
explicit title marker. The fixture presents a reference entry without a title
delimiter, so this expected-positive failure has some fixture ambiguity. Its other failures were an inconsistent attribution rejection on the
supported-duration control and an unsafe extension of the long-term chow-fed
qualifier to the short-term result. These are semantic failures, not ID errors;
the paper arm is diagnostic and does not support promotion. In the off-target
regional-fat control, the expected rejection occurred but the verifier also
marked the narrow factual claim unsupported and said the question was answered.
Outcome matching alone therefore does not establish that every verdict field
was semantically correct.

Both Qwen3.5 replay files completed, covering all four paper cases. Assistant citation/trace inspection found
three complete supported answers (methods, cited-study attribution and total fat
mass) and one safe refusal against the incomplete ATP-concentration context.
The cited-study response includes supported details from the current paper's
statistical-methods passage to distinguish it from the external publication.
No repair or structural evidence-ID error occurred. The ATP refusal was an
initial draft decision, not a verifier verdict; it does not establish absence
from the full paper. This replaces the off-target ATPase answer observed in its
v21 trial, but the small known set is not an independent validation result.

GPT-OSS disjoint-source preflight passed. It completed 25/25 expected control
outcomes, then exhausted its 4,096-token output budget on
`off_target_atpase_activity_for_atp_concentration_question`. The failed call took
194.4 seconds, returned `done_reason=length`, and had empty final content. It was
not a timeout or a semantic refusal. Five controls are incomplete; the prespecified
paper gate skipped all four GPT-OSS paper cases. The original overall run is
incomplete, not a 25/25 full-suite success. Raw reports, replay completion digests, audits and HTTP calls are retained
in the ignored `evaluation-results/shared-evidence-v22-20260930/` directory in the
main checkout. The local freeze pins 48 files and has SHA-256
`94800c1c81bfa946412a5a56b017df64c194f97fc962689e1f193c98de2ee2a1`.
Original sources and historical study artifacts are unchanged.

## Prespecified v23 schema-visibility follow-up

After the preserved v22 output-limit failure, the verifier prompt now includes
its compact bounded JSON schema as well as sending the same schema to Ollama's
`format` field. The failed trace distinguished ATPase from ATP early but spent
its remaining reasoning guessing field names and the nested response shape.
This is a plausible mitigation, not a proven cause or a promise of no future
output-limit failures. It follows [Ollama's structured-output guidance](https://docs.ollama.com/capabilities/structured-outputs).

The application contract is v23 and a separate
`benchmarks/shared-evidence-v23-protocol.json` freezes its code and candidate
fingerprints. All model, reasoning, sampling, timeout and token settings remain
identical to v22. Preserve v22 inputs, reports, failure and reconciliation.

Run the disjoint-source positive preflight and a fresh 11-control selection for
each candidate: all nine new measurement/multi-claim controls, plus
`supported_requested_duration` and `unsupported_shared_population`. This includes
the failed GPT control and all three Qwen expected-outcome failures. The original
21 controls are not rerun in full; this follow-up cannot claim a new 30/30 result.
Use a new ignored `shared-evidence-v23-20260930/` directory, freeze inputs before
calls and apply the same completeness, semantic-failure and paper gates. No
retries, setting changes or model promotion. Replay and inspect the same four
paper questions only for eligible arms. Human review remains deferred.

The v23 offline suite passed 278 tests; strict mypy passed 61 files. Both
preflights and all 11 selected model verdicts completed for each candidate. Both
matched 10/11 outcomes. Qwen still accepted the unsupported shared population
qualifier. GPT accepted the regional-fat answer to the total-fat question: its
claim verdict cited the regional result (ID 2), while whole-question coverage
cited the separate total-fat result (ID 1). This is an unsafe off-target
acceptance, despite valid evidence IDs. No output-limit failure occurred in this
run; one follow-up cannot establish that schema visibility prevents them.

Assistant citation inspection of the four paper cases found three supported
answers and one context-limited ATP refusal for Qwen. GPT had two supported
answers, one safe ATP refusal, and a supported cited-literature answer whose
explicit distinction from current-paper experiments was incomplete. GPT methods
and fat answers used the existing repair after malformed drafts. These diagnostic
results do not support model promotion. The schema is included before the untrusted input, and a regression
test checks that it equals the dynamic API schema. The response shape and runtime
source-boundary validation are unchanged.

## Prespecified v24 evidence-link follow-up

The supported whole-question evidence IDs must now be a subset of the IDs used
by approved claim verdicts. A verifier cannot approve an answer from an extra
excerpt that was not used to support the rendered claims. The prompt explicitly
instructs this relationship, and deterministic validation enforces it after
all claims pass. Complete negative verdicts remain structurally valid. This is
an evidence-link consistency gate, not proof of semantic relevance or truth.
The shared-population failure can still occur when both assessments misread the
same excerpt.

This is a stricter output contract: a valid answer whose verifier cites additional
whole-question excerpts must also attach them to its claim verdicts. It could
cause avoidable refusals. The cited-study paper case specifically tests this risk;
its v23 Qwen verdict used extra author/year IDs only for coverage. Runtime source
permissions, quotes and the single repair remain unchanged.

A new v24 fingerprint and `benchmarks/shared-evidence-v24-protocol.json` preserve
both earlier experiments. Run fresh disjoint-source preflights and the same 11
selected controls, followed by the same gated four-case replays for each model.
Settings are unchanged; no retries, promotion, new retrieval or judge calls.
The frozen local directory is `shared-evidence-v24-20260930/`. This is another
known-case diagnostic follow-up, not independent validation or a full-suite run.

Offline suite passed 279 tests and strict mypy passed 61 files. Both disjoint
preflights passed. Qwen completed 11 structurally/evidence-ID valid verdicts and
matched 10/11 expected outcomes; its shared-population false acceptance remains.
GPT attempted all 11 controls and matched 10/11 outcomes. Its misbound-ATP
rejection omitted the required `requested_answer.supporting_evidence_ids` field,
although both the embedded prompt schema and API format require it. The runtime
rejected that response, and the harness correctly counted an incomplete verdict
rather than a successful semantic refusal. The prespecified gate skipped GPT's
four paper cases. Overall v24 validation is therefore incomplete, not fully green.
There were no timeout or output-limit failures in this final run.

Qwen's paper audit again found three complete supported answers and one safe ATP
refusal against incomplete context, with no repair or structural failure. Every
accepted answer's coverage IDs stayed within the approved claim-verdict union.
The cited-work/current-methods answer used coverage `[4,9,10,11]`, matching its
claim evidence union and avoiding the anticipated extra-coverage refusal in this
known case. GPT's fresh off-target regional-fat control was rejected. Independently,
deterministic replay of the preserved unsafe v23 verdict was rejected by the new
coverage gate; this is a runtime regression check, not another model trial.

| Development run | Qwen3.5 control outcomes | GPT-OSS control outcomes | GPT-OSS paper arm |
| --- | --- | --- | --- |
| v22, full 30 controls | 27/30; three semantic mismatches | 25 complete expected outcomes, then output-limit failure | Skipped |
| v23, selected 11 controls | 10/11; shared-population false acceptance | 10/11; off-target regional-fat false acceptance | Diagnostic; two supported, one incomplete distinction, one context-limited refusal |
| v24, same selected 11 | 10/11; shared-population false acceptance | 10/11; one incomplete but safely rejected verdict | Skipped |

The safety changes are reviewable, with no implementation blocker found in static
reviews. These findings do not establish general verifier reliability. Default
GPT paper validation remains a follow-up, Qwen is not promoted, and Thomas and
Emma's review plus independent v1 validation remain outstanding. The stricter
coverage contract may refuse valid answers if a verifier fails to attach all
coverage excerpts to its claim verdicts.

The final protocol and code were committed before calls at `c928865`. Its local
freeze pins 49 files, with SHA-256
`596735846bb5f1f96a48af863827711e0a97a6cb0c91103a618deb1e90d45ced`.
The ignored v24 directory retains controls, raw HTTP calls, skipped-arm reason,
Qwen replay completion digests and citation audit, deterministic v23-rejection
replay and `reconciliation.json`. Reconciliation checks frozen revisions,
source-report inputs, completion hashes and audit bindings without altering
historical reports. The v23 freeze is retained separately with SHA-256
`f37e8efd1eb263d7cec02a1ddaabc8d3de11b4dba49e0a74bb5d87f6a007f9d0`.

### Reproduce the final targeted selection

At the v24 application revision, use fresh output paths. For GPT-OSS, the exact
11-control selection is:

```bash
RAG_GROUNDING_MODEL=gpt-oss:20b RAG_DRAFT_THINK=low RAG_VERIFIER_THINK=medium \
RAG_GROUNDING_SAMPLING='{"temperature":1,"top_p":1}' \
RAG_GROUNDING_TIMEOUT_SECONDS=300 RAG_GROUNDING_OUTPUT_TOKENS=4096 \
uv run python -m scripts.check_grounding \
  --output evaluation-results/shared-evidence-v24-gpt-new.json \
  --case supported_requested_duration \
  --case unsupported_shared_population \
  --case supported_total_fat_mass_35_percent \
  --case unsupported_total_fat_mass_24_percent \
  --case off_target_regional_fat_24_for_total_question \
  --case unsupported_atp_concentration_from_atpase_activity \
  --case off_target_atpase_activity_for_atp_concentration_question \
  --case supported_atpase_activity_29_percent \
  --case supported_atp_concentration_4_8_nmole \
  --case supported_multiclaim_gtt_methods \
  --case supported_multiclaim_cited_title
```

For Qwen3.5, use the same case flags and a fresh output path with the Qwen settings
above. The same paper recorder command applies using the v24 protocol instead
of v22 and a fresh output directory, subject to the completeness gate. The exact
local disjoint preflight and observer still require access to ignored artifacts.
