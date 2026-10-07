# Duration support in approved evidence

The [retrieval follow-up](qualifier-retrieval.md) returned the missing three-day
cohort passage, but the answer still cited only its numerical result. The model
approved the duration even though its selected quote established a fold change.

The grounding pipeline now checks explicit durations in each approved claim
against that claim's verifier-selected evidence IDs. An uncited retrieved passage,
an unselected excerpt, or the question's wording cannot supply this check's
support. Missing support triggers the existing single repair attempt. A repair
can cite and approve the cohort excerpt alongside the result; an unsupported
replacement is refused. The number of model stages and inference settings remain
unchanged.

The check recognizes numbers before seconds, minutes, hours, days, weeks, months
or years, including English cardinal words through ninety-nine, hyphens and exact
ranges. Signed numbers, decimal values, grouped digits and fractions preserve their
values. Fixed-unit equivalents such as one week and seven days compare exactly;
calendar months and years are not converted to a fixed number of days. A fold
change supplies no duration evidence. The helper's implementation hash is included
in the grounding fingerprint, so evaluations cannot resume across a changed guard.

This is a quantity consistency check, not proof of semantic entailment. Matching
a duration does not establish that it belongs to the correct cohort or experiment.
Other qualifiers and unsupported temporal forms, such as “short-term” or “day 7,”
still rely on semantic verification. Missing evidence can cause a refusal; this
change does not certify arbitrary scientific claims.

## Development checks

Regression tests supply a falsely positive verifier verdict: a claim containing
three-day timing is rejected when only its fold-change quote is approved, even
if the duration passage was retrieved or cited. A repair approving both excerpts
is accepted and exposes both page references; a failed repair stops after four
model calls. Offline tests use an empty model cache.

The captured false-positive draft and verifier verdict from the retrieval trial
were replayed without model calls and rejected by the new duration check.
Four known development questions were then generated once each using the exact
previously captured source arrays. No retrieval, reindexing, embeddings, reference
answers or model judge were used. The application and model fingerprints stayed
fixed throughout the run, and the original source report remained unchanged.

| Case | Observed result |
| --- | --- |
| Longitudinal assessment schedule | Supported answer after repairing invalid draft fields; cited timing matches the passage. |
| Three-day food restriction | Refusal. The initial verifier rejected the missing duration citation. Repair added that citation but also an unsupported extra claim, which verification rejected. Its result evidence ID also pointed to a different measurement. |
| Unreported IL-6 blockade | Refusal. |
| Human HbA1c control | Refusal. |

This is one answered case out of two answerable development cases, with both
unanswerable controls refused. The observed food repair remains inadequate;
neither this trial nor the synthetic repair test establishes reliable live
repair. These inspected cases do not complete the independent v1 fresh check.

Local, Git-ignored trial:
`evaluation-results/duration-grounding-trial-20261007T150654399851Z.json`.
Its SHA-256 is
`fa3c964af7f1ee27d4b0802c34e28c5ae9451893a87f0c6d9f43b66ba7205550`;
application fingerprint:
`4baa3e2fe9e048d82dcf09095e05d59a7ffc85b84ebf9c29242a046565aadd7d`.
The trial records the source-report hash, unchanged corpus provenance, settings,
all draft/verifier outputs, call counts and timings. Ollama was `0.40.0`, with
`gpt-oss:20b` digest
`9ba9cc2b4e02463b933096090530aef679d534dd91ecc9afadfb2dbfdc59f3c5`.
An independent source-based agent review binds that exact trial hash in
`evaluation-results/duration-grounding-review-20261007T151658786891Z.json`.
It found no emitted unsupported answer and confirmed the food case's incomplete
coverage and incorrect repair evidence selection; it made no model calls.
