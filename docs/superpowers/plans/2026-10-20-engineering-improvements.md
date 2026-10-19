# Research RAG Assistant — Engineering Improvement Implementation Plan

> **For agentic workers:** Use `superpowers:subagent-driven-development` (recommended for behavior-sensitive PRs) or `superpowers:executing-plans` to implement **one PR at a time**. Use RED → GREEN → REFACTOR, run the stated gates, request a fresh review, and stop before merging without human approval. This is a planning artifact only; no application code changes are part of this plan.

**Plan date:** 2026-10-20  
**Reference repository:** `tristrange/research-rag-assistant`, `main` at `2ad65955636601620787dd13d6c62e446055887b` (2026-10-12)  
**Repository plan path:** `docs/superpowers/plans/2026-10-20-engineering-improvements.md`  
**Goal:** Improve maintainability, CI quality, grounding reliability, performance reproducibility, governance, and project discoverability without overstating model quality or breaking existing behavior.

**Architecture:** Preserve the local-first FastAPI + PostgreSQL/pgvector + Ollama application. Use additive quality gates, behavior-preserving extraction of grounding responsibilities, then separately measured semantic changes. Treat evaluations and source provenance as versioned scientific contracts.

**Stack:** Python 3.14, uv, FastAPI, SQLAlchemy, pgvector/PostgreSQL, PyMuPDF, Ollama, sentence-transformers, unittest, mypy strict, Node.js 24, Playwright, GitHub Actions.

**Source of requirements:** Current `README.md`, `AGENTS.md`, `docs/architecture.md`, `docs/development.md`, `docs/local-v1-fresh-check-r3.md` and existing tests on the pinned branch. This plan itself is the cross-cutting spec; individual PR descriptions should carry the applicable subset.

## Global constraints

- Do **not** deploy the service publicly or relax its loopback-only security boundary.
- Preserve `app.grounding.grounded_answer(...)`, current grounding contract v41, JSON/evidence shape, and evaluation-facing imports during refactors unless a separately approved change explicitly supersedes them.
- Do not conflate successful CI or synthetic tests with scientifically valid answers.
- No unreviewed loosening of attribution, evidence selection, coverage checks, or deterministic duration validation.
- Keep PDFs and raw evaluation material in Git-ignored `data/` and `evaluation-results/` as instructed by `AGENTS.md`; store public hashes, protocols, and aggregate results only.
- Preserve failed trials, frozen inputs, corpus/model digests and original reports; no cherry-picked retries or test-set laundering.
- Reindex when extraction, chunking, or embedding compatibility changes. This plan does not include changing them.
- Maintain support for Apple Silicon macOS; CI may use Ubuntu for isolated PostgreSQL contracts.
- Use only one concern per reviewable PR; no mass-format + semantic refactor in the same PR.
- New runtime dependencies require justification; prefer development-only tooling additions.

## Review focus: high-risk scenarios

1. **Citation remapping:** multi-paper `answer_each_document` retains correct source indices after extraction/refactor; test `tests/test_rag.py` and grounding contract fixtures.
2. **Safe refusal vs service failure:** unsupported answer returns insufficient evidence, whereas malformed model payload or output exhaustion remains a service error; test `tests/test_grounding.py`, `tests/test_query_mode.py`.
3. **Qualifiers and attribution:** same-experiment time/cohort/condition and references-to-other-papers are not silently treated as primary findings; test dedicated fixture regressions.
4. **Evidence boundaries:** accepted excerpt text must originate from selected passages, with no model-generated quotes, and duration/identifier guards must still apply; test `tests/test_grounding.py`, `tests/test_grounding_durations.py`.
5. **Repeatable timings:** model warm-up, cached weights, reused index, stage names and timeouts are recorded and cannot be mixed into a single misleading aggregate; test benchmark record schema and summary calculations.

## Standard verification gates

Use the repository's documented commands, with real output recorded in the PR. From a configured local checkout:

