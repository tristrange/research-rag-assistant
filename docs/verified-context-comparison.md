# Verified answers with three versus six expanded passages

## Protocol frozen before generation

Application baseline: `e218abe` (PR #15 merged). Compare the expanded strategy
with three and six seed passages using all existing questions on both papers:
20 sample questions (18 answerable, including cited-literature questions, and two
unanswerable) and ten housing questions (eight answerable, two unanswerable).
These are inspected development sets, not independent holdouts.

Run one trial per case in this fixed order: sample / three, housing / six,
sample / six, housing / three. Each arm uses the same paper-specific isolated
index, ten vector candidates, existing reranker, two page-local neighbors and
6,000-character context cap. No reindexing, benchmark-label edits, prompt edits,
model changes or cutoff tuning during the experiment.

Verified generation uses installed GPT-OSS 20B, draft reasoning `low` and verifier
reasoning `medium`, with its existing bounded repair. Qwen3 8B judges with thinking
disabled, evaluator version 9 and calibration version 2. Each arm must pass the
existing calibration. A calibration failure stops that arm; a transport or model
error remains a failed checkpoint. Continue to the next arm without retrying a
completed answer or changing settings to improve results. Preserve all reports.

Record automated scores and manually inspect every answer against the returned
sources and reference: requested facts, unsupported additions, document/page
citations, attribution to cited work, and refusals. Report corpus-answerable
refusals separately from appropriate unanswerable refusals. Exact labelled-quote
coverage is diagnostic; alternative supporting passages may be valid.

Compare paired case outcomes within each paper. Publish answer and judge timings
separately, including mean, median and maximum answer time. These are single-trial
end-to-end configuration timings, including loading/cache effects and verification,
not isolated inference benchmarks. Model roles alternate with judging; the fixed
arm order does not fully control time or cache confounding.

Recommend API expansion only if the wider context has no observed new unsupported
claims, citation/attribution failures or inappropriate answers to unanswerable
questions, and offers useful answer coverage at acceptable measured latency.
Any regression or incomplete arm blocks a rollout recommendation from this trial.
Even a clean result is provisional: independent labels and a fresh paper remain
necessary for general quality claims. The normal API is not changed by this PR.

## Reproduction

Use a new output filename for every run. The sample arms use the normal `rag`
database; housing arms use `rag_housing_eval` and the housing manifest/PDF.

```bash
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
uv run python -m scripts.evaluate_answers \
  --strategy expanded --answer-mode verified --top-k 3 \
  --output evaluation-results/verified-context-sample-k3-first.json

RAG_DATABASE_URL='postgresql+psycopg://rag:rag@localhost:5432/rag_housing_eval' \
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
uv run python -m scripts.evaluate_answers \
  --benchmark benchmarks/housing-temperature-2025.json \
  --pdf data/housing-temperature.pdf \
  --strategy expanded --answer-mode verified --top-k 6 \
  --output evaluation-results/verified-context-housing-k6-first.json
```

Then repeat for sample / six and housing / three with new report filenames.
Raw reports contain excerpts and stay in ignored `evaluation-results/`.
