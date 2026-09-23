# Vector-reserve retrieval experiment

The first verified run on the mitochondrial-dynamics paper answered seven of
eight answerable questions. For `cytosolic-mtdna`, the reranked top three omitted
the Mfn1/Mfn2 finding even though the relevant chunk was the second vector-search
candidate and fifth reranked candidate. The report and index remain unchanged.

This is a development experiment, not an independent accuracy estimate. A
retrieval-only inspection across the three existing development papers compared
top-three reranking, three-seed neighbor expansion, reciprocal-rank fusion, and
top-three reranking plus the highest vector candidate not already selected. The
last option adds one raw chunk without querying page neighbors. Its exact-quote
coverage was 28/34 labelled answerable cases versus 26/34 for the baseline; the
metric requires a full quote inside one returned source and therefore misses
some evidence spread across chunks. A single unjudged verified-generation probe
of `cytosolic-mtdna` with the extra chunk answered the question and cited page 4.
These observations selected the candidate; they are not validation of it.

## Prespecified next trial

Add an **opt-in** `vector_reserve` evaluation strategy. Search the usual ten
vector candidates, rerank them, keep the top three reranked chunks, then append
the first vector-ranked chunk absent from those three. Keep raw chunks and their
order; do not merge or expand neighbors. Record the strategy in the report and
preserve all returned sources for judging. Leave normal API retrieval unchanged.

Run one complete verified-answer evaluation on the already inspected
mitochondrial-dynamics benchmark (all ten cases, including the two
unanswerable controls). Use its existing isolated index, same PDF, model settings,
judge calibration, labels, and top-three cutoff as the first-run baseline. Save
to a fresh ignored JSON report; do not overwrite or resume the baseline. Compare
answer correctness, citation support, false refusals, unanswerable refusals,
answer time, and source size. Inspect individual answer/source bundles because
the exact-quote metric may miss split evidence. Run without retries or selecting
only successful cases. Any prompt or retrieval change after this run needs a new
trial and report.

This paper and the two earlier papers are development data. A favorable result
would justify a separate validation plan on an unseen paper before changing the
default retrieval behavior.
