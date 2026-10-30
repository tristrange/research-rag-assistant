# Project status

**Last updated:** 2026-10-30

**Application code baseline:** `38e474a` (2026-10-29)

**Dependency update:** `pymupdf` 2.0 and `fastapi` 0.156.3 (`uv.lock`);
`filelock` 4.2.4 and `setuptools` 84.2.1 security patches (PR #96); the
`certifi` 2026.10.19 security update is retained.

**Decision:** local v1 remains open. Current `main` includes the merged grounding
contract v49 from PR #92; its focused development controls passed, but the broader
semantic quality gate has not passed. The project is at a documentation stopping
point for an experimental local portfolio prototype. The portfolio milestone
includes no further model experiments or application changes; further experiments
are optional. Do not tag v1 or describe answers as generally reliable.

This page is the current status authority. It summarizes evidence; it does not
replace the dated protocols, reports or historical findings linked below.
“Verified” describes the application's checking process, not independent factual
verification.

## Where the project stands

The assistant is a local-first, single-user research tool for text-based academic
PDFs. It indexes papers into PostgreSQL/pgvector, retrieves and reranks passages,
drafts claims, checks evidence and returns a refusal when the checks do not
establish sufficient support. Engineering and review tooling are complete enough
to demonstrate the approach. This is an experimental local portfolio prototype,
and the original v1 answer-quality target remains unmet; answer completeness and
verifier reliability remain open.

## Evaluated code and contracts

| Item | Current record |
| --- | --- |
| Current application code | `38e474a` (2026-10-29), grounding v49; dependency-only change since `5b95dfd` |
| Historical v49 evaluation commit | `c285cfa` (2026-10-22), grounding v49; focused controls passed, product completeness target unmet |
| Previous merged baseline | `5b95dfd` (2026-10-25), grounding v49 with FastAPI and PyMuPDF updates; superseded by PR #96 |
| Dependency security | GitHub marked four Dependabot alerts (#2–#5) fixed on 2026-10-29 after PR #96 updated `filelock` to 4.2.4 and `setuptools` to 84.2.1: three `filelock` alerts (one high, two low) and one low `setuptools` alert. The earlier `certifi` alert #1 had been withdrawn. See [Dependabot alerts](https://github.com/tristrange/research-rag-assistant/security/dependabot). |
| Latest reserved quality evaluation | Commit `6b33f221`, 2026-10-12, grounding contract v40 |
| Latest known-question end-to-end development check | v49 at `c285cfa`, 2026-10-22: 2/6 answerable cases supported (four answerable refusals), both controls refused, no pipeline errors; not fresh validation |
| Latest narrow verifier check | v49 at `c285cfa`: supported comparison accepted; all six rejection controls rejected; three deterministic decisions, four model proofs |
| Last recorded live startup check | `5b95dfd`, 2026-10-27: isolated synthetic paper (not included in the repository) and disposable PostgreSQL; startup, indexing, query and evidence inspection passed; not a quality evaluation |
| Current grounding contract | `claim-grounding-v49`; see [architecture](architecture.md#grounding-module-contract) |
| Current verified-answer settings | `gpt-oss:20b`; draft thinking low, verifier thinking medium; temperature/top-p 1; 12,288 context; 4,096 output; 300-second stage timeout |
| Retrieval | `nomic-embed-text`; `BAAI/bge-reranker-base`; 20 vector candidates; six sources, normally five reranked plus one page-reserve candidate |

Current application code is `38e474a` (2026-10-29). It includes the v49 grounding
code merged from PR #92 (`c285cfa`), later FastAPI and PyMuPDF dependency
updates, and the PR #96 `filelock` and `setuptools` security patches; the change
since `5b95dfd` is dependency-only. The v49 evaluation was run at `c285cfa` on
eight previously inspected questions with fresh retrieval from the existing
read-only index. Its captured
application, settings, Ollama, corpus and PDF fingerprints matched before and
after generation. Its two complete answers out of six do not meet the product
target or demonstrate a general improvement. The latest reserved result still
describes v40; no fresh reserved check has been run on v49 or on the current
application code.

The PyMuPDF 2.0 upgrade changes the recorded extraction version. A future
evaluation should use a freshly indexed corpus, and any comparison with the earlier
v49 run must acknowledge changed extraction provenance or chunks. Reindexing alone
does not make the inputs identical.

## Engineering gates

| Gate | Latest result |
| --- | --- |
| Python regressions | PR #96 head `3e37627`: 494 test methods; 477 passed, 17 PostgreSQL contracts skipped locally; the CI job passed |
| JavaScript logic | 29 passed locally on `5b95dfd`; the PR #96 CI job passed on `3e37627` |
| Real-browser smoke | 7 passed locally on `5b95dfd`; the PR #96 CI job passed on `3e37627` |
| Static checks | Ruff and strict mypy (91 files) passed locally on `3e37627`; CodeQL passed in PR #96 |
| PostgreSQL contracts | Passed in the PR #96 Ubuntu CI job against disposable pgvector |
| Lockfile | `uv lock --check` passed locally on `3e37627` |
| CI workflows | `Python, UI and types`, `PostgreSQL contracts` and `CodeQL` passed for PR #96 head `3e37627`; this documentation update is not represented in that record |
| Performance baseline | Pending; instrumentation exists, no measured baseline is recorded |
| Live startup and synthetic example trial | 2026-10-27 on `5b95dfd` with an isolated synthetic paper (not included) and disposable PostgreSQL: startup and indexing passed; both example questions returned `insufficient_evidence`; not a quality evaluation |

The local checks on `5b95dfd` used the supported Apple Silicon macOS target and
Python 3.14; the JavaScript suite ran on the locally installed Node.js 26. The
documented target and CI use Node.js 24. Full commands and setup are in the
[development guide](development.md) and [fresh-install checks](install-smoke-test.md).
The PR #96 head and merge commit `38e474a` have identical file contents.

## Review evidence

No independent human review has been completed. “Independent” below is not used
as a synonym for AI review.

| Evidence | Scope and result | Status |
| --- | --- | --- |
| [Third reserved fresh-question check](local-v1-fresh-check-r3.md) | Eight AI-authored questions: 2 of 6 answerable cases supported, both controls refused, three safe refusals, one output-budget error; no material unsupported displayed claim or attribution error observed | **Failed** the unchanged stopping rule; see the [reservation protocol](../benchmarks/local-v1-fresh-check-2026-10-12-r3.json) |
| [Question-copy typography replay](../benchmarks/verifier-question-typography-results-2026-10-21.json) | Two saved-source development cases: one supported answer, one answerable refusal; the target U+2011 failure was not reproduced | Development only; fresh reserved validation **not completed** |
| [Proof-window v45 check](../benchmarks/verifier-proof-window-v45-results-2026-10-22.json) | Source-faithful positive rejected; broader replay not started | **Failed**, retained; superseded by a different v49 implementation |
| [Complete-context v49 check](../benchmarks/verifier-context-v49-results-2026-10-22.json) | Seven targeted controls pass; known-question pipeline: 2/6 supported complete answers, four answerable refusals, both controls refused; no unsupported displayed claim or attribution error observed | Focused PR acceptance passed (pre-merge); product completeness rule **not met**; fresh validation not completed |
| [AI-assisted development review](v1-readiness.md#development-review-protocol-frozen-before-new-generation) | 16 historical inspected cases: 12 passed, including 8 of 12 answerable cases and all 4 controls | Accepted as portfolio evidence; not current-code accuracy or independent validation; see the [review record](../benchmarks/v1-development-review.json) |
| Optional human worksheet | Not completed | Outstanding |

No quality row above evaluates the current application code after the v49 merge.
The v49 row is development evidence from `c285cfa`; the reserved result is v40. The
current application code also includes later dependency updates, so it is not a new
quality result.

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

The merged v49 code keeps the strict proof instruction text. It displays
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
| Fresh validation | The v41 question-copy fix and merged v49 code have development evidence, but no newly reserved validation; the current application code also includes later dependency updates | Freeze a candidate and reserve different, not previously inspected questions; obtain independent human source review if available, otherwise report validation as not completed |
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

## Optional future work

This is the portfolio stopping point: an experimental local prototype. The focused
v49 check passed, but local v1 remains open: the known-case v49 pipeline still
returned only two of six complete supported answers, and the historical five-of-six
product target is unchanged. The current application code has not been re-evaluated
since the v49 merge and later dependency updates. Further experiments are optional,
not required for the portfolio milestone.

Before a new evaluation, use a freshly indexed corpus. The PyMuPDF 2.0 upgrade
changes extraction provenance and can change chunks; a comparison with the earlier
v49 run must record those differences. Reindexing alone does not make the inputs
identical.

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
| 2026-10-23 | Merged PR #92; grounding v49 became current `main` code. Focused controls pass; known-question completeness remains 2/6 and local v1 remains open | [v49 results](../benchmarks/verifier-context-v49-results-2026-10-22.json), `a2c869d` |
| 2026-10-25 | Updated FastAPI and PyMuPDF through Dependabot; no new evaluation. PyMuPDF 2.0 changes extraction provenance and can change chunks. Future evaluations should use a freshly indexed corpus, and comparisons with the v49 run must acknowledge those differences; reindexing alone does not make the inputs identical | `5b95dfd`, `uv.lock` |
| 2026-10-27 | Corrected the status record so v49 is described as current `main` code rather than an unmerged candidate; no quality transition | This page, `app/grounding_models.py` |
| 2026-10-27 | Tried a locally generated synthetic example PDF; the generator, its tests and the example are not included in this change. Indexing succeeded; the fact-bearing example question and the absent-answer question both refused with `insufficient_evidence`. No retry or model tuning was applied; this is not a quality evaluation | This page |
| 2026-10-29 | Recorded the portfolio stopping point: removed the unvalidated synthetic example from the proposed change and documented further experiments as optional; no application or model change | This page, `README.md` |
| 2026-10-29 | Observed four open Dependabot alerts: three for `filelock` (one high, two low) and one low for `setuptools`; the earlier `certifi` alert #1 had been withdrawn | GitHub alerts #2–#5 |
| 2026-10-29 | Merged PR #96 updating `filelock` 3.32.5 → 4.2.4 and `setuptools` 84.0.0 → 84.2.1; GitHub marked alerts #2–#5 fixed on the same date. No application code or model change | `38e474a`, `uv.lock` |

Historical reports and dated findings remain unchanged. Update this page for
validated transitions or factual corrections supported by the current repository
state; do not overstate quality.
