# Reviewed answer coverage follow-up

## Historical development review

The accepted AI-assisted review inspected 16 frozen September 28 answers against
their returned passages and source PDFs. It recorded 12 passes: 8 of 12 answerable
questions and all 4 unanswerable controls. All eight factual answers were
supported; four answerable questions received refusals. This is development
evidence from inspected questions, not independent validation or current-code
accuracy. The original reports, labels, PDFs and human worksheet remain unchanged.
Human review is available as optional additional review.

Further inspection refined the failure diagnosis: the cited-publication case had
sufficient returned evidence. The other three cases lacked some required context.
In particular, the Activin passages contained both numerical results but did not
establish the short-term population's chow-fed qualification. Finding the numbers
alone does not establish the complete comparison.

## Current-code reproduction

Four fresh, document-filtered queries ran once each on application commit
`f7223c675fcfe2321db034282bcd1c22ecdd8abf`, using the normal unexpanded reranked
three-passage path. The existing four-paper library contained 1,043 chunks; every
paper's stored indexing provenance matched its local PDF and current extraction,
chunking and embedding settings. The corpus fingerprint was
`92a2f8def85239a9dd06020d59c725f9dae52817de25e3561d6d0b8285e9b9b8`.

GPT-OSS 20B generated and verified answers with draft thinking low, verifier
thinking medium, temperature 1, top-p 1, a 12,288-token context, a 4,096-token
output budget and a 300-second timeout per stage. Retrieval used nomic-embed-text
and BAAI/bge-reranker-base, with ten vector candidates. Model weight digests,
runtime snapshots, selected passages, approved claims, rejected drafts and stage
traces were saved locally. No reference answers or judge scores were supplied to
the generator or verifier. Index contents and model/runtime snapshots matched
before and after the run.

| Question | Three-passage outcome | Diagnosis |
| --- | --- | --- |
| Cited Rosiglitazone publication | Supported answer | The answer distinguishes the referenced study from the queried paper. |
| Housing temperature and BAT ATP | Refusal | Retrieved SERCA ATPase activity does not establish ATP concentration; the verifier correctly rejected that substitution. |
| Mfn1/Mfn2 versus Fis1/Drp1 cytosolic mtDNA | Refusal | Returned passages did not establish both halves of the comparison. |
| Short- versus long-term Activin liver triglycerides | Refusal | The short-term population/diet qualification was missing. |

These four selected failures produced one supported answer and three refusals.
Do not combine them with historical passes to claim a current 16-case score.

## Retrieval diagnosis

A retrieval-only probe ranked ten candidates for each of the 16 development
questions and inspected the three- and six-passage prefixes. The BAT ATP result
was sixth after reranking. Six passages also retained complementary positive and
negative mitochondrial findings across different chunks. The Activin diet
qualification was absent even from the ten-candidate pool; widening the cutoff
alone cannot establish it.

The mitochondrial ranking differed between the initial live reproduction and
later retrieval probes. Two subsequent isolated probes matched each other exactly.
The cause of the earlier difference was not established. The six-passage answer
trial also had different leading mitochondrial passages from the baseline, so
its recovery cannot be attributed solely to widening the cutoff. A separate reranker
process overlapped the initial run; this observation is not proof of a ranking
algorithm defect. Treat timing as diagnostic only: these were sequential
single trials with different context sizes, cache states and machine load, not
repeated controlled latency measurements.

## Six-passage development trial

A separate fresh run retained six of ten reranked candidates without
neighbor expansion. It included the four failures above and all four unanswerable
controls. Every selected case was generated once, including normal built-in
repair. The trial used the explicit cutoff option on the same application commit,
index, models and settings as the reproduction; runtime and corpus snapshots
matched before and after. The trials did not run concurrently with each other.

| Question | Six-passage outcome | Review |
| --- | --- | --- |
| Cited Rosiglitazone publication | Supported answer | Correct external attribution and page-10 quote; required one built-in repair after a verifier requirement exceeded the schema's 200-character limit. |
| Housing temperature and BAT ATP | Supported answer | Approximately twofold increase at both temperatures, supported by the sixth passage, from the page-2 abstract. |
| Mfn1/Mfn2 versus Fis1/Drp1 cytosolic mtDNA | Supported answer | Complementary page-4 evidence in passages one and five establishes both halves. Ranking variation limits causal comparison with the baseline. |
| Short- versus long-term Activin liver triglycerides | Refusal | Safe, but incomplete coverage remains: the short-term chow-fed qualification is missing. |
| Own-study Rosiglitazone dose | Refusal | Appropriate; the cited study does not establish an intervention in this paper. |
| Housing female response | Refusal | Appropriate; the experimental cohort is male. |
| Rab5c inhibitor dose in mice | Refusal | Appropriate; the requested inhibitor experiment is absent. |
| Activin female glucose tolerance | Refusal | Appropriate; the requested population/result is absent. |

An independent AI reviewer inspected final answers, approved quotes, source-index
mappings and attribution. Three of four answerable cases and all four unanswerable
controls passed: seven of eight selected development cases. No unsupported claim
or attribution error was observed in these outputs. This small, previously
inspected selection does not measure general reliability or establish that other
historical successes remain unchanged.

The default for normal verified reranked targeted queries now retains six seeds.
Explicit cutoffs, plain answering, vector-only retrieval, overviews and vector
reserve keep their previous behavior; expanded retrieval already defaults to six.
Fresh evaluation reports record the chosen cutoff, and resumed reports retain
their saved cutoff. The candidate pool remains ten. Grounding, attribution,
quote-matching and question-coverage checks are unchanged. No fallback generation
or neighbor expansion was enabled. Wider context can increase inference cost;
the successful cited-publication answer took approximately 319 seconds with repair,
compared with 131 seconds in the baseline. These single observations are not a
controlled speed comparison.

The [Activin context investigation](activin-context-coverage.md) records the
remaining qualifier gap and retrieval-only follow-up. A
cutoff change cannot recover evidence absent from the candidate pool. The
200-character verifier-format rejection and unresolved ranking variation are
also retained as diagnostics rather than silently discarded.

Local artifact directories are `reviewed-failures-current-20261007T001331297932Z`
(baseline and 16-case retrieval probe) and
`reviewed-six-seed-candidate-20261007T003510854516Z` (eight-case answer trial).
Their `run.json` files record commit, model digests, settings, corpus fingerprints,
complete results, timings and traces. They are diagnostic reports, not the
schema-v3 benchmark runner's scored reports. Original historical artifacts and
the optional human worksheet were preserved.

Raw reports and source passages remain in ignored `evaluation-results/`. This
study does not complete the reserved [final validation](v1-readiness.md).
