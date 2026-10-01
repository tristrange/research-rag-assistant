# Local v1 readiness

The release goal is a personal research assistant: start it locally, maintain a
small PDF library, ask routine questions, and inspect evidence for each answer.
Hosting, accounts, OCR, and advanced cross-paper synthesis are later extensions.

## Milestones

- [ ] Human-reviewed answer quality and documented limitations.
- [x] Cited evidence clearly distinguished from other retrieved passages.
- [x] Straightforward library management, service checks, useful errors, and progress.
- [x] Automated regression checks, current setup guide, architecture diagram,
      and a fresh-install smoke test.

The browser now exposes each final accepted claim's attribution and exact
verifier-selected excerpts separately from all retrieved passages. Links open
the corresponding page's context. Refused and rejected drafts expose no claim
evidence. This completes the evidence-display implementation; it does not
complete the deferred human quality review or establish answer reliability.

Service-error guidance is implemented for the paper list and questions, including
database failures, unavailable or missing Ollama models, timeouts and output-budget
exhaustion. Failed queries permit another attempt. Read-only service checks now
run on page load and through a Check services button, checking database/schema
access and installed Ollama models. They are advisory and do not run inference or
establish answer quality. Library inventory and transactional index removal are
available through `scripts.manage_library`, alongside the existing PDF indexer.
The browser can refresh papers without a page reload and shows elapsed time
while waiting for an answer, stopping the timer on success or failure. It does
not infer backend stages or an estimated finish time. The PDF indexing CLI
reports actual reading, chunk preparation, completed embeddings, and saving;
completion is printed only after the transaction commits. This completes the
basic local usability implementation; it does not approve a release.

The `Regression checks` workflow installs locked dependencies in a fresh macOS
environment and runs the Python and browser regressions plus strict mypy. It needs
no paper library or model/database services. The [fresh-install check](install-smoke-test.md)
separates these installation checks from the live setup and question smoke test.
The [architecture diagram](architecture.md) documents the current ingestion,
retrieval, verification and service boundaries. The recorded 2026-10-01 live
startup check passed with an isolated PostgreSQL container, a synthetic PDF and
the default verified model. Existing package/model caches were reused; cold model
downloads were not tested. This completes the basic local setup/release-tooling
milestone. Green CI and successful startup do not approve release or answer quality.
Human review and the reserved final validation below remain outstanding before v1.

## Development review protocol (frozen before new generation)

Run these 16 inspected cases once each with the normal unexpanded reranked top
three, verified answering, GPT-OSS 20B, draft thinking low, verifier thinking
medium, and Qwen3 8B judging. Keep current extraction, index, embeddings, prompts,
and labels. Use isolated single-paper indexes and fresh reports. Preserve failures;
do not selectively retry completed answers. Existing reports from older prompts
or expanded contexts are not substituted for these new runs.

| Paper | Selected development cases |
| --- | --- |
| Sample | `c26-body-mass-loss`, `glucose-tolerance-protocol`, `cited-rosiglitazone`, `own-rosiglitazone-dose` |
| Housing | `housing-fat-loss`, `housing-bat-atp`, `housing-grip-runs`, `housing-female-response` |
| Mitochondrial dynamics | `cytosolic-mtdna`, `muscle-csa-sexes`, `food-intake-negative`, `rab5c-inhibitor-mouse-dose` |
| Activin | `activin-long-regimen`, `activin-human-myotubes`, `activin-liver-tg-duration`, `activin-female-gtt` |

These cover quantitative findings, methods, complementary evidence, population
and duration qualifiers, supported negative results, cited-study attribution,
and four unanswerable controls. All cases and papers have already been inspected
during development. They are not an independent validation set.

All four reports completed on 2026-09-28 using application commit `e5b9c0f`.
The selection protocol was committed as `085bcd6` before generation. Each
selected question was generated once, with no selective retries. Thomas and
Emma will review the packet together; their decisions are still pending.

