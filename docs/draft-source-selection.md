# Draft source selection

## Contract v36

Draft and repair calls select source IDs instead of copying evidence text. This
removes a failure mode where an otherwise useful draft changed an extraction
hyphen, punctuation or quote boundary and was rejected for an inexact quote.
The draft input no longer duplicates each passage as a list of quote choices.

The application still constructs the same whitespace-normalized evidence spans
from each claim's selected sources. The verifier selects numeric excerpt IDs;
claim support, attribution, requirement coverage, full-question coverage,
duration validation and isolated proof of the final excerpts remain required.
An unknown or empty source, an extra draft quote field, or an invalid evidence
selection fails closed. Only the existing single repair is allowed.

Public `claim_evidence` keeps its `source_index` and `quote` fields. Quotes remain
application-owned source text. Rendered locations now come from the final
approved excerpts, including when a caller does not request evidence capture.
Selecting a candidate source does not cause an unused passage to be cited.
Retrieval, indexing, models and inference settings are unchanged; no reindexing
is needed.

## Development check: 2026-10-11

The preselected check generates two inspected quote-copy failure cases and two
inspected refusal controls once each, using their unchanged six saved passages.
Only the question and passages reach generation. No benchmark answer, label or
evaluation judge is supplied. Built-in repair is allowed; failed calls and drafts
are preserved. This tests generation, not end-to-end retrieval, and is not a
fresh-question release gate.

The local ignored report is
`evaluation-results/v36-generation-check-20261011T174047883938Z.json`, with its
runner saved alongside it. It records raw requests/responses, stage traces,
settings, model digest and application/source fingerprints. The baseline report
hash is `a0da09ecbe1818f999ed5773c13e73a9e03c9bc55f81c80c2e2b2d88daa851d2`;
the unchanged 1,043-chunk corpus hash is
`92a2f8def85239a9dd06020d59c725f9dae52817de25e3561d6d0b8285e9b9b8`.
The generation fingerprint is
`ec26bfedada93f72e9b3bc2a7efb95dd0939f46c8c1f6f03c880a33bce384fb0`.
The completed run hash is
`be2f5f54e432323069c1731c4c03f8d3a25301519b2fb26403a6c70e1732b442`.
Ollama 0.40.3 served `gpt-oss:20b` with digest
`9ba9cc2b4e02463b933096090530aef679d534dd91ecc9afadfb2dbfdc59f3c5`.
Runtime metadata, application hash and generation fingerprint matched before
and after the run. Reasoning remained low for draft and medium for repair,
verification and proof, with the existing 12,288-token context, 4,096-token
output budget and sampling temperature/top-p of 1.0.

| Inspected case | Result | Calls / elapsed |
| --- | --- | --- |
| Day-14 C26 glucose tolerance and insulin | Supported answer; final excerpts establish cohort, day and insulin independence | 4 / 199 s |
| Short-term Activin blockade and adipose uptake | Supported negative answer; final excerpts establish short-term treatment, lean mice and insulin-stimulated adipose uptake | 3 / 152 s |
| Housing SERCA inhibition and force | Valid `answerable=false` refusal | 1 / 7 s |
| Activin metformin cotreatment and pyruvate response | Valid `answerable=false` refusal | 1 / 7 s |

The first case initially returned malformed claim field names. Deterministic
validation rejected it; the existing single repair produced the supported
answer. The Activin answer omitted an unused abstract source from final
evidence and rendered locations. Neither control needed repair or failed on
schema, transport or budget errors. Separate AI review checks the displayed
excerpts and saved passages; it is not a human scientific review.
The separate review is saved beside the report as
`v36-generation-check-20261011T174047883938Z-source-review.json`, with SHA256
`eed7cc9543b70e54da68f3c1a38534b734b520dbec66d13d7f23ce0bb3fb8049`.

Two of two answerable cases have complete displayed support, and two of two
controls refuse appropriately. These four outcomes are a bounded development
result, not an accuracy estimate or evidence that all previously failed cases
are fixed. Housing and mitochondrial answerable cases were not rerun here.

Regression checks pass: 426 Python tests (17 skipped) and strict typing across
79 files. They cover source-only drafts, rejection of injected quote fields,
exact application-owned evidence, and removal of unused locations with and
without evidence capture. Existing grounding rejection/proof controls remain.

This change removes model quote copying; source selection and semantic
verification can still fail. A separately reserved fresh-question check remains
necessary before claiming local v1 answer reliability.