```bash
uv sync --locked
RAG_DATABASE_URL=sqlite:///:memory: HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  uv run --locked python -m unittest discover -s tests -v
node --test tests/test_ui_rendering.js
uv run --locked mypy
```

For browser-affecting PRs:

```bash
uv run --locked python -m playwright install chromium
RAG_DATABASE_URL=sqlite:///:memory: HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  uv run --locked python -m unittest discover -s tests/browser -v
```

PostgreSQL contracts use `RAG_TEST_POSTGRES_URL` with the disposable test setup from `docs/postgres-contract-tests.md`; CI already runs these independently. Grounding semantic evaluations requiring Ollama must state installed models, runtime, corpus fingerprint, cold/warm condition, and report path. Tests that skip for unavailable PostgreSQL must not be reported as passed contracts.

---

## PR 1 — Add Ruff without changing behavior

**Branch:** `chore/ruff-quality-gates`  
**Dependency:** none  
**Risk:** low–medium (accidental mass edits, lint rules disagreeing with established code).  
**Scope:** diagnostics, one isolated formatting pass if needed, docs and CI; no algorithm changes.

**Files**
- Modify: `pyproject.toml` — add a pinned/locked dev dependency `ruff` and explicit `[tool.ruff]`, `[tool.ruff.lint]` config (choose a conservative initial rule set such as `E4,E7,E9,F,I`; configure Python target for 3.14).
- Modify: `uv.lock` — generated by `uv lock`.
- Modify: `.github/workflows/regression.yml` — separate named steps for `uv run --locked ruff check .` and `uv run --locked ruff format --check .`.
- Modify: `AGENTS.md`, `docs/development.md`, `README.md` — documented commands and precedence.
- Modify: relevant Python files **only** for mechanical lint/format fixes; record code-format-only diff explicitly.

**Implementation tasks**
- [ ] Capture baseline full regression, mypy and diff on a clean worktree; record exact Ruff version selected and existing violations.
- [ ] Add Ruff to the dev dependency group; regenerate lockfile; start with conservative rules, rather than enabling every linter family.
- [ ] Run lint + format check; fix reported violations as mechanical edits; verify with `git diff --check` and inspect potential runtime-sensitive changes.
- [ ] Add CI steps and local documentation. Make `ruff check` and `ruff format --check` required checks **after** first green run.
- [ ] Run all standard gates and PostgreSQL job; compare behavior-sensitive tests to baseline; reviewer checks no semantic changes.

**Acceptance:** both Ruff checks, mypy, existing CI jobs and behavior regressions green; no altered public APIs or evaluation outcomes attributable to this PR; `uv.lock` synchronized. **Rollback:** revert lint/format changes together and restore previous lockfile.

## PR 2 — Freeze grounding contracts and create extraction seams

**Branch:** `refactor/grounding-contract-tests`  
**Dependency:** PR 1 merged  
**Risk:** medium.  
**Scope:** tests and explicit contracts only; no production behavior changes yet.

**Files**
- Modify: `tests/test_grounding.py`, `tests/test_draft_sources.py`, `tests/test_grounding_durations.py`, `tests/test_rag.py`, `tests/test_query_mode.py` — characterize boundary conditions.
- Create: `tests/fixtures/grounding_contracts/` with **synthetic**, manually inspectable, license-safe JSON fixtures and expected public responses.
- Modify: `docs/architecture.md` — document existing module responsibilities and contract before extraction.

**Interfaces to freeze:** `grounded_answer(question, sources, claim_evidence=...)`; existing `grounding_fingerprint`, `generate_draft_json`, `generate_verification_json`, `verify_draft`, `generate_approved_proof_json` exports and any evaluation-script imports discovered by `rg 'from app.grounding|app.grounding\.'`.

