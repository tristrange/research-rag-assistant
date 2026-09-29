# Question coverage and exact evidence

The v13 verifier selected its own list of question requirements. In the earlier
Qwen3.5 non-thinking control, it accepted an effect summary for “At what dose did
treatment delay weight loss in the cited Smith study?” The reference title gave
the effect but no dose. The verifier omitted dose from its requirements, so code
had nothing to reject. The original comparison and raw report remain unchanged.

## v14 contract

Verification must return a fixed `question_coverage` object. Its
`requested_answer` check quotes the entire original question, allowing whitespace
normalization, and cannot be marked `not_requested`. Nine qualifier checks cover
document/study, population, sex, species, intervention, dose, comparison, time
period, and other explicit qualifiers. Each field is mandatory: an unasked
qualifier is the literal `"not_requested"`; a requested qualifier is an object
marked supported or unsupported. Requested qualifiers select exact question text from a bounded question-only
catalogue: the whole normalized question plus individual whitespace-delimited
words, capped at 128 unique choices. The whole question is always
available for long or later qualifiers. This selects textual anchors without
interpreting scientific terms. Single-word anchors avoid many overlapping
phrase alternatives in constrained generation. Unasked
qualifiers have no nested object, question excerpt, evidence, or explanation to
generate. This keeps the explicit checks while reducing output tokens.

For every claim, the application builds an evidence catalogue from all exact
sentence spans in that claim's cited passages. Each ID belongs to a particular
claim and source. This includes adjacent population and attribution sentences,
even when the draft selected only the result sentence. Uncited retrieved
passages are excluded. The verifier schema restricts evidence IDs to that
catalogue, and runtime validation checks them again. The generation schema also
encodes valid combinations of status, question excerpt, and evidence; Pydantic
model validators alone do not communicate those rules to Ollama.

A supported question check or claim verdict requires at least one evidence ID.
IDs must be unique and valid; a claim verdict cannot use another claim's IDs.
Incomplete coverage, rewritten question targets, unsupported checks, or rejected
claims prevent rendering the entire answer. Verification traces retain the
catalogue alongside the verdict so its evidence links can be inspected.

The draft and verifier still use the configured local model in separate calls.
There is at most one repair, and no added model round trip. The verifier produces
more structured output, so unchanged call counts do not imply unchanged latency.
Transport and output-budget failures still propagate rather than becoming safe
refusals. A supported negative result remains answerable; merely measuring an
outcome cannot establish no effect. No default model, extraction, retrieval,
embedding, or corpus setting changes, so no reindexing is needed.

## Limits

These checks establish complete output structure and exact textual provenance,
not semantic entailment. The model can still misclassify a requested qualifier
as unasked, bind an excerpt to the wrong population or time period, or approve an
excerpt that does not answer the question. Exact evidence makes those decisions
auditable; it does not make them infallible. Independent human review and a fresh
paired replay are still needed before a model-promotion decision.

The 16-case development packet remains inspected development data. Thomas and
Emma's review is deferred, and this change does not complete that milestone or
establish v1 readiness.

## Control protocol

The live control runner now requires a complete, structurally valid and
evidence-linked verifier response for every semantic control, including negative
cases. A malformed rejection cannot count as a passing negative. The sole
intentional deterministic exception is a current-study claim citing a references
section. Added pairs test a supported dose and duration against titles that omit
them. Expected answers are not supplied to the verifier.

The run uses all 21 synthetic controls once per model, sequentially. Qwen3.5 uses
thinking disabled in both stages; GPT-OSS retains low drafting and medium verifier
reasoning. Both use temperature zero, 12,288 context tokens, 4,096 output tokens,
and a 180-second per-call timeout. These are development checks, not a new
16-question benchmark or independent validation. Reports preserve exact model
outputs, evidence catalogues, fingerprints, settings and timings. Original and
failed outputs are not overwritten or retried.

Raw artifacts are ignored under
`evaluation-results/qualifier-evidence-20260929/` in the main checkout. A local
manifest records installed model digests, Ollama 0.34.4 and file hashes.

```bash
RAG_GROUNDING_MODEL=qwen3.5:9b \
RAG_DRAFT_THINK=false RAG_VERIFIER_THINK=false \
RAG_GROUNDING_SAMPLING='{"temperature":0}' \
RAG_GROUNDING_TIMEOUT_SECONDS=180 RAG_GROUNDING_OUTPUT_TOKENS=4096 \
uv run python -m scripts.check_grounding \
  --output evaluation-results/question-coverage-qwen35-new.json

RAG_GROUNDING_MODEL=gpt-oss:20b \
RAG_DRAFT_THINK=low RAG_VERIFIER_THINK=medium \
RAG_GROUNDING_SAMPLING='{"temperature":0}' \
RAG_GROUNDING_TIMEOUT_SECONDS=180 RAG_GROUNDING_OUTPUT_TOKENS=4096 \
uv run python -m scripts.check_grounding \
  --output evaluation-results/question-coverage-gpt-oss-new.json
```

Each invocation needs a fresh output path. Before rerunning the 16 saved
questions, freeze a new schema-3 comparison protocol for this implementation;
the historical protocols cannot be reused by replacing their hashes.
