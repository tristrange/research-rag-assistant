import json
import unittest
from unittest.mock import Mock, patch

from pydantic import ValidationError

from app.answer_evaluation import (
    AnswerEvaluationCase,
    EXACT_REFUSALS,
    evaluate_case,
    evidence_found,
    normalize,
    judge_prompt,
    summarize,
)
from app.grounding import INSUFFICIENT_EVIDENCE
from app.types import AnswerResult, ChunkData


def case(*, answerable: bool = True) -> AnswerEvaluationCase:
    return {
        "id": "case",
        "question": "What happened?",
        "answerable": answerable,
        "reference_answer": "The response increased.",
        "evidence": ([{"document": "paper.pdf", "page": 2,
                       "quote": "response increased"}] if answerable else []),
    }


def result(answer: str = "The response increased.") -> AnswerResult:
    return {
        "answer": answer,
        "sources": [ChunkData(document="paper.pdf", page=2, chunk_index=1,
                              text="The re-\nsponse increased after treatment.")],
    }


def judge(prompt: str, schema: dict[str, object]) -> dict[str, object]:
    if schema.get("title") == "AbstentionDecision":
        return {"abstained": False, "explanation": "Substantive answer."}
    return {"correctness": 2, "completeness": 2, "citation_support": 2,
            "abstained": False,
            "explanation": "The answer matches the reference and evidence."}


def abstention_judge(prompt: str, schema: dict[str, object]) -> dict[str, object]:
    return {**judge(prompt, schema), "abstained": True}


