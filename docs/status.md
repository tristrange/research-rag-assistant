# Project status

**Last updated:** 2026-10-23

**Application baseline:** `ecc6ba3` (2026-10-22)

**Dependency update:** `certifi` 2026.10.19 (security only; `uv.lock`); GitHub alert #1 fixed

**Decision:** local v1 remains open. PR #92 has passed its focused development
controls; the broader semantic quality gate has not passed. Do not tag v1 or
describe answers as generally reliable.

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
| Merged application code | `ecc6ba3` (2026-10-22), grounding v41 |
| Evaluated PR #92 candidate | `c285cfa`, grounding v49; focused controls passed, product completeness target unmet |
| Dependency security | `certifi` 2026.10.19 (patched); alert #1 fixed 2026-10-22; no open Dependabot alerts observed |
| Latest reserved quality evaluation | Candidate `6b33f221`, 2026-10-12, grounding contract v40 |
| Latest known-question end-to-end development check | v49, 2026-10-22: 2/6 answerable, both controls refused, no pipeline errors; not fresh validation |
| Latest narrow verifier check | v49: supported comparison accepted; all six rejection controls rejected; three deterministic decisions, four model proofs |
| Last recorded live startup check | `0b654537`, 2026-10-01 |
| Merged grounding contract | `claim-grounding-v41` |
| PR #92 candidate contract | `claim-grounding-v49`; see [architecture](architecture.md#grounding-module-contract) |
| Current verified-answer settings | `gpt-oss:20b`; draft thinking low, verifier thinking medium; temperature/top-p 1; 12,288 context; 4,096 output; 300-second stage timeout |
| Retrieval | `nomic-embed-text`; `BAAI/bge-reranker-base`; 20 vector candidates; six sources, normally five reranked plus one page-reserve candidate |

The merged `ecc6ba3` baseline includes the v41 question-copy fix, performance
instrumentation and patched `certifi` lockfile. The v49 candidate has been checked
on eight previously inspected questions with fresh retrieval from the existing
read-only index. Its captured application, settings, Ollama, corpus and PDF
fingerprints matched before and after generation. Its two complete answers out
of six do not meet the product target or demonstrate a general improvement.
The latest reserved result still describes v40; no fresh reserved check has been
run on v49. No reindex is required because indexing and retrieval are unchanged.

## Engineering gates

| Gate | Latest result |
| --- | --- |
| Python regressions | v49: 494 test methods; 477 passed, 17 PostgreSQL contracts skipped locally |
| JavaScript logic | 29 passed |
| Real-browser smoke | 7 passed |
| Static checks | Ruff and strict mypy (91 files) pass; CodeQL passes for `c285cfa` |
| PostgreSQL contracts | Pass in the Ubuntu CI job against disposable pgvector |
| Lockfile | `uv lock --check` passes |
| CI workflows | `Python, UI and types`, `PostgreSQL contracts` and `CodeQL` pass for `c285cfa`; documentation follow-up reruns them |
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
| [Proof-window v45 check](../benchmarks/verifier-proof-window-v45-results-2026-10-22.json) | Source-faithful positive rejected; broader replay not started | **Failed**, retained; superseded by a different v49 implementation |
| [Complete-context v49 check](../benchmarks/verifier-context-v49-results-2026-10-22.json) | Seven targeted controls pass; known-question pipeline: 2/6 supported complete answers, four answerable refusals, both controls refused; no unsupported displayed claim or attribution error observed | Focused PR acceptance passed; product completeness rule **not met**; fresh validation not completed |
| [AI-assisted development review](v1-readiness.md#development-review-protocol-frozen-before-new-generation) | 16 historical inspected cases: 12 passed, including 8 of 12 answerable cases and all 4 controls | Accepted as portfolio evidence; not current-code accuracy or independent validation; see the [review record](../benchmarks/v1-development-review.json) |
| Optional human worksheet | Not completed | Outstanding |

The r3 source review was performed by a separate AI reviewer. The question-copy
replay source review was performed by the primary agent, not an independent or
human reviewer. The v49 code and source reviews were performed by a separate AI
reviewer. The historical review is AI-assisted. None of these results
establishes general scientific accuracy.

The latest reserved check used grounding contract v40. The 21 October
question-copy change is limited to the verifier's copy comparison: typographic
dash variants normalize to ASCII hyphen-minus, while numbers, words, spelling,
conditions, study attribution and evidence checks remain exact. See
[named identifiers and question-copy limits](question-identifiers.md#question-copy-typography).

The v49 candidate keeps merged main's strict proof instruction text. It displays
and proves all intervening source context between selected quotes, rather than
infer experiment identity from a merged window's starting chunk number. Selected
ID/duration guards still run before that assembly. Named question IDs must also
occur in displayed claims; explicit effect-strength wording is required for
absolute absence-of-effect or complete-restoration claims. These necessary
lexical checks cannot resolve all semantics or aliases and can refuse valid
paraphrases. See [architecture](architecture.md#grounding-module-contract) and the
[development record](../benchmarks/verifier-context-v49-results-2026-10-22.json).

## Known blockers

| Blocker | Evidence | Next action |
| --- | --- | --- |
| Answer completeness | r3 and the known-question v49 development check each met 2 of 6 answerable cases against a 5-of-6 target; the latter had four answerable refusals | Diagnose one refusal mechanism at a time without weakening evidence guards |
| Verifier and proof reliability | v49 passes targeted controls but still rejects sufficient evidence and produces overstrong drafts that guards must stop; no broad reliability claim | Preserve failures, add adversarial tests and run repeated and fresh validation before claiming an improvement |
| Fresh validation | The v41 question-copy fix and v49 complete-context candidate have development evidence but no newly reserved validation | Freeze a candidate and reserve different, not previously inspected questions; obtain independent human source review if available, otherwise report validation as not completed |
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

The focused PR check passed, but local v1 remains open. The known-case pipeline
still returned only two of six complete supported answers; the historical
five-of-six product target is unchanged. Do not reserve more questions or collect
a performance baseline just to avoid these failures.

1. Choose one remaining completeness mechanism: false per-animal quantifier
   rejection, premature draft refusal, repeated no-effect overstatement, or
   omitted duration evidence. Isolate it before proposing another behavior change.
2. Keep the supported and adversarial controls, exact context/proof/display
   binding, and the single repair. Freeze each candidate and preserve failures.
3. A known-question replay is development evidence. Fresh reserved validation and
   any independent human source review remain separately outstanding.
4. Collect the performance baseline only after the semantic candidate is stable.

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
| 2026-10-23 | Completed v49 source review: focused controls and PR acceptance pass; known-question pipeline has 2/6 complete answers and two appropriate controls. Local v1 remains open; earlier failed candidates retained | [Protocol and results](../benchmarks/verifier-context-v49-results-2026-10-22.json) |

Historical reports and dated findings remain unchanged. Update this page only
when a validated status transition occurs.
