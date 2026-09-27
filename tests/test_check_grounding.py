import unittest

from scripts.check_grounding import complete_verifier_verdict, control_passed


CLAIM_REJECTION: dict[str, object] = {
    "claim_index": 1, "supported": False,
    "correct_attribution": True, "relevant": True,
    "reason": "The cited result omits the population.",
}

VALID_REJECTION: dict[str, object] = {
    "requirements": [{"requirement": "population", "supported": False,
                      "reason": "The source does not identify the short-term population."}],
    "answers_question": False,
    "reason": "The claim exceeds its cited evidence.",
    "verdicts": [CLAIM_REJECTION],
}


class GroundingControlTests(unittest.TestCase):
    def test_population_control_requires_complete_semantic_verdict(self) -> None:
        self.assertFalse(control_passed("unsupported_shared_population", False, False, False))
        self.assertTrue(control_passed("unsupported_shared_population", False, False, True))
        self.assertTrue(control_passed("supported_shared_population", True, True, True))

    def test_malformed_or_incomplete_verifier_response_cannot_pass(self) -> None:
        self.assertFalse(complete_verifier_verdict([], 1))
        self.assertFalse(complete_verifier_verdict([{"answers_question": False}], 1))
        self.assertFalse(complete_verifier_verdict([{**VALID_REJECTION, "verdicts": []}], 1))
        self.assertFalse(complete_verifier_verdict([{**VALID_REJECTION, "verdicts": [
            {**CLAIM_REJECTION, "claim_index": 2},
        ]}], 1))
        self.assertTrue(complete_verifier_verdict([VALID_REJECTION], 1))

    def test_existing_deterministic_controls_can_reject_before_verifier(self) -> None:
        self.assertTrue(control_passed("reference_as_current_study", False, False, False))
