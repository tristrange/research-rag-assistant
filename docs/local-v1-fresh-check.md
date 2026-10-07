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

Pending. The [frozen question reservation](../benchmarks/local-v1-fresh-check-2026-10-07.json)
records the application, configuration, model/corpus fingerprints and label-file
hash. It is a protocol manifest, not input to the legacy single-paper benchmark
runner. The protocol and reservation are committed before generation.
Source PDFs, labels with raw quotations, generated answers and traces remain in
ignored `evaluation-results/`. Public question text and aggregate findings are
recorded alongside hashes for the local artifacts.
