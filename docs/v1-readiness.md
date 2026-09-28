# Local v1 readiness

The release goal is a personal research assistant: start it locally, maintain a
small PDF library, ask routine questions, and inspect evidence for each answer.
Hosting, accounts, OCR, and advanced cross-paper synthesis are later extensions.

## Milestones

- [ ] Human-reviewed answer quality and documented limitations.
- [ ] Cited evidence clearly distinguished from other retrieved passages.
- [ ] Straightforward library management, service checks, useful errors, and progress.
- [ ] Automated regression checks, current setup guide, architecture diagram,
      and a fresh-install smoke test.

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

Prepare a local HTML packet and CSV worksheet from the completed reports. Pin
report hashes and case IDs in `benchmarks/v1-development-review.json`. The packet
shows recorded answers and every retrieved passage, with reference labels in a
separate expandable section. Model-judge scores are omitted. Paper PDFs and the
packet stay in ignored local directories; do not commit them.

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
claim. A material failure requires a fix and a new separately reserved check;
do not rerun the same questions until they pass and call that validation.

Complete the remaining usability and release milestones, record known limits,
then tag v1. This review tooling and a green worksheet alone do not approve release.
