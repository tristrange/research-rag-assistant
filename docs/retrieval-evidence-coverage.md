# Evidence coverage with a wider bounded context

The expanded strategy now retains six reranked seed passages instead of three,
within the existing 6,000-character rendered-context budget. It still searches ten
candidates and uses the same reranker, page-local neighbors and section boundaries.
The API and default `reranked` evaluation remain at three passages without expansion.
`--top-k` makes the evaluation cutoff explicit; resume restores the recorded cutoff
and rejects an explicitly different value.

## Diagnosis and scope

After correcting publisher section labels, the housing ATP evidence was still
missing from returned context. The relevant page 2 passage ranks fifth among vector
candidates but sixth after reranking; selecting three loses it. Expanding neighbors
of those three cannot recover a passage on a different page.

Two preliminary alternatives did not fix it: searching 20 or 40 candidates moved
the relevant passage to reranker positions 10 and 15, respectively, and reranking
individual expanded windows still omitted it from the first three. We therefore
retained six seeds, without a new model, lexical heuristics or paper-specific rules.
This cutoff was chosen after inspecting a failure; it is a development choice,
not an independently optimized or universally sufficient setting.

## Repeated retrieval comparison

The comparison uses all 26 answerable cases across both existing papers, with their
unchanged evidence labels. It warms the first case once, then repeats each case
three times. Each pair shares the same vector search and ten-candidate reranking;
only seed selection and bounded expansion differ. Reports record evidence at the
candidate, seed and expanded-source stages, plus sources, corpus fingerprints and
timings. No generation or judging occurs in this comparison.

| Paper | All expected quotes, 3 seeds | All expected quotes, 6 seeds | Mean retrieval ms, 3 / 6 | Median retrieval ms, 3 / 6 |
| --- | --- | --- | --- | --- |
| Housing temperature | 7/8 | 8/8 | 201 / 214 | 200 / 212 |
| Original sample | 17/18 | 18/18 | 212 / 224 | 211 / 220 |

Coverage was identical in all three repetitions: 21/24 versus 24/24 housing trials,
and 51/54 versus 54/54 sample trials. The recovered cases are `housing-bat-atp` and
`food-restriction-grip-strength`. No previously covered labelled quote was lost.
The sample case already had alternative supporting text on pages 6 and 9; its
improvement is recovery of the labelled page 7 quote, not proof that the old
context could not answer it.
The maximum rendered contexts were 5,922 and 5,982 characters respectively; average
context lengths increased from 2,228 to 4,561 and from 3,076 to 5,203 characters.

Timing covers warmed search, reranking and expansion, not answer generation.
The paired cutoffs share most work and are not independent latency trials; local
validation also ran on this machine. Larger contexts may increase generation time
and introduce distracting evidence. Exact-quote coverage cannot establish answer
correctness, citation accuracy or appropriate refusals. Unanswerable cases are
excluded. Both papers are inspected development data, even though the original
housing manifest retains its historical `holdout` label.

## Reproduction

Use the existing sample index, or the isolated housing index rebuilt in PR #14.
The runner verifies PDF, labels and indexed text and rejects a mixed-paper index.
It never reindexes, overwrites an existing output or changes benchmark labels.
Partial and failed runs retain their completed results.

```bash
uv run python -m scripts.compare_evidence_coverage \
  --output evaluation-results/coverage-sample-new.json

RAG_DATABASE_URL='postgresql+psycopg://rag:rag@localhost:5432/rag_housing_eval' \
uv run python -m scripts.compare_evidence_coverage \
  --benchmark benchmarks/housing-temperature-2025.json \
  --pdf data/housing-temperature.pdf \
  --output evaluation-results/coverage-housing-new.json
```

Defaults are three versus six seeds and three repetitions. Use a new output path
for every run. End-to-end evaluation can select either cutoff with
`--strategy expanded --top-k 3` or `--strategy expanded --top-k 6`; a fresh expanded
run without `--top-k` now selects six. Existing reports resume with their original
recorded cutoff, preserving the experiment rather than silently widening context.

## Provenance

Application base: `1abfdd4` (PR #14 merged). Embeddings: `nomic-embed-text`;
reranker: `BAAI/bge-reranker-base`, installed locally. No model downloads or index
changes occurred. The housing and sample corpus fingerprints remain
`9cb8565471218f33f9c55f5b7c9297a6ae79173b9b48ec7cc0306e3bd99e3f66` and
`3b617920e02426f2c0ad0bca835c6ae1627b43b0009511f8e77d67a64f815ce7`.
The runner fingerprint is
`2b89eef62663ccda16a0b168c3972d0e733e894bc37250a73389ed8841e541c9`.

Raw reports remain under ignored `evaluation-results/`, including the preliminary
`coverage-3-vs-6-housing-first.json` and `coverage-3-vs-6-sample-first.json` probes.
The completed repeated reports have these SHA-256 hashes:

| Report | SHA-256 |
| --- | --- |
| `coverage-housing-repeated.json` | `a53234c0a9f4bb928a0b314d3eac60f0925f1e20519b4c0cb42c8ef77d39de35` |
| `coverage-sample-repeated.json` | `a11797c0a32777eb15cf297c40be64e8a12d203f304d0c2af1049ce00feed513` |

Automated validation: 162 tests pass; strict type checking passes for 57 Python
files. Tests cover expanded defaults, explicit cutoffs, invalid limits, provenance,
and preserving a recorded three-seed cutoff on resume.

## Verified generation spot checks

One verified-generation call per recovered case used the six-seed sources saved
in the first repetition, without re-retrieving or rerunning a judge. GPT-OSS 20B
(draft reasoning `low`, verifier `medium`) answered the ATP question with the
two-fold increase regardless of temperature and cited page 2. It answered that
food restriction did not alter grip strength, citing the supporting figure caption
on page 6; this is valid alternative support to the benchmark's page 7 quote.
Both answers were checked against their saved sources. No retries were made.
Generation took 64.3 and 89.2 seconds respectively, including any loading effects;
there is no paired three-seed generation timing or full answer-quality evaluation.

The raw `coverage-recovered-verified.json` report has SHA-256
`7d0f66e2a77174daa5a039c6d54e2412d89cba5097d6b50d6859e115101f144f`.
These two spot checks do not justify enabling expansion in the normal API; a full
verified-mode comparison including unanswerable and cited-literature questions is
the next validation step.
