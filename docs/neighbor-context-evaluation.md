# Neighboring-context experiment

The baseline evaluation missed nearby result/method passages for body mass,
grip-strength readout, and KPC food intake. This experiment expands the existing
top-three reranked passages without changing embedding search or reranking.

## Fixed-seed evidence comparison

The saved sources from all 20 cases in the
[17 September baseline](evaluation-2026-09-17.md) were expanded against the same
212-chunk corpus. Its fingerprint was verified before and after the comparison.
No new model generation or ranking was used for this part of the experiment.

| Context | Labelled excerpts present | Answerable cases with a labelled excerpt | Mean rendered characters | Maximum |
|---|---:|---:|---:|---:|
| Original reranked passages | 14/19 | 12/16 | 1,361.1 | 1,533 |
| One preceding/following chunk | 17/19 | 14/16 | 2,241.0 | 3,149 |
| Two preceding/following chunks | 18/19 | 15/16 | 3,220.3 | 4,866 |

Both windows preserved every previously matched excerpt. The two-chunk radius
recovered all three target passages; the body-mass result was two chunks beyond
its selected passage. Every merged window in these comparisons was an exact
substring of the extracted source page. The remaining missing quote is the
known grip-strength-effect label with alternate supporting wording on page 9.

The two-chunk radius was selected using this development set. This is tuning on
one paper, not held-out evidence of generalization. More context can introduce
irrelevant statements or increase latency; additional papers should be tested.

## Behavior and limits

Expansion fetches at most two chunks before and after each seed, on the same
document and page. It queries text/metadata once and does not load embeddings.
Seeds receive budget before neighbors; nearer neighbors are attempted first.
Windows merge only across consecutive chunk indexes. Exact suffix/prefix matches
of at least eight characters are removed; smaller matches are retained to avoid
mistaking punctuation or short repeated words for overlap. This is a text-matching
heuristic because stored chunks do not include character offsets.

The rendered context, including citation headers and separators, never exceeds
6,000 characters. Whole evidence passages are retained or omitted rather than
being cut through a number or sentence. No expansion crosses a page boundary.
The returned source text is exactly what the generator receives; a merged source's
`chunk_index` identifies its first included stored chunk.

## Reproduce the answer comparison

With the evaluation paper indexed and the local services running:

```bash
uv run python -m scripts.evaluate_answers --strategy reranked --output evaluation-results/context-baseline.json
uv run python -m scripts.evaluate_answers --strategy expanded --output evaluation-results/context-expanded.json
```

Use new filenames for each attempt. Each report records strategy, radius, budget,
models, judge configuration, and the corpus fingerprint. Resume requires matching
settings. A single sampled answer per case is not a controlled quality or latency
benchmark; inspect the answers and supporting passages alongside the judge scores.

## Full answer evaluation: 17 September 2026

The expanded run completed all 20 cases with calibration passing 6/6. It used
Qwen3 8B for generation (default sampling/thinking) and judging (temperature 0,
thinking disabled), the same 212-chunk corpus, and unchanged prompts and labels.
The baseline is the earlier saved run, not a paired multi-sample experiment.

| Metric | Baseline | Expanded |
|---|---:|---:|
| Automated composite passes | 15/20 | 17/20 |
| Correctness / completeness / source support, answerable only | 0.8125 each | 1.0 each |
| Answerable evidence hit rate | 0.75 | 0.9375 |
| Mean evidence recall | 0.71875 | 0.9375 |
| Judge-classified unanswerable abstention | 3/4 | 2/4 |
| Mean answer time | 33.81 s | 23.95 s |
| Mean judge time | 5.71 s | 7.50 s |
| Total run time, including calibration | 823.4 s | 651.8 s |

These timings describe two local runs, not a demonstrated speed improvement.
Generation length, sampling, model warmup, and machine load can affect them.

Inspection confirmed all three target answers now use the recovered evidence:

- Food-restricted mice lost 1.2 g (3.9%), versus controls gaining 0.7 g (2.1%).
- Grip strength used three measurements per mouse and the maximum reading.
- KPC mice showed no change in food intake.

The three expanded-run failures require different interpretations:

- `food-restriction-grip-strength`: correct answer with alternate supporting
  wording, but the exact labelled excerpt is absent. This remains a label limitation.
- `human-survival`: explicitly says “I do not have enough information.” The judge
  nevertheless emitted `abstained=false`, contradicting its own explanation.
- `drug-treatment`: a real unsupported answer. It names Rosiglitazone as most
  effective in the authors' experiments based on a bibliography entry for another
  study. The baseline refused this question. Both contexts contained that reference,
  so one sampled pair does not establish that expansion caused the regression.

The other three unanswerable responses declined to provide the requested finding.
The answerable-only averages do not capture the drug-treatment error.

**Rollout decision:** keep expansion opt-in (`--strategy expanded`, or
`answer_question(..., expand_context=True)`). The FastAPI default remains the
existing unexpanded reranked path. Before changing that default, distinguish
references/background from the paper's own experiments and repeat the comparison
on additional papers and sampled answers. Do not change labels or judge thresholds
to conceal the observed failures.

### Report provenance

The raw reports remain local under the ignored `evaluation-results/` directory.
The committed summary records their fingerprints for comparison:

- Baseline: `answers-judge-no-thinking-full.json`, evaluator version 3,
  SHA-256 `252ec2ee6da88766de60eceb12e38257afa08d93dcebf1e495517350c3fcb60b`.
- Expanded: `answers-expanded-radius2-full.json`, evaluator version 4,
  SHA-256 `02bb181739d481a5c7a4d842ed928d771e6ea13e5229e9483febe4733c352448`.
  Started 2026-09-17 14:04:42 UTC; finished 14:15:33 UTC.
- Corpus: `6caf2e6f0a9bcdd0919cbd597ee0d46b1be6cbf7f7b909df6f88319817aa1f00`.

Evaluator version 4 adds the expanded strategy and records radius/budget; scoring
and judge prompts are unchanged.
