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

## First full development run

The predeclared protocol was committed as `1aba1d0` before the full run. The
unchanged isolated index contained 387 chunks of the mitochondrial-dynamics
paper, with corpus fingerprint
`af3c6850cfa80378e0092e1e5a5deae396d8b87a512b9bc7265b986134d29ac2`.
Judge calibration passed. All ten cases ran once, in manifest order, with the
same models and thinking settings as the earlier three-passage run. The complete
ignored report is
`evaluation-results/mitochondrial-dynamics-vector-reserve-verified-first.json`
(SHA-256 `925839c6afd3bf5065f97b5df9cbd7d70a5bc8f1c10fc373bef69738f731e6ad`).

| Outcome | Reranked top 3 | Vector reserve |
| --- | ---: | ---: |
| Answerable cases answered | 7/8 | 8/8 |
| Unanswerable cases refused | 2/2 | 2/2 |
| Exact-quote evidence hits | 7/8 | 7/8 |
| Recorded pass rate | 9/10 | 9/10 |
| Mean rendered source characters | 1,430 | 1,902 |
| Mean answer time | 37.7 s | 65.6 s |

The `cytosolic-mtdna` answer correctly says that cytosolic mtDNA increased in
Fis1/Drp1-deficient myoblasts but not in Mfn1/Mfn2-deficient myoblasts, citing
page 4. Manual inspection confirms both findings in returned page-4 chunks 4
and 2 respectively. The judge scored correctness, completeness, and source
support at 2/2. The exact-quote metric still marks the case as a miss because
its single long label spans chunks 2–4 and the returned raw sources contain
chunks 2 and 4 separately. Do not read the unchanged recorded pass rate as an
unchanged answer-quality outcome or silently alter the metric for this trial.

The other seven answerable cases received correct, source-supported answers
under the judge, and both unanswerable cases returned the fixed refusal. There
were no observed answer regressions in these ten cases. The extra passage raised
mean rendered source size by about 33%. Mean answer time was higher in this
single sequential run, but model loading and response variability were not
controlled, so it is not a steady-state latency estimate. The assistant-authored
labels and local model judge are development evidence only. Normal API
retrieval remains the three-passage default pending independent validation.

After review, `vector_reserve` rejects `--top-k 10`: with ten fetched candidates,
there would be no unused candidate to append. It also raises if a smaller corpus
has no extra candidate. This input guard does not change the ten-case trial's
selected sources or answers; that run used `--top-k 3` and had ten candidates.

To reproduce this opt-in trial with the matching local PDF, isolated index, and
model settings, use a fresh output path:

```bash
RAG_DATABASE_URL='postgresql+psycopg://rag:rag@localhost:5432/rag_mito_2023_eval' \
RAG_GENERATOR_MODEL=qwen3:8b RAG_GROUNDING_MODEL=gpt-oss:20b \
RAG_JUDGE_MODEL=qwen3:8b RAG_DRAFT_THINK=low RAG_VERIFIER_THINK=medium \
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
uv run python -m scripts.evaluate_answers \
  --benchmark benchmarks/mitochondrial-dynamics-2023.json \
  --pdf data/mitochondrial-dynamics-2023.pdf \
  --strategy vector_reserve --top-k 3 --answer-mode verified \
  --output evaluation-results/mitochondrial-dynamics-vector-reserve-new-trial.json
```
