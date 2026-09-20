# Housing-temperature model comparison

## Result and recommendation

All three first runs completed all ten questions with calibration passing 6/6.
They received identical retrieved passages for every case and the same 219-chunk
corpus fingerprint. No failed run or completed answer was retried.

**GPT-OSS 20B is the strongest candidate for further validation, but this small run
does not justify a default change.** All models answered the same seven requested
facts correctly and appropriately declined both unanswerable questions. When
retrieval missed the eighth fact, GPT-OSS declined to invent it; both Qwen models
produced unsupported answers. GPT-OSS also had the lowest mean answer latency in
this run. Sampling, reasoning, cache state and model loading were not controlled
independently, so these are observed configuration results, not universal rankings.
Plain remains Qwen3 8B by default; verified mode continues using GPT-OSS 20B.

| Observation | Qwen3 8B | GPT-OSS 20B | Qwen3 Coder 30B |
|---|---:|---:|---:|
| Requested facts correctly answered (assistant review) | 7/8 | 7/8 | 7/8 |
| Unsupported answer on the missing ATP evidence | Yes | No; refused | Yes |
| Correct refusals on unanswerable questions (assistant review) | 2/2 | 2/2 | 2/2 |
| Corpus-answerable questions refused (assistant review) | 0/8 | 1/8 | 0/8 |
| Expected evidence found in retrieval | 7/8 | 7/8 | 7/8 |
| Raw automated composite passes | 7/10 | 8/10 | 8/10 |
| Mean answer time, including retrieval | 28.16 s | 24.54 s | 35.59 s |
| Median answer time | 23.89 s | 21.78 s | 33.82 s |
| Mean judge time | 7.41 s | 12.06 s | 11.16 s |

“Requested facts correctly answered” does not certify every added sentence or
citation field. Section labels were wrong in several outputs, and the Coder ATP
answer also attached a page 4 label to text from page 8. Review below distinguishes
these defects. Assistant review is not an independent domain-expert evaluation.

### Case-level review

The first seven cases—temperature assignments, acclimation, grip-strength runs,
glucose-test time points, lipid count after QC, imputation and fat-mass reduction—
returned the requested facts for all three models. Their supporting page locations
were present in the returned passages. The core results were 22 ± 1 / 30 ± 1 °C,
three weeks, five trials two days before dissection, 0/20/40/60/90 minutes,
777 lipid species, k-nearest-neighbour with k=10, and a 35% fat-mass decrease.

For `housing-bat-atp`, the full paper reports a two-fold increase regardless of
housing temperature on page 2. Retrieval instead returned pages 8, 4 and 5, with
SERCA ATPase activity, other results and a figure caption mentioning ATP
concentration. Those text passages do not establish the requested two-fold result.

- **Qwen3 8B** substituted SERCA ATPase activity and incorrectly said the study did
  not directly measure ATP levels. The returned figure caption explicitly lists
  ATP concentration as a measured quantity.
- **GPT-OSS 20B** explained that the supplied excerpts lacked the ATP result and
  refused. This is a missed answer at the full-pipeline level, but an appropriate
  refusal given the retrieved text. The primary coverage failure is retrieval.
- **Qwen3 Coder 30B** inferred no significant ATP change at standard temperature
  and a reduction at thermoneutral temperature. This contradicts the reference and
  conflates ATP concentration with ATPase activity. Its lengthy explanation and
  assurance that it was not inferring facts did not make the answer supported.
  One supporting citation labelled page 8 text as page 4.

Both `housing-female-response` and `housing-human-survival` were correctly declined
by all models. They did not substitute male-mouse findings for female results or
invent a human survival duration. Qwen3 Coder added page 3 to its female-response
citation even though that question's returned passages were from pages 2, 10 and 5;
page 2 does support the male-only study description. These plain-mode citation
issues are separate from the decision to refuse the requested unsupported result.

### Why the raw scores cannot select a winner

The judge's abstention labels are inconsistent with the actual responses:

- It labelled all three female-response refusals as `abstained=false`.
- It also labelled Qwen3 8B's human-survival refusal as `abstained=false`.
- It gave GPT-OSS's ATP refusal full correctness and completeness with
  `abstained=false`, despite the paper-level reference containing an answer.