Prepare a local HTML packet and CSV worksheet from the completed reports. Pin
report hashes and case IDs in `benchmarks/v1-development-review.json`. The packet
shows recorded answers and every retrieved passage, with reference labels in a
separate expandable section. Model-judge scores are omitted. Paper PDFs and the
packet stay in ignored local directories; do not commit them.

The current answer reports do not retain the original structured draft or
selected quote for each claim. This packet can assess displayed page references
against returned passages and the PDF, but cannot reconstruct the original
quote-level verification. A cited page may match multiple passages. Exposing
the selected evidence is part of the separate evidence-display milestone.

The recorded answer configuration hash is
`7851218bd54bbee9fe17a63f4aec70125d637596547e3272554948c12b31308e`.
It binds model tags and report settings, including the grounding prompt/schema
fingerprint, embedding model, and reranker. It does not pin model weight digests.
The exporter rejects reports with a different configuration even when their
file hashes match the selection manifest.

With the matching local reports and PDFs present, run from the repository root:

```bash
uv run python -m scripts.prepare_human_review \
  --output evaluation-results/v1-human-review
```

Open `packet.html` in that directory in a browser. Reviewers can inspect the
cases together and enter agreed decisions in `review.csv`; note disagreements
or disputed labels. Edit only the `decision` and `notes` columns. The remaining
columns bind the worksheet to this exact selection. The provenance file records
the source reports and index fingerprints. PDF page links open the original
local file in a new tab; the exporter checks its hash against the report before
preparing the packet.
No database or model service is needed to prepare or review the
packet. The output directory must be new so existing review work is preserved.

To count decisions and detect pending cases, missing rows, or unresolved issues:

```bash
uv run python -m scripts.prepare_human_review \
  --summarize evaluation-results/v1-human-review/review.csv
```

The review CSV is bound to the frozen selection; it cannot be reused after
changing reports, case IDs, or configuration. Decisions and notes stay local.

## Human review

A human reviewer should read the question and answer first, then inspect the
original PDF, cited passages, and reference label. Record one decision per case:

- `pass`: the answer is correct and sufficiently complete, its cited passages
  establish all material claims and requested qualifiers, and attribution is
  accurate; or it appropriately refuses an unanswerable question.
- `needs_fix`: a wrong or incomplete answer, unsupported claim, attribution or
  citation failure, or refusal to an answerable question. Explain the failure.
- `label_issue`: the reference answer, answerability, or evidence labels need
  correction before judging the response. Explain the disputed label.
- `pending`: not yet reviewed.

Do not grant a pass merely because a labelled quote appears in retrieved text.
Population, dose, duration, comparison, and current-study attribution must also
be established by the passages the answer cites. Alternative valid evidence is
acceptable; a long label split across chunks is not automatically a retrieval
failure. A fact-free refusal can be safe while still revealing missing retrieval.

Human review remains outstanding until a person completes the worksheet. An
assistant's inspection or a model-judge score does not complete this milestone.
Resolve material issues in bounded follow-up changes, preserving original labels
and reports. Version corrected labels rather than silently replacing history.

## Final validation and stopping rule

After development fixes, freeze the candidate configuration. A human should
prepare six to eight fresh questions, including at least two unanswerable
questions, and keep them out of tuning until that freeze. Existing papers may
be reused, but this is then a fresh-question check in a known domain, not an
unseen-paper or general scientific reliability benchmark.

The local v1 target is no observed material unsupported claim or attribution
error, appropriate refusal on every unanswerable control, and correct,
sufficiently complete cited answers for at least 80% of answerable questions in
that small final set. Report exact counts and limitations, not a broad accuracy
claim. An unsupported claim, attribution error, inappropriate unanswerable
answer, or coverage below that target requires a fix and a new separately
reserved check; do not rerun the same questions until they pass and call that
validation. Any allowed false refusals must be documented as limitations.

Complete the remaining usability and release milestones, record known limits,
then tag v1. This review tooling and a green worksheet alone do not approve release.
