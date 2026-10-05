import json
import math
import unittest
from collections.abc import Callable
from unittest.mock import patch

import httpx

from app.embeddings import EMBEDDING_MODEL, MAX_EMBEDDING_BATCH_SIZE, OLLAMA_EMBED_URL, embed_text, embed_texts
from app.llm.errors import OllamaResponseError
from app.llm.ollama import OLLAMA_URL, OllamaOutputLimitError, chat, generate_json
from app.llm.telemetry import capture_calls


_UNSET = object()


def response(
    url: str,
    *,
    payload: object = _UNSET,
    content: bytes | None = None,
    status_code: int = 200,
) -> httpx.Response:
    request = httpx.Request("POST", url)
    if payload is not _UNSET:
        content = json.dumps(payload, allow_nan=True).encode("utf-8")
    return httpx.Response(
        status_code,
        content=content or b"",
        headers={"content-type": "application/json"},
        request=request,
    )


class ProviderResponseTests(unittest.TestCase):
    def assert_response_error(self, operation: str, call: Callable[[], object]) -> None:
        with self.assertRaises(OllamaResponseError) as raised:
            call()
        error = raised.exception
        self.assertIsInstance(error, RuntimeError)
        self.assertEqual(error.operation, operation)
        self.assertTrue(str(error))
        self.assertNotIn("private provider payload", str(error))

    def test_chat_accepts_optional_completion_metadata_and_extra_fields(self) -> None:
        body = {
            "message": {"content": "answer", "role": "assistant", "extra": True},
            "model": "fixture-model",
            "extra": "allowed",
        }
        with patch("app.llm.ollama.httpx.post", return_value=response(OLLAMA_URL, payload=body)):
            self.assertEqual(chat("Question?"), "answer")

    def test_chat_rejects_malformed_envelopes(self) -> None:
        malformed: list[object] = [
            None,
            [],
            "private provider payload",
            {},
            {"message": None},
            {"message": []},
            {"message": {}},
            {"message": {"content": None}},
            {"message": {"content": 12}},
            {"message": {"content": "answer"}, "done": False},
            {"message": {"content": "answer"}, "done": None},
            {"message": {"content": "answer"}, "done": 1},
            {"message": {"content": "answer"}, "done_reason": 12},
            {"message": {"content": "partial"}, "done": False, "done_reason": "length"},
            {"message": None, "done_reason": "length"},
        ]
        for body in malformed:
            with self.subTest(body=body), patch(
                "app.llm.ollama.httpx.post", return_value=response(OLLAMA_URL, payload=body),
            ):
                self.assert_response_error("chat", lambda: chat("Question?"))

    def test_chat_invalid_json_is_a_safe_response_error(self) -> None:
        with patch(
            "app.llm.ollama.httpx.post",
            return_value=response(OLLAMA_URL, content=b"private provider payload {"),
        ):
            self.assert_response_error("chat", lambda: chat("Question?"))

    def test_chat_keeps_length_and_empty_json_content_errors_distinct(self) -> None:
        length_response = response(OLLAMA_URL, payload={
            "message": {"content": "partial"}, "done": True, "done_reason": "length",
        })
        with patch("app.llm.ollama.httpx.post", return_value=length_response):
            with self.assertRaises(OllamaOutputLimitError):
                chat("Question?")

        empty_response = response(OLLAMA_URL, payload={"message": {"content": ""}})
        with patch("app.llm.ollama.httpx.post", return_value=empty_response):
            with self.assertRaises(ValueError) as raised:
                generate_json("Judge", {})
        self.assertNotIsInstance(raised.exception, OllamaResponseError)

    def test_chat_preserves_valid_request_and_http_error_behavior(self) -> None:
        body = {"message": {"content": "answer"}, "done": True, "done_reason": "stop"}
        with patch(
            "app.llm.ollama.httpx.post", return_value=response(OLLAMA_URL, payload=body),
        ) as post:
            self.assertEqual(chat(
                "Question?", response_format={"type": "json"}, temperature=0.2,
                think="low", model="fixture-model", num_ctx=4096, num_predict=100,
                sampling={"top_p": 0.9}, timeout_seconds=7,
            ), "answer")
        self.assertEqual(post.call_args.args[0], OLLAMA_URL)
        self.assertEqual(post.call_args.kwargs["timeout"], 7)
        self.assertEqual(post.call_args.kwargs["json"], {
            "model": "fixture-model",
            "messages": [{"role": "user", "content": "Question?"}],
            "stream": False,
            "format": {"type": "json"},
            "options": {
                "temperature": 0.2, "top_p": 0.9, "num_ctx": 4096, "num_predict": 100,
            },
            "think": "low",
        })

        failed = response(OLLAMA_URL, payload={"error": "provider error"}, status_code=500)
        with patch("app.llm.ollama.httpx.post", return_value=failed):
            with self.assertRaises(httpx.HTTPStatusError):
                chat("Question?")

    def test_embedding_requires_a_single_finite_768_value_vector(self) -> None:
        valid_vector = [0, 1.25, *([2] * 766)]
        with patch(
            "app.embeddings.httpx.post",
            return_value=response(OLLAMA_EMBED_URL, payload={"embeddings": [valid_vector]}),
        ) as post:
            result = embed_text("paper passage")
        self.assertEqual(len(result), 768)
        self.assertEqual(result[:3], [0.0, 1.25, 2.0])
        self.assertTrue(all(type(value) is float for value in result))
        self.assertEqual(post.call_args.args[0], OLLAMA_EMBED_URL)
        self.assertEqual(post.call_args.kwargs["json"], {
            "model": EMBEDDING_MODEL, "input": "paper passage",
        })
        self.assertEqual(post.call_args.kwargs["timeout"], 120.0)

    def test_embedding_rejects_malformed_envelopes_and_vectors(self) -> None:
        short_vector = [0.0] * 767
        long_vector = [0.0] * 769
        invalid_vectors: list[object] = [
            None,
            [],
            [[], []],
            ["not a vector"],
            [short_vector],
            [long_vector],
            [[0.0] * 767 + ["1"]],
            [[0.0] * 767 + [True]],
            [[0.0] * 767 + [None]],
            [[0.0] * 767 + [math.nan]],
            [[0.0] * 767 + [math.inf]],
            [[0.0] * 767 + [-math.inf]],
            [[0.0] * 767 + [10 ** 400]],
        ]
        malformed: list[object] = [None, [], "private provider payload", {}, {"embeddings": None}]
        malformed.extend({"embeddings": vectors} for vectors in invalid_vectors)
        for body in malformed:
            with self.subTest(body=body), patch(
                "app.embeddings.httpx.post",
                return_value=response(OLLAMA_EMBED_URL, payload=body),
            ):
                self.assert_response_error("embedding", lambda: embed_text("passage"))

    def test_embedding_invalid_json_is_safe_and_http_errors_are_unchanged(self) -> None:
        with patch(
            "app.embeddings.httpx.post",
            return_value=response(OLLAMA_EMBED_URL, content=b"private provider payload {"),
        ):
            self.assert_response_error("embedding", lambda: embed_text("passage"))

        failed = response(OLLAMA_EMBED_URL, payload={"error": "provider error"}, status_code=500)
        with patch("app.embeddings.httpx.post", return_value=failed):
            with self.assertRaises(httpx.HTTPStatusError):
                embed_text("passage")

    def test_batch_vectors_keep_input_order_and_caller_client_ownership(self) -> None:
        payloads: list[object] = []

        def handle(request: httpx.Request) -> httpx.Response:
            payloads.append(json.loads(request.content))
            return response(OLLAMA_EMBED_URL, payload={"embeddings": [[0] * 768, [1.5] * 768]})

        with httpx.Client(transport=httpx.MockTransport(handle)) as client, capture_calls() as calls:
            vectors = embed_texts(["First", "Second β"], client=client)
            self.assertFalse(client.is_closed)
        self.assertTrue(client.is_closed)
        self.assertEqual(vectors, [[0.0] * 768, [1.5] * 768])
        self.assertEqual(payloads, [{"model": EMBEDDING_MODEL, "input": ["First", "Second β"]}])
        self.assertEqual([(c.operation, c.status) for c in calls], [("embedding", "complete")])

    def test_batch_rejects_wrong_cardinality_and_invalid_later_vectors(self) -> None:
        invalid: list[object] = [
            [], [[0.0] * 768], [[0.0] * 768] * 3,
            [[0.0] * 768, [0.0] * 767],
            [[0.0] * 768, [0.0] * 767 + [True]],
            [[0.0] * 768, [0.0] * 767 + [math.nan]],
        ]
        for vectors in invalid:
            with self.subTest(vectors=vectors), patch(
                "app.embeddings.httpx.post",
                return_value=response(OLLAMA_EMBED_URL, payload={"embeddings": vectors}),
            ), capture_calls() as calls:
                self.assert_response_error("embedding", lambda: embed_texts(["First", "Second"]))
            self.assertEqual([c.status for c in calls], ["failed"])

    def test_empty_and_oversized_batches_do_not_call_provider(self) -> None:
        with patch("app.embeddings.httpx.post") as post, capture_calls() as calls:
            self.assertEqual(embed_texts([]), [])
            with self.assertRaises(ValueError):
                embed_texts(["text"] * (MAX_EMBEDDING_BATCH_SIZE + 1))
        post.assert_not_called()
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
