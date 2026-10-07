from typing import Any
import unittest

from app.grounding import GroundedClaim, _validate_draft, build_verifier_evidence
from scripts.check_grounding import (
    DETERMINISTIC_CONTROLS, FIXTURES, MEASUREMENT_FIXTURES, MULTI_CLAIM_FIXTURES,
    RESULT, all_control_fixtures, complete_verifier_verdict, control_passed,
    draft_for_fixture, select_control_fixtures,
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
                          "reason": "The passage answers the question.", "supporting_evidence_ids": [1]}],
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
        for fixture in all_control_fixtures():
            identifier, expected = fixture.identifier, fixture.expected
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
            for field in ["requested_answer", "claim", "requirement"]:
                malformed = valid_verdict()
                pointer = (malformed["requested_answer"] if field == "requested_answer"
                           else malformed["requirements"][0] if field == "requirement"
                           else malformed["verdicts"][0])
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

    def test_measurement_controls_pair_requested_targets_and_expected_outcomes(self) -> None:
        controls = {fixture.identifier: fixture for fixture in all_control_fixtures()}
        expected = {
            "supported_total_fat_mass_35_percent": True,
            "unsupported_total_fat_mass_24_percent": False,
            "off_target_regional_fat_24_for_total_question": False,
            "unsupported_atp_concentration_from_atpase_activity": False,
            "off_target_atpase_activity_for_atp_concentration_question": False,
            "supported_atpase_activity_29_percent": True,
            "supported_atp_concentration_4_8_nmole": True,
        }
        self.assertEqual(len(MEASUREMENT_FIXTURES), len(expected))
        for identifier, should_accept in expected.items():
            with self.subTest(identifier=identifier):
                self.assertEqual(controls[identifier].expected, should_accept)
        self.assertIn("35%", controls["supported_total_fat_mass_35_percent"].claims[0][0])
        self.assertIn("24%", controls["off_target_regional_fat_24_for_total_question"].claims[0][0])
        self.assertIn("ATPase activity", controls["supported_atpase_activity_29_percent"].claims[0][0])
        self.assertIn("ATP concentration", controls["supported_atp_concentration_4_8_nmole"].claims[0][0])

    def test_multiclaim_controls_dedupe_shared_evidence_and_require_each_verdict(self) -> None:
        self.assertEqual(len(MULTI_CLAIM_FIXTURES), 2)
        for fixture in MULTI_CLAIM_FIXTURES:
            with self.subTest(identifier=fixture.identifier):
                self.assertEqual(fixture.expected, True)
                self.assertEqual(len(fixture.claims), 2)
                self.assertEqual(
                    [selected.identifier for selected in select_control_fixtures([fixture.identifier])],
                    [fixture.identifier],
                )
                draft = draft_for_fixture(fixture)
                claims = draft.claims
                self.assertEqual(len(claims), 2)
                evidence = build_verifier_evidence(claims, [fixture.source])
                self.assertGreaterEqual(len(evidence), 2)
                evidence_ids_by_quote = {entry["quote"]: entry["evidence_id"] for entry in evidence}
                self.assertEqual(len(evidence_ids_by_quote), len(evidence))
                for entry in evidence:
                    self.assertEqual(entry["claim_indexes"], [1, 2])
                claim_evidence_ids = [
                    evidence_ids_by_quote[claim_fixture[2]] for claim_fixture in fixture.claims
                ]

                verdict = valid_verdict()
                verdict["requested_answer"]["question_excerpt"] = fixture.question
                verdict["requested_answer"]["supporting_evidence_ids"] = claim_evidence_ids
                verdict["verdicts"] = [
                    {"claim_index": index, "supported": True, "correct_attribution": True,
                     "relevant": True, "reason": "Shared passage supports this claim.",
                     "supporting_evidence_ids": [claim_evidence_ids[index - 1]]}
                    for index in (1, 2)
                ]
                self.assertTrue(complete_verifier_verdict(fixture.question, [verdict], claims, [fixture.source]))

                missing_claim_verdict = valid_verdict()
                missing_claim_verdict["requested_answer"]["question_excerpt"] = fixture.question
                missing_claim_verdict["requested_answer"]["supporting_evidence_ids"] = claim_evidence_ids
                missing_claim_verdict["verdicts"] = verdict["verdicts"][:1]
                self.assertFalse(
                    complete_verifier_verdict(fixture.question, [missing_claim_verdict], claims, [fixture.source])
                )

    def test_all_control_ids_are_unique_and_legacy_fixture_tuples_are_preserved(self) -> None:
        controls = all_control_fixtures()
        identifiers = [fixture.identifier for fixture in controls]
        self.assertEqual(len(identifiers), len(set(identifiers)))
        self.assertEqual(len(FIXTURES), 21)
        self.assertEqual(len(controls), 30)
        self.assertTrue(all(isinstance(fixture, tuple) and len(fixture) == 7 for fixture in FIXTURES))

    def test_all_verifier_fixtures_use_exact_source_quotes(self) -> None:
        for fixture in all_control_fixtures():
            if fixture.identifier in DETERMINISTIC_CONTROLS:
                continue
            with self.subTest(identifier=fixture.identifier):
                _validate_draft(draft_for_fixture(fixture), [fixture.source])
