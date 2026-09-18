# Verified claims experiment

PR #10 showed that adding section labels and attribution instructions did not fully
prevent unsupported additions or incorrect inline page references. This experiment
adds an opt-in structured generation and verification path while retaining the plain
answer baseline.

## Contract

1. Assign request-local source IDs to the retrieved passages.
2. Draft at most three claims with an attribution category and supporting quotes.
3. Reject invalid source IDs, missing/nonmatching quotes, obvious model-authored
   citation markers, and current-study claims citing references. Quote matching
   normalizes whitespace only; it does not change case, punctuation, or numbers.
4. Ask the local verifier whether every factual detail is supported, correctly
   attributed, relevant, and collectively answers the question. It sees only each
   claim's cited passages. Exactly one verdict per claim is required.
5. Render only wholly approved answers, appending document/page labels from the
   stored source metadata. Cited-work claims are labelled “Cited literature”. There
   is no final free-text rewrite that could invent new citations or claims.

A malformed draft, incomplete verdict set, rejected claim, or insufficient evidence
returns a fixed refusal. A network failure remains an error. This all-or-nothing
policy can discard correct claims when another claim fails. Source text itself,
quote presence, and model approval do not constitute proof of truth. Incorrect
stored metadata or incorrect semantic approval remain possible failure modes.

The query API accepts `answer_mode: "verified"`; its default remains `plain`.
The evaluation CLI independently selects retrieval strategy and answer mode.
No database migration or reindexing is required beyond PR #10's section metadata.

## Validation design

Unit coverage checks deterministic evidence validation, citation rendering, fail-closed
handling of malformed or incomplete verdicts, all-or-nothing rejection, transport
errors, source isolation, API routing, and evaluation/resume settings.

Eight fixed synthetic controls exercise the real local verifier. Two supported
claims must be accepted. The negative controls cover a wrong number, references
presented as current-study results (including a misleading attribution label),
unsupported pharmacology added to a supported claim, mixed current/cited attribution,
and a missing treatment comparison. Expected decisions are not sent to the model.
These checks are a sanity check, not an accuracy estimate.

The end-to-end run uses all 24 existing questions with expanded retrieval, the same
207-chunk section-aware corpus as PR #10, and Qwen3 8B for drafting, verification,
and judging. Verified drafting and verification use temperature zero; drafting disables thinking
and the verifier enables it. The historical plain-expanded comparison used the generator's default
sampling/thinking settings, so differences cannot be attributed to verification
alone. No labels, judge rubric, or pass thresholds were changed.

Reports fingerprint both prompts, schemas, and the versioned grounding contract.
Answer timing includes retrieval, drafting, and verification; judge time is separate.
All results are development measurements on one paper, not a generalization claim.
Raw reports remain in the ignored `evaluation-results/` directory.

## Reproduce

```bash
uv run python -m scripts.check_grounding --output evaluation-results/grounding-controls.json
uv run python -m scripts.evaluate_answers --strategy expanded --answer-mode verified --output evaluation-results/verified-expanded.json
uv run python -m scripts.evaluate_answers --strategy expanded --answer-mode plain --output evaluation-results/plain-expanded.json
```

Use new filenames for each attempt. Both answer mode and verifier configuration
must match to resume a checkpoint.

## Development failures retained

The initial end-to-end attempt was stopped after five completed answers, all refusals.
The judge incorrectly passed two of these refusals. A saved-source diagnostic showed
that drafting filled the six-claim limit with unrequested details, changed some quotes,
and labelled current-study results as cited work. The draft contract now requests the
minimum needed (usually one claim), allows at most three, preserves short quotes, and
explains that citing a source ID does not mean the finding belongs to another study.

A second diagnostic produced a valid, concise current-study claim, but the verifier
with thinking disabled rejected it. The same fixed claim was accepted with reasoning
enabled. The final verifier configuration therefore enables reasoning; drafting and
the evaluation judge keep thinking disabled. Initial reports and diagnostic traces
remain local and are not counted as final evaluation results. This is development
tuning, not independent evidence of general reliability.

