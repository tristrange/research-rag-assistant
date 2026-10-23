# Grounding refusal diagnostics

## Initial diagnostic plan

PR #16 is merged. At baseline `7e91954`, replay the unchanged saved sources for
`kpc-food-intake` and `cited-ceramide-study` from both sample-paper arms. Run the
three-seed report first, then six seeds, once per case. This includes the two
observed refusals and their successful paired contexts. Preserve original reports
and every replay, including failures. Do not re-retrieve, rejudge, or alter prompts
before inspecting these traces.

Pin GPT-OSS 20B, draft reasoning `low`, verifier reasoning `medium`, and all other
application settings to the original protocol. Record draft, verification and
repair stages through the existing replay runner. Classify the refusal stage:
initial drafting, deterministic citation validation, semantic verification, or
bounded repair. A replay is a new generation trial, not a recovered trace of the
original answer; a changed outcome cannot establish the original failure cause.

Use findings to select a narrow next change only if the evidence supports one.
Do not weaken evidence, attribution or question-qualifier checks merely to improve
answer coverage. Any subsequent prompt/code experiment is separate from these
baseline replays and from the first-run evaluation in PR #16.

## Narrow verifier experiment

Both original refusal outcomes reproduced. The three-seed KPC refusal occurs in
the initial draft. The six-seed cited-title draft is correct, but verification
invents unsupported requirements for unspecified population, sex, species, study
design, dose and comparison; repair then declines. Its own `answers_question`
flag is true, but the deterministic requirement gate correctly rejects the
inconsistent verdict.

Clarify the verifier prompt and requirement-schema descriptions to enumerate only
requirements asked by, or necessary to identify the target of, the actual question.
Unasked dimensions are omitted, never automatically marked supported. Keep the
strict requirement gate and attribution/quote checks unchanged. Do not change
the draft prompt or add retries for initial refusals in this experiment.

Run one new replay of the same four saved contexts, then the live adversarial
verifier controls, including paired cited-title questions with and without a
requested dose. Keep every result. This is targeted development validation, not a
new benchmark or a reason to enable API expansion by default.

## First candidate result and revised validation plan

The first candidate correctly verifies the six-seed cited title, but regresses the
six-seed KPC answer: it treats “Was food intake lower?” as requiring lower intake,
rejects the supported negative result, and repair declines. The three-seed KPC
initial-draft refusal persists. Preserve this failed candidate and its controls.

A second clarification will distinguish evidence that determines the answer from
evidence affirming a yes/no proposition. A supported negative or unchanged outcome
satisfies a yes/no question; absent outcome evidence does not. Add paired synthetic
controls for a supported negative answer and an unsupported negative claim. Rerun
the four fixed contexts once and all sixteen controls without changing sources,
draft instructions, deterministic gates or call limits.

## Results

Each row below is one new generation trial over the same saved question and source
passages. “Answered” means the final output passed the existing checks; it does
not imply the first draft or first verification passed.

| Verifier wording | Expanded seeds | KPC food-intake question | Cited ceramide title question |
| --- | ---: | --- | --- |
| Baseline (v12) | 3 | Refused in initial draft | Answered |
| Baseline (v12) | 6 | Answered | Refused after verifier invented unasked requirements |
| First candidate | 3 | Refused in initial draft | Answered |
| First candidate | 6 | Refused after verifier demanded a positive result | Answered |
| Revised candidate (v13) | 3 | Refused in initial draft | Answered |
| Revised candidate (v13) | 6 | Answered after one bounded repair | Answered |

The revised verifier lists only actual question requirements and treats cited
evidence of an unchanged outcome as sufficient to answer a yes/no question with
“no”. It still rejects a negative answer when the source only says the outcome
was measured. The live verifier controls passed 16/16, including paired checks
for unasked versus requested dose, supported versus missing negative-result
evidence, requested population and duration, numerical accuracy, attribution,
and unsupported embellishment. The first candidate passed its 14 controls yet
regressed KPC, which is why the negative-answer pair was added.

The revised six-seed KPC first verification still inconsistently sets
`answers_question=false` even while marking its requirement and claims supported.
The existing bounded repair produced an accepted answer. The three-seed KPC
refusal remains in the initial draft, before verification. These controls are
assistant-authored, inspected development cases with one run each, not an
independent benchmark or a broad accuracy estimate. This result does not justify
making neighbor expansion the API default.

All JSON reports below are retained locally in the ignored `evaluation-results/`
directory; they are not included in this PR. SHA-256 hashes identify the exact
saved trials. The code records its prompt/schema fingerprint in each report.

