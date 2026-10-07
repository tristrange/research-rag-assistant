# Repair reasoning and evidence pointers

The [duration follow-up](duration-evidence.md) preserved a failed repair that
added checking commentary to a scientific answer and selected evidence for a
different measurement. Repair now reuses the verifier's reasoning and timeout
profile; the first draft keeps its existing profile. With default GPT-OSS
settings, these are medium and low reasoning respectively. The verifier prompt
labels each draft-selected quote with its application-owned evidence ID rather
than its passage ID. The full cited context and eligible evidence catalogue
remain available. All claims must still pass; no claims are silently discarded.

## Development observations

Two prompt-only attempts returned refusals; their prompt edits were discarded.
One medium-reasoning attempt produced a single supported scientific claim with
result and duration citations, but verification selected a different measurement's
evidence ID and the duration guard refused it. After binding the selected quotes
to evidence IDs, one fresh verification of that fixed repair selected the correct
result and duration excerpts and passed. No drafting or retrieval was repeated
for this final check, and no reference answers or labels were supplied.

This is a known development case with captured inputs. It does not prove general
repair reliability, complete the independent v1 fresh check, or compare latency
across equivalent full pipelines. Medium reasoning can increase repair latency;
the number of model calls and the single-repair limit are unchanged.

Original and failed reports remain Git-ignored in `evaluation-results/`:

- `repair-commentary-trial-20261007T181104735187Z.json`
- `repair-commentary-trial-20261007T181309752302Z.json`
- `repair-reasoning-trial-20261007T181531508357Z.json`
- `repair-evidence-id-trial-20261007T182128343033Z.json`

The final report records source-report hashes, corpus provenance, fixed settings,
all verifier output, call telemetry and unchanged runtime snapshots. Its SHA-256
is `20bcebed2178ea4a837ce9ff9ce87e0d6e7a79521e5fcf9be5220de509bfb635`;
application fingerprint:
`58c91d9d461a1768f609bc9d15d4944c31473de22e3dd44a01357b413c7bb421`.
Ollama was `0.40.0`, using `gpt-oss:20b` digest
`9ba9cc2b4e02463b933096090530aef679d534dd91ecc9afadfb2dbfdc59f3c5`.
The independent source-based review binds the final report hash in
`repair-evidence-id-review-20261007T182424652910Z.json`; it made no model calls.
