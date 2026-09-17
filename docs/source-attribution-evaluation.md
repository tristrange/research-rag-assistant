# Source attribution experiment

The previous expanded-context run answered a question about the current authors'
experiments using a Rosiglitazone result from a bibliography entry for another
publication. This change keeps cited literature available but makes its location
and attribution explicit.

## Implementation and limits

Chunking recognizes a small dictionary of standalone section headings (including
numbered headings), carries labels across pages, and resets at document changes.
It splits at recognized transitions before applying the existing sentence-aware
chunker. Text remains an exact page substring and chunk indexes remain unique
within each page. References continue across pages; explicit appendix or
supplementary headings can end that section. Unknown headings do not create new
labels, so text inherits the preceding recognized section or starts as `unknown`.

The database and API sources now carry `section`. Neighbor expansion does not cross
recognized section boundaries, and merged sources retain their section labels.
Every prompt source header includes the section. The generator must distinguish
this paper's findings from prior work, require explicit attribution for questions
about the authors' experiments, and qualify answers based on cited literature.
References are not removed from search. A results/discussion label does not prove
that a claim belongs to the current study; the prompt still requires reading the
actual passage.

This is a text-heading heuristic, not layout-aware scientific document parsing.
Unusual headings, line wrapping, columns, and headings resembling citation titles
can produce incomplete or mistaken labels. Prompt instructions reduce a known
failure opportunity but do not enforce correct model behavior.

## Validation setup

The PostgreSQL migration was applied to the existing index, followed by atomic
reindexing of the same PDF. Section boundaries changed the corpus from 212 to 207
chunks. All persisted text and section labels were checked against fresh extraction
and chunking. Repeating initialization twice preserved the complete corpus
fingerprint, including section labels and embeddings:

`f8504892995f7716b14310106e60f008d0c66508638797e1c8342935cf9f3d20`

The evaluation adds four development cases to the previous 20:

- A question about the cited Asp et al. Rosiglitazone result (answerable).
- A question about a Rosiglitazone dose in the current paper (unanswerable).
- A question about the cited Morigny et al. ceramide-inhibition title (answerable).
- A paired question attributing the cited Rosiglitazone finding to this paper's
  own experiments (unanswerable).

There are now 18 answerable and six unanswerable cases. Positive evidence labels
were validated against the PDF. The negative labels remain assistant-authored and
should receive independent review before use as benchmark ground truth.

The final comparison runs both strategies with the same updated prompt and index.
It therefore compares retrieval modes under the new implementation. Historical
PR #9 results used different chunk boundaries and instructions; they are context,
not a controlled estimate of the effect of section labels alone. The initially
started 23-case run was deliberately interrupted after one completed case to add
the paired attribution case and fingerprint the rendered source-header format.
Its checkpoint is retained locally but excluded from the final comparison.

Qwen3 8B generates using its existing default sampling/thinking settings. The same
model judges with temperature zero and thinking disabled. Judge prompts, score
thresholds, and calibration examples are unchanged. Evaluator version 5 records
section-bearing sources, incorporates sections in the corpus fingerprint, and
checks a generator prompt fingerprint that includes rendered source headers.
Old reports require a fresh run.

## Reproduction

```bash
uv run python -m scripts.init_db
uv run python -m scripts.index_pdf
uv run python -m scripts.evaluate_answers --strategy reranked --output evaluation-results/attribution-reranked.json
uv run python -m scripts.evaluate_answers --strategy expanded --output evaluation-results/attribution-expanded.json
```

Use fresh output filenames. Raw reports contain source excerpts and remain in the
ignored local `evaluation-results/` directory. Both modes are sampled once on one
paper used for development; this does not establish generalization or reliability.

## Full comparison results (18 September local time)

Both runs completed all 24 cases and passed calibration 6/6. No runtime failures
occurred in the final comparison.

| Metric | Unexpanded reranked | Expanded |
|---|---:|---:|
| Automated composite passes | 16/24 | 17/24 |
| Correctness, answerable only | 0.8889 | 1.0000 |
| Completeness, answerable only | 0.8889 | 1.0000 |
| Source-bundle support, answerable only | 0.8333 | 0.9722 |
| Answerable evidence hit rate | 0.7778 | 0.9444 |
| Mean evidence recall | 0.7500 | 0.9444 |
| Judge-classified unanswerable abstention | 2/6 | 1/6 |
| Mean answer time | 29.89 s | 38.34 s |
| Mean judge time | 6.09 s | 10.58 s |
| Total run time, including calibration | 894.7 s | 1213.0 s |

