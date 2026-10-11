# Remaining evidence-selection check

This development diagnostic checks the two scope-selection cases omitted from
the [first source-only draft check](draft-source-selection.md), plus one refusal
control. The baseline uses the merged v36 contract; the candidate adds explicit
bounded response schemas to the draft and repair prompts (v37). Models,
inference settings, retrieval, indexing and all verification gates stay unchanged.

The cases were selected before generation:

- `housing-fgf21-temperature-effect`
- `mito-mitophagic-flux-knockdown-groups`
- `housing-unreported-serca-inhibition-force`

Each recorded question runs once through normal `grounded_answer` with its six
unchanged saved passages. The existing single repair is allowed. Only questions
and passages reach generation; labels, reference answers and model judges are
excluded. Failures are retained without selective retries.

This isolates generation and evidence selection. It does not test current
retrieval, repeatability, or fresh-question release readiness. Separate AI review
must assess every displayed claim against its final approved excerpts, including
C26 identity for the housing result and stable-knockdown identity for mitophagy.

## Baseline: v36

Both answerable cases safely refused despite sufficient saved input. Their
initial drafts used `source_ids` instead of required `citations`; the mitophagy
draft also added an unsupported `type` field. The existing repair corrected the
structure, but final selected evidence omitted C26 identity or stable-knockdown
identity. The isolated proof rejected both answers. The SERCA control returned a
valid `answerable=false, claims=[]` refusal.

Separate AI source review confirmed these two coverage failures and the valid
control. No unsupported answer reached display; the correct numeric result and
knockdown comparison do not excuse incomplete evidence.

The ignored report is
`evaluation-results/v36-remaining-check-20261011T191935802429Z.json`, SHA256
`29ba233e9d4ea79c7055599b7d934920fe4e50009ca0ff11c62e8fffa8fe9d32`.
Its sibling `-source-review.json` has SHA256
`63c4f1ebd1a140d4161e873e2190e00077725c880f3a43d98a949f58518d01cc`.
The baseline generation fingerprint is
`ec26bfedada93f72e9b3bc2a7efb95dd0939f46c8c1f6f03c880a33bce384fb0`.

## Candidate: v37

Draft and repair previously referred to a schema supplied through the Ollama API
without showing its field structure in the prompt. Both now show the same
compact, source-bounded schema sent to the API, following the existing verifier
pattern. Empty sources remain ineligible and extra fields remain forbidden. The
regression test reproduces the wrong-field draft and checks schema equality for
both initial generation and repair.

The same three cases ran once on this candidate, with no further variants or
selective retries.

| Case | v36 baseline | Discarded v37 trial |
| --- | --- | --- |
| Housing FGF21 | Safe refusal after malformed draft and missing displayed C26 scope | Schema-valid initial draft; displayed answer still lacks C26 evidence |
| Stable-knockdown mitophagy | Safe refusal after malformed draft and missing displayed stable-KD scope | Supported answer after repair selects both stable-KD scope and group results |
| SERCA force control | Valid refusal | Valid refusal |

All initial candidate drafts were schema-valid. The housing proof nevertheless
accepted C26 identity by inferring it from the numeric effect; its displayed
excerpt does not establish that identity. The mitophagy initial proof rejected
missing stable-knockdown scope, and the existing repair selected both scope and
results for final display. Correct structure is not sufficient evidence support.

The candidate is discarded: one of two answerable cases has complete displayed
support, while the other violates the required evidence rule. These single
stochastic trials do not establish repeatability or prove that the schema text
caused the false approval. No runtime change or additional retry is retained.

The ignored candidate report is
`evaluation-results/v37-schema-check-20261011T192621978889Z.json`, SHA256
`2358e8686a019bafdc2645d055f98f441b51588d7a19f4f5ccf0333d4059ce2f`.
Its independent AI review is saved beside it as `-source-review.json`, SHA256
`3b8cc2b8228136a382b9d4739cf34a8ec369190d103654544caebc3f1d8a031b`.
The tested patch is preserved beside it as `-candidate.patch`, SHA256
`99d3fc3bfc556163378c2eb3ec992b1854b7e7620b7c8e4ad98d46dc4083fc14`.
Its application hash is
`f1430f5d9523ab08feca7fa6b178acefee93b66ebc675983cd0565e5e96b0100`;
its generation fingerprint is
`4005fa8b78a55599ad6a03bc1d72704eb3b3713fd3b4273fa307300b10a68168`.

Both reports retain their runner, raw requests/responses, traces and settings.
Application hashes, generation fingerprints and observed model/runtime metadata
matched before and after each run. Ollama 0.40.3 served `gpt-oss:20b` with digest
`9ba9cc2b4e02463b933096090530aef679d534dd91ecc9afadfb2dbfdc59f3c5`.
The saved-source baseline and corpus hashes match the first v36 check; this replay
does not query the current database or prove that its contents still match.

The discarded candidate passed 427 Python tests (17 skipped) and strict typing
across 79 files. Those checks demonstrate the schema contract, not model accuracy.
The retained change only documents the findings.

## Next work

Keep local v1 open. Missing experiment scope must not be inferred from a question
or a matching numeric outcome. Fix evidence selection and final-excerpt proof
before another separately reserved fresh-question check. Do not treat either
of these inspected replays as release validation.
