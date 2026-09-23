# Unexpanded verified-answer evaluation on a third paper

## Protocol frozen before generation

Application baseline: merged `main` at `f2edf14` (PRs #17 and #18 merged). The
change in PR #17 addressed verifier refusals seen with expanded context. Test
the current verified answer path with the API's normal retrieval selection:
reranking, three passages, and no neighbor expansion. `scripts.evaluate_answers`
calls the same `answer_question` function as the API with those parameters. This
is a quality check of that path, not a change to the default answer mode.

Use the version-of-record PDF for Irazoki et al., *Disruption of mitochondrial
dynamics triggers muscle inflammation through interorganellar contacts and
mitochondrial DNA mislocation*, Nature Communications 14, 108 (2023), DOI
10.1038/s41467-022-35732-1. Emma Frank is an author. The publisher identifies
the article as CC BY 4.0. Download the [publisher PDF](https://www.nature.com/articles/s41467-022-35732-1.pdf)
to ignored `data/mitochondrial-dynamics-2023.pdf`; use the exact PDF with SHA-256
`d9b9673dfe072f2327a5f3902807eb1168039a90a2cdb27c637cc017b21bc8a0`.
The [publisher article and license notice](https://www.nature.com/articles/s41467-022-35732-1)
provide authorship and reuse terms. This is a different study from the two papers
already used for development, although it shares researchers and muscle biology.

The frozen manifest is `benchmarks/mitochondrial-dynamics-2023.json`: eight
answerable and two unanswerable questions in its listed order. Its evidence
excerpts are exact PDF extraction on numbered pages. The labels are
assistant-authored, not independently reviewed by a domain expert. `holdout`
means only that this paper and question set were reserved before this first run;
after results are inspected, treat the set as development data. Do not claim
scientific or broad-domain accuracy from ten cases.
Manifest SHA-256: `b78cb939f70329989dc9c39e1954c8e53a2122e9cd4da5956c3bdecec5e4f3cd`.

Pin installed GPT-OSS 20B `17052f91a42e` for verified drafting and verification
at temperature zero, with draft reasoning `low` and verifier reasoning `medium`.
Pin Qwen3 8B `500a1f067a9f` as the judge; keep the generator setting at Qwen3 8B
for completeness although verified mode uses GPT-OSS. Use the existing embedding
and reranker models, prompts, judge calibration, and deterministic checks. Record
their fingerprints in the report. Change no code, labels, retrieval settings, or
model settings during the run. Do not retry a completed answer to improve it.

Index only this paper in a dedicated database. Run the manifest's `--validate-only`
check before indexing, then run all ten cases once with a new local report path:

```bash
uv run python -m scripts.evaluate_answers \
  --benchmark benchmarks/mitochondrial-dynamics-2023.json \
  --pdf data/mitochondrial-dynamics-2023.pdf --validate-only

docker compose exec db createdb -U rag rag_mito_2023_eval
RAG_DATABASE_URL='postgresql+psycopg://rag:rag@localhost:5432/rag_mito_2023_eval' \
  uv run python -m scripts.init_db
RAG_DATABASE_URL='postgresql+psycopg://rag:rag@localhost:5432/rag_mito_2023_eval' \
  uv run python -m scripts.index_pdf data/mitochondrial-dynamics-2023.pdf

RAG_DATABASE_URL='postgresql+psycopg://rag:rag@localhost:5432/rag_mito_2023_eval' \
RAG_GENERATOR_MODEL=qwen3:8b RAG_GROUNDING_MODEL=gpt-oss:20b \
RAG_JUDGE_MODEL=qwen3:8b RAG_DRAFT_THINK=low RAG_VERIFIER_THINK=medium \
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
uv run python -m scripts.evaluate_answers \
  --benchmark benchmarks/mitochondrial-dynamics-2023.json \
  --pdf data/mitochondrial-dynamics-2023.pdf \
  --strategy reranked --top-k 3 --answer-mode verified \
  --output evaluation-results/mitochondrial-dynamics-reranked-verified-first.json
```

Preserve incomplete runs and record failures as failures. Check judge calibration,
retrieved evidence, final answers and citations manually against the saved PDF;
report appropriate and false refusals separately, along with answer/citation
scores and latency. The same local model drafts and verifies answers, and an
assistant-authored judge grades them, so their agreement is not independent
validation. Keep the raw report and PDF local; report only the necessary derived
findings and provenance in this document after the run.

## First-run result

The pre-run protocol and manifest were committed as `cee8c18` before any model
answers were generated. The isolated index contained only this paper (387
chunks). Judge calibration passed. The ten cases ran once, in manifest order,
from 00:43:48 to 00:52:35 UTC on 2026-09-23, with no code, label, model or index
changes. The complete ignored report is
`evaluation-results/mitochondrial-dynamics-reranked-verified-first.json`
(SHA-256 `95b9132dbe633c54c82a2636e2d9ddf97410900e067574307449b9c27b0530cb`).
Its corpus fingerprint is
`af3c6850cfa80378e0092e1e5a5deae396d8b87a512b9bc7265b986134d29ac2`;
the grounding prompt/schema fingerprint is
`9808eeca3e7f1cbc8c2bef56b01d11869eb20f67ff97e49c11376a57ff494646`.

Seven of eight answerable questions received answers supported by their returned
passages and correctly cited PDF pages. Both unanswerable questions received the
fixed insufficient-evidence response. The `cytosolic-mtdna` answerable case was
also refused. Its three returned passages described the Fis1/Drp1 side but did
not include the Mfn1/Mfn2 comparison required by the question. The missing
comparison was vector candidate 2 of 10 and reranked position 5, outside the
three passages passed to the model. This is a retrieval miss on this trial; the
refusal did not require weakening the verifier or inventing the missing finding.
The supported negative `food-intake-negative` case was answered correctly.

| Outcome | Cases |
| --- | --- |
| Supported answer | `fragmented-inflammation`, `ddc-mtdna-depletion`, `tlr9-inhibitor`, `rab5c-downregulation`, `food-intake-negative`, `muscle-csa-sexes`, `salicylate-regimen` |
| Answerable but refused | `cytosolic-mtdna` |
| Appropriate refusal | `human-salicylate-endurance`, `rab5c-inhibitor-mouse-dose` |

The judge reported a 9/10 pass rate, 7/8 evidence-hit rate, 7/8 answerable
coverage, 2/2 unanswerable abstention, and mean answer time 37.7 seconds. Its
aggregate citation-support score was 1.0, but that calculation also assigns
full citation support to fact-free refusals. Manual review confirmed the seven
substantive answers against their returned passages; each cited page was among
the returned sources. These are inspected, assistant-labelled development
results, not an independent estimate of accuracy or steady-state latency.

A separate local FastAPI `POST /query` smoke request used `answer_mode=verified`
and the food-intake question against the same index. It returned HTTP 200, a
supported negative answer citing page 10, and three sources. This was a new
generation trial, excluded from the ten-case metrics. Its ignored record is
`evaluation-results/mitochondrial-api-smoke.json` (SHA-256
`a8df4ae93dd7b5c10ad0920a69f5dc88cc697d1297b0c864d38fd9c6648e9a70`).

The next retrieval experiment should test how to keep complementary evidence
from adjacent chunks without admitting unrelated text, using development cases
and a separately reserved validation paper. The current result does not justify
changing API defaults. Independent subject-matter review of the labels remains
needed before making a stronger quality claim.
