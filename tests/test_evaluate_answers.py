from contextlib import ExitStack, redirect_stdout
from hashlib import sha256
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from app.answer_evaluation import AnswerEvaluationCase, evaluate_case
from app.types import ChunkData, PageData
from scripts.answer_quality_cases import ANSWER_CASES
from scripts.evaluate_answers import main, validate_index, validate_labels


class AnswerRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.case = AnswerEvaluationCase(id="test", question="What increased?", answerable=True,
                                        reference_answer="The response increased.", evidence=[
                                            {"document": "paper.pdf", "page": 1, "quote": "response increased"},
                                        ])
        self.pages = [PageData(document="paper.pdf", page=1, text="The response increased.")]

    def test_labels_are_validated_against_pages_not_chunk_boundaries(self) -> None:
        validate_labels([self.case], self.pages)
        # A quote absent from a single chunk is a retrieval miss, not invalid ground truth.
        validate_index([ChunkData(document="paper.pdf", page=1, chunk_index=0,
                                  text="The response")], self.pages)

    def test_invalid_dataset_is_rejected(self) -> None:
        invalid_sets: list[list[AnswerEvaluationCase]] = [
            [], [self.case, self.case], [{**self.case, "answerable": False}],
            [{**self.case, "evidence": []}],
        ]
        for cases in invalid_sets:
            with self.subTest(cases=cases), self.assertRaises(ValueError):
                validate_labels(cases, self.pages)
        with self.assertRaisesRegex(ValueError, "absent"):
            validate_labels([self.case], [PageData(document="wrong.pdf", page=1, text="The response increased.")])

    def test_stale_index_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "another PDF"):
            validate_index([ChunkData(document="paper.pdf", page=1, chunk_index=0,
                                      text="The response decreased.")], self.pages)

    def test_failure_preserves_completed_results(self) -> None:
        first = evaluate_case(ANSWER_CASES[0], lambda question: {"answer": "Unknown", "sources": []},
                              lambda prompt, schema: {"correctness": 0, "completeness": 0,
                                                       "citation_support": 0, "abstained": False,
                                                       "explanation": "Wrong answer"})
        with TemporaryDirectory() as directory, ExitStack() as stack:
            output = Path(directory) / "answers.json"
            stack.enter_context(patch("sys.argv", ["evaluate_answers", "--output", str(output)]))
            stack.enter_context(patch("pathlib.Path.read_bytes", return_value=b"paper"))
            stack.enter_context(patch("scripts.evaluate_answers.PAPER_SHA256", sha256(b"paper").hexdigest()))
            stack.enter_context(patch("scripts.evaluate_answers.extract_pages", return_value=self.pages))
            stack.enter_context(patch("scripts.evaluate_answers.validate_labels"))
            stack.enter_context(patch("scripts.evaluate_answers.validate_index"))
            stack.enter_context(patch("scripts.evaluate_answers.indexed_sources", return_value=[]))
            stack.enter_context(patch("scripts.evaluate_answers.snapshot", return_value={"chunks_by_document": {"sample.pdf": 1}}))
            stack.enter_context(patch("scripts.evaluate_answers.evaluate_case", side_effect=[first, RuntimeError("model offline")]))
            with redirect_stdout(io.StringIO()), self.assertRaisesRegex(RuntimeError, "model offline"):
                main()
            report = json.loads(output.read_text())
            self.assertEqual(report["status"], "failed")
            self.assertEqual(len(report["results"]), 1)
            self.assertIsNone(report["metrics"])
            self.assertIn("model offline", report["error"])

    def test_existing_report_is_preserved_before_services_are_called(self) -> None:
        with TemporaryDirectory() as directory:
            output = Path(directory) / "answers.json"
            output.write_text("existing report")
            with patch("sys.argv", ["evaluate_answers", "--output", str(output)]), \
                    patch("scripts.evaluate_answers.snapshot") as snapshot, \
                    patch("sys.stderr", new_callable=io.StringIO):
                with self.assertRaises(SystemExit) as error:
                    main()
                self.assertEqual(error.exception.code, 2)
                snapshot.assert_not_called()
            self.assertEqual(output.read_text(), "existing report")


if __name__ == "__main__":
    unittest.main()