**Implementation tasks**
- [ ] Inventory every `app.grounding` import (including `scripts/`, tests and compatibility exports); record call graph of generation, verification, repair, proof, evidence assembly.
- [ ] Add synthetic tests for: supported negative vs missing evidence, malformed verifier JSON, nonexistent source ID, external-paper attribution, repaired qualifiers, quote provenance, adjacent same-experiment excerpts, citation indices after multi-paper aggregation, output exhaustion vs refusal.
- [ ] Run each new characterization test on the existing main behavior. If a test encodes *desired* but absent behavior, move it to PR 4 as a deliberately failing reliability test; do not alter baseline behavior here.
- [ ] Lock down stable public data contracts and expected exception propagation with fixture assertions, not brittle internal call-count assertions.
- [ ] Run Python, JS, mypy and integration suites.

**Acceptance:** expanded contract tests pass against unchanged production code; reviewers can compare public response and error behavior before and after module extraction. **Rollback:** revert tests/docs only.

## PR 3 — Split `app/grounding.py` into cohesive components

**Branch:** `refactor/grounding-components`  
**Dependencies:** PRs 1–2 merged  
**Risk:** high (subtle semantic drift across LLM/verifier stages).  
**Scope:** behavior-preserving extraction; no prompt tuning, new retries, inference-setting changes or altered evidence thresholds.

**Proposed files and ownership** (confirm import graph in PR 2 before finalizing):
- Keep `app/grounding.py` — stable public facade, orchestration entry point (`grounded_answer`) and compatibility re-exports.
- Create `app/grounding_models.py` — Pydantic draft, claim, verifier, proof contracts and validation types.
- Create `app/grounding_prompts.py` — draft, repair and verifier prompt builders and text catalogue construction.
- Create `app/grounding_validation.py` — structural, source-ID, attribution, coverage, identifier and verifier approval checks; reuse `app/grounding_durations.py`.
- Create `app/grounding_evidence.py` — bounded candidate evidence construction, excerpt selection, approved evidence assembly, rendering.
- Modify: `tests/test_grounding.py`, `tests/test_draft_sources.py`, `tests/test_grounding_durations.py` for module-specific unit tests, retaining public-facade tests.
- Modify: `docs/architecture.md` to show new dependency direction.

**Implementation tasks (separate commits, each independently green)**
- [ ] Move immutable Pydantic schemas/constants to `grounding_models.py`, re-export existing names; run focused grounding/mypy tests and commit.
- [ ] Move prompt generation and source catalogue to `grounding_prompts.py` without changing prompt bytes. Add snapshot/byte-equivalence assertions for synthetic inputs; run focused tests; commit.
- [ ] Move pure structural and semantic validation helpers to `grounding_validation.py`; keep deterministic duration verification intact; run focused tests; commit.
- [ ] Move evidence selection and rendering into `grounding_evidence.py`; preserve exact excerpt, ordering, citation mapping and refusal behavior; run focused tests; commit.
- [ ] Keep a thin facade/orchestrator; examine cycles, side effects and configuration evaluation timing; run full standard/CI gates. For local inference, compare a small *recorded* set of calls but treat outputs as nondeterministic unless fully stubbed.

**Acceptance:** no changed prompt bytes for equivalent inputs, no changed serialized public responses with stubbed deterministic providers, all exceptions/refusals and compatibility imports preserved, all CI green, measurable reduction in mixed responsibilities within `grounding.py` without circular imports. **Rollback:** revert entire extraction PR; no database migration involved.

## PR 4 — Instrument and diagnose verification failures

**Branch:** `feat/verification-diagnostics`  
**Dependencies:** PR 3 merged  
**Risk:** medium (sensitive source leakage, instrumentation side effects).  
**Scope:** observability first, **not** a claim that accuracy improved.

**Files**
- Modify: `app/llm/telemetry.py` — stable stage labels and counters for draft, verifier, repair, final proof, output-limit and invalid-JSON events.
- Modify: `app/llm/ollama.py`, `app/grounding.py` and the extracted modules — instrumentation hooks at stage boundaries, avoiding source/prompt logging by default.
- Modify: `scripts/record_grounding_replays.py`, `scripts/replay_grounding.py`, `scripts/evaluate_grounding_replays.py` **only where compatible**, or create a new opt-in diagnostic script if schemas are incompatible.
- Create: `tests/test_verification_diagnostics.py` — timing/outcome, redaction, failure classification and stage ordering.
- Modify: `docs/answer-evaluation.md` / `docs/grounding-refusal-diagnostics.md` — interpretation and safety notes.

