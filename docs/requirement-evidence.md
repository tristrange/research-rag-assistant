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

## Normal-generation follow-up

The four inspected qualifier failures were each generated once on the unchanged
six passages saved in the revised fresh-question report. This used normal
drafting, verification, the isolated proof check and the existing single repair.
There was no retrieval, database access, reference answer, judge, tuning or
selective retry. Separate AI source review assessed final displayed evidence
against the passages and papers. These are development cases, not new validation.

| Case | Final displayed answer | Source review |
| --- | --- | --- |
| C26 day-14 insulin | Refusal | Safe but incomplete: the draft cited the insulin result without day-14 scope; verification rejected it and repair abandoned the answer. |
| Housing FGF21 | Refusal | Safe but incomplete: the full verifier approved the result-only excerpt; the isolated proof rejected its missing C26 scope and repair abandoned the answer. |
| Mitophagic flux | Answer after repair | Supported and complete: displayed excerpts pair stable-knockdown scope with the increased and unchanged flux results from the same experiment. |
| Activin adipose uptake | Refusal | Safe but incomplete: the initial draft violated the schema; repair corrected its shape, but verification returned content that failed JSON parsing. |

The mitophagy initial draft used an invalid field name. The built-in repair
corrected its schema, and the final verifier selected both scope and result
excerpts. This successful normal-generation case extends the earlier fixed-draft
observation; it does not establish repeatability or prove that v30 caused the
improvement.

All four supplied six-passage pools contain sufficient evidence. The first two
failures arise after retrieval: scope passages go uncited, and repair returns
insufficient evidence rather than completing those citations. Activin is a
model-output failure, not a completed semantic rejection. Its repaired draft
also lacks lean-cohort evidence, but no valid verifier verdict was obtained;
do not count this as proof that a semantic gate caught that omission.

One of four answerable cases passed; three safely refused. No unsupported claim
or attribution error was displayed. This check contains no unanswerable controls
and makes no claim about current control performance. The four cases took
102, 110, 184 and 105 seconds respectively, across 14 model calls in total.
The run used GPT-OSS 20B, draft thinking low, verifier/repair thinking medium,
temperature and top-p of 1, a 12,288-token context, a 4,096-token output budget,
and 300-second per-call timeouts. The observed Ollama version was 0.40.0.
Application files, settings and observed model/runtime identity stayed unchanged
throughout the run; the raw report records the model digest and input hashes.

The next development targets are complete scope selection from the existing
catalogue and reliable structured output, without weakening either verification
gate or adding selective retries. Keep local v1 open and reserve a different
fresh-question set after addressing those gaps. Earlier failed checks retain
their original results. This four-case replay does not establish repeatability,
end-to-end retrieval quality or a broad accuracy improvement.

Preserved artifacts in the primary checkout's ignored `evaluation-results/`:

- Run: `v30-generation-check-20261008T124532713650Z.json`;
  SHA-256 `98fe07fc9a56b5ed23a286f688e278a91a44d43b41d9afbafe8e8cbd5041f262`.
- Source review: `v30-generation-check-20261008T124532713650Z-source-review.json`;
  SHA-256 `d5627dad52e6d96979bac4ea41bfa93c2ec19cf7cf2d9db37dc2a8431e1a6bcc`.
- Runner: `v30-generation-check-20261008T124532713650Z-runner.py`;
  SHA-256 `50153b5f91f6ddf7d21b60ebf0fe633fe93e06667c39190b20df248ccb3e528d`.

These findings change documentation only; application behavior and indexing are
unchanged. Artifact hashes and frozen inputs were checked. A full Python baseline
run was stopped before test execution while blocked reading an installed
Transformers file; it is not a passing test result.

## Scientific quotes and scope evidence

Contract v35 fixes two deterministic false rejections found during development:

- Quote choices reuse ingestion's sentence boundaries and abbreviation rules.
  `vs.`, `Fig.` and `et al.` stay attached to their sentence. When an abbreviation
  precedes a possible new sentence starting with a capitalized word, the catalogue
  also offers the separate excerpts. Both choices remain exact source text, so
  a sentence ending in `et al.` need not merge cited and current-study results.
  The previous
  splitter rejected a valid repaired housing quote and detached figure identities
  from results. Whitespace normalization, exact catalogue-entry matching and the
  4,000-character quote cap remain unchanged. Synthetic control quotes now include
  the author prefix in the same sentence; source text and expected decisions are unchanged.
