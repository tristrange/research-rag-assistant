# Third local-v1 fresh-question check

## Frozen protocol

Merged candidate `6b33f221e6e07a97cc1ddfa609f1fa1d0218f634` uses grounding
contract v40. Commit `8d8cc00` freezes application files, settings, the indexed
corpus, original PDF provenance and Ollama runtime before question authorship.
The [reservation manifest](../benchmarks/local-v1-fresh-check-2026-10-12-r3.json)
binds these inputs and the local artifacts.

Two GPT-6 Luna agents prepare eight new questions on the four known papers:
six answerable questions and two unanswerable controls. A separate reviewer
checks original PDF context, labels and semantic novelty against 114 recorded
question texts and inspected development facts before generation. This is an
AI-authored portfolio check on known papers, not human review or unseen-paper
validation. Raw labels and PDF passages remain ignored locally.

The normal document-scoped verified path uses the unchanged default retrieval:
20 vector candidates, six unexpanded reranked passages with the existing page
reserve, local nomic embeddings and BGE reranking. GPT-OSS 20B drafts with low
thinking; verification, proof and the existing single repair use medium thinking.
Sampling remains temperature/top-p 1, context 12,288 tokens, output 4,096 tokens
and stage timeout 300 seconds. No model judge is invoked.

Reserve the reviewed questions before the first generation. Generate each once,
without reference answers, label quotes or reviewer notes in retrieval/generation.
Do not change prompts, retrieval, labels, models or inference settings between
cases. Preserve errors and refusals without selective retries. Separate AI
source review checks final displayed excerpts, PDF context, completeness,
qualifiers and attribution. Application, settings, corpus, PDFs and observed
runtime must match the freeze before and after the run.

Use an isolated copy of the stopped local database. Remove the temporary
container and copied volume after the check; preserve the original library and
all recorded failures. Reranker package versions are captured, but its weight
digest is not pinned by the Ollama snapshot.

## Unchanged stopping rule

- At least five of six answerable cases have correct, complete supported answers.
- Both unanswerable controls receive appropriate refusals.
- No material unsupported claim or attribution error is observed.

A safe refusal to an answerable case fails completeness. Correct facts in the
full paper do not excuse missing scope in the approved excerpts. A failure keeps
local v1 open and requires development work plus different separately reserved
questions for another check. Passing development replays cannot rescue a failed
validation result. Report exact counts and limitations, without a broad accuracy
claim. The optional human worksheet remains unchanged.
