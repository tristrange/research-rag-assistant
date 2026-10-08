# Evidence for question requirements

The [revised fresh-question check](local-v1-fresh-check-r2.md) found four answers
whose approved excerpts omitted requested qualifiers. One combined a result
from one cohort with timing from another. Correct facts elsewhere in the paper
did not make the displayed evidence sufficient.

Previously, the verifier marked each question requirement as supported without
selecting its evidence. Contract v27 requires exact evidence IDs for every
supported requirement. Those IDs must also appear in whole-question coverage
and approved claim evidence, which the browser displays. Missing, unknown or
duplicate IDs fail validation. The same guard applies to initial and repaired
drafts; negative verdicts remain valid inputs to the existing repair step.

The verifier instructions require scope and result excerpts to describe the
same experiment. Full passage context can help interpret a quote or reveal a
conflict, but cannot replace missing approved evidence. No inference stages,
model settings, retrieval rules or indexing changes were added.

The ID checks enforce evidence selection, not scientific entailment. The model
can still overlook a requirement or incorrectly connect two excerpts. A refusal
prevents an unsupported answer but remains incomplete when the supplied sources
could answer the question.

## Development replay

Six inspected questions were generated once using their unchanged recorded
passages: the four coverage failures, one supported answer and one refusal
control. The normal GPT-OSS 20B verified path and built-in repair were used,
without reference answers, a judge, retrieval or selective retries. Separate
AI source review assesses the final approved excerpts.

The replay completed on 2026-10-08 (Europe/Copenhagen), with unchanged application
files, configuration and observed Ollama runtime throughout generation.

| Case | Source-review result |
| --- | --- |
| C26 day-14 insulin | Safe refusal; the earlier mixed-cohort answer is rejected, but sufficient returned evidence goes unused. |
| Housing FGF21 | Coverage failure: the approved result still omits C26 cohort identity. |
| Mitophagic flux | Coverage failure: the approved result still omits stable knockdown. |
| Activin adipose uptake | Coverage failure: the approved result still omits the lean cohort. |
| SLC25A33 expression | Supported, complete answer retained. |
| Metformin co-treatment control | Appropriate refusal retained. |

One of five answerable cases is supported and complete, one is safely refused,
and three still fail approved-evidence coverage. The one unanswerable control
refuses appropriately. Matching evidence IDs do not prove the requested qualifier:
the verifier still incorrectly treats a result excerpt as sufficient scope proof
in those three cases. This guard closes a structural gap, not the remaining
semantic coverage failures. The earlier C26 spleen retrieval miss is outside
this change.

This inspected replay does not rerun retrieval or meet the fresh-question stopping
rule. Keep local v1 open. The earlier failed checks and optional human worksheet
remain unchanged; a later validation needs different reserved questions.

Raw artifacts stay under ignored `evaluation-results/` in the primary checkout:

- Run: `qualifier-binding-trial-20261007T231032461306Z.json`;
  SHA-256 `9d46c357b4e5315a791513eed62c0a39e206859a6cfe0e8566b2296fc784499d`.
- AI source review: `qualifier-binding-trial-20261007T231032461306Z-review.json`;
  SHA-256 `0a337eecff5ca76533afe65d3cf34734f278c9ecbcb54f20a92c5c47cf68a484`.
- Baseline: `local-v1-fresh-check-r2-20261007T190121519224Z/run.json`;
  SHA-256 `a0da09ecbe1818f999ed5773c13e73a9e03c9bc55f81c80c2e2b2d88daa851d2`.
- Application SHA-256:
  `3ae059581325ff2921d2f095558f9aacd8935491389b48f683c2a4da82142bc7`.
- Grounding fingerprint:
  `57f91b37d3f3b37a9c92526b5d6a21a0988f08502ee3e2b7e7cbfaaa55b7437f`.

The synthetic regression rejects a positive qualifier verdict when its evidence
is omitted from either whole-question coverage or displayed claim evidence,
and accepts it when both include that evidence. Another regression rejects a
supported requirement with no evidence IDs. The Python suite passed 416 tests
with 17 skips; strict mypy passed for 78 source files.

## Discarded selected-bundle experiment

An unshipped v28 candidate restricted proof IDs to draft-selected bundles and
kept full source text in a separate contradiction field. Its six-case replay
still made all three qualifier mistakes. Two extra refusals arose from malformed
outputs rather than correct scope checks. The candidate was discarded; raw
results and its patch remain under ignored `evaluation-results/`:

- `excerpt-bundle-trial-20261008T002254661891Z.json`;
  SHA-256 `762800af235e53456bcdb98d060df6759df486033e8231024ac6a1b26ffbcd39`.
- Review: `excerpt-bundle-trial-20261008T002254661891Z-review.json`;
  SHA-256 `14a300756f2a07bfa26b51605b8bb79e5bd2144f736b418877c37239c2b3d34d`.
- Patch: `excerpt-bundle-trial-20261008T002254661891Z-candidate.patch`;
  SHA-256 `a362d0a28dcd9cd9e5f67b0b3c25950976d98dee59177563f95532d53b6c1af4`.

## Isolated approved-excerpt check

Contract v29 adds a small proof check after the existing full-context verifier
approves a draft. It receives only the question, claim targets and the exact
approved excerpts that would be displayed. Full passages and earlier verifier
verdicts or explanations are excluded. Missing scope can trigger the existing
single repair; repaired drafts must pass both checks before evidence is exposed.
The full-context verifier remains responsible for contradiction and attribution
checks. Invalid proof output fails closed; transport failures still propagate.

