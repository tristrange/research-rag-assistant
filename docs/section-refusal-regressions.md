# Section and refusal evaluation regressions

The first housing-paper comparison exposed two infrastructure defects: numbered
headings separated by a vertical bar were not recognized, and the judge confused
some natural-language refusals with answers. This change addresses those observed
failures. It does not rerun generation or change model defaults, and makes no new claim of
retrieval or answer-quality improvement.

## Section recognition

Standalone numbered headings now accept an optional `|` separator, including PDF
Unicode whitespace and forms such as `2|Methods`. The existing exact heading-name
allowlist remains: prose such as `2 | Methods were applied` and arbitrary pipes
must not change section state. Text offsets and extracted passage contents are
preserved; the references-section guard still prevents article titles from
switching back into a scientific section.

At the normal 500-character chunk size and 100-character overlap, extracting the
housing paper produces 216 chunks instead of 219 because newly recognized section
boundaries alter chunking. Page 3 methods now carry `methods`; the references at
the end of page 10 and onward carry `references`. The original sample still
produces 207 chunks. This is a parser fix, not a claim that every publisher layout
is recognized. Wrapped or unrecognized headings can still remain in a prior section.

Existing database labels are not changed by editing Python code. Reindex each
affected PDF using the same database selection as its original import. There is no
schema migration. Old evaluation reports retain their original source text and
section labels; a changed corpus must not be resumed as the same experiment.

## Refusal classification and grading

Noncanonical responses use two local judge calls:

1. The behavior classifier receives only the question and answer. It never sees
   the reference, answerability label or source bundle. A partial answer or guess
   counts as an attempted answer; explaining that the requested population or
   result is absent can still be a refusal.
2. The factual grader receives the reference and returned passages, with expected
   evidence quotes removed. Those quotes are benchmark labels, not retrieved
   evidence, and must not be treated as source support.

The behavior decision owns the final abstention flag. Code sets correctness and
completeness to zero for an answerable question that was refused, even when the
factual grader mistakenly grants reference-answer credit. Support of explanatory
claims is still graded. A refusal to an unanswerable question is not automatically
awarded full credit when its explanation contains invented facts.

The canonical application refusal and three explicitly listed fact-free sentences
use a deterministic fast path. Matching requires the whole response: added text,
explanations and guesses cannot trigger it.
Other responses cost two evaluation calls instead of one; judge timing includes
both. Classification remains model-dependent and can still be wrong. No keyword
rule assumes that any answer containing “not enough information” is a refusal.

Evaluator version 9 fingerprints both prompts and the exact-refusal set.
Calibration version 2 uses the same evaluation path on thirteen controls, including partial answers, missing retrieval,
curly-apostrophe refusals, explanatory refusals, guesses after refusal language and
negative findings. Historical reports remain readable, but cannot be resumed under
the new grading contract.

## Validation

The first live calibration attempt passed 9/12. It incorrectly classified two
partial answers as refusals and treated reference evidence as retrieved evidence
on the missing-retrieval case. That failed report is retained. The revised prompt
specifies the partial-answer decision order and includes examples, and the factual
input omits expected evidence quotes. The revised run passed all 12 controls.
These are development controls used to improve the evaluator, not an independent
measurement of its accuracy.

The seven saved refusal responses from the first model comparison are regraded
with their original questions, answers and retrieved passages. No retrieval or
answer generation is repeated, and the original reports are not modified. The
results below are regression checks on inspected cases, not a new held-out score.

The first saved-answer recheck classified all seven responses as refusals but
incorrectly scored GPT-OSS's short human-survival refusal 0/2 for correctness and
completeness (six of seven regression checks passed). The final change scores that
exact fact-free sentence directly and adds it as a thirteenth control. Longer
responses still receive semantic checks, and appended guesses never use the fast
path. Both intermediate reports remain intact.

The final live calibration passed **13/13 controls**, and the final saved-response
recheck passed **7/7**: six unanswerable refusals receive correctness/completeness
2/2, while the answerable ATP refusal receives 0/0. All seven are classified as
abstentions. These results use `qwen3:8b` as judge; they do not establish general
judge reliability or revise the original model-comparison scores.

The isolated `rag_housing_eval` database was reindexed successfully. Its 216 stored
chunks exactly match fresh extraction/chunking, including text, page, index and
section. All page 3 chunks are `methods`. The normal `rag` database still contains
207 `sample.pdf` chunks. The rebuilt evaluation corpus fingerprint is
`9cb8565471218f33f9c55f5b7c9297a6ae79173b9b48ec7cc0306e3bd99e3f66`.
All 158 automated tests and strict type checking of 56 tracked Python files pass.

Raw reports are retained locally under ignored `evaluation-results/`; hashes below
identify the runs without committing paper excerpts. Both final runs use evaluator
prompt fingerprint `b9c68934238f422d44debca5ab4cc7f1668e961edbad49f93cbfe0a2ec0a3e73`.

| Report | Result | SHA-256 |
| --- | --- | --- |
| `judge-calibration-v2-first.json` | 9/12 | `f81962d185840267f6477389c0ae043e2fb438f41679e573ce5d062e399e9a8a` |
| `judge-calibration-v2-revised.json` | 12/12 | `dbcd696f864239979f896dca3f562b859d59e12f234869bfe74faeef3913da21` |
| `refusal-regressions-evaluator-v9.json` | 6/7 | `a890261d29ad005f665b7e08376aa9a1dc28a1cd6d1e06f55ec6216a45a651c8` |
| `judge-calibration-v2-final.json` | 13/13 | `b291c7a85a9f550f874fae85adba81f165a222c0e7ec43815c0da6bd7022b929` |
| `refusal-regressions-evaluator-v9-final.json` | 7/7 | `91d6958ad6732dd5dfb3d07dd3ce986f5fda078e0c79744b2fbbdde63e1336cf` |

The three original comparison report hashes were checked and remain unchanged
from the [first housing-paper comparison](housing-model-comparison.md).
