# Evaluation evidence and inference records

New end-to-end answer reports use schema version 3. Fixed-source grounding replays
and their scored reports use version 2 of their own formats. These are local,
Git-ignored artifacts under `evaluation-results/`; accepted quotes and source
passages may contain copyrighted paper text.

## Accepted evidence

Each generated checkpoint and completed result retains `claim_evidence`: the final
claims approved by the grounding verifier, their attribution, and its selected
quotes. Each quote's zero-based `source_index` points into that result's `sources`.
Loading checks source bounds and exact, case-sensitive text membership after
whitespace normalization. It does not rerun semantic verification or certify the
answer's correctness.

- `null` means evidence was not captured or the answer used plain mode.
- `[]` means evidence capture completed with no approved claims, such as a verified
  insufficient-evidence response.
- A populated list contains only final approved evidence, including the final
  approved correction if grounding repaired the draft.

Human review packets show this evidence separately from all retrieved passages and
the reference labels. A machine-approved claim still needs human review for the
v1 milestone. Replays capture new approvals directly; they never reuse the original
answer's approvals or reconstruct approvals from rejected drafts.

## Model and runtime identity

`runtime_before` and `runtime_after` record the observed Ollama version and installed
model digests, keyed by requested model name. Implicit `:latest` tags are resolved
when reading the installed model list. Metadata reads use short timeouts and do
not run inference, download models, or change the index. Unavailable or malformed
metadata remains `null`.

An observed identity change prevents the run from publishing aggregate metrics.
These are start/end observations, not continuous attestation: missing metadata or
a model changed and restored between observations cannot establish a stable runtime.

Resume rechecks every previously known model digest and Ollama version; a changed
or unavailable known identity requires a new evaluation. `resume_runtime` records
the new process's start observation. The original report remains untouched, and
historically unknown identities remain unknown. Review configuration fingerprints
include `runtime_before` when captured; legacy fingerprints remain unchanged.

## Timing

`answer_ms` still covers retrieval, reranking, model loading, drafting, verification
and any correction. `judge_ms` covers the separate abstention and grading work.
Calibration and runtime metadata probes are outside those timings. Fixed-source
replay `elapsed_ms`/scored `answer_ms` excludes retrieval.

Each result also records `answer_calls` and `judge_calls`. Calibration has its own
`calibration_calls`; failed end-to-end runs retain `failed_stage` and `failed_calls`.
Failed replays retain the attempted calls even when no answer was produced.

Each call records its operation, requested and returned model names, wall-clock
`elapsed_ms`, and `complete`/`failed` status. When Ollama supplies them, records also
contain token counts, completion reason and total/load/prompt-evaluation/generation
durations, converted from nanoseconds to milliseconds. Missing, negative, nonfinite
or incorrectly typed metadata stays `null`, rather than becoming zero.

`complete` means the provider envelope passed validation; it does not mean the
generated content passed its grounding or grading schema. A timed-out request has
wall-clock timing but usually no server timing. Ollama durations are provider
measurements and do not need to sum to client wall time; do not add them to it.
Call records contain no prompts, answers, source text, upstream bodies or error
messages. Capture is context-local and enabled only by evaluation/replay code;
normal API requests do not collect these records or probe runtime metadata.

## Older artifacts

New answer reports record `settings.reserve_vector_page`: whether normal verified
reranking reserves one vector-ranked passage within `top_k`, preferring a
document/page absent from the reranked selection. If no new page exists, it uses
the highest unselected vector candidate. The flag records the policy, not whether
another page was actually found. Legacy reports load with this flag false, and
frozen review configuration hashes omit it when it was absent. Resuming requires the same candidate count and selection policy; an old
pure-rerank report cannot continue under today's verified retrieval defaults.
Fixed-source replays retain the saved retrieval settings because they do not run
retrieval, while recording the current grounding settings for the new generation.

Schema-v2 end-to-end reports and unversioned older replays still load. Missing claim
evidence, call records and runtime snapshots become `null`, never reconstructed
from today's defaults or old traces. An explicitly captured empty call list means
no adapter calls occurred in that phase; `null` means no measurement exists.

Resuming writes a new schema-v3 report and preserves old results and pending answers
with their unknown fields. It does not regenerate a saved pending answer. Scoring
an old replay also preserves unknown generation evidence and timing. Schema-v1
end-to-end reports still cannot resume because they lack pending checkpoints and
enough evaluator settings. Existing frozen report files and manifests are not
rewritten by this change.

These additions do not change prompts, scoring, model selection, inference settings
or index contents. No reindex is required. Use fresh output paths with the existing
evaluation and replay commands described in the README.
