# Verified claims experiment

PR #10 showed that adding section labels and attribution instructions did not fully
prevent unsupported additions or incorrect inline page references. This experiment
adds an opt-in structured generation and verification path while retaining the plain
answer baseline.

## Current result: v12

The final configuration is ready for review as an **opt-in experimental feature**.
The expanded-retrieval run completed all 24 questions on the unchanged 207-chunk
corpus, with judge calibration passing 6/6. Inspection of the answers, their cited
passages and saved generation traces found 17 supported factual answers out of
18 answerable questions, one false refusal, and correct refusals on all six
unanswerable questions. The earlier incorrect “Cited literature” labels did not
recur. Both positive cited-study answers were correctly labelled as cited work.

| Measure | Final v12 result |
|---|---:|
| Answerable questions returning a factual answer | 17/18 |
| Answerable questions returning the fixed refusal | 1/18 |
| Unanswerable questions returning the fixed refusal | 6/6 |
| Automated composite passes | 22/24 |
| Fixed synthetic controls | 12/12 |
| Mean answer time, including retrieval and verification | 59.42 s |
| Mean evaluation-judge time across all cases | 8.63 s |

The two composite failures have different causes:

- **KPC food intake:** the draft returned insufficient evidence even though the
  retrieved passage says food intake did not change. This is a real false refusal
  and remains a coverage limitation. No question or reference label was changed.
- **Food restriction and grip strength:** the answer correctly says grip strength
  did not change, citing the page 6 Figure 3 caption. The judge gave 2/2 for
  correctness, completeness and source support. The composite still failed because
  the benchmark's exact expected excerpt is on page 7 and was not retrieved.
  The raw score and original evidence label are preserved.

For the previously failing female-mice question, the draft again tried to infer a
female-specific result. This time the verifier marked the population requirement
unsupported, rejected the claim, and the correction returned the fixed refusal.
The remaining five unanswerable cases also refused. This demonstrates the intended
check on these cases, not a guarantee against unsupported extrapolation generally.

The 12 controls comprise three supported claims accepted and nine negative claims
rejected. One negative is caught by the deterministic references-section rule;
the others exercise semantic verification. The suite has 135 passing unit tests,
and strict mypy passes across 53 files. Model choice, reasoning settings and
validation changed together, and the questions were used throughout development:
this is neither an isolated estimate of verification's benefit nor a held-out test.
The API still uses reranked retrieval without neighbor expansion; these 24-case
quality measurements apply to the expanded evaluation strategy.

The verifier assesses full cited passages. A selected exact quote can omit some
supporting detail, and one answer repeated an AKT result across two claims. Neither
exact quote matching nor verifier approval proves semantic correctness. Known
limitations include false refusals, redundant wording, model-dependent decisions,
and substantial local latency. Plain remains the default.

The live `/query` smoke test also passed against local PostgreSQL and Ollama using
the API's normal unexpanded retrieval. It returned HTTP 200, “GraphPad Prism 10”,
a page 3 citation and three sources in 39.80 seconds. This checks integration on
one question; it does not extend the expanded benchmark to all API queries.

### Final provenance

- API smoke: `api-verified-v12-smoke.json`, SHA-256
  `7f0022676f1f4d3167d0340f48d35f6100f97136e8717ce3fd1bf82650970e2a`.
- Full report: `answers-verified-v12-expanded-24.json`.
- Report SHA-256: `1f0f373da7d59e3ba2c757606b600b0a2a0d751017d2b2dffdd6e54f20d6d717`.
- Controls: `grounding-controls-v12.json`.
- Controls SHA-256: `4408f287a4684aa6cb840078d9716df063cdfaf5e51a0d96aed4028c946fcd7e`.
- Traces: `grounding-traces-v12.json`.
- Traces SHA-256: `70815dd5efa7457dc173203980ffc35632d4b69e4b3a0bdf7e40b896a8878003`.
- Grounding contract: `claim-grounding-v12`, SHA-256
  `3ccdde2ef9279ebf736686e88cf5146c4c7dec6d78fda19b42954aca9959eac7`.
- Corpus SHA-256: `f8504892995f7716b14310106e60f008d0c66508638797e1c8342935cf9f3d20`.
- GPT-OSS model digest:
  `17052f91a42e97930aa6e28a6c6c06a983e6a58dbb00434885a0cf5313e376f7`.
- Full run: 2026-09-19 16:31:17–16:59:02 UTC. Evaluator version 7.
- GPT-OSS 20B: low draft reasoning, medium verification reasoning, temperature zero,
  context 12,288, output budget 4,096. Qwen3 8B judges non-refusal answers with
  thinking disabled; exact fixed refusals are scored deterministically.

## Contract

1. Assign request-local source IDs to the retrieved passages.
2. Draft at most three claims with an attribution category and supporting quotes.
   Quotes are selected from application-provided exact excerpts. The generation
   schema pairs each allowed quote with its actual source ID.
3. Reject invalid source IDs, missing/nonmatching quotes, obvious model-authored
   citation markers, and current-study claims citing references. Quote matching
   normalizes whitespace only; it does not change case, punctuation, or numbers.
