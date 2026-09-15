import unittest
from unittest.mock import Mock, patch

from pydantic import ValidationError

from app.answer_evaluation import (
    AnswerEvaluationCase,
    evaluate_case,
    evidence_found,
    normalize,
    summarize,
)
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
                    return {**judge(prompt, schema), field: value}
                with self.assertRaises(ValidationError):
                    evaluate_case(case(), lambda question: result(), bad_judge)

    def test_empty_evidence_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            evidence_found({"document": "paper.pdf", "page": 2, "quote": " "}, result()["sources"])

    def test_correct_refusals_do_not_inflate_answerable_quality_scores(self) -> None:
        wrong_answer = evaluate_case(case(), lambda question: result("The response decreased."),
                                    lambda prompt, schema: {**judge(prompt, schema), "correctness": 0})
        refusal = evaluate_case(case(answerable=False),
                                lambda question: result("I cannot determine that."), abstention_judge)
        metrics = summarize([wrong_answer, refusal])
        self.assertEqual(metrics["correctness"], 0)
        self.assertEqual(metrics["unanswerable_abstention_rate"], 1)


if __name__ == "__main__":
    unittest.main()
