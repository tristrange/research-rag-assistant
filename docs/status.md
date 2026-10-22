# Project status

**Last updated:** 2026-10-22

**Application baseline:** `ecc6ba3` (2026-10-22)

**Dependency update:** `certifi` 2026.10.19 (security only; `uv.lock`); GitHub alert #1 fixed

**Decision:** local v1 remains open; PR #92 is blocked from merge. Engineering checks are usable, but the
semantic quality gate has not passed. Do not tag v1 or describe answers as
generally reliable.

This page is the current status authority. It summarizes evidence; it does not
replace the dated protocols, reports or historical findings linked below.
“Verified” describes the application's checking process, not independent factual
verification.

## Where the project stands

The assistant is a local-first, single-user research tool for text-based academic
PDFs. It indexes papers into PostgreSQL/pgvector, retrieves and reranks passages,
drafts claims, checks evidence and returns a refusal when the checks do not
establish sufficient support. Engineering and review tooling are complete enough
for continued development. Answer completeness and verifier reliability remain
the release blockers.

## Evaluated code and contracts

| Item | Current record |
| --- | --- |
| Application code | `ecc6ba3` (2026-10-22); v45 proof-window candidate in this draft; not approved |
| Dependency security | `certifi` 2026.10.19 (patched); alert #1 fixed 2026-10-22; no open Dependabot alerts observed |
| Latest end-to-end quality evaluation | Candidate `6b33f221`, 2026-10-12, grounding contract v40 |
| Latest narrow verifier check | v45: the source-faithful VDAC1 comparison was rejected; the control gate blocked the eight-case saved-source grounding replay |
| Last recorded live startup check | `0b654537`, 2026-10-01 |
| Merged grounding contract | `claim-grounding-v41` |
| Draft candidate contract | `claim-grounding-v45`; positive control failed; see [architecture](architecture.md#grounding-module-contract) |
| Current verified-answer settings | `gpt-oss:20b`; draft thinking low, verifier thinking medium; temperature/top-p 1; 12,288 context; 4,096 output; 300-second stage timeout |
| Retrieval | `nomic-embed-text`; `BAAI/bge-reranker-base`; 20 vector candidates; six sources, normally five reranked plus one page-reserve candidate |

The `ecc6ba3` baseline includes the v41 question-copy fix, performance
instrumentation and the patched `certifi` lockfile. The v45 candidate labels
source-window metadata and requires quoted wording to connect scope and outcome;
it does not change retrieval, drafting, verification or evidence binding. Its
source-faithful positive control failed. No end-to-end quality evaluation has
been run against `ecc6ba3` or v45. The latest quality result therefore describes
candidate `6b33f221`, not the current baseline.

## Engineering gates

| Gate | Latest result |
| --- | --- |
| Python regressions | Draft v45: 483 test methods; 466 passed, 17 PostgreSQL contracts skipped locally |
| JavaScript logic | 29 passed |
| Real-browser smoke | 7 passed |
| Static checks | Ruff and strict mypy pass; CodeQL runs on this change |
| PostgreSQL contracts | Pass in the Ubuntu CI job against disposable pgvector |
| Lockfile | `uv lock --check` passes |
| CI workflows | Previous `Python, UI and types`, `PostgreSQL contracts` and `CodeQL` passed at `ecc6ba3`; this change reruns them |
| Performance baseline | Pending; instrumentation exists, no measured baseline is recorded |
| Live startup | Last recorded 2026-10-01; not repeated against current `main` |

The 2026-10-22 post-merge run used the supported Apple Silicon macOS target,
Python 3.14 and Node.js 24. Full commands and setup are in the
[development guide](development.md) and [fresh-install checks](install-smoke-test.md).

## Review evidence

No independent human review has been completed. “Independent” below is not used
as a synonym for AI review.

| Evidence | Scope and result | Status |
| --- | --- | --- |
| [Third reserved fresh-question check](local-v1-fresh-check-r3.md) | Eight AI-authored questions: 2 of 6 answerable cases supported, both controls refused, three safe refusals, one output-budget error; no material unsupported displayed claim or attribution error observed | **Failed** the unchanged stopping rule; see the [reservation protocol](../benchmarks/local-v1-fresh-check-2026-10-12-r3.json) |
| [Question-copy typography replay](../benchmarks/verifier-question-typography-results-2026-10-21.json) | Two saved-source development cases: one supported answer, one answerable refusal; the target U+2011 failure was not reproduced | Development only; fresh reserved validation **not completed** |
| [Proof-window v45 check](../benchmarks/verifier-proof-window-v45-results-2026-10-22.json) | Source-faithful positive rejected; three negative controls rejected; four calls, 139.71 seconds; gated eight-case replay not started | **Failed** development acceptance; candidate remains draft, not merge-ready |
| [AI-assisted development review](v1-readiness.md#development-review-protocol-frozen-before-new-generation) | 16 historical inspected cases: 12 passed, including 8 of 12 answerable cases and all 4 controls | Accepted as portfolio evidence; not current-code accuracy or independent validation; see the [review record](../benchmarks/v1-development-review.json) |
| Optional human worksheet | Not completed | Outstanding |

The r3 source review was performed by a separate AI reviewer. The question-copy
replay source review was performed by the primary agent, not an independent or
human reviewer. The historical review is AI-assisted. None of these results
establishes general scientific accuracy.

The latest reserved check used grounding contract v40. The 21 October
question-copy change is limited to the verifier's copy comparison: typographic
dash variants normalize to ASCII hyphen-minus, while numbers, words, spelling,
conditions, study attribution and evidence checks remain exact. See
[named identifiers and question-copy limits](question-identifiers.md#question-copy-typography).

The 22 October v45 proof-window candidate is limited to how the isolated proof
reads a claim's approved citations and labels source-window metadata. The v44
positive check had accepted a no-effect overstatement; it is not a supported-answer
quality result. It does not
auto-approve evidence, add a repair, or combine qualifiers across different
experiments, conditions, documents, or claims. It requires the
claim text itself to state every requested qualifier. The fixed-draft checks are
regression evidence, not a reliability claim; see the
[v45 development check](../benchmarks/verifier-proof-window-v45-results-2026-10-22.json).

## Known blockers

| Blocker | Evidence | Next action |
| --- | --- | --- |
| Answer completeness | r3 met 2 of 6 answerable cases against a 5-of-6 target; three safe refusals despite sufficient retrieval | Diagnose one refusal mechanism at a time without weakening evidence guards |
| Verifier and proof reliability | r3 had one output-budget error; adjacent context and scope qualifiers can still cause false rejection or missing support. The v45 source-faithful positive control failed; merged source windows do not provide per-excerpt origins | Preserve failures, add adversarial tests and run repeated and fresh validation before claiming an improvement |
| Fresh validation | The v41 question-copy fix and v45 proof-window candidate have development evidence but no newly reserved validation | Freeze a candidate and reserve different, not previously inspected questions; obtain independent human source review if available, otherwise report validation as not completed |
| Human quality review | Optional worksheet is pending | Complete it or retain the limitation explicitly |
| Performance | No matching local hardware/model/corpus baseline | Run the documented procedure after the semantic candidate is stable; do not cite latency until then |
| Repository controls | Branch protection still needs owner configuration for PR-only merging and required checks | Apply the GitHub settings described in the [development guide](development.md#branch-and-pull-request-workflow) |

## Security and deployment limits

| Limit | Consequence |
| --- | --- |
| Local single-user design, loopback-only, no accounts | Do not expose the API, PostgreSQL or Ollama publicly |
| Text PDFs only | Scanned PDFs requiring OCR are outside local v1 |
| Retrieval uses selected passages, not a complete reading | A refusal does not establish that the paper lacks a result |
| Evidence checks use a language model | They can accept unsupported claims or reject valid answers; inspect cited passages |
| Prompt-injection defenses are mitigations | Untrusted PDF text can still influence output; there are no guarantees |
| Advanced cross-paper synthesis is not implemented | Across-paper retrieval may omit papers; each-paper mode answers separately |

See the [local security boundary](local-usage.md#local-security-boundary) for
setup and operational constraints.

## Next experiment

PR #92 remains a draft. The v45 source-faithful positive control failed, so its
frozen gate blocks the eight-case saved-source grounding replay. No fresh
validation or performance baseline is completed by this work.

1. Preserve actual per-excerpt origins or quoted connecting context before trying
   another proof candidate. Do not rely on a merged window's starting chunk number.
2. Keep the omitted-population, no-effect overstatement and hidden experiment-
   boundary controls. Require the faithful positive to pass as well.
3. Restore a usable local database before a retrieval-to-answer evaluation. A
   saved-source replay cannot substitute for an end-to-end check.
4. Freeze any later candidate before generation; preserve failures without
   selective retries. Fresh reserved validation and any human review remain
   separately outstanding.
5. Collect the performance baseline only after the semantic candidate is stable.

## Decision log

| Date | Decision | Evidence |
| --- | --- | --- |
| 2026-09-28 | Accepted the AI-assisted review of 16 historical development cases for the portfolio milestone; not release approval | [V1 readiness](v1-readiness.md#development-review-protocol-frozen-before-new-generation) |
| 2026-10-07 | Local v1 remains open after the original and revised reserved checks failed | [Original check](local-v1-fresh-check.md), [revised check](local-v1-fresh-check-r2.md) |
| 2026-10-12 | Local v1 remains open after the third reserved check failed (2 of 6 answerable) | [Third check](local-v1-fresh-check-r3.md), [reservation protocol](../benchmarks/local-v1-fresh-check-2026-10-12-r3.json), [aggregate result](../benchmarks/local-v1-fresh-check-results-2026-10-12-r3.json) |
| 2026-10-21 | Merged the v41 question-copy typography fix and verification diagnostics; deterministic regression passed, live target not reproduced, fresh reserved validation not completed | [Evidence](../benchmarks/verifier-question-typography-results-2026-10-21.json) |
| 2026-10-21 | Merged stage-level performance instrumentation; baseline explicitly pending | [Performance procedure](performance-baselines.md) |
| 2026-10-22 | Consolidated current status and evidence status; no semantic quality transition | This page and the `a8d6799` gates |
| 2026-10-22 | Updated `certifi` to patched 2026.10.19 and refreshed the application baseline to `a8d6799`; no application code or model change | `uv.lock`, this page |
| 2026-10-22 | Refreshed the application baseline to `ecc6ba3`; confirmed `certifi` alert #1 fixed and no open Dependabot alerts observed | This page, GitHub alert #1 |
| 2026-10-22 | Added the v44 adjacent-context proof clarification; fixed-draft acceptance and omitted-qualifier, different-population and cross-chunk controls passed; fresh reserved validation not completed | [Development check](../benchmarks/verifier-adjacent-context-development-2026-10-22.json) |
| 2026-10-22 | v45 failed the source-faithful positive control; the eight-case replay was not started and PR #92 remains draft. The v44 retained positive also overstated no rescue as no effect | [Frozen protocol](../benchmarks/verifier-proof-window-v45-protocol-2026-10-22.json), [results](../benchmarks/verifier-proof-window-v45-results-2026-10-22.json) |

Historical reports and dated findings remain unchanged. Update this page only
when a validated status transition occurs.