## Final control run

The reasoning-enabled verifier passed all eight fixed controls (two positive, six
negative). One negative is rejected by the deterministic references-section rule
without a model call. The other controls exercise semantic verification.

- Report: `grounding-controls-v3.json`.
- Report SHA-256: `d5558801b648b9659f80bc5a2eebcff7f031ed1e8a478102e73bc42418de78ab`.
- Grounding contract SHA-256: `ae87915673aaa6e36100a01e22ad6e338c0ef5db7876aa5fa0fff3e151612aa8`.
- Started 2026-09-18 11:19:23 UTC; finished 11:24:55 UTC.
- Unit suite: 106 tests pass; strict mypy passes across 51 files.

## Final end-to-end result and rollout decision

The final run completed all 24 cases with calibration passing 6/6. The automated
composite reports 19/24 passes, but **that number is misleading**: several fixed
refusals received full correctness/completeness scores and `abstained=false`.
The evaluator reports only 3/18 answerable false abstentions; direct comparison
against the application's fixed refusal string finds **8/18**. No scoring rules
were changed to improve the reported result.

| Observed behavior | Count |
|---|---:|
| Answerable questions returning a factual answer | 10/18 |
| Answerable questions returning the fixed refusal | 8/18 |
| Returned answers incorrectly labelled “Cited literature” | 4/10 |
| Unanswerable questions returning the fixed refusal | 5/6 |
| Mean answer time, including verification | 42.42 s |
| Mean evaluation-judge time | 7.71 s |

The eight false refusals were muscle glucose uptake, food-restriction protocol,
food-restriction grip-strength effect, AKT phosphorylation, glucose-tolerance
protocol, significance threshold, cited Rosiglitazone, and cited ceramide. The
incorrect attribution labels occurred on KPC mouse strain, immunoblot loading
control, tumor-mass correction, and KPC food intake: these are findings or methods
of the current paper, not merely another cited study. The semantic verifier
approved those labels despite the draft instructions.

The three earlier missing-evidence controls returned their key facts: 1.2 g/3.9%
body-mass loss, three grip-strength trials with the maximum used, and unchanged
KPC food intake. The last of these carried the incorrect attribution label. The
original drug-treatment question returned the fixed refusal. For the paired
own-study Rosiglitazone question, the answer returned a qualified cited-literature
statement instead of directly resolving the question about the authors' experiments.
Both positive cited-literature questions were refused, a material utility regression.

All appended document/page labels came from the stored source metadata. This
eliminates the earlier failure where the generator invented a different page for
its selected source; it does not prove that the claim is supported or correctly
attributed. Passing simple synthetic controls did not predict performance on the
longer real passages. Reasoning enabled on the same local model is insufficient
for reliable semantic verification here.

**Keep this PR as a draft experiment and keep both API/CLI defaults plain.** Do not
promote this mode based on the misleading 19/24 automated score. The deterministic
citation/quote checks are useful groundwork, but the semantic verifier and evaluation
judge need independent validation on these observed failures. Any follow-up should
preserve this report and compare actual answer coverage and attribution errors,
not just aggregate judge grades.

### End-to-end provenance

- Report: `answers-verified-v3-expanded-24.json`.
- SHA-256: `66eb7321acfef92a7fa0c6e56f4f528ad20dc770b088348c404151670ef981f0`.
- Same 207-chunk corpus as PR #10; corpus fingerprint:
  `f8504892995f7716b14310106e60f008d0c66508638797e1c8342935cf9f3d20`.
- Evaluator version 6. Drafting: Qwen3 8B, temperature 0, thinking disabled.
  Verification: Qwen3 8B, temperature 0, thinking enabled. Evaluation judge:
  Qwen3 8B, temperature 0, thinking disabled.

The historical plain-expanded report had mean answer time 38.34 s, but its settings
and sampled generation differed. This experiment neither establishes a quality
improvement nor provides a controlled latency comparison.