4. Ask the local verifier whether every factual detail is supported, correctly
   attributed, relevant, and collectively answers the question. It sees only each
   claim's cited passages. It must also establish the question's requested population,
   study, intervention and other qualifiers. Exactly one verdict per claim is required.
5. Allow at most one correction attempt after a rejected draft, then repeat every
   deterministic and semantic check. Transport failures propagate without retry.
6. Render only wholly approved answers, appending document/page labels from the
   stored source metadata. Cited-work claims are labelled “Cited literature”. There
   is no final free-text rewrite that could invent new citations or claims.

A malformed draft, incomplete verdict set, rejected claim, or insufficient evidence
returns a fixed refusal. A network failure remains an error. This all-or-nothing
policy can discard correct claims when another claim fails. Source text itself,
quote presence, and model approval do not constitute proof of truth. Incorrect
stored metadata or incorrect semantic approval remain possible failure modes. The
verifier checks the full cited passage, so a selected quote is not guaranteed to
contain every supporting detail. Quotes are diagnostic evidence and are not
returned as standalone supporting excerpts in the API response.

The query API accepts `answer_mode: "verified"`; its default remains `plain`.
The evaluation CLI independently selects retrieval strategy and answer mode.
No database migration or reindexing is required beyond PR #10's section metadata.

## Validation design

Unit coverage checks deterministic evidence validation, citation rendering, fail-closed
handling of malformed or incomplete verdicts, all-or-nothing rejection, transport
errors, source isolation, API routing, and evaluation/resume settings.

Twelve fixed synthetic controls exercise the real local verifier. Three supported
claims must be accepted and nine unsupported claims rejected. Negative controls
cover wrong numbers, both directions of study-attribution error, unsupported
pharmacology, mixed current/cited attribution, a missing treatment comparison,
and unsupported population and duration qualifiers. Expected decisions are not
sent to the model.
These checks are a sanity check, not an accuracy estimate.

The historical v3 end-to-end run used all 24 existing questions with expanded retrieval, the same
207-chunk section-aware corpus as PR #10, and Qwen3 8B for drafting, verification,
and judging. Verified drafting and verification use temperature zero; drafting disables thinking
and the verifier enables it. The historical plain-expanded comparison used the generator's default
sampling/thinking settings, so differences cannot be attributed to verification
alone. No labels, judge rubric, or pass thresholds were changed.

Reports fingerprint the draft, correction and verification prompts, schemas,
excerpt selection rules, and the versioned grounding contract.
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
enabled. That historical verifier configuration therefore enabled reasoning; drafting and
the evaluation judge kept thinking disabled. Initial reports and diagnostic traces
remain local and are not counted as final evaluation results. This is development
tuning, not independent evidence of general reliability.

## Historical v3 control run

The reasoning-enabled verifier passed all eight fixed controls (two positive, six
negative). One negative is rejected by the deterministic references-section rule
without a model call. The other controls exercise semantic verification.

- Report: `grounding-controls-v3.json`.
- Report SHA-256: `d5558801b648b9659f80bc5a2eebcff7f031ed1e8a478102e73bc42418de78ab`.
- Grounding contract SHA-256: `ae87915673aaa6e36100a01e22ad6e338c0ef5db7876aa5fa0fff3e151612aa8`.
- Started 2026-09-18 11:19:23 UTC; finished 11:24:55 UTC.
- Unit suite: 106 tests pass; strict mypy passes across 51 files.

## Historical v3 end-to-end result and rollout decision

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

**The v3 decision was to keep the PR in draft and both API/CLI defaults plain.**
The misleading 19/24 automated score did not justify promotion. Follow-up work
retained this report and checked actual answer coverage and attribution errors,
as well as aggregate judge grades.

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


## Follow-up diagnostics

The v3 result is preserved above. Evaluator version 7 recognizes the application's
exact refusal directly instead of asking the judge to infer abstention. It assigns
zero correctness/completeness for answerable cases and full credit for unanswerable
cases; other responses still use the judge. Historical v3 scores are not rewritten.

`scripts.replay_grounding` reuses a report's saved questions and source passages,
records new drafts, verifier decisions and rejection reasons, and checkpoints on
failure or interruption. It does not rerun retrieval or the evaluation judge, and
is a development diagnostic rather than an end-to-end benchmark:

```bash
uv run python -m scripts.replay_grounding evaluation-results/verified-expanded.json \
  --case c26-muscle-glucose-uptake --output evaluation-results/grounding-replay.json
```

Enabling drafting reasoning on Qwen3 8B first hit the 120-second timeout. A bounded
attempt with an explicit 12,288-token context, 4,096 generated-token limit and
300-second timeout exhausted its generation budget without usable JSON on the
first case (about 262 seconds). It was stopped rather than counted as a successful
quality evaluation. Increasing reasoning alone did not solve the observed failures.

The v5 probe clarified attribution enum names and requested verifier explanations.
It answered muscle glucose uptake and rejected the false-premise Rosiglitazone
question, but still refused three answerable probes. Traces showed an incomplete
food-restriction draft, the wrong mouse cohort, and bibliography numbers confused
with catalogue IDs. The installed Qwen3 Coder 30B model also made ID and quote-copy
errors on the same saved evidence. These diagnostic probes do not establish that
a larger model or a changed prompt is reliable.


