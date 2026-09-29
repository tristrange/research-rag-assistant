# Ollama inference settings

The previous [model comparison](verified-model-comparison.md) found timeouts in
thinking-enabled Qwen runs at temperature zero. Qwen's
[Qwen3 model card](https://huggingface.co/Qwen/Qwen3-8B) warns against greedy
thinking and recommends temperature 0.6, top_p 0.95, top_k 20, and min_p 0.
The [Qwen3.5 model card](https://huggingface.co/Qwen/Qwen3.5-9B) recommends
temperature 1.0 with those filters, presence penalty 1.5 and repetition penalty 1.0
for general thinking tasks. These are starting points for experiments, not
settings validated for this assistant's evidence checks.

The application now selects those general-thinking profiles automatically for
model families `qwen3` and `qwen3.5` (including namespace-qualified Ollama names).
Their thinking flags default to `true`; named GPT-OSS levels such as `low` are
rejected for these families. When either drafting or verification thinks, both
stages share the family's thinking sampling profile. Mixed thinking flags do not
silently leave the thinking stage at temperature zero.

`RAG_GROUNDING_SAMPLING` overlays explicitly supplied fields on this profile.
An absent variable, `{}`, or a filter-only override preserves the recommended
temperature. Explicit zero remains possible for controlled experiments; it is
not recommended for Qwen thinking. Both stages with thinking disabled retain the
tested temperature-zero baseline; other models and the judge retain their prior
settings. Custom aliases do not imply a model family, so configure them explicitly.

## Configure a fresh trial

Set variables before starting Python. For Qwen3 thinking:

```bash
RAG_GROUNDING_MODEL=qwen3:8b \
RAG_GROUNDING_TIMEOUT_SECONDS=180 RAG_GROUNDING_OUTPUT_TOKENS=4096 \
uv run python -m scripts.check_grounding \
  --output evaluation-results/qwen3-sampling-new.json
```

For Qwen3.5 thinking, change only the model to `qwen3.5:9b`; the profile selects
temperature `1.0` and presence penalty `1.5`. Ollama calls its repetition-penalty option
`repeat_penalty`.

For the faster Qwen3.5 configuration from the previous comparison:

```bash
RAG_GROUNDING_MODEL=qwen3.5:9b \
RAG_DRAFT_THINK=false RAG_VERIFIER_THINK=false \
RAG_GROUNDING_SAMPLING='{"temperature":0}' \
uv run uvicorn app.main:app --reload --reload-dir app
```

Restart the API after changing settings. The latter command uses a 120-second
timeout per call; it remains experimental and does not change repository defaults.
No reindexing is required. A verified answer can make up to four calls (draft,
verification, repair, and repair verification), and each-paper scope can repeat
that pipeline for multiple documents. The HTTP timeout applies to individual
network operations, not the entire question. Raising it gives a slow call more
time; it does not speed inference up.

Output budgets include thinking. A `done_reason: length` response from
[Ollama chat](https://docs.ollama.com/api/chat) raises an explicit output-budget
error, even if its content happens to be valid JSON. The failed call propagates
to the report instead of triggering repair or being scored as a safe refusal.
There are no transport retries or automatic fallback models. Increasing the
output budget can increase latency and memory demand; keep context and output
budgets suitable for the machine.

## Reproducibility

Evaluation and replay reports record actual sampling overrides and effective
draft/verifier timeouts. These values and the output budget enter the grounding
fingerprint, so changing them prevents evaluation resume. Older reports remain
readable with unknown inference fields; their frozen configuration hashes and
raw bytes are preserved. Older verified reports cannot be resumed as if the new fields had been
recorded originally. The judge and plain-generation defaults are unchanged.

New paired comparisons use protocol schema 3. Each candidate must explicitly
freeze `sampling`, `draft_timeout_seconds`, `verifier_timeout_seconds`, and
`output_tokens`, in addition to its model identity, thinking controls and grounding
fingerprint. The scorer checks those values as well as the completion-time replay
digest. Retrieval, questions, passages and context remain fixed. The recorder pins
the candidate's sampling/output/timeout environment for each subprocess.
Schema-2 protocols retain their original rules; their historical files are not
rewritten. The tracked older comparison protocols refer to the previous grounding
implementation and cannot generate compliant new runs under this implementation.
Prepare a fresh protocol with current code/fingerprint hashes before any new
paired comparison; do not relabel old runs or edit their hashes.

## Bounded diagnostics, 2026-09-29

Before generation, three arms were frozen locally: Qwen3.5 thinking with its
recommended general-task sampling; Qwen3 thinking with its recommended sampling;
and Qwen3.5 with thinking disabled and temperature zero. All use 12,288 context
tokens, 4,096 output tokens and a 180-second per-call timeout. Four existing
verifier controls were selected for each: supported current-study result, wrong
number, unsupported shared population, and supported shared population. Each arm
stops on a failed call without retries. Installed model identities, runtime and
source code hashes are retained with the protocol and completion hashes locally.
These diagnostic runs used commit `fcec66f` and explicit settings, before the
automatic-profile adjustment. Their files and results remain unchanged. The new
automatic thinking profiles select the same sampling values; that equivalence
does not turn the earlier incomplete or failing controls into passes.

After the automatic-profile adjustment, four fresh one-token transport probes
exercised drafting and verification for both Qwen models without sampling or
thinking overrides. Both resolved to their documented profiles, and each call
raised the expected output-budget error on the installed runtime. These checks
confirm request compatibility, not correct answers or adequate thinking budgets.
The ignored `automatic-qwen-profiles.json` report has SHA-256
`82ac93cf2687b1d782d7d3fbab24c35e55283ffb7c0086b26c750e557590aac4`.

| Configuration | Completed controls | Correct verdicts | Observed call times | Outcome |
| --- | --- | --- | --- | --- |
| Qwen3.5, thinking, recommended sampling | 1 of 4 | 1 of 1 completed | 179.57 s, then a 180 s timeout | Arm failed on the wrong-number control; later controls were not run |
| Qwen3, thinking, recommended sampling | 4 of 4 | 3 of 4 | 35.83–48.29 s | Completed; incorrectly accepted the unsupported shared-population claim |
| Qwen3.5, no thinking, temperature zero | 4 of 4 | 4 of 4 | 16.61–28.72 s | Completed; median 26.08 s |

All completed controls had a complete semantic verifier response. A timeout is
not a correct refusal, and the incomplete Qwen3.5 thinking arm cannot be reported
as a four-case pass. Recommended sampling alone did not eliminate Qwen3.5's
thinking timeout. Model loads are included, and timing is specific to this Mac
and these small prompts. The arms change both thinking and sampling, so these
results do not isolate a temperature effect.

A separate, prespecified two-case synthetic smoke check exercised drafting and
verification with Qwen3.5, thinking disabled and temperature zero, using the
default 120-second timeout. It returned the supported male-mouse glucose-uptake
result with the application-owned citation in 25.40 seconds, and refused the
unsupported female-mouse question in 2.27 seconds. Both checks passed. A separate
one-request transport probe deliberately allowed only one output token and
confirmed the installed Ollama raises `OllamaOutputLimitError` through the client.
Neither probe retrieves papers or establishes general answer reliability.

These are single-trial synthetic verifier diagnostics. They do not test retrieval,
draft generation against papers, repair quality, or overall answer quality, and
are not directly comparable to the previous 16-question study. Its original
zero-temperature artifacts remain unchanged. The Thomas/Emma paper-review packet
is still pending, and no v1 or default-model decision follows from these checks.

Local raw files are under `evaluation-results/inference-settings-20260929/` and
remain ignored. SHA-256 digests of the three control reports, captured on process
completion:

| Report | SHA-256 |
| --- | --- |
| `qwen35-thinking.json` | `1335ccf965a958b9d5b3eefe271f8a1a97adf84d6fdd5ca40e49971649246b9e` |
| `qwen3-thinking.json` | `edbb0669bb88ca041d6e78a5dbe1d60bcea50c3c7c999be5ec7e9dc93e8937b5` |
| `qwen35-direct.json` | `f96c068d0e1454381bd963bbf5ff519cd9c023471ae89372b97940d67d296b83` |
| `qwen35-direct-integrated.json` | `64aa61ddef5e3399187b1ba2149b986ae90a5647f39c4d57255cbccfc3e9e33b` |
| `output-budget-probe.json` | `b16d6829e8f725a53a03aa68fd571dc0dfed40aca231306d7e0f783f7c4c31f0` |

The local diagnostic protocol digest is
`1ff9add2c945339fd8a8cae1f20ff09dda8020c466d9d95d1f5c3817a0899721`.
