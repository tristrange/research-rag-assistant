# Unexpanded verified-answer evaluation on a third paper

## Protocol frozen before generation

Application baseline: merged `main` at `f2edf14` (PRs #17 and #18 merged). The
change in PR #17 addressed verifier refusals seen with expanded context. Test
the current verified answer path with the API's normal retrieval selection:
reranking, three passages, and no neighbor expansion. `scripts.evaluate_answers`
calls the same `answer_question` function as the API with those parameters. This
is a quality check of that path, not a change to the default answer mode.

Use the version-of-record PDF for Irazoki et al., *Disruption of mitochondrial
dynamics triggers muscle inflammation through interorganellar contacts and
mitochondrial DNA mislocation*, Nature Communications 14, 108 (2023), DOI
10.1038/s41467-022-35732-1. Emma Frank is an author. The publisher identifies
the article as CC BY 4.0. Download the [publisher PDF](https://www.nature.com/articles/s41467-022-35732-1.pdf)
to ignored `data/mitochondrial-dynamics-2023.pdf`; use the exact PDF with SHA-256
`d9b9673dfe072f2327a5f3902807eb1168039a90a2cdb27c637cc017b21bc8a0`.
The [publisher article and license notice](https://www.nature.com/articles/s41467-022-35732-1)
provide authorship and reuse terms. This is a different study from the two papers
already used for development, although it shares researchers and muscle biology.

The frozen manifest is `benchmarks/mitochondrial-dynamics-2023.json`: eight
answerable and two unanswerable questions in its listed order. Its evidence
excerpts are exact PDF extraction on numbered pages. The labels are
assistant-authored, not independently reviewed by a domain expert. `holdout`
means only that this paper and question set were reserved before this first run;
after results are inspected, treat the set as development data. Do not claim
scientific or broad-domain accuracy from ten cases.
Manifest SHA-256: `b78cb939f70329989dc9c39e1954c8e53a2122e9cd4da5956c3bdecec5e4f3cd`.

Pin installed GPT-OSS 20B `17052f91a42e` for verified drafting and verification
at temperature zero, with draft reasoning `low` and verifier reasoning `medium`.
Pin Qwen3 8B `500a1f067a9f` as the judge; keep the generator setting at Qwen3 8B
for completeness although verified mode uses GPT-OSS. Use the existing embedding
and reranker models, prompts, judge calibration, and deterministic checks. Record
their fingerprints in the report. Change no code, labels, retrieval settings, or
model settings during the run. Do not retry a completed answer to improve it.

Index only this paper in a dedicated database. Run the manifest's `--validate-only`
check before indexing, then run all ten cases once with a new local report path:

```bash
uv run python -m scripts.evaluate_answers \
  --benchmark benchmarks/mitochondrial-dynamics-2023.json \
  --pdf data/mitochondrial-dynamics-2023.pdf --validate-only

docker compose exec db createdb -U rag rag_mito_2023_eval
RAG_DATABASE_URL='postgresql+psycopg://rag:rag@localhost:5432/rag_mito_2023_eval' \
  uv run python -m scripts.init_db
RAG_DATABASE_URL='postgresql+psycopg://rag:rag@localhost:5432/rag_mito_2023_eval' \
  uv run python -m scripts.index_pdf data/mitochondrial-dynamics-2023.pdf

RAG_DATABASE_URL='postgresql+psycopg://rag:rag@localhost:5432/rag_mito_2023_eval' \
RAG_GENERATOR_MODEL=qwen3:8b RAG_GROUNDING_MODEL=gpt-oss:20b \
RAG_JUDGE_MODEL=qwen3:8b RAG_DRAFT_THINK=low RAG_VERIFIER_THINK=medium \
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
uv run python -m scripts.evaluate_answers \
  --benchmark benchmarks/mitochondrial-dynamics-2023.json \
  --pdf data/mitochondrial-dynamics-2023.pdf \
  --strategy reranked --top-k 3 --answer-mode verified \
  --output evaluation-results/mitochondrial-dynamics-reranked-verified-first.json
```

Preserve incomplete runs and record failures as failures. Check judge calibration,
retrieved evidence, final answers and citations manually against the saved PDF;
report appropriate and false refusals separately, along with answer/citation
scores and latency. The same local model drafts and verifies answers, and an
assistant-authored judge grades them, so their agreement is not independent
validation. Keep the raw report and PDF local; report only the necessary derived
findings and provenance in this document after the run.
