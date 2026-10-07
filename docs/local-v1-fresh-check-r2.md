# Revised local-v1 fresh-question check

The revised check did not meet the unchanged stopping rule. Separate AI source
review recorded one of six answerable cases as complete and supported by its
approved evidence, and both unanswerable controls as appropriate refusals.
One answerable case was refused. Four answers state correct facts from the full
papers, but their approved excerpts do not establish every requested qualifier.
No factual hallucination or authorship-attribution error was observed.

## Candidate and reservation

Merged candidate `9d9bf08` first passed four inspected development regressions:
two previously failing questions and two refusal controls. That regression
result does not overturn the [original failed check](local-v1-fresh-check.md).
The revised application, configuration, indexed corpus and observed Ollama runtime
were then frozen in commit `cb2e4d9`, before new question authorship.

Two GPT-6 Luna agents authored eight questions on the existing four papers.
A separate AI reviewer checked answerability, original PDF context and semantic
novelty against 97 prior question records and inspected development cases.
Before generation, exact quotations were corrected, an Activin question was
narrowed to the supported lean cohort, and a SERCA control was scoped to the
unreported force outcome rather than claiming no inhibition assay existed.
Original drafts remain preserved locally.

Commit `7b2f869` reserved the reviewed questions and label hashes before the first
generation. The [reservation manifest](../benchmarks/local-v1-fresh-check-2026-10-07-r2.json)
records the candidate, settings, PDF/model/corpus fingerprints and questions.
The normal document-scoped verified path generated each once, with no reference
answers, model judge, selective retries or changes between cases. Three cases
used the existing repair step. Separate AI review checked all five accepted
claims and six approved excerpts against the original PDFs and returned passages.

The unchanged rule requires at least five of six supported, complete answers,
both control refusals, and zero material unsupported claims or attribution errors.
Correct facts in the full paper do not excuse missing support in the approved
evidence. This is an AI-authored check on known papers, not human review,
unseen-paper validation or a general accuracy estimate.

## Findings

- C26 spleen mass: safe refusal; the requested result was absent from the selected
  passages, which included a different KPC cohort's spleen result.
- C26 day-14 insulin: the approved evidence combines C26 timing with a KPC insulin
  result. The correct C26 insulin passage was retrieved but not approved.
- Housing FGF21: the numerical result is correct, but the approved excerpt starts
  after a page break and omits the C26 cohort context.
- Mitophagy: the group comparison is correct, but the approved excerpt omits the
  requested stable-knockdown qualifier.
- Activin adipose uptake: the negative result is correct, but the approved excerpt
  does not establish the requested lean cohort.
- SLC25A33 expression: the comparison and evidence pass. Both unsupported-outcome
  controls receive appropriate refusals.

These are four material approved-evidence coverage failures, including one
combination of evidence from different cohorts. Authorship remains correctly
attributed to the queried papers. The distinction matters: the failure is source
coverage, even though the reported scientific facts are correct in the full PDFs.

## Evidence and next work

All eight queries completed on 2026-10-07. Recorded application files, settings,
the 1,043-chunk corpus, PDF provenance and Ollama model digests matched before
and after generation. The reranker weight digest was not pinned; package versions
were recorded. The run took about fifteen minutes; individual queries took
9.6–389.3 seconds. These are single observations, not a speed comparison.
Checks used an isolated copy of the existing database; the temporary container
and copied volume were removed afterward.

The [result record](../benchmarks/local-v1-fresh-check-results-2026-10-07-r2.json)
binds the freeze, labels, reviews and completed run by SHA-256. PDFs, labels,
answers and traces remain in ignored
`evaluation-results/local-v1-fresh-check-r2-20261007T190121519224Z/`.
These diagnostic artifacts use schema version 1, separate from the legacy
answer-evaluation report format.

Keep local v1 open. Investigate why verification and repair accept requested
qualifiers without approving their supporting context, including cohort mixing.
These eight questions are now development cases. After a bounded fix, reserve
different questions for another check; passing replays cannot rescue this result.
The optional human worksheet and original failed check remain unchanged.
