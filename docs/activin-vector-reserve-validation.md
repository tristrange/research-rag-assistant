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