class AnswerEvaluationTests(unittest.TestCase):
    def test_normalize_repairs_pdf_line_wraps(self) -> None:
        self.assertEqual(normalize("The re-\nsponse  increased"), "the response increased")

    def test_evidence_requires_quote_document_and_page(self) -> None:
        label = case()["evidence"][0]
        self.assertTrue(evidence_found(label, result()["sources"]))
        wrong_page = [ChunkData(document="paper.pdf", page=3, chunk_index=1,
                                text="The response increased")]
        self.assertFalse(evidence_found(label, wrong_page))

    def test_abstention_uses_judgement_of_the_whole_answer(self) -> None:
        evaluated = evaluate_case(case(answerable=False),
                                 lambda question: result("The context does not provide this, but it was 30%."),
                                 judge)
        self.assertFalse(evaluated["abstained"])
        self.assertFalse(evaluated["passed"])

    def test_answerable_case_passes_with_evidence_and_full_scores(self) -> None:
        with patch("app.answer_evaluation.perf_counter", side_effect=[1.0, 1.2, 1.3, 1.6]):
            evaluated = evaluate_case(case(), lambda question: result(), judge)
        self.assertTrue(evaluated["passed"])
        self.assertEqual(evaluated["evidence_recall"], 1)
        self.assertAlmostEqual(evaluated["answer_ms"], 200)
        self.assertAlmostEqual(evaluated["judge_ms"], 300)

    def test_unanswerable_case_requires_explicit_abstention(self) -> None:
        evaluated = evaluate_case(
            case(answerable=False),
            lambda question: result("The context does not provide this information."),
            abstention_judge,
        )
        self.assertTrue(evaluated["passed"])
        self.assertTrue(evaluated["abstained"])
        self.assertIsNone(evaluated["evidence_recall"])

    def test_fixed_refusal_is_scored_without_judge_for_answerable_case(self) -> None:
        semantic_judge = Mock(side_effect=AssertionError("judge must not be called"))
        with patch("app.answer_evaluation.perf_counter", side_effect=[1.0, 1.2, 1.3, 1.35]):
            evaluated = evaluate_case(
                case(), lambda question: result(INSUFFICIENT_EVIDENCE), semantic_judge
            )
        semantic_judge.assert_not_called()
        self.assertTrue(evaluated["abstained"])
        self.assertEqual(
            evaluated["judge"],
            {
                "correctness": 0,
                "completeness": 0,
                "citation_support": 2,
                "explanation": "Recognized the application's fixed insufficient-evidence response.",
            },
        )
        self.assertAlmostEqual(evaluated["judge_ms"], 50)
        self.assertFalse(evaluated["passed"])

    def test_fixed_refusal_is_scored_without_judge_for_unanswerable_case(self) -> None:
        semantic_judge = Mock(side_effect=AssertionError("judge must not be called"))
        evaluated = evaluate_case(
            case(answerable=False),
            lambda question: result(INSUFFICIENT_EVIDENCE),
            semantic_judge,
        )
        semantic_judge.assert_not_called()
        self.assertTrue(evaluated["abstained"])
        self.assertEqual(evaluated["judge"]["correctness"], 2)
        self.assertEqual(evaluated["judge"]["completeness"], 2)
        self.assertEqual(evaluated["judge"]["citation_support"], 2)
        self.assertTrue(evaluated["passed"])

    def test_only_exact_fixed_refusal_skips_semantic_judge(self) -> None:
        answers = [
            f"{INSUFFICIENT_EVIDENCE} ",
            f"{INSUFFICIENT_EVIDENCE} The response increased.",
        ]
        for answer_text in answers:
            with self.subTest(answer=answer_text):
                answer = Mock(return_value=result(answer_text))
                semantic_judge = Mock(side_effect=judge)
                evaluated = evaluate_case(case(), answer, semantic_judge)
                self.assertEqual(semantic_judge.call_count, 2)
                self.assertFalse(evaluated["abstained"])

    def test_invalid_judge_response_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            evaluate_case(case(), lambda question: result(),
                          lambda prompt, schema: {"correctness": 3})

    def test_summary_separates_evidence_and_abstention(self) -> None:
        answerable = evaluate_case(case(), lambda question: result(), judge)
        unanswerable = evaluate_case(
            case(answerable=False),
            lambda question: result("There is not enough information."),
            abstention_judge,
        )
        metrics = summarize([answerable, unanswerable])
        self.assertEqual(metrics["evidence_hit_rate"], 1)
        self.assertEqual(metrics["abstention_accuracy"], 1)
        self.assertEqual(metrics["pass_rate"], 1)

    def test_summary_marks_missing_groups_unavailable(self) -> None:
        evaluated = evaluate_case(case(), lambda question: result(), judge)
        with self.assertRaises(ValueError):
            summarize([])
        metrics = summarize([evaluated])
        self.assertIsNone(metrics["unanswerable_abstention_rate"])
        self.assertEqual(metrics["answerable_false_abstention_rate"], 0)

    def test_missing_evidence_does_not_pass_on_judge_scores_alone(self) -> None:
        evaluated = evaluate_case(case(), lambda question: {"answer": "The response increased.", "sources": []}, judge)
        self.assertFalse(evaluated["passed"])
        self.assertEqual(evaluated["evidence_recall"], 0)

    def test_generator_receives_only_the_question(self) -> None:
        answer = Mock(return_value=result())
        evaluate_case(case(), answer, judge)
        answer.assert_called_once_with(case()["question"])

    def test_judge_rejects_coerced_scores_and_abstention(self) -> None:
        for field, value in [("correctness", True), ("completeness", "2"), ("abstained", "false")]:
            with self.subTest(field=field):
                def bad_judge(prompt: str, schema: dict[str, object]) -> dict[str, object]:
                    if schema.get("title") == "AbstentionDecision":
                        return judge(prompt, schema)
                    return {**judge(prompt, schema), field: value}
                with self.assertRaises(ValidationError):
                    evaluate_case(case(), lambda question: result(), bad_judge)

    def test_empty_evidence_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            evidence_found({"document": "paper.pdf", "page": 2, "quote": " "}, result()["sources"])

    def test_correct_refusals_do_not_inflate_answerable_quality_scores(self) -> None:
        wrong_answer = evaluate_case(case(), lambda question: result("The response decreased."),
                                    lambda prompt, schema: judge(prompt, schema) if schema.get("title") == "AbstentionDecision" else {**judge(prompt, schema), "correctness": 0})
        refusal = evaluate_case(case(answerable=False),
                                lambda question: result("I cannot determine that."), abstention_judge)
        metrics = summarize([wrong_answer, refusal])
        self.assertEqual(metrics["correctness"], 0)
        self.assertEqual(metrics["unanswerable_abstention_rate"], 1)


