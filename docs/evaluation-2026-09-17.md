# Local evaluation: 17 September 2026

The full 20-question reranked evaluation completed without a timeout, including
all six judge-calibration checks. This is one exploratory run on one paper, with
assistant-authored reference labels and a same-model judge. Scores are provisional.

## Configuration

- Generator and judge: local `qwen3:8b`.
- Generator: model-default sampling and thinking behavior.
- Judge: temperature 0, `think: false`; clarified that abstention describes the
  answer's behavior independently of whether refusing was correct.
- Retrieval: top 10 candidates, reranked to 3 chunks; 212 indexed chunks.
- Evaluator version: 3. Calibration version: 1 (unchanged checks).
- Report: `evaluation-results/answers-judge-no-thinking-full.json` (local,
  Git-ignored); SHA-256:
  `252ec2ee6da88766de60eceb12e38257afa08d93dcebf1e495517350c3fcb60b`.
- Corpus fingerprint:
  `6caf2e6f0a9bcdd0919cbd597ee0d46b1be6cbf7f7b909df6f88319817aa1f00`.

## Recorded results

| Measurement | Result |
|---|---:|
| Completed cases | 20/20 |
| Calibration checks passed | 6/6 |
| Automated composite passes | 15/20 |
| Answerable-case correctness / completeness / source support | 0.8125 each |
| Evidence hit rate | 0.75 |
| Mean labelled evidence recall | 0.71875 |
| Judge-classified abstention accuracy | 0.90 |
| Judge-classified unanswerable abstention rate | 0.75 |
| Mean retrieval + generation time | 33.8 seconds |
| Mean judge time | 5.7 seconds |
| Recorded run duration | 823.4 seconds |

These metrics use the existing rubric and have not been manually corrected. In
particular, the composite pass rate is not a direct measure of factual accuracy.
Calibration may warm the model; these are not controlled latency measurements.

## Manual inspection of failures

- **Food-restriction body mass:** returned passages omit the numerical result.
  The assistant declines to answer rather than inventing numbers. This is a
  retrieval miss against the reference. The judge's zero source-support score
  is questionable under the rubric's treatment of refusals.
- **Food-restriction grip strength:** the answer is correct and supported by an
  alternate passage on page 9. The required quote on page 7 is absent, producing
  an evidence-label false negative.
- **Grip-strength readout:** the answer invents one measurement per mouse. The
  reference says three measurements, using the maximum; the returned context
  omits that method detail. This is a real answer error after a retrieval miss.
- **KPC food intake:** the response declines to answer after retrieval misses
  the explicit result. The judge incorrectly marks `abstained=false`.
- **Female mice:** the response appropriately says the context lacks the requested
  information. The judge awards full semantic scores but incorrectly marks
  `abstained=false`, causing a composite failure.

All four unanswerable responses decline to provide the requested result on manual
inspection. The automated 0.75 abstention rate therefore understates this run's
behavior. Passing synthetic calibration did not eliminate judge errors.

## Interpretation and next work

Earlier judge calls timed out at 120 seconds. With thinking disabled, the initial
six diagnostic requests completed in approximately 3–6 seconds each, but the two
refusal checks still failed. Clarifying the abstention instruction and its schema
description then passed all six unchanged checks. The full run used that revision.
This is evidence for a practical local configuration, not a controlled proof of
the cause of every prior timeout or a guarantee for other machines.

The next retrieval experiment should target the missing body-mass, grip-method,
and KPC food-intake passages—for example, testing neighboring-chunk context after
retrieval. Review alternate evidence labels and abstention classifications alongside
the actual answers when assessing that experiment. Do not tune solely to the
automated composite score or claim generalization from this single paper.
