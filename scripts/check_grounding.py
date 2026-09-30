"""Live adversarial sanity checks for the claim verifier (not a benchmark)."""

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from time import perf_counter

from pydantic import ValidationError

from app.grounding import (
    GroundedClaim, GroundedDraft, GROUNDING_MODEL, VERIFIER_THINK, VerificationResult,
    build_verifier_evidence, generate_verification_json, grounding_fingerprint,
    validate_verification_structure, verify_draft,
    GROUNDING_SAMPLING, GROUNDING_VERIFIER_TIMEOUT_SECONDS, GROUNDING_OUTPUT_TOKENS,
)
from app.types import ChunkData


REFERENCE = ChunkData(document="synthetic.pdf", page=10, chunk_index=0,
                      section="references", text=(
                          "Smith et al. Treatment delayed weight loss in mice. Journal 2011.\n"
                          "Jones et al. AMPK activity is elevated in cachectic muscle. Journal 2020."
                      ))
DOSE_REFERENCE = ChunkData(document="synthetic.pdf", page=11, chunk_index=0,
                            section="references", text=(
                                "Smith et al. Treatment at 5 mg/kg daily delayed weight loss in mice. Journal 2011."
                            ))
DURATION_REFERENCE = ChunkData(document="synthetic.pdf", page=12, chunk_index=0,
                                section="references", text=(
                                    "Smith et al. Treatment for six weeks delayed weight loss in mice. Journal 2011."
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
    ("supported_requested_dose", "At what dose did treatment delay weight loss in the cited Smith study?", DOSE_REFERENCE,
     "Smith et al. reported that treatment at 5 mg/kg daily delayed weight loss in mice.",
     "external_publication", "Treatment at 5 mg/kg daily delayed weight loss in mice.", True),
    ("title_with_requested_missing_duration", "For how long was treatment given in the cited Smith study?", REFERENCE,
     "The cited title reports that treatment delayed weight loss in mice.",
     "external_publication", "Treatment delayed weight loss in mice.", False),
    ("supported_requested_duration", "For how long was treatment given in the cited Smith study?", DURATION_REFERENCE,
     "Smith et al. reported that treatment for six weeks delayed weight loss in mice.",
     "external_publication", "Treatment for six weeks delayed weight loss in mice.", True),
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

# Paired measurement controls keep the observed analyte and population fixed
# while varying only the answer's requested measurement or target.
TOTAL_AND_REGIONAL_FAT = ChunkData(
    document="synthetic.pdf", page=20, chunk_index=0, section="results", text=(
        "Compared with controls, total fat mass in C26 mice decreased by 35%. "
        "Gonadal and subcutaneous white adipose tissue weights decreased by 24%."
    ),
)
BAT_ACTIVITY = ChunkData(
    document="synthetic.pdf", page=21, chunk_index=0, section="results", text=(
        "At standard temperature, BAT SERCA ATPase activity was 29% lower in "
        "C26 mice than in controls. The figure caption labels a panel BAT ATP concentration."
    ),
)
BAT_ATP_CONCENTRATION = ChunkData(
    document="synthetic.pdf", page=22, chunk_index=0, section="results", text=(
        "At standard temperature, BAT ATP concentration in C26 mice was "
        "4.8 nmol/mg protein, unchanged from controls."
    ),
)

MEASUREMENT_FIXTURES = [
    ("supported_total_fat_mass_35_percent",
     "By what percentage did total fat mass decrease in C26 mice compared with controls?",
     TOTAL_AND_REGIONAL_FAT,
     "Total fat mass in C26 mice decreased by 35% compared with controls.",
     "this_document_authors",
     "Compared with controls, total fat mass in C26 mice decreased by 35%.", True),
    ("unsupported_total_fat_mass_24_percent",
     "By what percentage did total fat mass decrease in C26 mice compared with controls?",
     TOTAL_AND_REGIONAL_FAT,
     "Total fat mass in C26 mice decreased by 24% compared with controls.",
     "this_document_authors",
     "Gonadal and subcutaneous white adipose tissue weights decreased by 24%.", False),
    ("off_target_regional_fat_24_for_total_question",
     "By what percentage did total fat mass decrease in C26 mice compared with controls?",
     TOTAL_AND_REGIONAL_FAT,
     "Gonadal and subcutaneous white adipose tissue weights decreased by 24%.",
     "this_document_authors",
     "Gonadal and subcutaneous white adipose tissue weights decreased by 24%.", False),
    ("unsupported_atp_concentration_from_atpase_activity",
     "How did BAT ATP concentration change in C26 mice at standard temperature compared with controls?",
     BAT_ACTIVITY,
     "BAT ATP concentration was 29% lower in C26 mice than in controls.",
     "this_document_authors",
     "At standard temperature, BAT SERCA ATPase activity was 29% lower in C26 mice than in controls.", False),
    ("off_target_atpase_activity_for_atp_concentration_question",
     "How did BAT ATP concentration change in C26 mice at standard temperature compared with controls?",
     BAT_ACTIVITY,
     "BAT SERCA ATPase activity was 29% lower in C26 mice than in controls.",
     "this_document_authors",
     "At standard temperature, BAT SERCA ATPase activity was 29% lower in C26 mice than in controls.", False),
    ("supported_atpase_activity_29_percent",
     "How did BAT SERCA ATPase activity change in C26 mice at standard temperature compared with controls?",
     BAT_ACTIVITY,
     "BAT SERCA ATPase activity was 29% lower in C26 mice than in controls.",
     "this_document_authors",
     "At standard temperature, BAT SERCA ATPase activity was 29% lower in C26 mice than in controls.", True),
    ("supported_atp_concentration_4_8_nmole",
     "What was the BAT ATP concentration in C26 mice at standard temperature compared with controls?",
     BAT_ATP_CONCENTRATION,
     "BAT ATP concentration was 4.8 nmol/mg protein in C26 mice, unchanged from controls.",
     "this_document_authors",
     "At standard temperature, BAT ATP concentration in C26 mice was 4.8 nmol/mg protein, unchanged from controls.", True),
]

GTT_METHODS = ChunkData(
    document="synthetic.pdf", page=23, chunk_index=0, section="methods", text=(
        "Mice were fasted for six hours. Glucose was measured at 0, 15 and 30 minutes."
    ),
)
CITED_TITLE_REFERENCE = ChunkData(
    document="synthetic.pdf", page=24, chunk_index=0, section="references", text=(
        "Smith AB and Jones CD (2024). Treatment delayed weight loss and anorexia in mice."
    ),
)

@dataclass(frozen=True)
class ControlFixture:
    identifier: str
    question: str
    source: ChunkData
    claims: tuple[tuple[str, str, str], ...]
    expected: bool


MULTI_CLAIM_FIXTURES = [
    ControlFixture(
        "supported_multiclaim_gtt_methods",
        "How long were the mice fasted and when was glucose measured?",
        GTT_METHODS,
        (
            ("Mice were fasted for six hours.",
             "this_document_authors", "Mice were fasted for six hours."),
            ("Glucose was measured at 0, 15 and 30 minutes.",
             "this_document_authors", "Glucose was measured at 0, 15 and 30 minutes."),
        ),
        True,
    ),
    ControlFixture(
        "supported_multiclaim_cited_title",
        "Who authored the cited Smith study and when, and what effect does its title describe?",
        CITED_TITLE_REFERENCE,
        (
            ("The cited external publication is by Smith AB and Jones CD and dates to 2024.",
             "external_publication", "Smith AB and Jones CD (2024)."),
            ("Its title reports that treatment delayed weight loss and anorexia in mice.",
             "external_publication", "Treatment delayed weight loss and anorexia in mice."),
        ),
        True,
    ),
]


def all_control_fixtures() -> list[ControlFixture]:
    """Normalize legacy one-claim tuples and new controls without changing FIXTURES."""
    controls = [
        ControlFixture(identifier, question, source, ((text, attribution, quote),), expected)
        for identifier, question, source, text, attribution, quote, expected
        in (*FIXTURES, *MEASUREMENT_FIXTURES)
    ]
    return [*controls, *MULTI_CLAIM_FIXTURES]


def select_control_fixtures(case_ids: list[str] | None) -> list[ControlFixture]:
    """Apply CLI case filtering consistently across legacy and added controls."""
    return [fixture for fixture in all_control_fixtures()
            if case_ids is None or fixture.identifier in case_ids]


def draft_for_fixture(fixture: ControlFixture) -> GroundedDraft:
    """Create the positive-evidence draft submitted for one control case."""
    return GroundedDraft.model_validate({
        "answerable": True,
        "claims": [{
            "text": text,
            "attribution": attribution,
            "citations": [{"source_id": 1, "quote": quote}],
        } for text, attribution, quote in fixture.claims],
    })

# This one control is intentionally rejected by deterministic validation because
# a current-study claim cites a reference entry. All others test the verifier.
DETERMINISTIC_CONTROLS = frozenset({"reference_as_current_study"})


def complete_verifier_verdict(
    question: str, outputs: list[dict[str, object]], claims: list[GroundedClaim], sources: list[ChunkData],
) -> bool:
    """Require a schema- and evidence-valid complete semantic verdict."""
    if len(outputs) != 1:
        return False
    try:
        result = VerificationResult.model_validate(outputs[0])
        validate_verification_structure(question, result, claims, sources)
    except (ValidationError, TypeError, ValueError):
        return False
    indexes = [verdict.claim_index for verdict in result.verdicts]
    return len(indexes) == len(claims) and set(indexes) == set(range(1, len(claims) + 1))


def control_passed(identifier: str, expected: bool, accepted: bool, verifier_verdict_complete: bool) -> bool:
    return accepted == expected and (identifier in DETERMINISTIC_CONTROLS or verifier_verdict_complete)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--case", dest="case_ids", action="append",
                        help="run just this control (repeat to select more)")
    args = parser.parse_args()
    fixtures = select_control_fixtures(args.case_ids)
    if not fixtures or (args.case_ids and set(args.case_ids) != {fixture.identifier for fixture in fixtures}):
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
        for fixture in fixtures:
            identifier = fixture.identifier
            question = fixture.question
            sources = [fixture.source]
            draft = draft_for_fixture(fixture)
            outputs: list[dict[str, object]] = []
            verifier_evidence = build_verifier_evidence(draft.claims, sources)

            def record(prompt: str, schema: dict[str, object]) -> dict[str, object]:
                response = generate_verification_json(prompt, schema)
                outputs.append(response)
                return response

            start = perf_counter()
            accepted = verify_draft(question, draft, sources, verifier=record)
            verdict_complete = complete_verifier_verdict(question, outputs, draft.claims, sources)
            passed = control_passed(identifier, fixture.expected, accepted, verdict_complete)
            results.append({"id": identifier, "expected": fixture.expected, "accepted": accepted,
                            "passed": passed, "verifier_called": bool(outputs),
                            "verifier_verdict_complete": verdict_complete, "question": question,
                            "draft": draft.model_dump(), "sources": sources,
                            "verifier_evidence": verifier_evidence,
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
