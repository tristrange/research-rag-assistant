# Bounded verifier comparison

This development experiment asks whether repeated semantic verification adds useful
safety or instead prevents supported answers. It keeps GPT-OSS 20B and v40's
inference settings, initial drafting and single repair unchanged. No application
behavior changes in this research spike.

First, both verifier arms assess the same eight synthetic fixed drafts: four
supported answers and four unsupported variants covering linked experimental
context versus a separate cohort, measurement identity, negative results versus absent measurements, and
study attribution. Then both pipelines answer the same eight inspected r3
questions with exactly the six passages previously retrieved for each question.
Each case alternates which arm runs first. Every arm/case runs once.

The current arm uses the full-context verifier, deterministic validation and
isolated final-excerpt proof. The experimental arm selects evidence and judges
support, attribution, relevance and whole-question coverage in one call. It
projects that result into the existing citation-binding, identifier and duration
validators. It removes model-generated requirement decomposition, question echo
and the second semantic proof; it therefore cannot be assumed equally safe.
Both arms use the existing draft/repair prompts and model budgets.

The candidate and inputs are frozen before generation. Local raw reports contain
requests, responses, traces, timings and artifact hashes; paper excerpts remain
ignored. The experiment admits at most 72 chat calls and starts no additional
call after 60 minutes. An in-flight call can finish after that limit. Existing
300-second per-call timeouts remain unchanged. Failures are retained, without
retuning or selective retries. A budget stop makes the comparison incomplete.

A candidate has no promotion signal if it accepts any unsupported calibration
draft, answers either unanswerable replay, or separate source review finds a
material unsupported displayed claim or attribution error. A useful development
signal also requires at least two additional complete supported answers among
the six answerable replays. Latency and model/schema errors are reported separately.
Passing this small, inspected set would justify further work, not release approval
or general safety. Fresh questions would still be required after a product change.