class AbstentionSeparationTests(unittest.TestCase):
    def test_exact_fact_free_refusals_are_deterministic_but_prefixes_are_not(self) -> None:
        for answer in EXACT_REFUSALS:
            for answerable in [True, False]:
                with self.subTest(answer=answer, answerable=answerable):
                    unused_judge = Mock(side_effect=AssertionError("no model call"))
                    evaluated = evaluate_case(case(answerable=answerable), lambda question: result(answer), unused_judge)
                    self.assertTrue(evaluated["abstained"])
                    self.assertEqual(evaluated["judge"]["correctness"], 0 if answerable else 2)
                    unused_judge.assert_not_called()
            graded = Mock(side_effect=judge)
            evaluated = evaluate_case(case(), lambda question: result(answer + " But I guess it increased by 30%."), graded)
            self.assertFalse(evaluated["abstained"])
            self.assertEqual(graded.call_count, 2)

    def test_classifier_cannot_see_reference_sources_or_answerability(self) -> None:
        calls: list[dict[str, object]] = []

        def classify_then_grade(prompt: str, schema: dict[str, object]) -> dict[str, object]:
            if schema.get("title") == "AbstentionDecision":
                payload = json.loads(prompt.split("Abstention data (JSON):\n")[1])
                calls.append(payload)
                return {"abstained": True, "explanation": "Declines the requested outcome."}
            return {"correctness": 2, "completeness": 2, "citation_support": 1,
                    "abstained": False, "explanation": "Incorrectly credited refusal."}

        answer = "The excerpt lacks outcomes, so I cannot answer."
        evaluated = evaluate_case(case(), lambda question: result(answer), classify_then_grade)
        self.assertEqual(calls, [{"question": "What happened?", "answer": answer}])
        self.assertTrue(evaluated["abstained"])
        self.assertEqual(evaluated["judge"]["correctness"], 0)
        self.assertEqual(evaluated["judge"]["completeness"], 0)
        self.assertEqual(evaluated["judge"]["citation_support"], 1)
        self.assertFalse(evaluated["passed"])

    def test_classifier_schema_and_second_call_transport_failures_propagate(self) -> None:
        with self.assertRaises(ValidationError):
            evaluate_case(case(), lambda question: result(), lambda prompt, schema: {
                "abstained": "false", "explanation": "Wrong type."
            })
        failing_judge = Mock(side_effect=[
            {"abstained": False, "explanation": "Substantive answer."},
            TimeoutError("grading unavailable"),
        ])
        with self.assertRaisesRegex(TimeoutError, "grading unavailable"):
            evaluate_case(case(), lambda question: result(), failing_judge)
        self.assertEqual(failing_judge.call_count, 2)

    def test_expected_evidence_is_not_exposed_as_grading_source(self) -> None:
        prompt = judge_prompt(case(), result())
        payload = json.loads(prompt.split("Evaluation data (JSON):\n")[1])
        self.assertNotIn("evidence", payload["case"])
        self.assertEqual(payload["case"]["reference_answer"], case()["reference_answer"])
        self.assertEqual(payload["sources"], result()["sources"])

    def test_partial_or_guessed_answer_is_not_overridden_by_grader(self) -> None:
        def classify_then_grade(prompt: str, schema: dict[str, object]) -> dict[str, object]:
            if schema.get("title") == "AbstentionDecision":
                return {"abstained": False, "explanation": "Offers a guess."}
            return {"correctness": 1, "completeness": 1, "citation_support": 0,
                    "abstained": True, "explanation": "Contains refusal words."}

        evaluated = evaluate_case(case(), lambda question: result("I do not know, but perhaps 30%."), classify_then_grade)
        self.assertFalse(evaluated["abstained"])
        self.assertEqual(evaluated["judge"]["correctness"], 1)

    def test_unanswerable_refusal_does_not_hide_unsupported_explanation(self) -> None:
        def classify_then_grade(prompt: str, schema: dict[str, object]) -> dict[str, object]:
            if schema.get("title") == "AbstentionDecision":
                return {"abstained": True, "explanation": "Declines requested answer."}
            return {"correctness": 0, "completeness": 2, "citation_support": 0,
                    "abstained": False, "explanation": "Invented study description."}

        evaluated = evaluate_case(case(answerable=False), lambda question: result("I cannot answer because this was a dog study."), classify_then_grade)
        self.assertTrue(evaluated["abstained"])
        self.assertEqual(evaluated["judge"]["correctness"], 0)
        self.assertFalse(evaluated["passed"])


if __name__ == "__main__":
    unittest.main()