| Report pair | Three-seed SHA-256 | Six-seed SHA-256 | Grounding fingerprint |
| --- | --- | --- | --- |
| `refusal-diagnostic-*-baseline.json` | `6cb81ed6f1dddf3d172cda95ad0cf335d1490581781fec1d0361d55c830be72f` | `15bf3c6d867fc1418bc3baa6d47f03516b60ba7fdeab6b5ba7f38c8fc3c1111d` | `3ccdde2ef9279ebf736686e88cf5146c4c7dec6d78fda19b42954aca9959eac7` |
| `refusal-diagnostic-*-candidate.json` | `1021760c7e35ccad627e2804c53640352372964966e4b5803b74b802306c742e` | `f8a1d8c016271393af4c06bb93de0cf7cf021ccefbe8e6d98a8bf6580733976b` | `a41c00656cd99cd4b776ae4ce5042606f0b08683b875501f479da7ba88111373` |
| `refusal-diagnostic-*-revised.json` | `da18ddffb4018c51a0e92ce507a92e4d5920298f45de1cad12ab9475a7466e2a` | `427647323c18e138524718991630abf6bd4bacc3aa725a4f8a78ea73e0af3a3c` | `9808eeca3e7f1cbc8c2bef56b01d11869eb20f67ff97e49c11376a57ff494646` |

`refusal-verifier-revised-controls.json` passed all 16 checks and has SHA-256
`92d4b0fa5cf62cbb741d317ea938401af99b6ee409655d689f92872f4bc9c5d7`.
The first-candidate 14-check report is `refusal-verifier-candidate-controls.json`
(SHA-256 `36cee12b7ac257847323b647c5686cc4b7aa284bb640102df645d3e6f9d14b60`).

To repeat a fixed-source replay from a retained first-run report, use the same
model settings as the original evaluation and a fresh output path:

```bash
RAG_GENERATOR_MODEL=qwen3:8b RAG_GROUNDING_MODEL=gpt-oss:20b \
RAG_JUDGE_MODEL=qwen3:8b RAG_DRAFT_THINK=low RAG_VERIFIER_THINK=medium \
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
uv run python -m scripts.replay_grounding \
  evaluation-results/verified-context-sample-k6-first.json \
  --case kpc-food-intake --case cited-ceramide-study \
  --output evaluation-results/refusal-diagnostic-k6-new-trial.json

RAG_GROUNDING_MODEL=gpt-oss:20b RAG_VERIFIER_THINK=medium \
uv run python -m scripts.check_grounding \
  --output evaluation-results/refusal-verifier-new-controls.json
```

Use the corresponding `verified-context-sample-k3-first.json` for three seeds.
The replay does no retrieval or judging and preserves the saved source passages;
each new run may differ despite unchanged settings. Local verification also ran
164 unit tests and strict mypy over 58 tracked Python files successfully.

## Verification diagnostics

`grounded_answer(..., diagnostics=...)` records one sanitized `VerificationTrace`
per stage: contract fingerprint, stage, attempt (initial or repair), elapsed
milliseconds, parse status, stable failure category, and prompt/output token
counts when Ollama reports them. The record never contains prompts, questions,
source passages or freeform model output. `invalid_json` and `invalid_schema`
identify malformed or schema-invalid responses; an evidence refusal is
`draft_unanswerable`, `verifier_rejection` or `proof_rejection`; `output_limit`
and `transport_error` are recorded but still propagate exactly as before.

Replays write these records only when asked:

```bash
uv run python -m scripts.replay_grounding \
  evaluation-results/verified-context-sample-k6-first.json \
  --case kpc-food-intake --case cited-ceramide-study \
  --diagnostics --output evaluation-results/diagnostic-k6-new-trial.json
```

The sidecar is `diagnostic-k6-new-trial.diagnostics.json`. It is development
tooling, not a new benchmark, and it does not change generation or acceptance.

### Recorded 12 October development failures (analysis only)

These labels are retrospective. The raw reports remain unmodified in the ignored
local report directory and no validation was rerun.

| Recorded run | Observed failure | Diagnostic stage/category |
| --- | --- | --- |
| Verifier comparison, current arm | Activin repair verification used a whole-response JSON fence; strict parsing rejected it and the case refused | `repair_verification`, `invalid_json` (`malformed_json`) |
| Verifier comparison, current arm | Mitochondrial final proof demanded repeated experimental identity across adjacent same-source sentences | `verification_proof`, `proof_rejection` |
| Verifier comparison, compact arm | Ucp1 refused during initial drafting | `draft`, `draft_unanswerable` |
| Draft fidelity, cohort-2 inoculum | Both verifiers copied the question with U+2011 instead of the original U+002D, so question binding rejected both drafts | `verification`/`repair_verification`, `verifier_rejection` |
| Draft fidelity, mitochondrial comparison | Initial verifier selected only the VDAC1 excerpt, so final proof rejected the missing Bax/PPID support; repair then overstated rescue and repair verification rejected it | `verification_proof`, `proof_rejection`; `repair_verification`, `verifier_rejection` |

Neither run recorded an uncaught error, transport timeout or output-limit failure.
The verifier comparison's fenced response is the failure that motivated v41's
single-fence handling; the fence check is an analysis of that retained response,
not a new generation trial.

## 22 October adjacent-context proof check

The r3 mitochondrial case showed the isolated proof rejecting a repair claim
because the population was established in one approved excerpt and the Bax/PPID
outcome in another excerpt from the same claim. The v44 proof instructions add
document/page/chunk provenance and read all citations for one claim together
when they come from the same source chunk. The claim text itself must state every
requested qualifier; qualifier combinations across different source chunks,
experiments, conditions, documents or claims remain prohibited.