- Requirement evidence IDs must appear directly in approved claim evidence.
  They no longer have to be duplicated in the whole-question verdict. An observed
  complete housing bundle failed solely because that redundant copy was absent.
  Whole-question evidence must still belong to approved claims. Supported
  requirements, full-question approval, the original question anchor, attribution,
  duration checks and the isolated approved-excerpt proof remain required.

Draft/repair instructions, verifier source eligibility, model settings, retrieval,
indexing and the single repair limit otherwise retain v30 behavior. No additional
inference stage or reindex is needed. These changes remove specific blockers;
they do not establish reliable model source selection or local-v1 readiness.

A broader v33 candidate offered uncited retrieved passages from the same paper
and added draft/repair schema guidance. One normal generation per inspected case,
with unchanged recorded passages, completed with these reviewed results:

| Development case | Outcome |
| --- | --- |
| C26 day-14 insulin | Safe incomplete refusal: inconsistent verifier IDs, then repair changed an exact quote. |
| Housing FGF21 | Correct full-paper answer, incomplete displayed cohort proof: a leptin quote does not establish the FGF21 cohort. |
| Mitophagic flux | Complete supported answer after repair selected stable-knockdown scope and all four results. |
| Activin adipose uptake | Safe incomplete refusal: repaired result excerpt omitted lean-cohort scope. |
| SERCA-inhibition control | Appropriate refusal with valid model output. |
| Metformin co-treatment control | Appropriate refusal with valid model output. |

Strict completeness stayed at 1/4; both controls passed. No full-paper factual or
attribution error was found, but the housing isolated proof falsely approved an
incomplete display bundle. All four answerable passage pools were sufficient.
The cases took 223, 305, 351, 262, 12 and 11 seconds across 18 calls. Application,
settings, source passages and model/runtime identity stayed frozen. The broader
candidate was discarded; these results **do not evaluate the shipped v34 code**.

The v31 and v32 preliminary runs were interrupted and remain preserved with raw
responses, candidate patches and runners. Neither is a complete six-case result.
A fixed-input v30 Activin probe returned parseable but schema-invalid JSON; the
earlier parsing failure has not been tied to one specific provider bug. No
provider workaround, selective retry or model-setting change is included here.

Preserved v33 artifacts in the primary checkout's ignored `evaluation-results/`:

- Run: `v33-generation-check-20261008T144731440649Z.json`;
  SHA-256 `a1e6189069f2662608767192a60d4052a15011f018fe7b5a97e366a961e10d30`.
- Separate AI source review: `v33-generation-check-20261008T144731440649Z-source-review.json`;
  SHA-256 `930d04b184373b1bfb68425734c6caf97ca87875c969605e6d391c1421ca2a05`.
- Runner: `v33-generation-check-20261008T144731440649Z-runner.py`;
  SHA-256 `6f3ffb43601ee19657cb21710a601d8ecef43162e4ac43ab0bffc9ec0cd9bc73`.

The final v34 check replayed the unchanged saved v31 housing repair draft once.
Its exact quotes now pass deterministic validation, reproducing removal of the
`vs.` blocker. The normal full verifier exhausted its 4,096-token output budget
before returning content (242 seconds); isolated proof did not run.
This is an inference error, not a semantic refusal or a passing verifier check.
No answer was approved, no retry was made, and the raw response is preserved.

- Fixed-draft report: `v34-fixed-quote-recovery-20261008T151135224754Z.json`;
  SHA-256 `3dc4efae128c03827eda429ce36ad5d57f210a8739023ff3a04c93431300afa0`.
- Runner: `v34-fixed-quote-recovery-20261008T151135224754Z-runner.py`;
  SHA-256 `43b230810b4c878a347b1d4b90aee4f8c903347144e526cf8ac1e7a765659daf`.

Final-code checks: 424 Python tests passed (17 skipped), strict mypy passed for
78 files.

These inspected cases remain development evidence. Reserve different questions
for the final check; do not count repeated or fixed-draft trials as fresh validation.