## v10 implementation

The application extracts allowed quote choices by normalizing whitespace, splitting
at sentence-ending punctuation followed by whitespace, and splitting any remaining
span longer than 4,000 characters into contiguous pieces. It preserves case,
punctuation, numbers, and printed hyphens. Abbreviations can produce short spans;
these are quote choices, not a linguistic sentence parser. The model selects from
source-specific quote enums. Runtime source-ID, exact-substring and quote-enum membership validation still
run even when the backend claims to enforce the schema.

Attribution values explicitly identify the actor: `this_document_authors`,
`external_publication`, or `non_study_context`. The verifier gives bounded reasons
for its overall decision and each claim. A rejected draft can be corrected once
using only the original question, retrieved sources and validation feedback. The
corrected result must pass all checks again. A model-declared unanswerable response
returns immediately; transport errors are never converted into evidence refusals.

Verified drafting and verification now use the already-installed `gpt-oss:20b`,
low draft reasoning, medium verifier reasoning, temperature zero, a 12,288-token
context and a 4,096-token generated
output budget. Each reasoning request has a 300-second timeout; an answer may use
up to four calls if correction and re-verification are needed. Plain answers and
the evaluation judge retain Qwen3 8B. The judge has thinking disabled. Model choice,
reasoning and decoding settings changed together, so this is not an isolated test
of the verification technique.

The food-restriction probe that repeatedly failed due to PDF line-break hyphenation
now returns the three-day, approximately 30% protocol with exact quotes and stored
page references (`grounding-v8-food-probe.json`). Earlier failed attempts remain in
the local reports; they are not included in the final evaluation.


The v8 control run caught an attribution error: the verifier treated authors of a
cited passage as an external publication even when the passage described their own
experiments. v9 made attribution explicitly relative to the source document, which
fixed that negative control but rejected the supported reference-title control.
v10 keeps those same nine controls and expected outcomes, and raises verification
reasoning from low to medium. No control labels or benchmark reference answers
were changed to obtain a pass.


### v10 control result

All nine fixed controls passed: two supported claims accepted and seven negative
controls rejected, including both directions of study-attribution error. The
expected outcomes were unchanged. This is still a small development control set,
not evidence of general verifier accuracy.

- Report: `grounding-controls-v10.json`.
- SHA-256: `9f612e0c8292580ed19ed22bca0a23350a1962ef065c59e2dba76185456ce71b`.
- Grounding contract: `e67ab023591fb91c6ca5de59eda0b72bd81fe7f4fea59e55242625c8f2c34238`.
- GPT-OSS model digest from local Ollama:
  `17052f91a42e97930aa6e28a6c6c06a983e6a58dbb00434885a0cf5313e376f7`.
- Unit suite: 134 tests pass; strict mypy passes across 53 files.


### v10 full-run outcome: not approved for rollout

All 24 questions completed with calibration passing. The automated score was 20/24.
There were 16 factual answers out of 18 answerable questions, two false refusals
(muscle glucose uptake and KPC food intake), and correct refusals on five of six
unanswerable questions. The remaining negative case asked about female mice; the
answer substituted general mouse results without establishing the requested sex.
This is an unsupported extrapolation and blocks rollout of this version.

The grip-strength answer was correctly cited to page 6: the supplied Figure 3
caption explicitly states that food restriction does not alter grip strength. The
judge incorrectly penalized it because the reference label used page 7. The raw
judge grade is preserved. None of the returned factual answers had the earlier
incorrect external-publication labels. Mean answer time was 47.55 seconds; mean
judge time was 8.82 seconds.

- Report: `answers-verified-v10-expanded-24.json`.
- SHA-256: `fbf816c0bc6aaeefa92b39b39b18c4800223dd323359865d142c5933176ae5bd`.
- Evaluator version 7; unchanged 207-chunk corpus.

## v11 question requirements

Verification now lists the question's essential requirements and assesses each
against the cited passages. Population, sex, species, study, intervention, dose,
comparison and time-period qualifiers cannot be silently omitted. Code rejects
an answer if any requirement is unsupported, even when the overall answer and
claim verdicts otherwise say to accept it. The draft instructions require the same
scope discipline. Three additional controls check a supported population, an
unsupported population, and an unsupported duration; existing outcomes remain
unchanged.


The v11 saved-evidence replay recovered the muscle glucose-uptake answer and
refused the unsupported female-mice question. KPC food intake still returned a
false refusal at drafting, before verification. v12 explicitly distinguishes
sufficient evidence for a negative answer from insufficient evidence. That case
still refused, including a separate diagnostic with medium drafting reasoning.
The configuration therefore retains low drafting reasoning and records this
limitation rather than changing the question or its reference label.

The final full-run diagnostics additionally capture the actual draft, correction
and verifier output for every generated answer. The observational wrapper calls
the normal evaluation CLI and adds only local trace serialization; no generation
settings or model calls are changed. Timings include that small serialization
cost. The normal CLI commands above reproduce the evaluation without the extra
trace file.