**Implementation tasks**
- [ ] Define versioned `VerificationTrace` diagnostics schema: contract/model/settings fingerprint, stage, elapsed milliseconds, attempt, parse/schema status, verifier/refusal reason category, prompt/output token metadata when reported, and diagnostic ID; exclude passages, raw questions and freeform model output from public records.
- [ ] RED test: a stubbed malformed verifier response is tagged `invalid_schema`, not `insufficient_evidence`; expected original API exception behavior is unchanged.
- [ ] RED test: output exhaustion records exact stage and attempt, with preserved error propagation.
- [ ] RED test: normal refusal and approved answer traces show stage ordering; raw text and credentials absent from sanitized report.
- [ ] Add instrumentation at the narrowest possible adapter/orchestration boundaries; run focused tests and full gates.
- [ ] Reclassify the recorded Oct 12 development failures *as analysis only*, without rewriting or deleting raw reports or rerunning original validation.

**Acceptance:** stable diagnostics detect refusal mechanisms, invalid response and token exhaustion; no source text in committed traces; no changed model prompts or decision policy; no exception masking; CI green.

## PR 5 — One narrowly-scoped verifier reliability hypothesis

**Branch:** `fix/verifier-<specific-failure>`  
**Dependencies:** PR 4 merged  
**Risk:** high; scientifically meaningful behavior change.  
**Scope:** choose **one** diagnosed failure mechanism. Suggested first candidate: normalized question-identifier typography (hyphen/punctuation) **only if** diagnostics confirm it can be handled without weakening identifier/scope checks. Other candidates (adjacent evidence selection; repair attribution; output budgets) get separate future PRs.

**Files (candidate-specific)**
- Modify: `app/grounding_validation.py` and/or `app/grounding_prompts.py` / `app/grounding_evidence.py`, depending on root cause.
- Modify: `tests/test_grounding.py`, `tests/test_draft_sources.py`, `tests/test_grounding_durations.py`; add synthetic adversarial near-matches and controls.
- Modify: `docs/question-identifiers.md`, `docs/answer-evaluation.md` and relevant dated evaluation document.
- Create: a dated, public aggregate protocol/result JSON under `benchmarks/` **only after** controlled execution; ignore all raw model passages and reports.

**Implementation tasks**
- [ ] Write a brief hypothesis specifying failure, proposed minimal decision change, false-accept risk, expected improvement, and stop rule.
- [ ] RED tests: semantically identical typographic variants pass while truly different identifiers (cohort numbers, doses, conditions, study attribution) remain rejected. Add exact supporting/contradictory quote cases.
- [ ] Implement minimal normalization or verifier fix; no global permissive fuzzy matching, no ignored qualifiers, no changing retrieval parameters.
- [ ] GREEN focused tests, full Python/JS/browser/mypy/PostgreSQL gates.
- [ ] Run existing *development* cases under frozen models/index and preserve all outcomes including failures. Compare refusal causes, complete answers, unsupported acceptances and latency; results are development evidence only.
- [ ] Reserve **new, not previously inspected questions** with pre-registered acceptance criteria and independent human source review, then run exactly the declared trials once. If unavailable, report validation as **not completed**, not passed.

**Acceptance:** synthetic positive and adversarial tests green; zero observed material unsupported claim in newly reserved validation; improvements to completeness meet **pre-registered**, not retrospectively adjusted criteria. Do not mark reliability fixed from development-set success alone. **Rollback:** one revert returns to previous v41 behavior; preserve all evaluation reports.

## PR 6 — Reproducible stage-level performance baseline

**Branch:** `perf/reproducible-baseline`  
**Dependencies:** PR 4 for telemetry; can run in parallel with PR 5 after PR 4  
**Risk:** medium (misleading comparisons, accidental exposure of private corpus, cold-vs-warm bias).

