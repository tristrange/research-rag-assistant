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
        "requirements": [{"requirement": "Requested finding", "supported": True,
                          "reason": "The passage answers the question."}],
        "answers_question": True, "reason": "The passage supports the answer.",
        "verdicts": [{"claim_index": 1, "supported": True, "correct_attribution": True,
                      "relevant": True, "reason": "The passage supports the claim.",
                      "supporting_evidence_ids": [1]}],
        "requested_answer": {"status": "supported", "question_excerpt": QUESTION,
                             "supporting_evidence_ids": [1], "reason": "The passage answers the question."},
    }


class GroundingControlTests(unittest.TestCase):
    def test_every_non_deterministic_control_requires_valid_complete_verdict(self) -> None:
        self.assertEqual(DETERMINISTIC_CONTROLS, {"reference_as_current_study"})
        for fixture in FIXTURES:
            identifier, expected = fixture[0], bool(fixture[-1])
            if identifier in DETERMINISTIC_CONTROLS:
                continue
            with self.subTest(identifier=identifier):
                self.assertFalse(control_passed(identifier, expected, expected, False))
                self.assertTrue(control_passed(identifier, expected, expected, True))
        self.assertTrue(control_passed("reference_as_current_study", False, False, False))

    def test_complete_verdict_requires_full_question_claim_verdict_and_valid_evidence(self) -> None:
        self.assertTrue(complete_verifier_verdict(QUESTION, [valid_verdict()], [CLAIM], [RESULT]))
        for field in ["requested_answer", "requirements"]:
            missing = valid_verdict()
            del missing[field]
            with self.subTest(field=field):
                self.assertFalse(complete_verifier_verdict(QUESTION, [missing], [CLAIM], [RESULT]))
        narrowed = valid_verdict()
        narrowed["requested_answer"]["question_excerpt"] = "mass"
        self.assertFalse(complete_verifier_verdict(QUESTION, [narrowed], [CLAIM], [RESULT]))
        obsolete = valid_verdict()
        obsolete["question_coverage"] = {"species": "not_requested"}
        self.assertFalse(complete_verifier_verdict(QUESTION, [obsolete], [CLAIM], [RESULT]))
        for ids in [[], [99], [1, 1]]:
            for field in ["requested_answer", "claim"]:
                malformed = valid_verdict()
                pointer = malformed["requested_answer"] if field == "requested_answer" else malformed["verdicts"][0]
                pointer["supporting_evidence_ids"] = ids
                with self.subTest(ids=ids, field=field):
                    self.assertFalse(complete_verifier_verdict(QUESTION, [malformed], [CLAIM], [RESULT]))
        self.assertFalse(complete_verifier_verdict(QUESTION, [], [CLAIM], [RESULT]))
        self.assertFalse(complete_verifier_verdict(QUESTION, [valid_verdict(), valid_verdict()], [CLAIM], [RESULT]))

    def test_proper_unsupported_verdict_can_be_complete_without_being_accepted(self) -> None:
        verdict = valid_verdict()
        verdict["requirements"][0]["supported"] = False
        verdict["requested_answer"].update(status="unsupported", supporting_evidence_ids=[])
        verdict["answers_question"] = False
        verdict["verdicts"][0].update(supported=False, supporting_evidence_ids=[])
        self.assertTrue(complete_verifier_verdict(QUESTION, [verdict], [CLAIM], [RESULT]))
        self.assertTrue(control_passed("unsupported_requested_population", False, False, True))
        for ids in [[99], [1, 1]]:
            verdict["requested_answer"]["supporting_evidence_ids"] = ids
            with self.subTest(ids=ids):
                self.assertFalse(complete_verifier_verdict(QUESTION, [verdict], [CLAIM], [RESULT]))

    def test_requested_dose_and_duration_have_supported_and_missing_controls(self) -> None:
        identifiers = {fixture[0] for fixture in FIXTURES}
        self.assertTrue({"supported_requested_dose", "title_with_requested_missing_dose",
                         "supported_requested_duration", "title_with_requested_missing_duration"}
                        <= identifiers)
