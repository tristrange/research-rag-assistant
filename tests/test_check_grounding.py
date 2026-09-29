from typing import Any
import unittest

from app.grounding import GroundedClaim
from scripts.check_grounding import (
    DETERMINISTIC_CONTROLS, FIXTURES, RESULT, complete_verifier_verdict, control_passed,
)


QUESTION = "How much mass did the mice lose?"
CLAIM = GroundedClaim.model_validate({
    "text": "The authors found a loss of 1.2 g after three days of food restriction.",
    "attribution": "this_document_authors",
    "citations": [{"source_id": 1, "quote": RESULT["text"]}],
})


def valid_verdict() -> dict[str, Any]:
    return {
        "question_coverage": {
            "requested_answer": {"status": "supported", "question_excerpt": QUESTION,
                                 "supporting_evidence_ids": [1], "reason": "The passage answers the question."},
            "document_or_study": "not_requested", "population": "not_requested",
            "sex": "not_requested", "species": "not_requested",
            "intervention": "not_requested", "dose": "not_requested",
            "comparison": "not_requested", "time_period": "not_requested",
            "other_explicit_qualifier": "not_requested",
        },
        "answers_question": True, "reason": "The passage supports the answer.",
        "verdicts": [{"claim_index": 1, "supported": True, "correct_attribution": True,
                      "relevant": True, "supporting_evidence_ids": [1],
                      "reason": "The passage supports the claim."}],
    }


class GroundingControlTests(unittest.TestCase):
    def test_every_non_deterministic_control_requires_valid_complete_verdict(self) -> None:
        identifiers = {fixture[0] for fixture in FIXTURES}
        self.assertEqual(DETERMINISTIC_CONTROLS, {"reference_as_current_study"})
        for fixture in FIXTURES:
            identifier, expected = fixture[0], bool(fixture[-1])
            if identifier in DETERMINISTIC_CONTROLS:
                continue
            with self.subTest(identifier=identifier):
                self.assertFalse(control_passed(identifier, expected, expected, False))
                self.assertTrue(control_passed(identifier, expected, expected, True))
        self.assertIn("reference_as_current_study", DETERMINISTIC_CONTROLS)
        self.assertTrue(control_passed("reference_as_current_study", False, False, False))

    def test_complete_verdict_requires_question_coverage_claim_verdict_and_valid_evidence(self) -> None:
        self.assertTrue(complete_verifier_verdict(QUESTION, [valid_verdict()], [CLAIM], [RESULT]))

        missing_dose = valid_verdict()
        del missing_dose["question_coverage"]["dose"]
        self.assertFalse(complete_verifier_verdict(QUESTION, [missing_dose], [CLAIM], [RESULT]))

        obsolete_unrequested_object = valid_verdict()
        obsolete_unrequested_object["question_coverage"]["dose"] = {
            "status": "not_requested", "question_excerpt": None,
            "supporting_evidence_ids": [], "reason": "Not requested.",
        }
        self.assertFalse(complete_verifier_verdict(
            QUESTION, [obsolete_unrequested_object], [CLAIM], [RESULT],
        ))

        missing_claim_evidence = valid_verdict()
        missing_claim_evidence["verdicts"][0]["supporting_evidence_ids"] = []
        self.assertFalse(complete_verifier_verdict(QUESTION, [missing_claim_evidence], [CLAIM], [RESULT]))

        bad_evidence_id = valid_verdict()
        bad_evidence_id["question_coverage"]["requested_answer"]["supporting_evidence_ids"] = [99]
        self.assertFalse(complete_verifier_verdict(QUESTION, [bad_evidence_id], [CLAIM], [RESULT]))

        self.assertFalse(complete_verifier_verdict(QUESTION, [], [CLAIM], [RESULT]))
        self.assertFalse(complete_verifier_verdict(QUESTION, [valid_verdict(), valid_verdict()], [CLAIM], [RESULT]))

    def test_proper_unsupported_verdict_can_be_complete_without_being_accepted(self) -> None:
        verdict = valid_verdict()
        coverage = verdict["question_coverage"]
        coverage["requested_answer"].update(
            status="unsupported", supporting_evidence_ids=[],
        )
        verdict["answers_question"] = False
        verdict["verdicts"][0].update(
            supported=False, supporting_evidence_ids=[],
        )
        self.assertTrue(complete_verifier_verdict(QUESTION, [verdict], [CLAIM], [RESULT]))
        self.assertTrue(control_passed("unsupported_requested_population", False, False, True))

    def test_requested_dose_and_duration_have_supported_and_missing_controls(self) -> None:
        identifiers = {fixture[0] for fixture in FIXTURES}
        self.assertTrue({"supported_requested_dose", "title_with_requested_missing_dose",
                         "supported_requested_duration", "title_with_requested_missing_duration"}
                        <= identifiers)
