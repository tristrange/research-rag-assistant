# Bounded source-faithful drafting check

The candidate failed its frozen acceptance criterion. Keep the v41 application
unchanged: an extra instruction about result strength and experimental groups did
not prevent a repair draft from overstating a finding.

This follows the [verifier comparison](verifier-comparison.md). The
[protocol](../benchmarks/draft-fidelity-protocol-2026-10-12.json) was committed
before generation. Only six lines in the shared initial/repair draft instructions
changed, alongside an experimental v42 contract version. The verifier, final
semantic proof, evidence guards, model settings and single repair stayed fixed.
The candidate instructed drafting to preserve rescue strength and distinguish
experimental groups, including using a generic description where appropriate.

The trial ran each of two previously inspected questions once against the same
six saved passages. GPT-OSS 20B used nine chat calls in 341 seconds, within the
12-call and 600-second limits. Application, model, settings and PDF fingerprints
matched before and after generation. There was no retuning or selective rerun.

| Development case | Initial draft | Repair draft | Final outcome |
| --- | --- | --- | --- |
| Cohort-2 inoculum | Source-faithful | Source-faithful | Refused after both verifiers changed a hyphen in the question |
| VDAC1/Bax/PPID comparison | Source-faithful | Unsupported full-rescue qualifier | Refused; repair verification rejected the overstatement |

Three of four proposed drafts were source-faithful. Neither case produced a
displayed answer, and no unsupported claim reached the user. The frozen criterion
required **every** proposed draft to be faithful; safe final refusals do not make
the candidate pass. There were no uncaught pipeline errors.

## Failure details

For the inoculum question, the initial draft retained the distinct cell variants;
repair used a supported generic description. Both verifiers copied the question
with U+2011 instead of its original U+002D hyphen. The validator permits whitespace
normalization but rejects that change, so neither draft reached final proof. The
initial verifier also selected an excerpt from another cohort, although the
cohort-2 excerpt itself established the requested count.

For the mitochondrial comparison, the initial draft preserved rescue, partial
rescue and no rescue. Its verifier selected only the VDAC1 excerpt while treating
it as support for all three interventions. The isolated proof correctly rejected
the missing Bax/PPID support. Repair then added a full-rescue qualifier that its
cited passages do not establish. The repair verifier rejected that overstatement.
This is a different failure from incorrectly rejecting linked experimental
context when all necessary excerpts have been selected.

## Decision and next step

Do not ship the candidate instruction or rerun it until it happens to pass. Its
complete source file and raw traces remain in the ignored local report directory;
the [public summary](../benchmarks/draft-fidelity-results-2026-10-12.json) records
their hashes, settings, timings and stage-level findings. The application was
restored to v41 after the frozen run finished. PDFs, index and primary checkout
were not changed.

The next bounded fix should address question-copy typography failures. First
check whether the application can bind verification to its original question
without requiring the model to reproduce punctuation. Preserve semantic
whole-question coverage, claim support, attribution, evidence binding and final
proof; a formatting fix must not approve incomplete or unrelated answers. Missing
evidence selection and unsupported repair wording remain separate issues.

## Question-copy typography follow-up (21 October 2026)

**Hypothesis.** The recorded U+2011/U+002D copy change is a non-semantic
typographic substitution, not a different question. Refusing both source-faithful
drafts for it is a reliability failure. The minimal decision change is to compare
the verifier's `question_excerpt` after whitespace normalization and a fixed
typographic-dash translation only.

**False-accept risk.** Numbers, words, spelling, conditions, study attribution and
inserted or removed hyphens still differ and remain rejected. The excerpt is a
binding check; supporting evidence is selected and validated separately. No claim
support, citation, named-identifier, duration, coverage, attribution or proof
guard is relaxed.

**Expected improvement.** Both recorded drafts would no longer be refused solely
for the copied dash. An answer is not guaranteed: the initial inoculum verifier
also selected an excerpt from another cohort, and the mitochondrial repair had a
separate unsupported full-rescue qualifier.

**Stop rule.** Run the two saved-source development cases once each under frozen
model and index settings, and preserve every outcome without a retry. If the replay
displays a material unsupported claim or attribution error, or accepts any
non-dash identifier change, revert the change. A development pass is not
reliability validation: newly reserved questions and independent human source
review are required for that. If those are unavailable, report fresh validation as
**not completed**, not passed.

## Verification and limits

The primary Codex agent reviewed all four drafts against their cited saved
passages and inspected final evidence selections. All 27 catalogue quote
occurrences bound to their saved sources after the existing whitespace
normalization. This is AI source review, not independent or human certification;
it is not a new full-paper review.

The experimental candidate passed the Python suite (440 tests, 17 PostgreSQL
contracts skipped without a configured test database) and strict typing for 79
files. Those checks establish compatibility, not semantic success. Artifact and
protocol integrity checks passed. No application changes are included in this PR.

One stochastic trial on two inspected answerable questions, without a baseline
rerun or unanswerable controls, cannot establish a general quality improvement,
regression rate, retrieval performance or v1 readiness. No retrieval, embedding
or database operation ran in this check.
