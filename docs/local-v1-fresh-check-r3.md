# Third local-v1 fresh-question check

## Frozen protocol

Merged candidate `6b33f221e6e07a97cc1ddfa609f1fa1d0218f634` uses grounding
contract v40. Commit `8d8cc00` freezes application files, settings, the indexed
corpus, original PDF provenance and Ollama runtime before question authorship.
The [reservation manifest](../benchmarks/local-v1-fresh-check-2026-10-12-r3.json)
binds these inputs and the local artifacts.

Two GPT-6 Luna agents prepare eight new questions on the four known papers:
six answerable questions and two unanswerable controls. A separate reviewer
checks original PDF context, labels and semantic novelty against 114 recorded
question texts and inspected development facts before generation. This is an
AI-authored portfolio check on known papers, not human review or unseen-paper
validation. Raw labels and PDF passages remain ignored locally.

The normal document-scoped verified path uses the unchanged default retrieval:
20 vector candidates, six unexpanded reranked passages with the existing page
reserve, local nomic embeddings and BGE reranking. GPT-OSS 20B drafts with low
thinking; verification, proof and the existing single repair use medium thinking.
Sampling remains temperature/top-p 1, context 12,288 tokens, output 4,096 tokens
and stage timeout 300 seconds. No model judge is invoked.

Reserve the reviewed questions before the first generation. Generate each once,
without reference answers, label quotes or reviewer notes in retrieval/generation.
Do not change prompts, retrieval, labels, models or inference settings between
cases. Preserve errors and refusals without selective retries. Separate AI
source review checks final displayed excerpts, PDF context, completeness,
qualifiers and attribution. Application, settings, corpus, PDFs and observed
runtime must match the freeze before and after the run.

Use an isolated copy of the stopped local database. Remove the temporary
container and copied volume after the check; preserve the original library and
all recorded failures. Reranker package versions are captured, but its weight
digest is not pinned by the Ollama snapshot.

## Unchanged stopping rule

- At least five of six answerable cases have correct, complete supported answers.
- Both unanswerable controls receive appropriate refusals.
- No material unsupported claim or attribution error is observed.

A safe refusal to an answerable case fails completeness. Correct facts in the
full paper do not excuse missing scope in the approved excerpts. A failure keeps
local v1 open and requires development work plus different separately reserved
questions for another check. Passing development replays cannot rescue a failed
validation result. Report exact counts and limitations, without a broad accuracy
claim. The optional human worksheet remains unchanged.

## Results

The check did not meet the unchanged stopping rule. Two of six answerable cases
have complete supported answers; three receive safe refusals despite sufficient
retrieved evidence, and one ends in output-budget exhaustion. Both unanswerable
controls refuse appropriately. No material unsupported displayed claim or
attribution error was observed in this small set.

| Reserved case | Outcome | Review finding |
| --- | --- | --- |
| Cohort-2 tumor-cell inoculum | Answer | Supported dose and cohort; one repair for a typographic question-copy mismatch |
| C26 grip-strength groups | Refusal | Sufficient retrieval; repaired verification fails to approve the cohort excerpt alongside the numeric result |
| Ucp1 in adipose tissues | Refusal | Sufficient retrieval; initial valid refusal gives no diagnostic reason |
| Housing adiponectin control | Refusal | Appropriate missing-outcome control |
| VDAC1/Bax/PPID comparison | Refusal | Complete selected excerpts after repair; isolated proof incorrectly rejects adjacent same-experiment context |
| Endosome proximity | Answer | Both distance and contact-fraction comparisons are supported |
| DIO fat mass and depots | Error | Malformed initial verifier response, then output-budget exhaustion during repair verification |
| DIO bone-density control | Refusal | Appropriate missing-outcome control |

All six answerable questions retrieved sufficient evidence. These failures do
not justify more indexing or broader retrieval for this set. The Activin initial
draft also misread the PBS group's 34% gain as a treatment effect; that draft was
never displayed, and repair removed the unsupported magnitude before its
verifier exhausted the budget.

The normal pipeline generated each question once on the unchanged candidate.
Four cases used the existing repair. The run took about 26 minutes; individual
queries took 8.3–548.1 seconds. No network transport failure occurred. The budget
failure is preserved as an error, not counted as an appropriate refusal. These
observations do not establish repeatability, causation, or a speed comparison
with earlier question sets.

Application files, settings, indexed text/vectors, PDF provenance and observed
runtime/model digests matched before and after generation. The original database
remained stopped; only the temporary copy was used. The temporary container and
copied volume were removed after the completed run. Raw questions, labels,
requests/responses, traces and review artifacts remain in the ignored directory
named by the reservation manifest.

Reservation commit `ac5faaa452d1c3eb4401b478a9d53300dc8b2ffa` precedes the
first generation. The [aggregate result record](../benchmarks/local-v1-fresh-check-results-2026-10-12-r3.json)
binds the reservation, freeze, labels, raw run, saved runner and separate review
by SHA256. The completed run hash is
`532c8c020784bd64715b477d60296ba43ec3edd7c4c8a4bd47c5cefbd71af146`;
the final review hash is
`5af5138955b042f713b29796a1aa51389556580ad38066773845808fd34072c6`.
These schema-version-1 diagnostic artifacts are separate from legacy answer-
evaluation reports; the legacy resume/export workflow does not consume them.
The unchanged candidate passed Python/UI/browser, strict typing, PostgreSQL
contracts and CodeQL checks before this run. No product code changed here.

Keep local v1 open. These questions are now development cases. The next work is
to reduce unnecessary refusals and verifier-output failures while preserving
complete displayed evidence. The model can reject a valid evidence bundle as
well as accept an incomplete one. Do not loosen evidence guards, treat omitted
qualifiers as supported, or replay these questions until they pass and call that
release validation. Another stopping check requires different reserved questions.
