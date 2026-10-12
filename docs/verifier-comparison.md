# Bounded verifier comparison

This development experiment asks whether repeated semantic verification adds useful
safety or instead prevents supported answers. It keeps GPT-OSS 20B and v40's
inference settings, initial drafting and single repair unchanged. No application
behavior changes in this research spike.

First, both verifier arms assess the same eight synthetic fixed drafts: four
supported answers and four unsupported variants covering linked experimental
context, measurement identity, negative results versus absent measurements, and
study attribution. Then both pipelines answer the same eight inspected r3
questions with exactly the six passages previously retrieved for each question.
Each case alternates which arm runs first. Every arm/case runs once.

The current arm uses the full-context verifier, deterministic validation and
isolated final-excerpt proof. The experimental arm selects evidence and judges
support, attribution, relevance and whole-question coverage in one call. It
projects that result into the existing citation-binding, identifier and duration
validators. It removes model-generated requirement decomposition, question echo
and the second semantic proof; it therefore cannot be assumed equally safe.
Both arms use the existing draft/repair prompts and model budgets.

The candidate and inputs are frozen before generation. Local raw reports contain
requests, responses, traces, timings and artifact hashes; paper excerpts remain
ignored. The experiment admits at most 72 chat calls and starts no additional
call after 60 minutes. An in-flight call can finish after that limit. Existing
300-second per-call timeouts remain unchanged. Failures are retained, without
retuning or selective retries. A budget stop makes the comparison incomplete.

A candidate has no promotion signal if it accepts any unsupported calibration
draft, answers either unanswerable replay, or separate source review finds a
material unsupported displayed claim or attribution error. A useful development
signal also requires at least two additional complete supported answers among
the six answerable replays. Latency and model/schema errors are reported separately.
Passing this small, inspected set would justify further work, not release approval
or general safety. Fresh questions would still be required after a product change.

Question inputs come from the preserved check in [PR #76](https://github.com/tristrange/research-rag-assistant/pull/76).
The replay performs no retrieval, embedding or database operation; it does not
measure end-to-end latency or new-question accuracy. Synthetic calibration is a
small diagnostic and cannot certify a verifier. Generation is stochastic and the
single replicate cannot establish a reliable performance difference.
