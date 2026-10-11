# Named identifiers in approved evidence

Contract v38 adds a deterministic necessary condition before final-excerpt proof:
letter-leading contiguous ASCII alphanumeric question tokens containing a digit,
such as `C26`, `FGF21`, or `Fis1`, must occur in the approved claim excerpts.
Matching ignores case but preserves whole-token boundaries. `C260`, `C26A`,
document names, claim text and unselected source context cannot establish `C26`.
Quotes are checked individually; fragments across excerpts cannot form a name.

Missing identifiers trigger the existing single repair with specific feedback.
Repair must select the supporting scope excerpt so it reaches final display.
Identifier presence does not approve the answer: attribution, claim support,
requirement coverage, duration validation and isolated semantic proof remain.
Retrieval, indexing, models, prompts, schemas and inference settings are unchanged.
No reindexing is needed. The discarded v37 schema trial is not reinstated.

## Limits

This closes the missing-identifier failure class, not scientific entailment.
The guard cannot connect a named cohort to an outcome, reject a wrong numerical
result, or establish word-only qualifiers such as stable knockdown. Acronym-only
names and hyphenated forms such as `miR-21` remain semantic checks. It can
conservatively refuse valid answers expressed using aliases, including `Fis1KD`
for `Fis1`. It does not perform synonym or acronym expansion.

## Regression proof

Tests reproduce a permissive verifier/proof approving numeric evidence without
the question's named cohort. The application rejects it before proof and exposes
no claim evidence. They also cover repaired scope selection and display, case and
token boundaries, retained semantic rejection, and plain numerals/acronym expansion.

The exact faulty housing draft and full-verifier selection from the
[discarded v37 trial](remaining-evidence-check.md) were also replayed without
model calls. Reusing those outputs for both initial draft and repair now refuses
with missing `C26`; the saved incorrect positive proof is never invoked.
The ignored regression report is
`evaluation-results/v38-identifier-check-20261011T195029936496Z-recorded-regression.json`,
SHA256 `bb54332c760b075fbd80f5b4ad8fb682c65038c54678ac46c1e9fbbc3de5c7ae`.
This proves deterministic guard behavior, not improved model accuracy.

## Live development check

Housing FGF21, the previously supported SLC25A33 gene comparison, and the SERCA
force control are preselected for one normal-generation run each, with their six
unchanged saved passages and the existing single repair. No labels, reference
answers or judge reach generation; failures are preserved without further variants
or selective retries. A separate AI reviewer assesses only the final displayed
excerpts. This is a saved-source development check, not current retrieval testing,
repeatability evidence or a fresh-question release gate.

| Case | Final result | Calls / elapsed |
| --- | --- | --- |
| Housing FGF21 | Safe refusal: repair still omitted displayed C26 support; the new guard rejected it before proof | 3 / 134 s |
| SLC25A33 gene comparison | Supported answer after repair; displayed excerpts establish the Fis1 increase and Drp1 unchanged comparison | 4 / 225 s |
| SERCA force control | Valid `answerable=false, claims=[]` refusal | 1 / 8 s |

The housing and gene drafts initially used invalid fields, consuming repair;
this change does not address draft-format reliability. No transport failures or
unsupported final answers were observed in these three inspected cases. One of
two answerable cases passed, and the control refused appropriately. This is not
an accuracy estimate or proof that all missing-scope failures are fixed.

Independent review initially flagged the gene excerpt's apparent `SLC225A33`
typo. Reassessment accepted the same-experiment contrast together with the second
approved excerpt naming `SLC25A33`, consistent with the original r2 review.
The second excerpt's "did not enhance" alone would not establish "unchanged".
Both review versions are preserved; source support is assessed in context, not
by character equality between claim and quote.

The ignored live report is
`evaluation-results/v38-identifier-check-20261011T195029936496Z.json`, SHA256
`d4c00b52dd3d5ed8ad9b819a8de3052b5f20faf7829ac1bc39ced41c677dd514`.
Its original `-source-review.json` has SHA256
`ab62455a42fd9dfddee47be6310a813b8047e906db36b7a7b143019e346cdbe4`;
the final `-source-review-reassessment.json` has SHA256
`3a5680381649bad99d06453c15832d3a63ff628af15a2a711eada94df9bcdeac`.
The runner, raw calls, traces, settings and observed runtime are saved with the
report. Model/runtime metadata, application hash and generation fingerprint
matched before and after generation. The application hash is
`fb894bd5c68b6d1aeea912a3e48f5e3a0cbb08db97d40e88c30967f6bd07dc3c`;
the generation fingerprint is
`c5632c4dfd34b1fdeefd9d966e4a1d711f2aadb80312f16b908e77f19bf85d06`.

Regression checks pass: 431 Python tests (17 skipped) and strict typing across
79 files. Local v1 remains open for reliable evidence selection and a separately
reserved fresh-question check.
