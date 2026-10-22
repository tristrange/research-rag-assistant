# Project status

**Last updated:** 2026-10-22

**Application baseline:** `a8d6799` (2026-10-22)

**Dependency update:** `certifi` 2026.10.19 (security only; `uv.lock`)

**Decision:** local v1 remains open. Engineering checks are usable, but the
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
| Application code | `a8d6799` (2026-10-22) |
| Dependency security | `certifi` 2026.10.19 (patched); lockfile-only update |
| Latest end-to-end quality evaluation | Candidate `6b33f221`, 2026-10-12, grounding contract v40 |
| Latest narrow verifier replay | Base `d88baa6`, 2026-10-21, contract v41; the final fingerprint-only follow-up `71c589b` did not change the generation path |
| Last recorded live startup check | `0b654537`, 2026-10-01 |
| Current grounding contract | `claim-grounding-v41`; see [architecture](architecture.md#grounding-module-contract) |
| Current verified-answer settings | `gpt-oss:20b`; draft thinking low, verifier thinking medium; temperature/top-p 1; 12,288 context; 4,096 output; 300-second stage timeout |
| Retrieval | `nomic-embed-text`; `BAAI/bge-reranker-base`; 20 vector candidates; six sources, normally five reranked plus one page-reserve candidate |

The `a8d6799` baseline includes the v41 question-copy fix and performance
instrumentation merged after the last reserved quality check. No end-to-end
quality evaluation has been run against `a8d6799` or the dependency update. The
latest quality result therefore describes candidate `6b33f221`, not the current
baseline.

## Engineering gates

| Gate | Latest result |
| --- | --- |
| Python regressions | 481 test methods: 464 passed, 17 PostgreSQL contract tests skipped locally |
| JavaScript logic | 29 passed |
| Real-browser smoke | 7 passed |
| Static checks | Ruff and strict mypy pass; CodeQL passes |
| PostgreSQL contracts | Pass in the Ubuntu CI job against disposable pgvector |
| Lockfile | `uv lock --check` passes |
| CI workflows | `Python, UI and types`, `PostgreSQL contracts` and `CodeQL` pass |
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

## Known blockers

| Blocker | Evidence | Next action |
| --- | --- | --- |
| Answer completeness | r3 met 2 of 6 answerable cases against a 5-of-6 target; three safe refusals despite sufficient retrieval | Diagnose one refusal mechanism at a time without weakening evidence guards |
| Verifier and proof reliability | r3 had one output-budget error; adjacent context and scope qualifiers can still cause false rejection or missing support | Preserve failures, add adversarial tests and run a bounded development replay |
| Fresh validation | The v41 question-copy fix has deterministic regression proof but no newly reserved validation | Freeze a candidate and reserve different, not previously inspected questions; obtain independent human source review if available, otherwise report validation as not completed |
| Human quality review | Optional worksheet is pending | Complete it or retain the limitation explicitly |
| Performance | No matching local hardware/model/corpus baseline | Run the documented procedure after the semantic candidate is stable; do not cite latency until then |
| Repository controls | Branch protection still needs owner configuration for PR-only merging and required checks | Apply the GitHub settings described in the [development guide](development.md#branch-and-pull-request-workflow) |
| Dependency security | Critical `certifi` alert #1 was open at the `a8d6799` baseline; `uv.lock` now resolves 2026.10.19 | Confirm the GitHub alert closes after this dependency update merges |

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

1. Choose one diagnosed r3 failure: a safe answerable refusal or the verifier
   output-budget error. State the hypothesis, the smallest decision change, the
   false-accept risk and a stop rule before changing behavior.
2. Add adversarial synthetic tests and preserve the existing evidence guards.
   Run the full Python, JavaScript, browser, mypy, PostgreSQL and CodeQL gates.
3. Freeze the candidate, then reserve new questions that have not been inspected
   during development. Run the declared trial once and preserve failures.
   Replaying r3 is regression evidence, not release validation.
4. If independent human source review is unavailable, record the result as
   **not completed** rather than passed.
5. Only after the semantic gate is settled, collect a matching performance
   baseline and complete the release review. Do not infer latency or accuracy
   from CI or from the earlier development reports.

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

Historical reports and dated findings remain unchanged. Update this page only
when a validated status transition occurs.
