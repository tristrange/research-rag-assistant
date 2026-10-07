# Activin context coverage investigation

The six-passage trial still refused the short- versus long-term liver
triacylglycerol question. Both numerical results were present, but the short-term
chow-fed qualifier needed additional context. This is a known development
limitation, not an unsupported factual answer.

## Complete evidence chain

The short-term result is on PDF page 3, chunks 25–26. Its Results subsection
introduction on page 3, chunks 15–16, identifies the cohort as lean mice. The
Animals Methods on page 2, chunks 8–9, identify the lean animals' standard chow
diet. The long-term result on page 7 explicitly names its chow-fed comparison.
The two changes use their respective PBS controls; they do not establish a
statistically significant difference between treatment durations.

A scoped retrieval-only run with thirty vector candidates ranked the short-term
cohort introduction 22nd and the diet passage 27th after reranking. Both were
outside the six
selected passages. Both numerical benchmark labels already matched the first
three passages, illustrating why exact label coverage does not establish complete
question coverage. The original labels were preserved.

A separate Methods-filtered ten-candidate probe ranked the diet passage fifth,
after assay and regimen passages. Reserving just one Methods passage would miss
it. Nearby expansion around the numerical result also cannot reach the distant
cohort introduction.

One throwaway diversity probe selected six of the saved thirty candidate identities
using their stored embedding vectors and a fixed cosine-based maximal marginal
relevance weight of 0.5. It recovered the diet passage and both numerical results,
but omitted the short-term cohort introduction. This single inspected development
probe does not validate diversity retrieval, and its algorithm is not enabled in
the application. No answer generator or judge was run for these probes.

## Decision and reproducibility

Retain the current verified-search default and strict grounding checks. Widening
the pool, a single Methods reserve, or this fixed diversity selection did not
establish the complete short-term cohort/diet chain within six passages. Reliable
parent/subsection context is a possible future approach, but current chunk
metadata records coarse sections rather than subsection parent identities.
Arbitrarily adding first chunks would not establish a reliable general policy.

The existing coverage tool now accepts selected answerable cases and a bounded
candidate pool, and filters retrieval and PDF-text validation to the benchmark
paper inside a multi-paper library. It still fingerprints the entire library,
checks for changes, refuses to overwrite reports and retains partial failures.
See the [command and limits](answer-evaluation.md).

The live scoped report is
`evaluation-results/activin-qualifier-coverage-20261007T010702499932Z.json`.
It completed one measured repetition after warmup against the unchanged 1,043-chunk
four-paper corpus, whose fingerprint was
`92a2f8def85239a9dd06020d59c725f9dae52817de25e3561d6d0b8285e9b9b8`.
All returned candidates belonged to `activin-receptor-2025.pdf`. The report records
the runner source hash, model tags, selected case, cutoffs, complete candidate and
reranked passages, and timings. Model weight digests and reranker scores were not
captured by this coverage runner; this is not a controlled model comparison.
The earlier Methods and diversity probes were temporary diagnostics, not benchmark
runner reports. Their local logs are preserved alongside the scoped run.

PDFs, raw passages and diagnostic reports remain ignored. This investigation
neither resolves the refusal nor completes the reserved v1 validation.
