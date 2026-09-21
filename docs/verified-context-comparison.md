# Verified answers with three versus six expanded passages

## Result and rollout decision

**Keep expansion opt-in; do not enable it automatically in the API yet.** All four
arms completed all 68 answers, each after passing 13/13 calibration controls.
Six passages recovered an ATP answer and corrected an unnecessary KPC-food-intake
refusal, but introduced a refusal on a previously answered cited-study question.
That observed regression fails the predeclared rollout criterion. Mean answer time
also rose by roughly 55–59% in these runs. No application defaults change here.

| Assistant-reviewed outcome | Sample, 3 seeds | Sample, 6 seeds | Housing, 3 seeds | Housing, 6 seeds |
| --- | --- | --- | --- | --- |
| Supported answers / answerable questions | 17/18 | 17/18 | 7/8 | 8/8¹ |
| Answerable questions refused | 1 | 1 | 1 | 0 |
| Appropriate unanswerable refusals | 6/6 | 6/6 | 2/2 | 2/2 |
| Explicit cited-study answers | 2/2 | 1/2 | — | — |
| Expected quote coverage | 17/18 | 18/18 | 7/8 | 8/8 |
| Raw automated composite passes | 21/24 | 23/24 | 9/10 | 9/10 |

¹ The ATP answer gives the supported direction and temperature independence but
omits the reference's two-fold magnitude. Treat this as a partially complete
reference answer, not full recovery of the numerical result. The earlier two-case
spot check included the magnitude; this new trial did not. Neither run is replaced.

The review found no unsupported material claims, invalid document/page locations,
or confusion of cited literature with the current study's experiments in the
returned answers. This is an assistant review of inspected development data, not
independent scientific validation or proof of general reliability. A refusal can
be safe and still be an answer-coverage failure.

## Paired findings and judge disagreements

- **Housing ATP:** three seeds returned no labelled ATP result and the pipeline
  refused. Six returned the page 2 result and produced a supported answer about an
  increase regardless of temperature, without the two-fold magnitude. The judge
  scored support 0 even though the statement is explicitly present on the cited
  page. Its completeness concern is reasonable; its support explanation is not.
- **Sample KPC food intake:** three seeds refused despite the explicit unchanged
  food-intake result on page 6. Six answered correctly. Both contexts contained
  the labelled evidence, so this is not recovery of missing retrieval evidence.
- **Sample cited ceramide study:** three seeds correctly reported the cited title,
  clearly labelled as cited literature. Six refused despite returning the same
  supporting title on page 10. More evidence did not guarantee a better answer.
  A single trial cannot isolate context effects from model variability; the
  observed regression is enough to withhold rollout, not prove its root cause.
- **Sample cited Rosiglitazone study:** both answers correctly attributed the claim
  to the cited Asp publication. The three-seed judge incorrectly gave support 0
  despite the title being in its returned page 10 passage. The six-seed judge gave
  support 2 for the same answer. Raw grades remain unchanged.
- **Sample grip-strength outcome:** both cutoffs answered correctly using valid
  alternative support (page 9 with three seeds, page 6 with six). Only six also
  returned the exact page 7 benchmark quote. The composite metric therefore
  understates the quality of the three-seed answer.

All remaining paired questions retained their supported answer or appropriate
refusal outcome. Some wording varied: the three-seed muscle-glucose answer used
78%/35% from the page 1 abstract instead of the rounded page 3 values; both are
supported. Both AKT answers repeated the Ser473 finding. Both weight-loss answers
omitted the control-group gain in the reference, while answering the requested
food-restricted-group change. The loading-control answers repeated the source's
odd wording “housing genes”; the six-seed answer also cited a page 8 figure caption
that supports the control choice, with the rationale supported on page 3.

Calibration passing did not eliminate judge errors. The raw composite improvement
for the sample includes a corrected judge decision and extra exact-quote coverage;
it is not a net gain in the number of supported answers. Manual findings and raw
metrics are intentionally reported separately.

## Observed timing

| Arm | Mean answer, s | Median answer, s | Maximum answer, s | Mean judge, s |
| --- | ---: | ---: | ---: | ---: |
| Sample / 3 | 50.30 | 54.58 | 89.74 | 10.44 |
| Sample / 6 | 80.00 | 84.97 | 174.79 | 15.98 |
| Housing / 3 | 50.17 | 52.40 | 91.71 | 11.63 |
| Housing / 6 | 77.96 | 63.59 | 187.69 | 13.81 |

