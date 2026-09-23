import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import QueryRequest, app, query


class QueryModeTests(unittest.TestCase):
    def test_verified_request_reaches_answer_pipeline(self) -> None:
        with patch("app.main.answer_question", return_value={"answer": "Checked", "sources": []}) as answer:
            response = query(QueryRequest(question="Question?", answer_mode="verified"))
        answer.assert_called_once_with("Question?", answer_mode="verified", document=None)
        self.assertEqual(response.answer, "Checked")

    def test_legacy_request_defaults_to_plain_and_unknown_mode_is_rejected(self) -> None:
        self.assertEqual(QueryRequest(question="Question?").answer_mode, "plain")
        with self.assertRaises(ValidationError):
            QueryRequest.model_validate({"question": "Question?", "answer_mode": "unchecked-typo"})

    def test_documents_endpoint_lists_exact_indexed_filenames(self) -> None:
        with patch("app.main.list_documents", return_value=["a.pdf", "b.pdf"]) as listing:
            response = TestClient(app).get("/documents")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), ["a.pdf", "b.pdf"])
        listing.assert_called_once_with()

    def test_query_endpoint_passes_selected_document(self) -> None:
        with patch("app.main.answer_question", return_value={"answer": "Checked", "sources": []}) as answer:
            response = TestClient(app).post("/query", json={
                "question": "Question?", "answer_mode": "verified", "document": "paper.pdf",
            })
        self.assertEqual(response.status_code, 200)
        answer.assert_called_once_with("Question?", answer_mode="verified", document="paper.pdf")

    def test_document_must_be_a_nonempty_filename(self) -> None:
        for document in ["", "   ", "data/paper.pdf", "data\\paper.pdf"]:
            with self.subTest(document=document):
                response = TestClient(app).post("/query", json={
                    "question": "Question?", "document": document,
                })
                self.assertEqual(response.status_code, 422)
