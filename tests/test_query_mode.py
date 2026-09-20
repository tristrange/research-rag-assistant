import unittest
from unittest.mock import patch

from pydantic import ValidationError

from app.main import QueryRequest, query


class QueryModeTests(unittest.TestCase):
    def test_verified_request_reaches_answer_pipeline(self) -> None:
        with patch("app.main.answer_question", return_value={"answer": "Checked", "sources": []}) as answer:
            response = query(QueryRequest(question="Question?", answer_mode="verified"))
        answer.assert_called_once_with("Question?", answer_mode="verified")
        self.assertEqual(response.answer, "Checked")

    def test_legacy_request_defaults_to_plain_and_unknown_mode_is_rejected(self) -> None:
        self.assertEqual(QueryRequest(question="Question?").answer_mode, "plain")
        with self.assertRaises(ValidationError):
            QueryRequest.model_validate({"question": "Question?", "answer_mode": "unchecked-typo"})
