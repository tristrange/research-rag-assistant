# Grounding refusal diagnostics

## Initial diagnostic plan

PR #16 is merged. At baseline `7e91954`, replay the unchanged saved sources for
`kpc-food-intake` and `cited-ceramide-study` from both sample-paper arms. Run the
three-seed report first, then six seeds, once per case. This includes the two
observed refusals and their successful paired contexts. Preserve original reports
and every replay, including failures. Do not re-retrieve, rejudge, or alter prompts
before inspecting these traces.

Pin GPT-OSS 20B, draft reasoning `low`, verifier reasoning `medium`, and all other
application settings to the original protocol. Record draft, verification and
repair stages through the existing replay runner. Classify the refusal stage:
initial drafting, deterministic citation validation, semantic verification, or
bounded repair. A replay is a new generation trial, not a recovered trace of the
original answer; a changed outcome cannot establish the original failure cause.

Use findings to select a narrow next change only if the evidence supports one.
Do not weaken evidence, attribution or question-qualifier checks merely to improve
answer coverage. Any subsequent prompt/code experiment is separate from these
baseline replays and from the first-run evaluation in PR #16.

## Narrow verifier experiment

Both original refusal outcomes reproduced. The three-seed KPC refusal occurs in
the initial draft. The six-seed cited-title draft is correct, but verification
invents unsupported requirements for unspecified population, sex, species, study
design, dose and comparison; repair then declines. Its own `answers_question`
flag is true, but the deterministic requirement gate correctly rejects the
inconsistent verdict.

Clarify the verifier prompt and requirement-schema descriptions to enumerate only
requirements asked by, or necessary to identify the target of, the actual question.
Unasked dimensions are omitted, never automatically marked supported. Keep the
strict requirement gate and attribution/quote checks unchanged. Do not change
the draft prompt or add retries for initial refusals in this experiment.

Run one new replay of the same four saved contexts, then the live adversarial
verifier controls, including paired cited-title questions with and without a
requested dose. Keep every result. This is targeted development validation, not a
new benchmark or a reason to enable API expansion by default.

## First candidate result and revised validation plan

The first candidate correctly verifies the six-seed cited title, but regresses the
six-seed KPC answer: it treats “Was food intake lower?” as requiring lower intake,
rejects the supported negative result, and repair declines. The three-seed KPC
initial-draft refusal persists. Preserve this failed candidate and its controls.

A second clarification will distinguish evidence that determines the answer from
evidence affirming a yes/no proposition. A supported negative or unchanged outcome
satisfies a yes/no question; absent outcome evidence does not. Add paired synthetic
controls for a supported negative answer and an unsupported negative claim. Rerun
the four fixed contexts once and all sixteen controls without changing sources,
draft instructions, deterministic gates or call limits.

## Results

Each row below is one new generation trial over the same saved question and source
passages. “Answered” means the final output passed the existing checks; it does
not imply the first draft or first verification passed.

| Verifier wording | Expanded seeds | KPC food-intake question | Cited ceramide title question |
| --- | ---: | --- | --- |
| Baseline (v12) | 3 | Refused in initial draft | Answered |
| Baseline (v12) | 6 | Answered | Refused after verifier invented unasked requirements |
| First candidate | 3 | Refused in initial draft | Answered |
| First candidate | 6 | Refused after verifier demanded a positive result | Answered |
| Revised candidate (v13) | 3 | Refused in initial draft | Answered |
| Revised candidate (v13) | 6 | Answered after one bounded repair | Answered |

The revised verifier lists only actual question requirements and treats cited
evidence of an unchanged outcome as sufficient to answer a yes/no question with
“no”. It still rejects a negative answer when the source only says the outcome
was measured. The live verifier controls passed 16/16, including paired checks
for unasked versus requested dose, supported versus missing negative-result
evidence, requested population and duration, numerical accuracy, attribution,
and unsupported embellishment. The first candidate passed its 14 controls yet
regressed KPC, which is why the negative-answer pair was added.

The revised six-seed KPC first verification still inconsistently sets
`answers_question=false` even while marking its requirement and claims supported.
The existing bounded repair produced an accepted answer. The three-seed KPC
refusal remains in the initial draft, before verification. These controls are
assistant-authored, inspected development cases with one run each, not an
independent benchmark or a broad accuracy estimate. This result does not justify
making neighbor expansion the API default.

All JSON reports below are retained locally in the ignored `evaluation-results/`
directory; they are not included in this PR. SHA-256 hashes identify the exact
saved trials. The code records its prompt/schema fingerprint in each report.

| Report pair | Three-seed SHA-256 | Six-seed SHA-256 | Grounding fingerprint |
| --- | --- | --- | --- |
| `refusal-diagnostic-*-baseline.json` | `6cb81ed6f1dddf3d172cda95ad0cf335d1490581781fec1d0361d55c830be72f` | `15bf3c6d867fc1418bc3baa6d47f03516b60ba7fdeab6b5ba7f38c8fc3c1111d` | `3ccdde2ef9279ebf736686e88cf5146c4c7dec6d78fda19b42954aca9959eac7` |
| `refusal-diagnostic-*-candidate.json` | `1021760c7e35ccad627e2804c53640352372964966e4b5803b74b802306c742e` | `f8a1d8c016271393af4c06bb93de0cf7cf021ccefbe8e6d98a8bf6580733976b` | `a41c00656cd99cd4b776ae4ce5042606f0b08683b875501f479da7ba88111373` |
| `refusal-diagnostic-*-revised.json` | `da18ddffb4018c51a0e92ce507a92e4d5920298f45de1cad12ab9475a7466e2a` | `427647323c18e138524718991630abf6bd4bacc3aa725a4f8a78ea73e0af3a3c` | `9808eeca3e7f1cbc8c2bef56b01d11869eb20f67ff97e49c11376a57ff494646` |

`refusal-verifier-revised-controls.json` passed all 16 checks and has SHA-256
`92d4b0fa5cf62cbb741d317ea938401af99b6ee409655d689f92872f4bc9c5d7`.
The first-candidate 14-check report is `refusal-verifier-candidate-controls.json`
(SHA-256 `36cee12b7ac257847323b647c5686cc4b7aa284bb640102df645d3e6f9d14b60`).

To repeat a fixed-source replay from a retained first-run report, use the same
model settings as the original evaluation and a fresh output path:

```bash
RAG_GENERATOR_MODEL=qwen3:8b RAG_GROUNDING_MODEL=gpt-oss:20b \
RAG_JUDGE_MODEL=qwen3:8b RAG_DRAFT_THINK=low RAG_VERIFIER_THINK=medium \
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
uv run python -m scripts.replay_grounding \
  evaluation-results/verified-context-sample-k6-first.json \
  --case kpc-food-intake --case cited-ceramide-study \
  --output evaluation-results/refusal-diagnostic-k6-new-trial.json

RAG_GROUNDING_MODEL=gpt-oss:20b RAG_VERIFIER_THINK=medium \
uv run python -m scripts.check_grounding \
  --output evaluation-results/refusal-verifier-new-controls.json
```

Use the corresponding `verified-context-sample-k3-first.json` for three seeds.
The replay does no retrieval or judging and preserves the saved source passages;
each new run may differ despite unchanged settings. Local verification also ran
164 unit tests and strict mypy over 58 tracked Python files successfully.
