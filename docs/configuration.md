# Configuration

The browser/API uses GPT-OSS 20B for drafting and checking claims. Qwen3 8B is
still the default judge and plain-generation baseline in optional evaluation
scripts; it is not required to ask questions in the browser. Qwen3.5 9B was
[compared](verified-model-comparison-v21.md), but has not replaced those defaults.

Set these environment variables before starting the API or evaluation process:

Settings are resolved once at startup. Source your private `.env` before launch;
the application does not load it automatically. Restart after changing settings.

| Variable | Default | Role |
|---|---|---|
| `RAG_GENERATOR_MODEL` | `qwen3:8b` | Plain generation in local evaluation scripts |
| `RAG_GROUNDING_MODEL` | `gpt-oss:20b` | Verified drafting and verification |
| `RAG_JUDGE_MODEL` | `qwen3:8b` | Evaluation and judge calibration |
| `RAG_DRAFT_THINK` | `true` for Qwen3/Qwen3.5; otherwise `low` | Verified draft reasoning |
| `RAG_VERIFIER_THINK` | `true` for Qwen3/Qwen3.5; otherwise `medium` | Verified reasoning |
| `RAG_GROUNDING_SAMPLING` | `{}` (automatic profile below) | JSON sampling overrides shared by verified drafting, repair and verification |
| `RAG_GROUNDING_TIMEOUT_SECONDS` | 120 without explicit thinking; 300 with thinking | Per-call HTTP timeout override, greater than 0 and at most 600 seconds |
| `RAG_GROUNDING_OUTPUT_TOKENS` | `4096` | Per-call output budget, including reasoning; 1–8192 tokens |
| `RAG_DB_PASSWORD` | Required by Compose | Local PostgreSQL password |
| `RAG_DATABASE_URL` | No usable password by default; set via private `.env` | Index connection |

The API uses `RAG_GROUNDING_MODEL`; local plain-mode evaluation uses
`RAG_GENERATOR_MODEL` independently.
Reasoning values accept `true`, `false`, `low`, `medium`, or `high`; choose values
supported by the selected model. These settings do not change the embedding model
or require reindexing. Models must already be installed in Ollama; there is no
automatic download or fallback. Blank settings fail at startup. Restart the process
after changing settings. Model comparisons should keep the judge fixed and inspect
actual evidence, not rely only on aggregate model grades.

With Qwen3 or Qwen3.5, thinking flags must be Boolean. If either stage thinks,
the shared sampling profile uses temperature 0.6 for Qwen3 or 1.0 for Qwen3.5,
top_p 0.95, top_k 20, min_p 0, repeat_penalty 1, and presence_penalty 0 for
Qwen3 or 1.5 for Qwen3.5. These follow their general-thinking guidance.
When both stages disable thinking, temperature stays at the previously tested
zero baseline. GPT-OSS uses temperature 1.0 and top_p 1.0, following its
[recommended sampling](https://github.com/openai/gpt-oss#recommended-sampling-parameters).
Other grounding models retain temperature zero. Selecting Qwen
alone enables its thinking profile; use both `THINK=false` variables for the
faster non-thinking configuration.

Sampling accepts numeric `temperature` (0–2), `top_p` (greater than 0, at most 1),
integer `top_k` (1–1000), `min_p` (0–1), `presence_penalty` (0–2), and
`repeat_penalty` (greater than 0, at most 2). Explicit values override the selected
profile; omitted values inherit it, including when the JSON is `{}` or specifies
only a filter. Filters omitted from the selected profile retain the installed
model's defaults. Explicit temperature zero is available for controlled
experiments; it overrides the recommended Qwen thinking and GPT-OSS profiles. Unknown keys, invalid
types, non-finite numbers, and out-of-range values fail at startup.
These overrides affect verified calls only; the evaluation judge stays at
temperature zero with thinking disabled. Context remains 12,288 tokens.
For tested settings, commands, and limitations, see the
[inference-settings follow-up](ollama-inference-settings.md).