The expanded run takes about 28% longer per answer in this sampled comparison.
Runs were sequential, unexpanded first; timing is affected by sampling, response
length, warmup, and machine conditions. This is not a controlled latency benchmark.
The semantic averages are judge outputs, not verified factual-accuracy rates:
manual review found unsupported content that the judge scored as fully supported.

### Report provenance

- Unexpanded: `answers-attribution-reranked-24.json`, SHA-256
  `49de534c11ae4486ceb964afcc38488344cf09d494eda8e5353af10ed57bcd86`.
  Started 2026-09-17 22:20:28 UTC; finished 22:35:23 UTC.
- Expanded: `answers-attribution-expanded-24.json`, SHA-256
  `1afd07f9561003534c9aae2481a70164236447fcd166480198793f24883972b2`.
  Started 2026-09-17 22:35:26 UTC; finished 22:55:39 UTC.
- Shared generator prompt fingerprint:
  `839ed131ef7d987fcbde45c49e63eea9c0ab43ab7f19bee5f4857e668f5eaf77`.

## Manual review: unexpanded run

All six unanswerable responses avoided inventing the requested experimental result.
The original drug-treatment response explicitly identified its passages as references
to prior studies. Both cited-work positives attributed their main findings to the
cited publication. The Rosiglitazone answer added a broad interpretive sentence
about metabolic wasting beyond the literal title; the ceramide answer stayed close
to the supplied title.

The automated abstention rate should not be interpreted as practical attribution
success. The judge misclassified explicit insufficient-information responses for
female mice and Rosiglitazone dose. The paired own-study effect question exposed a
pass-rule limitation: a direct correction of the false premise (“the current paper
did not…”) can be correct while receiving `abstained=false`; the composite then
fails it despite full semantic scores. The long-term restriction response similarly
rejected the six-month premise but was not classified as abstention. Scores and
labels were left unchanged, and these issues are reported rather than hidden.

The three original missing-evidence controls remain incomplete without expansion:
body-mass magnitude is absent, grip-strength timing is substituted for the requested
replicate-selection method, and the food-intake answer declines to infer the result.
Grip-strength effect has correct alternate wording despite the absent exact label.

Manual review also found citation limitations that aggregate source-bundle scores
miss: the food-intake answer attributes a statement to page 6 although its returned
support was on pages 1/7, and the own-study Rosiglitazone answer misnames citation
numbers as sections and attaches an unsupported page-2 attribution. Correct
source-bundle support does not guarantee correct inline page attribution.

## Manual review: expanded run and rollout decision

Expansion preserved all three targeted retrieval improvements: the numerical
body-mass result, the three-measurement/maximum grip-strength method, and unchanged
KPC food intake. Their answers and page references were supported. It also recovered
both exact glucose-uptake labels. The original drug-treatment failure now explicitly
rejects drawing a current-paper treatment comparison from bibliography entries.
The paired own-study Rosiglitazone answer also attributes the finding to Asp et al.

However, the new positive Rosiglitazone question exposed **remaining attribution
leakage**. Its requested cited-study finding is correct, but the answer adds an
unsupported PPARγ detail and presents AMPK activity from another reference's title
as part of the current paper's findings. The judge awarded full support, missing
this defect. This means the underlying attribution problem is not solved by labels
and prompt instructions alone.

The cited ceramide answer correctly states the title's result but cites page 4,
whereas the supplied bibliography evidence is on page 10. The paired Rosiglitazone
answer cites page 7 for an attribution supported by the page-10 reference. The dose
answer correctly avoids inventing a dose but is less precise than explicitly saying
the current paper does not report administering the drug. The other unsupported
questions reject the requested findings; several composite failures again result
from the judge/pass-rule abstention issues described above.

**Keep expansion opt-in.** This PR supplies section-aware evidence, an explicit
attribution prompt, and regression cases, while retaining the current unexpanded
API default. Before promotion, constrain or verify each claim against its cited
passage, test inline document/page attribution, improve evaluation of false-premise
corrections, and repeat on additional papers. Do not present the successful original
drug-case answer as evidence that attribution is now reliable in general.