**Files**
- Create: `scripts/benchmark_pipeline.py` — CLI to run existing scoped queries and export a versioned metadata+metrics record to an ignored destination; avoid changing application response interfaces.
- Create: `app/performance.py` or reusable helpers under `app/llm/telemetry.py` — monotonic stage timer and summary calculations, with clear boundaries.
- Create: `tests/test_performance.py`, `tests/test_benchmark_pipeline.py` — synthetic clock, aggregation, missing stages, warm-up labeling, report schema and redaction.
- Create: `docs/performance-baselines.md` — hardware/runtime prerequisites, repeat counts, statistical reporting and interpretation.
- Modify: `AGENTS.md`, `docs/README.md` to link benchmark procedures.

**CLI contract to implement:** `uv run python -m scripts.benchmark_pipeline --cases <manifest> --output evaluation-results/<unique-report>.json --runs <n> --warmup <n>`; enforce non-overwrite by default, emit baseline schema version and failure records, not only successful trials.

**Minimum record:** commit SHA, UTC timestamp, OS/architecture, Python, Ollama version and exact model tag/digest, settings hash, corpus/index fingerprint, reranker identifier/cache condition, query manifest hash, stage breakdown (embedding, vector search, rerank, draft, verify, repair, proof), total wall time, token counts if provider supplies them, peak memory if reliably measurable, cold/warm, refusal/error categories.

**Implementation tasks**
- [ ] RED tests of time arithmetic, zero/missing stages, error paths, schema validation, output collision refusal and redaction.
- [ ] Add deterministic monotonic measurement hooks (not `time.time()` for durations) and a minimal benchmark runner; do not enable verbose telemetry in normal responses.
- [ ] Run synthetic benchmark tests and all CI gates; document that CI performance numbers are nonrepresentative.
- [ ] Define a fixed, legally shareable manifest and a standardized local protocol: e.g. one warm-up + five measured runs per case; preserve all runs; report median, p90 and raw individual samples, with variance and hardware state.
- [ ] Record one local baseline only when the target Apple Silicon hardware, models and corpus are actually available; otherwise ship instrumentation with `baseline pending` status.

**Acceptance:** anyone with the declared services and permitted corpus can reproduce the procedure; reports prevent incomparable corpus/model conditions from silently merging; error/timeout runs retained; initial baseline explicitly marked missing if not executed.

## PR 7 — GitHub controls and dependency maintenance

**Branch:** `chore/repository-governance`  
**Dependency:** PR 1 stable and green; can execute independently of PRs 2–6  
**Risk:** low–medium (blocked merges, noisy PRs, repository settings outside version control).

**Files**
- Create: `.github/dependabot.yml` for uv/pip dependencies and GitHub Actions if supported by the ecosystem; group patch/minor updates carefully, keep major changes separate.
- Create: `.github/pull_request_template.md` with sections for scope, behavior, evidence, tests, provenance and rollback.
- Create: `.github/CODEOWNERS` **only if** ownership/rules are meaningful for this solo repo; otherwise omit.
- Modify: `docs/development.md`, `AGENTS.md` — branch workflow, gate list and review rules.
- External settings (**manual owner action**): configure ruleset/branch protection for `main`, PR-only merging, required named checks (`Python, UI and types`, `PostgreSQL contracts`, plus any new lint jobs), block force pushes. Select rule names from actual GitHub check runs, not guesses.

**Implementation tasks**
- [ ] Confirm the existing CodeQL/default-code-scanning setup in GitHub settings; do not assume a dedicated workflow file is necessary.
- [ ] Add Dependabot and PR template, syntax-check YAML, submit review to ensure security updates won't silently change models/locked environment.
- [ ] Verify dependency PRs respect `uv.lock` synchronization; document `uv lock` and all required checks.
- [ ] Owner enables branch rules after all checks are confirmed green and captures screenshot/configuration summary in PR notes (do not commit secrets).
- [ ] Open a **test draft PR** to prove required checks appear; close without merge; revert settings if they block legitimate work.

