# Housing-temperature model comparison

## Protocol frozen before generation (2026-09-20)

This is the first answer-generation comparison on the ten reserved questions in
`benchmarks/housing-temperature-2025.json`. Freeze the benchmark, prompts, retrieval
and evaluator at commit `48f5620` before seeing results. Do not tune on failures or
rerun completed cases to select better answers. Preserve incomplete reports too.

Run one trial per case, sequentially, in this predeclared order:

1. `qwen3:8b`
2. `gpt-oss:20b`
3. `qwen3-coder:30b`

All runs use plain answer mode, expanded retrieval, the same isolated PostgreSQL
index and the `qwen3:8b` judge. Each run must pass the existing judge calibration.
Only `RAG_GENERATOR_MODEL` changes. Generator sampling and reasoning remain each
model's defaults; this is a comparison of the current plain-answer configurations,
not an isolated parameter-count experiment. The judge uses temperature zero and
thinking disabled. No model downloads, prompt changes, or default changes are part
of this experiment.

Record model digests, corpus/benchmark fingerprints, raw grades, actual refusals,
manual source/citation findings and end-to-end latency. The judge is also one of the
candidates, creating potential self-preference; its grades are not independent
ground truth. Source support grades concern the retrieved bundle, so manually
check inline document/page references. Review eight answerable and two unanswerable
cases separately. Keep exact-excerpt retrieval misses distinct from unsupported
answers.

Timeouts and transport failures remain failures rather than evidence refusals.
Preserve the report and its completed cases; report failed runs instead of silently
changing the timeout or retrying for a better outcome. If the runner cannot finish
one candidate, continue with the next candidate using the original protocol.

This is one small, assistant-labelled paper in the same domain and research group
as the development paper. It cannot establish broad generalization or statistical
superiority. Once the results guide model selection or changes, treat this set as
used evaluation data and obtain a new holdout for further independent claims.

## Reproduction

Acquire the PDF and initialize the separate `rag_housing_eval` database using
[the corpus guide](benchmark-corpus.md). Index it once. For each model above, use a
fresh report path:

```bash
RAG_DATABASE_URL='postgresql+psycopg://rag:rag@localhost:5432/rag_housing_eval' \
RAG_GENERATOR_MODEL=qwen3:8b RAG_JUDGE_MODEL=qwen3:8b \
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
uv run python -m scripts.evaluate_answers \
  --benchmark benchmarks/housing-temperature-2025.json \
  --pdf data/housing-temperature.pdf --strategy expanded --answer-mode plain \
  --output evaluation-results/housing-qwen3-8b-first.json
```

Change the generator model and output filename for the other candidates. The
normal sample-paper database is not replaced. Local raw reports remain ignored by
Git; final results and their hashes will be recorded here.

## Installed model digests

- Qwen3 8B: `500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41`.
- GPT-OSS 20B: `17052f91a42e97930aa6e28a6c6c06a983e6a58dbb00434885a0cf5313e376f7`.
- Qwen3 Coder 30B: `06c1097efce0431c2045fe7b2e5108366e43bee1b4603a7aded8f21689e90bca`.
- Nomic Embed Text: `0a109f422b47e3a30ba2b10eca18548e944e8a23073ee3f3e947efcf3c45e59f`.