Answer time includes retrieval, drafting, verification, any bounded repair and
model loading. Judge time is separate. Calibration and other arm overhead are not
in these answer statistics. Runs were sequential with no dedicated generation
warmup, fixed arm order and uncontrolled system/cache state. These are observed
configuration timings, not a causal estimate of the cost of three extra passages.
The longest housing-six answer was the fat-loss question; the female-outcome
refusal also took about 141 seconds. Reports do not retain grounding traces, so
these durations cannot establish which internal stage caused the delay.

## Next development step

Use fixed-source diagnostic replays with grounding traces to investigate the
unnecessary KPC and cited-ceramide refusals, preserving these first-run reports.
Keep any resulting fixes and new exploratory trials separate from this comparison.
Then validate the candidate against the current unexpanded API path and a freshly
labelled, appropriately licensed paper before a broader rollout decision.

## Protocol frozen before generation

Application baseline: `e218abe` (PR #15 merged). Compare the expanded strategy
with three and six seed passages using all existing questions on both papers:
24 sample questions (18 answerable, including cited-literature questions, and six
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
necessary for general quality claims. The normal API is not changed by this PR. Both arms enable expansion, so this
experiment isolates the seed cutoff within expansion; it does not directly measure
the normal API's unexpanded context or its default plain-answer mode. A clean
result can support a verified-mode rollout candidate, not a blanket API default
change across answer modes.

The initial protocol prose counted 20 sample cases, but the unchanged runner
contains 24 (18 answerable and six unanswerable). This count was corrected during
the first calibration, before any generated answers were inspected. All existing
cases remain included; the four arms therefore contain 68 answers in total.

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

## Validation and provenance

Protocol initially committed as `90eb460`, with count corrections in `469dcf8`
and `ca7e8d3` before inspecting any generated answers. The runner always selected
all 24 sample cases; these prose corrections did not change the experiment.
Runtime code remained at application baseline `e218abe`. No completed case was
retried, model/prompt settings and indexed content stayed fixed, and
all four processes exited successfully. Only the predeclared cutoff and
paper-specific database varied between arms.

Every report was loaded through the strict report schema. Checks confirmed the
expected case count/order, matching per-paper cases and corpus fingerprints across
cutoffs, the recorded models/cutoffs, passed calibration, and context at or below
6,000 characters. Every factual answer's document/page reference was present in
its returned sources. Exact labelled-quote support was checked on cited pages;
the three alternative-support cases were inspected separately. All 68 answers
were reviewed against their question, reference and source support. This is a
documentation-only evaluation PR; it does not claim a new application test run.

Corpus fingerprints:

- Sample (207 chunks): `3b617920e02426f2c0ad0bca835c6ae1627b43b0009511f8e77d67a64f815ce7`.
- Housing (216 chunks): `9cb8565471218f33f9c55f5b7c9297a6ae79173b9b48ec7cc0306e3bd99e3f66`.

Installed model IDs checked before starting: GPT-OSS 20B `17052f91a42e`, Qwen3 8B
`500a1f067a9f`, and Nomic Embed Text `0a109f422b47`. No model downloads occurred.
The reranker remains `BAAI/bge-reranker-base`; evaluator version 9, calibration
version 2 and complete settings/fingerprints are recorded in each raw report.

| Local report | UTC interval | SHA-256 |
| --- | --- | --- |
| `verified-context-sample-k3-first.json` | Sep 20 22:44:57–23:10:15 | `17f4211d88b6ff21e1ac4fea9c7011be8b937df2153661e3ad99eec49f87c23b` |
| `verified-context-housing-k6-first.json` | Sep 20 23:10:19–23:27:06 | `2219621cd3d1ddeebce110be30a60f87ab1249dd07b83d74dc25d233002a9bbe` |
| `verified-context-sample-k6-first.json` | Sep 20 23:27:08–Sep 21 00:13:38 | `d64421471711e22dd09c462f4ea6fcc54317bbaf3504683724d4852edffc2dec` |
| `verified-context-housing-k3-first.json` | Sep 21 00:13:41–00:42:57 | `be39e143571ed94803da73e46ca8ffff148f6c569671601d96d79d286a0fd07d` |

All dates are in 2026. Raw files and logs remain in ignored `evaluation-results/`.
The separate assistant review notes, `verified-context-manual-review.json`, have
SHA-256 `712131bb508d4ef37de372f048dc70ceee2d73c7b5aa8414c494fc10b7017c7f`.
