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
