"""Live adversarial sanity checks for the claim verifier (not a benchmark)."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from time import perf_counter

from pydantic import ValidationError

from app.grounding import (
    GroundedDraft, GROUNDING_MODEL, VERIFIER_THINK, VerificationResult,
    generate_verification_json, grounding_fingerprint, verify_draft,
    GROUNDING_SAMPLING, GROUNDING_VERIFIER_TIMEOUT_SECONDS, GROUNDING_OUTPUT_TOKENS,
)
from app.types import ChunkData


REFERENCE = ChunkData(document="synthetic.pdf", page=10, chunk_index=0,
                      section="references", text=(
                          "Smith et al. Treatment delayed weight loss in mice. Journal 2011.\n"
                          "Jones et al. AMPK activity is elevated in cachectic muscle. Journal 2020."
                      ))
RESULT = ChunkData(document="synthetic.pdf", page=6, chunk_index=0,
                   section="results", text="In our experiments, mice lost 1.2 g after three days of food restriction.")

POPULATION = ChunkData(document="synthetic.pdf", page=3, chunk_index=0,
                       section="results", text="We studied male mice. Glucose uptake increased by 80%.")

NEGATIVE_RESULT = ChunkData(document="synthetic.pdf", page=4, chunk_index=0,
                            section="results", text="In our experiment, treatment left the measured response unchanged compared with controls.")
MISSING_RESULT = ChunkData(document="synthetic.pdf", page=4, chunk_index=0,
                           section="methods", text="In our experiment, we measured the response after treatment.")
MIXED_DIET_RESULTS = ChunkData(document="synthetic.pdf", page=5, chunk_index=0,
                               section="results", text=(
                                   "After short-term treatment, liver triacylglycerol increased "
                                   "2.8-fold in mice; after long-term treatment, it increased "
                                   "2.6-fold in chow-fed mice."
                               ))
CHOW_DIET_RESULTS = ChunkData(document="synthetic.pdf", page=5, chunk_index=0,
                              section="results", text=(
                                  "After short-term treatment, liver triacylglycerol increased "
                                  "2.8-fold in chow-fed mice; after long-term treatment, it "
                                  "increased 2.6-fold in chow-fed mice."
                              ))

# Fixed drafts deliberately include cases a generator should never emit.
# Expected answers are not sent to the verifier.
FIXTURES = [
    ("supported_current_study", "How much mass did the mice lose?", RESULT,
     "The authors found a loss of 1.2 g after three days of food restriction.",
     "this_document_authors", RESULT["text"], True),
    ("current_study_mislabelled_as_cited", "How much mass did the mice lose?", RESULT,
     "The authors found a loss of 1.2 g after three days of food restriction.",
     "external_publication", RESULT["text"], False),
    ("supported_requested_population", "How did glucose uptake change in male mice?", POPULATION,
     "Glucose uptake increased by 80%.",
     "this_document_authors", "Glucose uptake increased by 80%.", True),
    ("unsupported_requested_population", "How did glucose uptake change in female mice?", POPULATION,
     "Glucose uptake increased by 80%.",
     "this_document_authors", "Glucose uptake increased by 80%.", False),
    ("unsupported_requested_duration", "How much mass was lost after six weeks of food restriction?", RESULT,
     "Mice lost 1.2 g after food restriction.",
     "this_document_authors", RESULT["text"], False),
    ("wrong_number", "How much mass did the mice lose?", RESULT,
     "The authors found a loss of 12 g after three days of food restriction.",
     "this_document_authors", RESULT["text"], False),
    ("supported_cited_work", "What did the cited Smith study report?", REFERENCE,
     "Smith et al. reported that treatment delayed weight loss in mice.",
     "external_publication", "Treatment delayed weight loss in mice.", True),
    ("title_without_unasked_dimensions", "What effect does the cited Smith publication title describe?", REFERENCE,
     "The cited title reports that treatment delayed weight loss in mice.",
     "external_publication", "Treatment delayed weight loss in mice.", True),
    ("title_with_requested_missing_dose", "At what dose did treatment delay weight loss in the cited Smith study?", REFERENCE,
     "The cited title reports that treatment delayed weight loss in mice.",
     "external_publication", "Treatment delayed weight loss in mice.", False),
    ("supported_negative_answer", "Did treatment lower the measured response compared with controls?", NEGATIVE_RESULT,
     "Treatment did not lower the measured response compared with controls.",
     "this_document_authors", NEGATIVE_RESULT["text"], True),
    ("unsupported_negative_answer", "Did treatment lower the measured response compared with controls?", MISSING_RESULT,
     "Treatment did not lower the measured response compared with controls.",
     "this_document_authors", MISSING_RESULT["text"], False),
    ("unsupported_shared_population", "How did liver triacylglycerol change after short-term versus long-term treatment in chow-fed mice?",
     MIXED_DIET_RESULTS,
     "Liver triacylglycerol increased 2.8-fold after short-term and 2.6-fold after long-term treatment in chow-fed mice.",
     "this_document_authors", MIXED_DIET_RESULTS["text"], False),
    ("supported_shared_population", "How did liver triacylglycerol change after short-term versus long-term treatment in chow-fed mice?",
     CHOW_DIET_RESULTS,
     "Liver triacylglycerol increased 2.8-fold after short-term and 2.6-fold after long-term treatment in chow-fed mice.",
     "this_document_authors", CHOW_DIET_RESULTS["text"], True),
    ("reference_as_current_study", "What did this paper find about AMPK?", REFERENCE,
     "The current paper found that AMPK activity is elevated in cachectic muscle.",
     "this_document_authors", "AMPK activity is elevated in cachectic muscle.", False),
    ("mislabelled_attribution", "What did this paper find about AMPK?", REFERENCE,
     "The current paper found that AMPK activity is elevated in cachectic muscle.",
     "non_study_context", "AMPK activity is elevated in cachectic muscle.", False),
    ("unsupported_embellishment", "What did the cited Smith study report?", REFERENCE,
     "Smith et al. found that treatment, a PPARgamma agonist, delayed weight loss in mice.",
     "external_publication", "Treatment delayed weight loss in mice.", False),
    ("mixed_attribution", "What did the cited Smith study report?", REFERENCE,
     "Smith et al. found delayed weight loss; the current paper found elevated AMPK activity.",
     "external_publication", "Treatment delayed weight loss in mice.", False),
    ("missing_comparison", "Which treatment was most effective in this paper's experiments?", REFERENCE,
     "Smith et al. reported that treatment delayed weight loss in mice.",
     "external_publication", "Treatment delayed weight loss in mice.", False),
]

# These paired controls test semantic qualification, not deterministic quote
# validation. A rejected draft is not a passing negative unless the verifier ran.
SEMANTIC_CONTROLS = frozenset({"unsupported_shared_population", "supported_shared_population"})


def complete_verifier_verdict(outputs: list[dict[str, object]], claim_count: int) -> bool:
    """Require one schema-valid verdict covering every draft claim."""
    if len(outputs) != 1:
        return False
    try:
        result = VerificationResult.model_validate(outputs[0])
    except ValidationError:
        return False
    indexes = [verdict.claim_index for verdict in result.verdicts]
    return len(indexes) == claim_count and set(indexes) == set(range(1, claim_count + 1))


def control_passed(identifier: str, expected: bool, accepted: bool, verifier_verdict_complete: bool) -> bool:
    return accepted == expected and (identifier not in SEMANTIC_CONTROLS or verifier_verdict_complete)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--case", dest="case_ids", action="append",
                        help="run just this control (repeat to select more)")
    args = parser.parse_args()
    fixtures = [fixture for fixture in FIXTURES if args.case_ids is None or fixture[0] in args.case_ids]
    if not fixtures or (args.case_ids and set(args.case_ids) != {fixture[0] for fixture in fixtures}):
        parser.error("Selected control IDs must exist")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Reserve first; preserve each completed check even if a model call fails later.
    with args.output.open("x"):
        pass
    report: dict[str, object] = {
        "started_at": datetime.now(timezone.utc).isoformat(), "status": "running",
        "model": GROUNDING_MODEL, "temperature": GROUNDING_SAMPLING.temperature, "think": VERIFIER_THINK,
        "sampling": GROUNDING_SAMPLING.options(), "timeout_seconds": GROUNDING_VERIFIER_TIMEOUT_SECONDS,
        "output_tokens": GROUNDING_OUTPUT_TOKENS,
        "grounding_sha256": grounding_fingerprint(), "results": [],
        "methodology": f"{len(fixtures)} assistant-authored synthetic controls, one run each; not proof of verifier accuracy.",
    }
    results: list[dict[str, object]] = []
    try:
        for identifier, question, source, text, attribution, quote, expected in fixtures:
            draft = GroundedDraft.model_validate({"answerable": True, "claims": [{
                "text": text, "attribution": attribution,
                "citations": [{"source_id": 1, "quote": quote}],
            }]})
            outputs: list[dict[str, object]] = []

            def record(prompt: str, schema: dict[str, object]) -> dict[str, object]:
                response = generate_verification_json(prompt, schema)
                outputs.append(response)
                return response

            start = perf_counter()
            accepted = verify_draft(question, draft, [source], verifier=record)
            verdict_complete = complete_verifier_verdict(outputs, len(draft.claims))
            passed = control_passed(identifier, expected, accepted, verdict_complete)
            results.append({"id": identifier, "expected": expected, "accepted": accepted,
                            "passed": passed, "verifier_called": bool(outputs),
                            "verifier_verdict_complete": verdict_complete, "question": question,
                            "draft": draft.model_dump(), "sources": [source],
                            "verifier_outputs": outputs, "elapsed_ms": (perf_counter()-start)*1000})
            report["results"] = results
            args.output.write_text(json.dumps(report, indent=2) + "\n")
            print(f"{'PASS' if passed else 'FAIL'} {identifier}: accepted={accepted}", flush=True)
        report["status"] = "complete"
        report["passed"] = all(result["passed"] for result in results)
    except (Exception, KeyboardInterrupt) as error:
        report["status"] = "failed"
        report["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        args.output.write_text(json.dumps(report, indent=2) + "\n")
    if not report["passed"]:
        raise SystemExit("One or more grounding controls failed")


if __name__ == "__main__":
    main()
