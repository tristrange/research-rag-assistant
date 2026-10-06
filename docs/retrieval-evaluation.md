# Retrieval evaluation

Run from the repository root after loading `.env`. Use an isolated benchmark
index with the matching PDF and labels; do not replace your personal library.
These commands do not generate answers.

The retrieval pipeline is evaluated on development questions with expected document/page labels.

Hit@k is the fraction of questions with at least one expected page among the first k chunks. Relevance is currently labelled at page level.

The dated results below describe a small inspected development set, not current
independent answer accuracy. The normal chunk target is 500 characters with
100-character overlap; retrieval gets ten candidates and reranks to three.

### Compare reranking

Use the same indexed paper and the shared development questions in
`scripts/retrieval_cases.py`:

```bash
uv run python -m scripts.compare_reranking
```

The defaults compare vector search returning 3 chunks with vector search returning
10 candidates followed by reranking down to 3, matching the assistant's current
retrieval settings. Each strategy is warmed once before measurement, then evaluated
three times per question with alternating execution order. Timings include query
embedding and database retrieval, plus cross-encoder inference for the reranked
strategy; model loading and answer generation are excluded.

The output includes Hit@1, Hit@k, MRR@k (zero when no relevant result is in the top k),
mean/median latency, candidate hit rate, and per-question rank changes and excerpts.
Relevance requires both the expected document and a labelled page. An improvement
or regression refers to mean reciprocal rank, not a judgement of the generated answer.

Full JSON reports are saved under `evaluation-results/`, which is ignored by Git
because reports contain PDF passages. They record the questions, all measured runs,
separate retrieval/reranking timings, settings, model names, package versions, and a
fingerprint of the indexed text and vectors. The command rejects missing documents,
duplicate chunk identities, and an index that changes during the run. It does not
modify the index.

Options:

```bash
uv run python -m scripts.compare_reranking --top-k 3 --candidates 10 --repetitions 3
```

`--document` changes the indexed filename of the **same evaluation paper**; it does
not supply labels for a different paper. `--output` chooses a JSON file; existing
files are not overwritten. If you change the chunking configuration, reindex the
paper before comparing against these results.

### Measured comparison (2026-09-14)

Local run on macOS arm64, Python 3.14.7, sentence-transformers 6.0.1, and torch 2.14.0:
12 development questions, 3 measured repetitions, 141 chunks (500 characters, 100
overlap), `nomic-embed-text` embeddings, and `BAAI/bge-reranker-base` reranking.

| Strategy | Hit@1 | Hit@3 | MRR@3 | Mean latency | Median latency |
|---|---:|---:|---:|---:|---:|
| Vector top 3 | 0.750 | 0.917 | 0.819 | 32.9 ms | 26.4 ms |
| Retrieve 10, rerank to 3 | 0.750 | 0.917 | 0.819 | 197.9 ms | 194.2 ms |

Reranking added approximately 170 ms of inference per query. One question improved
from rank 3 to 1, one worsened from rank 1 to 3, and ten were unchanged. Candidate
Hit@10 was also 0.917: the missed discussion-summary question had no labelled page
among the candidates, so reranking could not recover it.

These results do not show an aggregate page-level ranking gain on this small
development set. They also do not establish answer quality: for the conclusion
question, the baseline's matching page contained a bibliography passage, while
reranking selected the actual conclusion. Passage-level relevance labels and new
held-out questions are needed before drawing a broader conclusion about reranking.
Latency is specific to this local run. The assistant's retrieval defaults are unchanged.
