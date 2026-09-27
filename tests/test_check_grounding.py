import unittest

from scripts.check_grounding import control_passed


class GroundingControlTests(unittest.TestCase):
    def test_population_control_must_reach_semantic_verifier(self) -> None:
        self.assertFalse(control_passed("unsupported_shared_population", False, False, False))
        self.assertTrue(control_passed("unsupported_shared_population", False, False, True))
        self.assertTrue(control_passed("supported_shared_population", True, True, True))

    def test_existing_deterministic_controls_can_reject_before_verifier(self) -> None:
        self.assertTrue(control_passed("reference_as_current_study", False, False, False))
