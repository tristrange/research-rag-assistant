import unittest
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.exc import OperationalError

from app.llm.ollama import OLLAMA_URL, OllamaOutputLimitError
from app.main import QueryRequest, _query_gate, app, query


def local_client(*, raise_server_exceptions: bool = True) -> TestClient:
    return TestClient(
        app, base_url="http://127.0.0.1", client=("127.0.0.1", 50000),
        raise_server_exceptions=raise_server_exceptions,
    )


class QueryModeTests(unittest.TestCase):
    def test_service_failures_return_safe_errors_and_allow_another_question(self) -> None:
        request = httpx.Request("POST", OLLAMA_URL)
        cases: list[tuple[Exception, int, str]] = [
            (OperationalError("private SQL", {}, Exception("secret-password")), 503, "database_error"),
            (httpx.ConnectError("secret-password", request=request), 503, "model_unavailable"),
            (httpx.ReadTimeout("secret-password", request=request), 504, "model_timeout"),
            (httpx.HTTPStatusError("secret-password", request=request,
                                   response=httpx.Response(404, request=request, json={"error": "private model output"})),
             503, "model_not_found"),
            (httpx.HTTPStatusError("secret-password", request=request,
                                   response=httpx.Response(500, request=request, text="private model output")),
             502, "model_service_error"),
            (OllamaOutputLimitError("private model output"), 502, "model_output_limit"),
        ]
        client = local_client()
        for error, status, code in cases:
            with self.subTest(code=code), self.assertLogs("app.main", level="WARNING") as logs:
                with patch("app.main.answer_question", side_effect=error):
                    response = client.post("/query", json={"question": "Question?"})
                self.assertEqual(response.status_code, status)
                self.assertEqual(response.json()["detail"]["code"], code)
                self.assertNotIn("answer", response.json())
                for secret in ("secret-password", "private model output", "private SQL"):
                    self.assertNotIn(secret, response.text)
                    self.assertNotIn(secret, " ".join(logs.output))
                with patch("app.main.answer_question", return_value={"answer": "Recovered", "sources": []}):
                    retry = client.post("/query", json={"question": "Question?"})
                self.assertEqual(retry.status_code, 200)

    def test_paper_list_database_failure_uses_the_same_safe_error(self) -> None:
        with patch("app.main.list_documents", side_effect=OperationalError("private SQL", {}, Exception("secret-password"))):
            response = local_client().get("/documents")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"]["code"], "database_error")
        self.assertIn("scripts.init_db", response.json()["detail"]["message"])
        self.assertNotIn("secret-password", response.text)

    def test_non_ollama_dependency_errors_are_not_reported_as_missing_answer_models(self) -> None:
        request = httpx.Request("GET", "https://example.invalid/model-download")
        error = httpx.HTTPStatusError("private dependency data", request=request,
                                      response=httpx.Response(404, request=request))
        with patch("app.main.answer_question", side_effect=error):
            response = local_client().post("/query", json={"question": "Question?"})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"]["code"], "dependency_error")
        self.assertNotIn("private dependency data", response.text)

    def test_service_errors_work_for_both_each_paper_scopes(self) -> None:
        for scope in ("each", "each_query"):
            with self.subTest(scope=scope), patch("app.main.answer_each_document", side_effect=OllamaOutputLimitError("private output")):
                response = local_client().post("/query", json={"question": "Question?", "scope": scope})
            self.assertEqual(response.status_code, 502)
            self.assertEqual(response.json()["detail"]["code"], "model_output_limit")

    def test_query_returns_claim_evidence_bound_to_response_sources(self) -> None:
        result = {"answer": "Finding (study.pdf, page 2)", "sources": [{
            "document": "study.pdf", "page": 2, "chunk_index": 7, "text": "Finding.", "section": "results",
        }], "claim_evidence": [{
            "text": "Finding", "attribution": "this_document_authors",
            "citations": [{"source_index": 0, "quote": "Finding."}],
        }]}
        with patch("app.main.answer_question", return_value=result):
            response = local_client().post("/query", json={"question": "What happened?"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), result)

    def test_non_loopback_client_cannot_read_or_query(self) -> None:
        client = TestClient(
            app, base_url="http://127.0.0.1", client=("192.0.2.1", 50000),
        )
        with patch("app.main.answer_question") as answer, patch("app.main.list_documents") as listing:
            self.assertEqual(client.get("/documents").status_code, 403)
            self.assertEqual(client.post("/query", json={"question": "Question?"}).status_code, 403)
            self.assertEqual(client.get("/").status_code, 403)
        answer.assert_not_called()
        listing.assert_not_called()

    def test_untrusted_host_is_rejected_even_from_loopback(self) -> None:
        client = TestClient(
            app, base_url="http://attacker.example", client=("127.0.0.1", 50000),
        )
        self.assertEqual(client.get("/documents").status_code, 400)

    def test_bracketed_ipv6_loopback_host_is_allowed(self) -> None:
        client = TestClient(
            app, base_url="http://127.0.0.1", client=("::1", 50000),
        )
        self.assertEqual(client.get("/", headers={"Host": "[::1]:8000"}).status_code, 200)

    def test_host_suffix_and_userinfo_are_rejected(self) -> None:
        client = local_client()
        for host in ("localhost.attacker.example", "attacker.example@127.0.0.1"):
            with self.subTest(host=host):
                self.assertEqual(client.get("/", headers={"Host": host}).status_code, 400)

    def test_verified_request_reaches_answer_pipeline(self) -> None:
        with patch("app.main.answer_question", return_value={"answer": "Checked", "sources": []}) as answer:
            response = query(QueryRequest(question="Question?", answer_mode="verified"))
        answer.assert_called_once_with("Question?", answer_mode="verified", document=None)
        self.assertEqual(response.answer, "Checked")

    def test_request_defaults_to_verified_and_unknown_mode_is_rejected(self) -> None:
        self.assertEqual(QueryRequest(question="Question?").answer_mode, "verified")
        with self.assertRaises(ValidationError):
            QueryRequest.model_validate({"question": "Question?", "answer_mode": "unchecked-typo"})

    def test_plain_mode_is_not_exposed_by_the_api(self) -> None:
        with patch("app.main.answer_question") as answer:
            response = local_client().post("/query", json={
                "question": "Question?", "answer_mode": "plain",
            })
        self.assertEqual(response.status_code, 422)
        answer.assert_not_called()

    def test_rejects_blank_and_oversized_questions_before_model_calls(self) -> None:
        with patch("app.main.answer_question") as answer:
            for question in ("", "   ", "x" * 2001):
                with self.subTest(length=len(question)):
                    response = local_client().post("/query", json={"question": question})
                    self.assertEqual(response.status_code, 422)
            answer.assert_not_called()

    def test_overlapping_query_is_rejected_without_starting_another_model_call(self) -> None:
        _query_gate.acquire()
        try:
            with patch("app.main.answer_question") as answer:
                response = local_client().post("/query", json={"question": "Question?"})
            self.assertEqual(response.status_code, 429)
            answer.assert_not_called()
        finally:
            _query_gate.release()

    def test_failed_query_releases_the_gate(self) -> None:
        with patch("app.main.answer_question", side_effect=RuntimeError("model unavailable")):
            response = local_client(raise_server_exceptions=False).post(
                "/query", json={"question": "Question?"},
            )
        self.assertEqual(response.status_code, 500)
        self.assertTrue(_query_gate.acquire(blocking=False))
        _query_gate.release()

    def test_documents_endpoint_lists_exact_indexed_filenames(self) -> None:
        with patch("app.main.list_documents", return_value=["a.pdf", "b.pdf"]) as listing:
            response = local_client().get("/documents")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), ["a.pdf", "b.pdf"])
        listing.assert_called_once_with()

    def test_query_endpoint_passes_selected_document(self) -> None:
        with patch("app.main.answer_question", return_value={"answer": "Checked", "sources": []}) as answer:
            response = local_client().post("/query", json={
                "question": "Question?", "answer_mode": "verified", "document": "paper.pdf",
            })
        self.assertEqual(response.status_code, 200)
        answer.assert_called_once_with("Question?", answer_mode="verified", document="paper.pdf")

    def test_document_must_be_a_nonempty_filename(self) -> None:
        for document in ["", "   ", "data/paper.pdf", "data\\paper.pdf"]:
            with self.subTest(document=document):
                response = local_client().post("/query", json={
                    "question": "Question?", "document": document,
                })
                self.assertEqual(response.status_code, 422)

    def test_each_paper_scope_uses_separate_answer_path(self) -> None:
        with patch("app.main.answer_each_document", return_value={
            "answer": "Answers by paper", "sources": [],
        }) as each, patch("app.main.answer_question") as relevant:
            response = local_client().post("/query", json={
                "question": "What were the findings?", "scope": "each",
            })
        self.assertEqual(response.status_code, 200)
        each.assert_called_once_with(
            "What were the findings?", answer_mode="verified", overview=True,
        )
        relevant.assert_not_called()

    def test_each_paper_targeted_scope_searches_each_document(self) -> None:
        with patch("app.main.answer_each_document", return_value={
            "answer": "Answers by paper", "sources": [],
        }) as each, patch("app.main.answer_question") as relevant:
            response = local_client().post("/query", json={
                "question": "What methods were used?", "scope": "each_query",
            })
        self.assertEqual(response.status_code, 200)
        each.assert_called_once_with(
            "What methods were used?", answer_mode="verified", overview=False,
        )
        relevant.assert_not_called()

    def test_each_paper_scope_rejects_a_selected_document(self) -> None:
        for scope in ("each", "each_query"):
            with self.subTest(scope=scope):
                response = local_client().post("/query", json={
                    "question": "Question?", "scope": scope, "document": "paper.pdf",
                })
                self.assertEqual(response.status_code, 422)