Thus the raw report claims GPT-OSS answered all answerable cases correctly, which
is false: it answered seven and refused one. The automated composite still fails
its ATP case because expected-evidence recall is zero. Calibration passing 6/6
was insufficient to detect these natural-language refusal errors. The deterministic
rule from PR #11 only recognizes the exact canonical verified-mode refusal; these
plain responses use different wording. Raw reports and scores are preserved,
not retroactively replaced by the review.

### Section metadata defect

The new PDF uses headings such as `2 | Materials and Methods`. The current section
recognizer removes the number but not the vertical bar, so the heading is missed.
The state remains `abstract` for later passages, including page 3 methods and
page 10 references. All three models received that incorrect metadata, and some
repeated it. For example, the imputation answers labelled page 3 as “abstract,”
although that text is in the methods. This is a parsing defect rather than evidence
that the models independently identified the wrong section.

The next implementation priority is to recognize this heading format conservatively
and add grader controls for the observed refusal wording. Keep retrieval coverage
for the ATP question as a separate diagnostic. Those fixes must not be presented as
independent improvements on an untouched holdout: this paper has now been inspected.

### Limits and next decision

This comparison used plain answers only; it does not evaluate verified mode on the
new paper. The judge is Qwen3 8B and may favor its own style. Single-trial model-default
sampling and reasoning are not matched across families. Generation alternates with
judging: Qwen3 is both its own generator and judge, whereas the others switch model
roles. Answer and judge timings include loading/cache effects and should not be
read as steady-state inference benchmarks.

The ten questions are now **used evaluation data**. Do not silently call a later
run on them a fresh holdout. Preserve the manifest used here; obtain another
appropriately licensed Emma Frank coauthored paper, and independently review its
labels, before making a new held-out quality claim. The outcome supports trying
GPT-OSS via `RAG_GENERATOR_MODEL=gpt-oss:20b`, not a claim of general reliability or
statistically established superiority.

### Final provenance

- Protocol committed before generation: `5429114` (application baseline `48f5620`).
- Evaluator version 8; expanded retrieval; plain mode; fixed Qwen3 8B judge.
- Corpus: 219 chunks, SHA-256
  `3bdc88ff9a4bc029842038d190c60a7465255d585f6217463d10afbcba273b11`.
- Benchmark file SHA-256:
  `53ef2a909fb226120a4a9208850f15c41ba43e214d2d0582ba7905ac684da9ed`.
- Selected-case SHA-256:
  `6f1941f3575864da5b61212b8a8a1077fdcf933c93aab50d395b2a7d425039d3`.
- PDF SHA-256: `3b4d5ef35f05fe0840096236a6758d312d1b7bc6dfc5f4c6ab3b79f0a140ce8e`.
- Generator prompt: `839ed131ef7d987fcbde45c49e63eea9c0ab43ab7f19bee5f4857e668f5eaf77`.
- Judge prompt: `6c8c4a5336002e8b2d4043c2c4c4547f5c2a712e27005d5935498fdd1bbb1e1d`.

| Local report | UTC run interval on 2026-09-20 | SHA-256 |
|---|---|---|
| `housing-qwen3-8b-first.json` | 01:26:08–01:32:41 | `26f8b2dc2f6c46540fb8324860c74fa49137e9218f8d2b28c10231c9d7108d31` |
| `housing-gpt-oss-20b-first.json` | 01:32:46–01:39:29 | `6ca9f6c990ef72cc1ab6c611e79e9adf214038773409b41f938c26eb6095b60a` |
| `housing-qwen3-coder-30b-first.json` | 01:39:34–01:47:55 | `9279cc1e26e868a91e4885d020b829f51c03a4ea359bc21a53552ddd0697215f` |

Reports remain in ignored `evaluation-results/`. Each was loaded through the strict
report schema and checked for ten completed cases, passing calibration, identical
source bundles and a matching corpus. No application code changed, so this PR does
not repeat the existing unit suite as evidence of new runtime behavior.

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
