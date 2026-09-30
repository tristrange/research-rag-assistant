# Shared evidence and measurement checks, v22

Status: v22 run preserved with incomplete GPT-OSS controls; v23 schema-visibility
follow-up prespecified below.

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

The single bounded repair, whole-question check, exact quote matching, attribution
rules, model defaults, retrieval and evaluation judge remain unchanged. No reindex
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

Status: offline suite passed 278 tests; strict mypy passed 61 files. Live checks
are pending. The schema is included before the untrusted input, and a regression
test checks that it equals the dynamic API schema. The response shape and runtime
source-boundary validation are unchanged.
