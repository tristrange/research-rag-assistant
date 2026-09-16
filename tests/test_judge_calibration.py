import json
import unittest

from pydantic import ValidationError

from app.judge_calibration import FIXTURES, run_calibration


def good_judge(prompt: str, schema: dict[str, object]) -> dict[str, object]:
    data = json.loads(prompt.split("Evaluation data (JSON):\n", 1)[1])
    fixture = next(item for item in FIXTURES if item.id == data["case"]["id"])
    scores: dict[str, object] = {"correctness": 2, "completeness": 2, "citation_support": 2,
                                 "abstained": False, "explanation": "Fixture graded."}
    scores.update({field: value if isinstance(value, bool) else value[0]
                   for field, value in fixture.expected.items()})
    return scores


class JudgeCalibrationTests(unittest.TestCase):
    def test_known_expected_scores_pass_without_exposing_them_in_prompt(self) -> None:
        def judge(prompt: str, schema: dict[str, object]) -> dict[str, object]:
            data = json.loads(prompt.split("Evaluation data (JSON):\n", 1)[1])
            self.assertEqual(set(data), {"case", "answer", "sources"})
            self.assertNotIn("expected", data["case"])
            return good_judge(prompt, schema)

        report = run_calibration(judge)
        self.assertTrue(report["passed"])
        self.assertEqual(len(report["results"]), 6)

    def test_reference_leaking_judge_fails_missing_number_and_support(self) -> None:
        def judge(prompt: str, schema: dict[str, object]) -> dict[str, object]:
            return {"correctness": 2, "completeness": 2, "citation_support": 2,
                    "abstained": False, "explanation": "Credited reference instead of answer."}

        report = run_calibration(judge)
        self.assertFalse(report["passed"])
        failed = {result["id"] for result in report["results"] if not result["passed"]}
        self.assertTrue({"missing_number", "contradictory_answer", "unsupported_answer",
                         "answerable_refusal", "unanswerable_refusal"} <= failed)

    def test_always_low_scores_do_not_pass(self) -> None:
        report = run_calibration(lambda prompt, schema: {
            "correctness": 0, "completeness": 0, "citation_support": 0,
            "abstained": True, "explanation": "Always reject.",
        })
        self.assertFalse(report["passed"])
        self.assertFalse(report["results"][0]["passed"])

    def test_schema_and_transport_errors_are_not_reported_as_passes(self) -> None:
        with self.assertRaises(ValidationError):
            run_calibration(lambda prompt, schema: {"correctness": "2"})

        def offline(prompt: str, schema: dict[str, object]) -> dict[str, object]:
            raise TimeoutError("judge unavailable")

        with self.assertRaisesRegex(TimeoutError, "judge unavailable"):
            run_calibration(offline)


if __name__ == "__main__":
    unittest.main()