The retained r3 repair claim with the population qualifier was accepted. Three
controls were rejected: the same evidence with the population removed from the
claim text; an outcome reported for control myoblasts instead of the requested
Mfn1KD myoblasts; and a Bax result from a different source chunk combined with
the VDAC1 excerpt. These are fixed-draft proof checks, not a final end-to-end
replay; pipeline-level answer completeness remains open. This is development
regression evidence, not fresh reserved validation or independent review. Raw
artifacts remain in the ignored `evaluation-results/` directory; the public
aggregate and artifact hashes are in
[`benchmarks/verifier-adjacent-context-development-2026-10-22.json`](../benchmarks/verifier-adjacent-context-development-2026-10-22.json).

### Follow-up: merged source windows (v45)

Review found that context expansion can merge several stored chunks into one
returned source. Its `chunk_index` identifies only the start of that window;
it cannot establish the original chunk of each quote. The v45 candidate labels
this field `source_window_start_chunk` in the isolated proof and removes the
same-chunk inference. The quoted wording must establish the connection between
scope and outcome; shared metadata, adjacency and omitted intervening text are
not evidence of continuity. The public citation shape and retrieval stay unchanged.

Source review also found that the retained v44 repair claim's PPID wording
strengthened no rescue into no effect on expression. Its earlier proof approval
is an observation, not evidence that every detail was supported. The v45 positive
control uses no-rescue wording, and the original stronger claim is retained as a
rejection control. A synthetic merged window hides a separate control-population
experiment between selected quotes to test the review finding directly.

The source-faithful positive control was rejected, so v45 does not resolve the
known refusal. Its gate blocks the eight-case grounding replay. Keep PR #92 in
draft; do not merge this candidate or count the blocked replay as validation.
The next implementation should preserve actual per-excerpt origins or enough
quoted connecting context, rather than infer continuity from a window's starting
chunk number. The local database was also unavailable during setup; saved-source
checks do not establish that current retrieval works end to end.

The frozen [v45 protocol](../benchmarks/verifier-proof-window-v45-protocol-2026-10-22.json)
and [results](../benchmarks/verifier-proof-window-v45-results-2026-10-22.json) record
four calls in 139.71 seconds: the positive was rejected and all three rejection
controls were refused. These refusals often cited missing population scope, so
they do not establish that each targeted failure mode was specifically detected.

### Complete displayed source context (v49)

The final candidate removes the experimental permission to transfer scope across
separate excerpts. Its proof instruction text matches merged main. Instead, the
application assembles the entire source span between selected quotes from one
source, including every intervening word. Proof and display use that same span.
This reveals an experiment boundary that sentence selection could otherwise hide.
Ambiguous multi-quote positions or context exceeding the 4,000-character quote
limit reject the attempt; sources never merge. This assembly can add source
context to a citation, but cannot add facts to the answer or satisfy deterministic
checks that still use only selected evidence IDs.

Named alphanumeric question identifiers must also occur in the displayed answer.
A necessary lexical guard rejects absence-of-effect and complete-restoration
wording without explicit matching strength language in the selected excerpts.
It handles specified English forms and immediate negation; it is not entailment
or alias resolution and may refuse valid paraphrases. The existing semantic
verifier, strict proof, duration checks and single repair remain required.
The proof reason limit is 1,000 diagnostic characters; approval types, required
fields and extra-field rejection stay strict. No timeout or token budget changed.

The frozen v49 check passed its seven controls: one supported comparison, omitted
population, no-effect overstatement, hidden experiment boundary, unsupported full
rescue, different population and cross-document scope transfer. Three negative
controls were rejected deterministically and four controls used live proof calls.
Earlier v46–v48 candidates failed their controls and never started their broader
runs; their original artifacts and failures remain preserved in the final record.

The normal document-scoped retrieval-to-answer path then ran all eight known r3
questions once, read-only against the existing index. It used 27 chat calls in
1,212.32 seconds including controls. Two answerable questions returned answers;
four answerable questions were refused, and both unanswerable controls refused.
No pipeline error occurred. This is not a performance baseline or a paired
comparison, and the unchanged five-of-six product target is not met.

The inoculum proof incorrectly demanded an explicit per-mouse quantifier before
repair refused. Ucp1 refused during drafting. The mitochondrial initial and repair
drafts both overstated no rescue as no effect, and the strength guard stopped
both. Activin repair still omitted selected duration evidence. These are retained
completeness failures; the successful fixed-draft control does not turn them into
successful end-to-end answers.

See the [frozen protocol](../benchmarks/verifier-context-v49-protocol-2026-10-22.json)
and [results](../benchmarks/verifier-context-v49-results-2026-10-22.json). Source
review and engineering checks establish the scope of this PR, not general answer
accuracy. Fresh reserved validation, optional human review and a performance
baseline remain outstanding; local v1 stays open.