Question inputs come from the preserved check in [PR #76](https://github.com/tristrange/research-rag-assistant/pull/76).
The replay performs no retrieval, embedding or database operation; it does not
measure end-to-end latency or new-question accuracy. Synthetic calibration is a
small diagnostic and cannot certify a verifier. Generation is stochastic and the
single replicate cannot establish a reliable performance difference.

## Results and decision

The frozen run completed all 32 arm/case pairs in 56.8 minutes, using 65 of the
72 allowed chat calls. Before/after application, settings, model and PDF
fingerprints matched. The [results summary](../benchmarks/verifier-comparison-results-2026-10-12.json)
binds the local reports, candidate and runner with SHA-256 hashes.

| Measure | Current v40 | Compact single pass |
| --- | ---: | ---: |
| Supported calibration drafts accepted | 4/4 | 4/4 |
| Unsupported calibration drafts rejected | 4/4 | 4/4 |
| Complete supported replay answers | 4/6 | 3/6 |
| Appropriate unanswerable-control refusals | 2/2 | 2/2 |
| Answerable replays refused | 2/6 | 2/6 |
| Answers with an unsupported detail | 0 | 1 |
| Attribution errors in displayed answers | 0 | 0 |
| Malformed JSON responses during replay | 1 | 0 |
| Replay chat calls | 26 | 19 |
| Total replay time | 26.9 min | 9.4 min |
| Median answerable replay time | 248.4 s | 89.4 s |

Both arms displayed four answers; source review disqualified one compact answer.
It correctly reported the inoculum count, but assigned C26 cells to every
tumor-bearing mouse where the methods distinguish NC26 and C26 groups. Exact
quote binding did not catch this unsupported qualifier. The candidate therefore
fails the predeclared safety condition and provides no promotion signal.
Keep the current application unchanged; do not replace its final semantic proof
with this candidate. Passing eight synthetic drafts did not establish safety on
the paper questions.

The fixed-draft calibration is a cleaner comparison of verifier work: current
used 12 calls, 15.0 minutes and 14,607 generated tokens; compact used eight calls,
5.5 minutes and 5,540 tokens. These are local timing observations, not estimates
of end-to-end retrieval performance or generally equivalent safety.

## What the failures tell us

- The compact Ucp1 refusal happened during initial drafting, before its verifier
  ran. Identical initial requests produced different drafts across arms. The
  current arm also answered Ucp1 where the earlier r3 run refused it under the
  same initial request. This replay cannot attribute answer-count differences
  solely to the changed verifier or establish an improvement over r3.
- The mitochondrial excerpts contain the requested comparison. Current final
  proofs incorrectly demanded repeated experimental identity in adjacent
  same-source sentences. However, draft wording also strengthened a no-rescue
  result into no effect on expression; compact repair added a full-rescue
  qualifier. Sufficient retrieval does not make every proposed answer supported.
- Current Activin verification correctly rejected missing duration evidence.
  Repair selected both duration and results, but its final verifier returned a
  fenced response with ordinary newlines. Strict JSON parsing rejected
  it, causing a safe refusal. The run had no uncaught pipeline errors, transport
  timeouts or output-limit errors; the malformed response is counted separately.
- Compact Activin repair correctly answered with both duration and result
  excerpts. Existing deterministic duration and identifier checks also stopped
  incomplete evidence selections in Activin and grip before repair.

The next bounded investigation should isolate structured-output reliability
using the preserved malformed response and valid/invalid fixtures. Any proposed
handling must retain schema and evidence checks and reject ambiguous input.
It should not silently strip escapes or relax grounding. Faithful draft wording
and linked-context proof remain separate issues; neither warrants another
unbounded series of prompt changes.

## Review and limits

An independent AI agent reviewed the calibration and the first 12 pipeline rows
against frozen labels, displayed excerpts and original PDF context. Its usage
limit prevented completion; the primary agent reviewed the remaining four
Activin rows and preserved the independent ratings after matching their row
hashes. The final local review identifies that split. This is AI source review,
not human certification.

No candidate, harness, paper text or raw model response is committed. No
application code, index or primary checkout changed. Only the frozen protocol,
public counts and findings are published. Guard self-checks and artifact-integrity
checks passed; the unchanged application test suite was not rerun. One inspected
stochastic trial does not establish general quality, equal safety or v1 readiness.

The newline description was corrected after inspecting the preserved response's
character codes: it contains 47 ordinary LF newlines and no literal backslash-n
sequences. The object inside the single JSON fence parses and passes the verifier
schema and deterministic checks. The recorded v40 refusal and all trial counts
remain unchanged; this correction does not retroactively count an answer.

## Single JSON fence handling (v41)

Grounding calls opt into decoding one whole-response lowercase
`json` code fence with ordinary LF delimiters, after trimming outer whitespace.
It passes the untouched interior to the same strict JSON decoder and object
check. Prose around a fence, multiple responses, broken JSON, literal escaped
delimiters and non-object payloads remain invalid. Plain text generation is
unchanged. Draft/verifier schemas, evidence guards, final semantic proof,
sampling, budgets and the single repair remain unchanged.
Evaluation calibration and scoring judges retain strict bare-JSON decoding;
their evaluator version and frozen protocol fingerprints remain applicable.

The [targeted diagnostic](../benchmarks/json-fence-check-2026-10-12.json) reuses the
preserved Activin repaired draft and verifier response, then requires a fresh
isolated final-excerpt proof. The original response's object values were
preserved; schema and deterministic checks passed, and the one new GPT-OSS 20B
proof approved it in 34.54 seconds. Before/after inputs matched. No retrieval or
database operation ran, and the original comparison reports were preserved.
This is a known-output regression check, not a new fresh-question result.

Regression tests cover value preservation, ambiguous/malformed wrappers,
schema rejection, negative final proofs and strict evaluation-judge decoding.
The Python suite ran 440 tests
successfully, with 17 PostgreSQL contracts skipped without a configured test
database; strict typing passed for 79 files. The grounding contract fingerprint
is now v41, so subsequent evaluations must record the new contract. No reindex
is needed because extraction, chunking and embeddings did not change.

The subsequent [bounded drafting check](draft-fidelity-check.md) failed its
all-drafts-faithful criterion; its candidate was not promoted and v41 remains current.