**Acceptance:** branch protections verified in GitHub UI/API, bypass policy deliberate, force pushes blocked, dependency automation produces actionable PRs, human review required for semantic changes. **Note:** settings cannot be enforced just by merging files; owner must apply them.

## PR 8 — Single project status and development roadmap

**Branch:** `docs/project-status-roadmap`  
**Dependencies:** can draft after PR 1; final references updated after PR 5/6 outcomes  
**Risk:** low (stale or misleading product claims).

**Files**
- Create: `docs/status.md` — concise current status, last evaluated commit, model/grounding contract, known blockers, latest independently reviewed results, next experiment, links to raw protocols and historical docs.
- Modify: `README.md` — 5–8 line status summary linking to `docs/status.md`, retain accurate warning on verified labels.
- Modify: `docs/README.md`, `docs/v1-readiness.md` — single authoritative navigation/status and decision log.
- Modify: `AGENTS.md` — requirement to update `docs/status.md` only on validated status transitions; keep historical evidence unchanged.

**Implementation tasks**
- [ ] RED documentation consistency check (small test/script or explicit link audit) that README and status point to an existing protocol/aggregate record, and no latest-results links 404.
- [ ] Create compact tables for engineering gates, semantic validation, security/deployment limits, open blockers, decision and next steps. Label AI-authored benchmark review honestly.
- [ ] Update index and README without claiming that a refactor or green CI resolves answer quality.
- [ ] Run Markdown link checks (choose one lightweight tool or script), relevant suites, and fresh technical review of all stated claims.

**Acceptance:** new reader locates run instructions, architecture, current limitations, latest valid assessment and future work within two navigational clicks; archived experiment reports remain accessible; version/quality claims match stored evidence.

---

## Recommended sequence and integration strategy

```text
PR 1 Ruff ──► PR 2 Grounding contracts ──► PR 3 Extract modules ──► PR 4 Diagnostics ──┬──► PR 5 Reliability hypothesis
                                                                                      └──► PR 6 Performance baseline
PR 1 ──► PR 7 GitHub governance
PR 1 ──► PR 8 Status docs (refresh after PRs 5–6)
```

Do not mix PRs 3 and 5: extraction must be demonstrably behavior-preserving; semantic tuning must be tested and evaluated separately. PR 5 may require multiple future small PRs for distinct failure modes. Prioritize one reliable improvement over many simultaneous changes. For each PR: self-contained plan/spec, isolated worktree, TDD, frequent focused commits, relevant green checks, fresh reviewer (ideally independently of implementation), explicit user approval before merge. Codex should never rewrite frozen benchmark evidence or mark source checks as independently human-reviewed.

## Definition of done across the program

- [ ] Engineering checks are locally reproducible and required on PRs.
- [ ] Grounding extraction preserves prompt bytes and deterministic public behavior at the time of extraction.
- [ ] Verifier errors, refusals and output budgets are transparently distinguishable.
- [ ] Any quality improvements show both adversarial unit tests and **new pre-registered** semantic evaluation results.
- [ ] Stage timing results include reproducibility metadata and all failures, without cross-run cherry-picking.
- [ ] Branch policies were **actually enabled and tested**, not merely documented.
- [ ] `docs/status.md` accurately identifies experimental status and latest evidence.
- [ ] All changes go through reviewed PRs; no public deployment or unapproved loss of privacy safeguards.

## Suggested Codex task handoff

> Read `AGENTS.md`, `README.md`, `docs/architecture.md`, `docs/development.md`, and this plan. Use the Superpowers writing-plans/executing-plans (or subagent-driven-development) discipline **for PR N only**. First inspect the repository's actual current branch and reconcile any drift from commit `2ad6595`. Create an isolated worktree and a bounded spec for that PR, keep evaluation evidence immutable, write tests first and observe RED→GREEN when behavior changes. Do not modify main or merge, push, change GitHub settings, or run destructive commands without approval. At the end provide diff summary, actual test outputs, unresolved risks, and a PR-ready description.

**Plan status:** proposed, not executed. No GitHub files, branches, rulesets, or issues were changed by creation of this document.