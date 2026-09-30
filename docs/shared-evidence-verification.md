# Shared evidence and measurement checks, v22

Status: implementation prepared; live development checks pending.

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

## Results

Pending. Raw reports and calls will remain ignored under
`evaluation-results/shared-evidence-v22-20260930/` in the main checkout.