A four-case fixed-input probe rejected all three result-only bundles missing
C26, stable-knockdown or lean-cohort scope, and accepted the mitophagy bundle
with stable-knockdown scope included. All four responses were schema-valid;
separate AI source review confirmed the bundle decisions. The positive reason
misidentified which excerpt established scope, so its explanation is imperfect.
These are inspected development controls, run once each, not fresh validation.
Prompt and response shape changed alongside context isolation, so the probe
does not establish which change alone caused the improvement.

- Probe: `quote-proof-probe-20261008T004719072349Z.json`;
  SHA-256 `3a8cb401415145d3304120d58b4b6c584748a2a28482df257c18e54be16f7bb8`.
- Review: `quote-proof-probe-20261008T004719072349Z-review.json`;
  SHA-256 `56020ea7927380a617488b7e3e36a4887d46e7b0110cafdc6e4ceadcc2cc053b`.

The probe's extra check took 19–32 seconds per case on this machine. Production
adds one verifier call for each draft that passes full-context verification,
including a repaired draft if needed. Model settings and retrieval are unchanged;
reindexing is unnecessary. This check can still make semantic mistakes and does
not establish answer verification accuracy at scale. Local v1 remains open.

The integrated mitophagy replay used the normal draft, full verifier and existing
single repair on six unchanged recorded passages. The first full verifier again
approved a result-only quote; the isolated check correctly rejected its missing
stable-knockdown scope. Repair selected scope evidence for whole-question coverage
but omitted it from approved claim evidence, so the existing v27 binding check
rejected it. Final result: a safe, incomplete refusal rather than a coverage
failure. Sufficient returned evidence still goes unused. The run took 341 seconds
across five model calls, including 41 seconds for the new proof check. No selective
retry, retrieval, judge or reference answer was used.

The fixed cohort-conflict control was correctly rejected by the full-context
verifier with a schema-valid explanation distinguishing C26 from KPC; it took
85 seconds and did not call the proof stage. Application code, configuration and
observed Ollama runtime stayed unchanged during both live cases. A subsequent
trace-only change records proof attempts before generation so parse failures
cannot count as passing controls; final prompts, schemas and settings retain
the run's grounding fingerprint.

- Integrated run: `approved-proof-trial-20261008T005106000172Z.json`;
  SHA-256 `c1011230a873e6184c5ccc0934bb1b827f1b4fa0556598199968e85aa8d4d702`.
- Review: `approved-proof-trial-20261008T005106000172Z-review.json`;
  SHA-256 `c6b5329beca771b3cff0347fcc615adbc98c5264877dc7d1a33d147cd364df3c`.

Regression tests cover the isolated input boundary, initial and repaired proof
checks, final displayed evidence, invalid verdicts, parse failures and propagated
transport failures. Live controls preserve proof traces and cannot pass merely
because proof generation produced invalid content. The final Python suite passed
422 tests with 17 skips; strict mypy passed for 78 source files.

## Complete proof selection at the output field

The v29 repair found the stable-knockdown scope excerpt and selected it for
whole-question coverage, but omitted it from the claim verdict. The application
correctly refused that mismatch. Contract v30 explains directly in the claim
verdict's evidence-ID field that its list owns the displayed proof: include
all necessary scope and result excerpts there, even when the scope IDs also
appear under requirements or whole-question coverage. The bounded response
schema and verifier prompt retain this field description.

This changes guidance only. Evidence eligibility, validation, the isolated proof
check, model settings, retrieval and the single repair limit remain unchanged;
there are no new inference calls or reindexing requirements.

A two-case fixed-draft check reused the exact earlier mitophagy draft and its six
recorded passages, plus the earlier mixed-cohort control. Each was checked once,
with no new draft generation, repair, retrieval, judge, reference answer or
selective retry. These are inspected development cases, not fresh validation.
The mitophagy verdict selected both scope and result IDs for the displayed claim;
the isolated check accepted that complete bundle. The two calls took 124 seconds,
including 31 seconds for the proof check. This is not comparable to the full-query
v29 timing, which also includes drafting and repair. One successful selection does
not establish repeatability or attribute the improvement conclusively to guidance.

The mixed-cohort control was rejected with a valid verdict distinguishing C26
from KPC, in 111 seconds. One auxiliary measurement requirement was incorrectly
marked unsupported despite the measurement sentence; its explanation demanded
additional outcome information. That rationale is imperfect, while the decisive
cohort-mismatch rejection is correct. Separate AI source review confirmed the
complete mitophagy bundle and the overall control decision.

Application code, configuration and observed Ollama runtime stayed unchanged
throughout generation. Artifacts remain under ignored `evaluation-results/`:

- Run: `complete-claim-trial-20261008T012157210945Z.json`;
  SHA-256 `ad568c4b2886d92291d7d9bed2d28668a85e22eca964777b7679bd0dce4c777c`.
- Review: `complete-claim-trial-20261008T012157210945Z-review.json`;
  SHA-256 `09d059f29e12ce574b811810a56626ecdbbc32486b247f1717a966871f240191`.

The existing Python suite passed 422 tests with 17 skips, including refusal on
missing scope selections and rejection of malformed proof on both initial and
repaired drafts. Strict mypy passed for 78 source files. These fixed-draft results
do not establish normal-query improvement, repeatability or a broad accuracy
claim. Local v1 remains open pending a new reserved fresh-question check.
