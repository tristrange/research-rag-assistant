# Local v1 fresh-question check

## Protocol frozen before questions

The application candidate is merged commit `783ed9f4fd3d53ea4ee98a0dafe96646ce658905`.
The configuration, model weight digests, complete indexed corpus and PDF provenance
were frozen before preparing fresh questions. The application source fingerprint
is `cdfabd25b269443076d0fa2e2f959f427798deb0ab9f91129e51a30e46a2c01b`;
documentation-only commits do not alter that candidate.

Eight AI-authored questions cover the existing four papers: six answerable
questions and two unanswerable controls. Authors inspect the original PDFs and
all prior benchmark questions to exclude semantic rewordings of tested facts.
An additional reviewer checks labels and question novelty before generation.
The questions and their label-file hashes are reserved before the first answer.
This is a fresh-question portfolio check on known papers in one scientific domain;
it is not human-authored validation, an unseen-paper test or a broad accuracy estimate.

The normal document-scoped verified query path uses ten vector candidates and six
unexpanded reranked passages. GPT-OSS 20B drafts with thinking low and verifies
with thinking medium, temperature 1 and top-p 1. The context is 12,288 tokens,
the output budget 4,096 tokens and each stage timeout 300 seconds. Embeddings use
nomic-embed-text; reranking uses BAAI/bge-reranker-base. Reranker package/environment
versions are recorded, but its weight digest is not pinned by the Ollama snapshot.

Generate each question once, including the application's normal built-in repair.
Do not tune retrieval, prompts, labels or inference settings between cases, and
preserve every failure. Reference answers, quotes and reviewer notes never enter
retrieval or generation. No model judge is run. Independent AI review inspects
final approved claims, exact quote/source mappings, PDF context, requested qualifiers
and attribution. A safe refusal to an answerable question fails completeness.
Check the frozen application, corpus and model runtime before and after the run;
any drift invalidates the check. Reports retain all answers and stage traces.

## Prespecified stopping rule

Require all of the following in this small check:

- At least five of six answerable questions receive correct, sufficiently complete,
  supported answers (the existing at-least-80-percent target).
- Both unanswerable controls receive appropriate refusals.
- No material unsupported claim or attribution error is observed.

A failure requires development work and a different separately reserved check.
Replaying this same set can be useful for debugging but cannot rescue the final
validation result. After use, these questions become development data. Report
exact counts and any allowed false refusal rather than a general accuracy claim.

The known Activin diet-qualifier refusal remains a documented limitation.
The optional historical human worksheet remains untouched. A human-authored check
can provide additional confirmation; this AI-assisted check does not impersonate
human review or independently certify scientific correctness.

## Results

The check did not meet the prespecified local-v1 stopping rule. All eight cases
completed once on 2026-10-07. Four of six answerable cases passed source-based
review, and both unanswerable controls received appropriate refusals. One
answerable case was refused; another contained a material source-coverage gap.
No attribution error was observed. The target required at least five supported,
complete answers and zero material unsupported claims.

| Reserved case | Final outcome | Source-based review |
| --- | --- | --- |
| `sample-longitudinal-assessment-schedule` | Refused | Fail: missing complete timing/MRI coverage |
| `sample-food-restriction-ptbc1d4` | Answered | Fail: numeric comparison correct, cohort duration absent from cited context |
| `housing-temperature-plasma-il6` | Answered | Pass |
| `housing-il6-blockade-unreported` | Refused | Pass: unanswerable control |
| `mito-in-vivo-localized-inflammation` | Answered | Pass |
| `mito-salicylate-il6-recovery` | Answered | Pass |
| `activin-short-term-muscle-protein-content` | Answered | Pass |
| `activin-human-hba1c-control` | Refused | Pass: unanswerable control |

The application, settings, 1,043-chunk corpus and Ollama runtime/model digests
matched the freeze before and after generation; local PDF hashes also matched
stored provenance. The run lasted about twelve minutes. Individual calls took
13.7–194.6 seconds, including normal retrieval and any built-in repair. Three
cases used that repair. These are single observations, not a controlled speed
comparison. There were no selective retries, model-judge calls or mid-run fixes.

The [frozen question reservation](../benchmarks/local-v1-fresh-check-2026-10-07.json)
records the application, configuration, model/corpus fingerprints and label-file
hash. Reservation commit `5da7756` preceded the first generation. It is a protocol
manifest, not input to the legacy single-paper benchmark runner. Its settings
retain legacy judge fields for provenance, but no judge was invoked.

The [aggregate result record](../benchmarks/local-v1-fresh-check-results-2026-10-07.json)
binds the completed run and separate review to SHA-256 hashes of `freeze.json`,
`reserved-cases.json`, `label-review.json`, `run.json` and `answer-review.json`.
Question authors used two GPT-6 Luna agents; a GPT-6.1 Sol agent reviewed source
labels before generation and final emitted answers afterward. The authors did
not generate the candidate answers. This is separate AI review, not blinded
human evaluation.

Source PDFs, labels with raw quotations, generated answers and traces remain in
ignored `evaluation-results/local-v1-fresh-check-20261007T014134850187Z/`.
The live diagnostic report uses its own schema-version-1 format; it is not a
schema-v3 answer-evaluation report and cannot be resumed or exported through the
legacy benchmark tools. Public question text and aggregate findings are recorded
alongside hashes for the local artifacts.

The longitudinal schedule question received a safe refusal despite being
answerable from the complete paper. Its returned passages did not establish the
complete glucose-tolerance/MRI schedule. This fails answer completeness.

The food-restriction answer correctly reported the numeric comparison, but its
approved claim also asserted the three-day cohort duration. That duration is
true in the full paper and present in the question, but absent from the returned
cited context. Under the frozen review rule it is a material source-coverage
failure, rather than an invented experimental result. A question's premise is
not evidence establishing a qualifier in an approved claim.

## Next development work

Keep local v1 open. Investigate retrieval coverage for timing and cohort
qualifiers, and why the verifier accepted a qualifier not established by its
selected evidence. Keep these eight outcomes as development evidence. After a
bounded fix, freeze the revised candidate and reserve different questions for
another stopping check. Passing replays of this set would be regression evidence,
not a replacement for this failed validation attempt.
