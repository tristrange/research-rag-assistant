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
