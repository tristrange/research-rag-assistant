# First unseen-paper vector-reserve comparison

## Frozen protocol, before retrieval or answer generation

PR #20 added an opt-in fourth raw source: the highest vector-ranked candidate
absent from the reranked top three. The first development comparison on the
mitochondrial-dynamics paper recovered one missing answer, but all three papers
used so far have been inspected during tuning. This trial checks the unchanged
`reranked` and `vector_reserve` strategies on a fourth paper that has not been
queried or indexed for this project. Do not use its results to revise either
strategy before both first runs finish.

Use Carlsson, Frank, et al. (2025), *Activin receptor type IIA/IIB blockade
increases muscle mass and strength, but compromises glycemic control in mice*,
Molecular Metabolism 102, 102261, [DOI](https://doi.org/10.1016/j.molmet.2025.102261).
The [University of Copenhagen record](https://researchprofiles.ku.dk/en/publications/activin-receptor-type-iiaiib-blockade-increases-muscle-mass-and-s/)
lists Emma Frank and CC BY. The published PDF also states CC BY 4.0. Its copy
from [NLM PMC Open Data](https://pmc-oa-opendata.s3.amazonaws.com/PMC12556210.1/PMC12556210.1.pdf)
is stored only at ignored `data/activin-receptor-2025.pdf`, SHA-256
`b60d1a5d4612320f50863460f11d763b524a20d45420ff8c8a0f62d97478f254`.
Do not commit the PDF or raw answer reports.

The frozen [`benchmarks/activin-receptor-2025.json`](../benchmarks/activin-receptor-2025.json)
has eight answerable and two unanswerable assistant-authored cases. The
answerable cases cover dosing, a glucose test, human myotubes, two treatment
durations across separate pages, lean mass, engineered tissue force, heart
glycogen, and the authors' qualified interpretation of glycemic disruption.
The unanswerable cases ask about female-mouse glucose tolerance and survival
benefit; methods specify male mice and no survival experiment. These are not
independently reviewed labels. In particular, claims from cited studies must
not be attributed to this paper's experiments.

Run `--validate-only` against the exact PDF before indexing. Create a dedicated
PostgreSQL database with no other documents, initialize pgvector, and index the
PDF once with the unchanged extraction, chunking, and embedding code. Record
the corpus fingerprint and verify the index contains only this document. Run
one complete verified-answer evaluation per arm, in manifest order: first
`reranked --top-k 3`, then `vector_reserve --top-k 3`. Pin GPT-OSS 20B for
verified drafting/verification, Qwen3 8B for judge and unused plain generator,
draft thinking `low`, verifier thinking `medium`, the same judge calibration,
prompts, models, PDF, labels, and corpus in both arms. Save to separate fresh
ignored JSON reports. Do not retry a completed case or select only successes.
If interrupted, preserve the original partial report and use the runner's
resume mechanism with the same settings rather than regenerating completed
answers. Record any calibration or runtime failure as a failed attempt.

Compare per-case substantive answers, source support and attribution, true and
false refusals, exact-quote hits, context size, and answer time. The exact-quote
metric only recognizes a complete quote in one returned source; inspect split
evidence manually. Judge scores and assistant-authored labels are aids, not
independent expert adjudication. Sequential run order and model variability
limit latency claims. This paper still shares authors and a biomedical domain
with the development corpus, so one favorable comparison would not establish
general RAG reliability or by itself justify changing the API default.

```bash
curl --fail --location \
  'https://pmc-oa-opendata.s3.amazonaws.com/PMC12556210.1/PMC12556210.1.pdf' \
  --output data/activin-receptor-2025.pdf
uv run python -m scripts.evaluate_answers \
  --benchmark benchmarks/activin-receptor-2025.json \
  --pdf data/activin-receptor-2025.pdf --validate-only

docker compose exec db createdb -U rag rag_activin_2025_eval
export RAG_DATABASE_URL='postgresql+psycopg://rag:rag@localhost:5432/rag_activin_2025_eval'
uv run python -m scripts.init_db
uv run python -m scripts.index_pdf data/activin-receptor-2025.pdf

export RAG_GENERATOR_MODEL=qwen3:8b RAG_GROUNDING_MODEL=gpt-oss:20b
export RAG_JUDGE_MODEL=qwen3:8b RAG_DRAFT_THINK=low RAG_VERIFIER_THINK=medium
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
uv run python -m scripts.evaluate_answers \
  --benchmark benchmarks/activin-receptor-2025.json \
  --pdf data/activin-receptor-2025.pdf \
  --strategy reranked --top-k 3 --answer-mode verified \
  --output evaluation-results/activin-reranked-verified-first.json
uv run python -m scripts.evaluate_answers \
  --benchmark benchmarks/activin-receptor-2025.json \
  --pdf data/activin-receptor-2025.pdf \
  --strategy vector_reserve --top-k 3 --answer-mode verified \
  --output evaluation-results/activin-vector-reserve-verified-first.json
```

## First-run findings

The protocol and manifest were committed as `fd1c8fe` before this paper was
indexed or queried. The isolated index contained 233 chunks of only this PDF,
with corpus SHA-256
`6421012d6fd57a87131d03ed8625bdb9fc737eacfe7faa65e5b4fc34d993a3be`.
Both judge calibrations passed. The baseline ran first from 01:51:40 to
02:01:03 UTC on 2026-09-23; vector reserve followed from 02:01:16 to 02:16:59
UTC. Both reports are complete, use the same PDF, cases, corpus, models,
prompts, thinking settings, and judge configuration, and contain one generation
per case with no retries or intervening changes.

| First-run outcome | Reranked top 3 | Vector reserve |
| --- | ---: | ---: |
| Answerable cases answered | 8/8 | 7/8 |
| Unanswerable cases refused | 2/2 | 2/2 |
| Exact-quote evidence hits | 7/8 | 8/8 |
| Recorded pass rate | 9/10 | 9/10 |
| Mean rendered source characters | 1,412 | 1,882 |
| Mean answer time | 40.7 s | 74.8 s |

The baseline answered `activin-long-regimen` correctly from the page-1 abstract
and cited page 1. Its frozen evidence label instead quotes the page-2 methods,
which the baseline did not return. Vector reserve added page-2 chunk 13 and
therefore passed the exact-quote gate, but produced the same answer with a page-1
citation. This is a gain in labelled-source coverage, not an observed gain in
answer quality for that case.

For `activin-liver-tg-duration`, the baseline returned the 2.8-fold short-term
result on page 3 and 2.6-fold long-term result on page 7, answered both, and
cited both pages. Vector reserve retained those three baseline chunks and added
page-7 chunk 3, then returned the fixed insufficient-evidence refusal. Both
labelled quotes were present in both arms. The added chunk also contains other
diet-induced-obesity comparisons, but one run cannot show whether those details
caused the refusal or whether generation/verification varied. The saved answer
report does not contain the original draft and verifier trace, so it cannot
identify the refusal stage.

The other six answerable cases received correct, source-supported answers with
citations to returned pages in both arms on manual inspection. Both unanswerable
controls refused; the survival question has a cited survival study in the
references, which neither arm misattributed to this paper. The judge's aggregate
citation-support score is 1.0 in both arms, but its scoring also gives full
support to fact-free refusals. The source-size increase was about 33%. The
observed answer-time increase is from single sequential runs, not a controlled
steady-state latency measure.

The ignored raw baseline report is
`evaluation-results/activin-reranked-verified-first.json` (SHA-256
`83a77077544db45a4f9aabbccb0c8f6b5bab326ad4777ddb60d39700f053ec58`).
The vector-reserve report is
`evaluation-results/activin-vector-reserve-verified-first.json` (SHA-256
`38103c21922c900dc195a707cbfa8d7f39928222bd422576962d5a64f43bcecf`).
The PDF and reports remain Git-ignored.

After review, the local model inventory was checked on 2026-09-23. Both arms
used the same installed model tags; Ollama reported these full digests, and the
reranker cache contained this sole Hugging Face snapshot:

| Role | Model | Local revision |
| --- | --- | --- |
| Verified draft and verifier | `gpt-oss:20b` | `17052f91a42e97930aa6e28a6c6c06a983e6a58dbb00434885a0cf5313e376f7` |
| Judge | `qwen3:8b` | `500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41` |
| Embeddings | `nomic-embed-text:latest` | `0a109f422b47e3a30ba2b10eca18548e944e8a23073ee3f3e947efcf3c45e59f` |
| Cross-encoder reranker | `BAAI/bge-reranker-base` | Hugging Face snapshot `2cfc18c9415c912f9d8155881c133215df768a70` |

Ollama's installed-model modification times precede both runs. These revisions
were recovered from the local inventory after the trial, not checkpointed in
the raw reports at generation time, so they are the best available provenance
rather than a cryptographic proof of the weights used for each call. Future
evaluations should capture model digests and the reranker snapshot in the report
before generation.

This first unseen-paper comparison is mixed and does not justify changing the
normal API default. It is a small, assistant-labelled set in a related research
area, and the paper is now development data. A separate fixed-source diagnostic
could inspect whether the cross-page refusal reproduces and which stage produces
it; any replay would be a new generation trial, not a reconstruction of this
first run.
