# Research corpus and evaluation protocol

The assistant accepts PDFs independently of this corpus. These papers are test
inputs, not built-in knowledge. PDF files under `data/` and generated reports under
`evaluation-results/` are ignored by Git. Source metadata and limited evaluation
excerpts are tracked so results can be interpreted and reproduced.

## Current development paper

Frank, E., Persson, K. W., Morigny, P., Ogueboule, Z. K. J., Pham, T. C. P.,
Knudsen, J. R., Rohm, M., Sylow, L., and Raun, S. H. (2026).
*Pre-clinical cancer cachexia causes glucose hypermetabolism prior to overt weight loss*.
Molecular Metabolism 111, 102422. [DOI](https://doi.org/10.1016/j.molmet.2026.102422).

- Local filename: `data/sample.pdf`.
- Copyright: © 2026 The Authors; published by Elsevier GmbH.
- License: [CC BY-NC-ND 4.0](https://creativecommons.org/licenses/by-nc-nd/4.0/),
  confirmed in the PDF and [university publication record](https://researchprofiles.ku.dk/en/publications/pre-clinical-cancer-cachexia-causes-glucose-hypermetabolism-prior/).
- PDF SHA-256: `072e84623519c3de66e77c6137e4ff92dd315409a639406e5d767bc4d5b262ca`.
- Cases: `scripts/answer_quality_cases.py`, 24 questions. Historical retrieval
  experiments also use this paper. This set has been used repeatedly for tuning;
  it is **development data**, never a held-out accuracy estimate.

Retain attribution rather than anonymizing the publication. The article's license
is separate from permissions for this repository's code. Noncommercial and
NoDerivatives conditions need to be considered for redistribution of article
content or a public service; the project does not assert that every RAG use is
covered. Renaming a file does not change its license.

The PDF was removed from the current tracked tree but exists in older Git commits.
The ignore rules do not erase history. This PR does not rewrite shared Git history
or claim historical copies have been purged.

## Evaluation paper (first comparison completed)

Irazoki, A., Frank, E., Pham, T. C. P., et al. (2025).
*Housing Temperature Impacts the Systemic and Tissue-Specific Molecular Responses
to Cancer in Mice*. Journal of Cachexia, Sarcopenia and Muscle 16, e13781.
[DOI](https://doi.org/10.1002/jcsm.13781).
The complete author list, including Emma Frank, is retained in
[`benchmarks/housing-temperature-2025.json`](../benchmarks/housing-temperature-2025.json).

- Copyright: © 2025 The Author(s); published by Wiley Periodicals LLC.
- License: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), confirmed
  in the PDF notice and its license hyperlink. The
  [institutional record](https://research.regionh.dk/da/publications/housing-temperature-impacts-the-systemic-and-tissue-specific-mole/)
  also records CC BY.
- [Published PDF from the Helmholtz institutional repository](https://push-zb.helmholtz-munich.de/deliver.php?id=41354).
- Local filename: `data/housing-temperature.pdf`.
- PDF SHA-256: `3b4d5ef35f05fe0840096236a6758d312d1b7bc6dfc5f4c6ab3b79f0a140ce8e`.
- Ten assistant-authored questions: eight answerable and two unanswerable.
  Excerpts retain extraction characters; reference answers are paraphrases.
  Neither the authors nor publisher endorse this benchmark.
- Reserved on 2026-09-20 and then used in the
  [first three-model comparison](housing-model-comparison.md). The original manifest
  is preserved as the pre-run record; its `holdout` label describes the initial
  split, not a guarantee that the set remains untouched. Treat subsequent use as
  development evaluation. Labels still need independent subject-matter review.

This broadens coverage beyond the original paper, but shares authors, scientific
field and mouse model. It is not a broad-domain generalization benchmark. We also
found the related 2024 conference abstract *Mitochondrial adaptations in thermogenic
tissues during cancer cachexia and upon different ambient temperatures*
([record](https://researchprofiles.ku.dk/en/publications/mitochondrial-adaptations-in-thermogenic-tissues-during-cancer-ca/)).
It is not counted as another independent paper, and its reuse license was not
confirmed. Additional papers should include the same Emma Frank in their author
list and have an explicitly checked license; preprint/published versions of one
study should not be placed on opposite sides of a development/evaluation split.

## Third paper reserved for unexpanded verified-answer evaluation

Irazoki, A., Gordaliza-Alaguero, I., Frank, E., et al. (2023).
*Disruption of mitochondrial dynamics triggers muscle inflammation through
interorganellar contacts and mitochondrial DNA mislocation*. Nature
Communications 14, 108. [DOI](https://doi.org/10.1038/s41467-022-35732-1).
The [publisher article](https://www.nature.com/articles/s41467-022-35732-1)
lists Emma Frank and identifies the version of record as CC BY 4.0.

- [Publisher PDF](https://www.nature.com/articles/s41467-022-35732-1.pdf), stored
  locally as ignored `data/mitochondrial-dynamics-2023.pdf`.
- PDF SHA-256: `d9b9673dfe072f2327a5f3902807eb1168039a90a2cdb27c637cc017b21bc8a0`.
- Ten assistant-authored questions, eight answerable and two unanswerable, in
  [`benchmarks/mitochondrial-dynamics-2023.json`](../benchmarks/mitochondrial-dynamics-2023.json).
  See the [frozen unexpanded verified-answer protocol](unexpanded-verified-third-paper.md).
  Labels have not been reviewed independently; this limits any quality claim.

## Fourth paper: first vector-reserve comparison completed

Carlsson, M., Frank, E., et al. (2025). *Activin receptor type IIA/IIB
blockade increases muscle mass and strength, but compromises glycemic control
in mice*. Molecular Metabolism 102, 102261.
[DOI](https://doi.org/10.1016/j.molmet.2025.102261).
The [university publication record](https://researchprofiles.ku.dk/en/publications/activin-receptor-type-iiaiib-blockade-increases-muscle-mass-and-s/)
lists Emma Frank and CC BY; the published PDF also carries a CC BY 4.0 notice.

- [Published PDF from NLM PMC Open Data](https://pmc-oa-opendata.s3.amazonaws.com/PMC12556210.1/PMC12556210.1.pdf),
  stored locally as ignored `data/activin-receptor-2025.pdf`.
- PDF SHA-256: `b60d1a5d4612320f50863460f11d763b524a20d45420ff8c8a0f62d97478f254`.
- Ten frozen assistant-authored questions, eight answerable and two
  unanswerable, in [`benchmarks/activin-receptor-2025.json`](../benchmarks/activin-receptor-2025.json).
  See the [prespecified first comparison](activin-vector-reserve-validation.md).
  The first run is complete and mixed: vector reserve recovered the one missing
  exact label, but refused a cross-page question that the baseline answered.
  This paper is now development data. Labels have not been reviewed
  independently, and it shares authors and a biomedical domain with the earlier
  papers.

## Download and validate without running models

From the repository root:

```bash
mkdir -p data
curl --fail --location 'https://push-zb.helmholtz-munich.de/deliver.php?id=41354' \
  --output data/housing-temperature.pdf
uv run python -m scripts.evaluate_answers \
  --benchmark benchmarks/housing-temperature-2025.json \
  --pdf data/housing-temperature.pdf --validate-only
```

Validation checks the exact PDF hash and evidence page/quote matches. It does not
connect to PostgreSQL or call Ollama, index a document, or create an answer report.
A new publisher PDF build can have a different hash even if the prose is similar;
review and version the manifest rather than bypassing the check.

## Isolated evaluation

The API can search multiple indexed documents. Evaluation currently uses **one
paper per run**: its unanswerable labels apply only to that paper. It rejects an
index containing other documents. Use a separate database rather than deleting
papers from your normal index. With the supplied Docker Compose database running,
create a new database once and select it in the current terminal:

```bash
docker compose exec db createdb -U rag rag_housing_eval
export RAG_DATABASE_URL='postgresql+psycopg://rag:rag@localhost:5432/rag_housing_eval'
uv run python -m scripts.init_db
uv run python -m scripts.index_pdf data/housing-temperature.pdf
```

For a follow-up verified-mode development evaluation, freeze the configuration and run:

```bash
RAG_GROUNDING_MODEL=gpt-oss:20b RAG_DRAFT_THINK=low RAG_VERIFIER_THINK=medium \
  uv run python -m scripts.evaluate_answers \
  --benchmark benchmarks/housing-temperature-2025.json \
  --pdf data/housing-temperature.pdf --strategy expanded --answer-mode verified \
  --output evaluation-results/housing-gpt-oss-verified.json
```

The CLI reads model settings at process startup. Use a new output path for every
run. To resume, supply the same `--benchmark`, `--pdf`, model environment and
`--resume` report; PDF hash, benchmark metadata, selected cases, model roles,
reasoning, prompts and corpus must match. Evaluator version 9 rejects resumes from
older versions but can still load old reports for inspection and replay.

For a controlled comparison of **plain answer models**, use the same questions,
retrieval strategy and judge and change only `RAG_GENERATOR_MODEL`, for example
`qwen3:8b`, `gpt-oss:20b`, and `qwen3-coder:30b`. Keep `--answer-mode plain` for all
three; changing a generator setting has no effect on verified mode. Compare
correctness, actual false refusals, cited-source support and latency, and inspect
judge disagreements. Model-default decoding still differs across model families.
Do not compare this directly to verified mode as an isolated model-size effect.

Changing the verified model also requires compatible reasoning settings. GPT-OSS
uses `low`/`medium`/`high`; models that accept boolean thinking controls can use
`true`/`false`. Unsupported model/configuration errors propagate. A successful
request does not establish that a replacement model is accurate: rerun the verifier
controls before a quality run. No automatic model download or fallback occurs.

After a predeclared comparison, record the first results before revising anything.
If those results influence prompts, retrieval or model selection, treat this set
as development data for subsequent work and obtain another evaluation set. Do not
repeat runs and report only the best. Two related papers and assistant-authored
labels remain insufficient to claim general reliability.

Use `unset RAG_DATABASE_URL` to return subsequent commands to the default database.
