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
