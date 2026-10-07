# Retaining timing and cohort evidence

The failed [fresh-question check](local-v1-fresh-check.md) exposed two retrieval
problems in normal document-scoped verified answering. Its questions are now
inspected development cases; improving them cannot overturn that validation result.

## Diagnosis and selection

A read-only probe on the unchanged 1,043-chunk library inspected fifty vector
candidates for each failing question. The longitudinal timing passage was vector
rank 13 and reranker rank 1, outside the old ten-candidate pool. For the food
restriction question, a Results passage identifying the three-day non-tumor-bearing
cohort was vector rank 4 but reranker rank 8. Several numerical-result passages
ranked above it, leaving the duration absent from the old six selected passages.
These are observed ranks for these questions, not guarantees about future retrieval.

Normal verified targeted searches now retrieve twenty candidates and retain five
reranked passages plus the highest vector-ranked passage from a document/page
not already represented. If no new page is available, use the highest unselected
vector candidate.
The source limit remains six. A regression test reproduces the food-restriction
ordering: taking the first unselected vector match would retain another numerical
passage from the same page and still lose the duration. For other explicit cutoffs, reserve one slot within
the limit; use ordinary reranking for a one-source cutoff or when all candidates
fit. Existing document filters, shared question embeddings, citations and strict
answer verification remain in place. Plain answering, overview search, expanded
context and the experimental extra-vector-candidate strategy keep their existing
selection paths. No reindex is needed.

This bounded change gives the reranker more candidates and preserves a second
selection signal. It can still miss a relevant passage or replace a useful sixth
reranked passage with a less relevant vector candidate. It does not establish
complete evidence coverage or general answer quality.

## Development checks

A new trial generated each of the two inspected failures and two unanswerable
controls once, using the normal document-scoped verified path and its built-in
repair. No labels, reference answers or model judge were supplied to generation.
Separate AI review inspected final claims, approved quotes and their source mappings.

| Development case | Result |
| --- | --- |
| Longitudinal assessment schedule | Correct timing answer with a supporting page-3 quote. |
| Food restriction, pTBC1D4 comparison | Numerical comparison correct; three-day cohort passage now retrieved, but the accepted quote still omits duration. Strict citation-coverage review fails. |
| Unreported IL6 blockade | Appropriate refusal. |
| Human HbA1c control | Appropriate refusal. |

The retrieval change succeeds at returning both missing passages; it does not
finish the food-restriction grounding fix. The model still approved a claim
containing the three-day qualifier while citing only the numerical comparison
on page 7, despite the duration being available on page 6. Retrieved context is
not equivalent to approved evidence. Keep this limitation visible and address
claim/citation completeness separately, without weakening verification.

Retrieval-only checks on the four remaining prior questions retained their central
reference evidence. No new answers were generated for those four, so this is not
an eight-case answer-quality result or a claim of complete qualifier coverage.
The failed fresh check remains unchanged; a new separately reserved question set
is still required for the local-v1 stopping rule.

The final trial used Ollama 0.40.0, GPT-OSS 20B digest
`9ba9cc2b4e02463b933096090530aef679d534dd91ecc9afadfb2dbfdc59f3c5`,
and unchanged nomic-embed-text weights. Inference settings and the 1,043-chunk
corpus matched the earlier check. Application files, corpus and observed runtime
were stable during this final trial. Ollama and the GPT-OSS digest differ from the
original baseline, so these results are not a controlled before/after comparison.
The earlier one-slot trial detected model-digest drift and remains preserved as
an invalidated diagnostic, not accepted validation. No selective retries or
mid-run application changes were used in the final trial.

Local, Git-ignored artifacts:

- `evaluation-results/qualifier-retrieval-probe-20261007T124109153397Z.json`
- `evaluation-results/qualifier-retrieval-trial-20261007T125331082033Z.json` (invalidated diagnostic)
- `evaluation-results/qualifier-retrieval-trial-20261007T130115115469Z.json`
- `evaluation-results/qualifier-retrieval-review-20261007.json`

Final trial SHA-256:
`346c589777101f4054ff2cf21e2e0f5f5721d7f3502c3a261eff8cf0499470c2`.
Its application fingerprint is
`21c4c9fa1a5f9091319281d1c9b160548f211c6a5b59250eb955bdd43866c193`.
The review binds this exact trial hash. PDFs, raw passages, historical reports,
labels and the optional human worksheet remain unchanged.
