import json
import math
import threading
import unittest
from unittest.mock import patch

import httpx
from pydantic import ValidationError

from app.embeddings import EMBEDDING_MODEL, OLLAMA_EMBED_URL, embed_text
from app.llm.ollama import OLLAMA_URL, chat
from app.llm.telemetry import (
    ModelCall,
    RuntimeSnapshot,
    capture_calls,
    observe_call,
    record_metadata,
    runtime_snapshot,
)


_UNSET = object()


def response(
    url: str,
    *,
    payload: object = _UNSET,
    content: bytes | None = None,
    status_code: int = 200,
) -> httpx.Response:
    request = httpx.Request("GET" if url.endswith(("/version", "/tags")) else "POST", url)
    if payload is not _UNSET:
        content = json.dumps(payload, allow_nan=True).encode("utf-8")
    return httpx.Response(
        status_code,
        content=content or b"",
        headers={"content-type": "application/json"},
        request=request,
    )


class ModelTelemetryTests(unittest.TestCase):
    def test_capture_is_opt_in_and_nested_calls_are_captured_once_per_ancestor(self) -> None:
        with observe_call("chat", "outside") as record:
            self.assertIsNone(record)

        with capture_calls() as outer:
            with observe_call("chat", "outer-only"):
                pass
            with capture_calls() as inner:
                with observe_call("embedding", EMBEDDING_MODEL):
                    pass
            self.assertEqual(len(inner), 1)
            self.assertEqual(len(outer), 2)
            self.assertEqual([call.requested_model for call in inner], [EMBEDDING_MODEL])
            self.assertEqual([call.requested_model for call in outer], ["outer-only", EMBEDDING_MODEL])

    def test_exception_records_failure_propagates_unchanged_and_resets_context(self) -> None:
        error = RuntimeError("private prompt and provider body")
        with self.assertRaises(RuntimeError) as raised:
            with capture_calls() as calls:
                with observe_call("chat", "fixture-model"):
                    raise error
        self.assertIs(raised.exception, error)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].status, "failed")
        self.assertGreaterEqual(calls[0].elapsed_ms, 0)
        self.assertNotIn("private", repr(calls[0]))

        with capture_calls() as subsequent:
            self.assertEqual(subsequent, [])

    def test_context_capture_does_not_leak_to_another_thread(self) -> None:
        observations: list[ModelCall | None] = []
        with capture_calls() as calls:
            thread = threading.Thread(
                target=lambda: self._observe_without_inherited_capture(observations),
            )
            thread.start()
            thread.join()
            with observe_call("chat", "captured"):
                pass
        self.assertEqual(observations, [None])
        self.assertEqual([call.requested_model for call in calls], ["captured"])

    @staticmethod
    def _observe_without_inherited_capture(observations: list[ModelCall | None]) -> None:
        with observe_call("chat", "thread-local") as call:
            observations.append(call)

    def test_model_call_fields_are_strict_finite_and_extra_forbid(self) -> None:
        valid = {
            "operation": "chat", "requested_model": "requested", "elapsed_ms": 0.0,
            "status": "complete",
        }
        self.assertEqual(ModelCall.model_validate(valid).response_model, None)
        for update in (
            {"elapsed_ms": True},
            {"elapsed_ms": -1.0},
            {"elapsed_ms": math.inf},
            {"prompt_eval_count": True},
            {"prompt_eval_count": -1},
            {"unexpected": "not allowed"},
        ):
            with self.subTest(update=update), self.assertRaises(ValidationError):
                ModelCall.model_validate(valid | update)

    def test_chat_capture_records_response_metadata_and_preserves_request(self) -> None:
        body = {
            "model": "fixture-model:latest",
            "message": {"content": "the answer"},
            "done_reason": "stop",
            "total_duration": 1_500_000_000,
            "load_duration": 250_000_000,
            "prompt_eval_duration": 500_000_000,
            "eval_duration": 750_000_000,
            "prompt_eval_count": 24,
            "eval_count": 8,
        }
        with patch(
            "app.llm.ollama.httpx.post", return_value=response(OLLAMA_URL, payload=body),
        ) as post, capture_calls() as calls:
            self.assertEqual(chat("private prompt", model="requested-model"), "the answer")

        self.assertEqual(len(calls), 1)
        call = calls[0]
        self.assertEqual(call.operation, "chat")
        self.assertEqual(call.requested_model, "requested-model")
        self.assertEqual(call.response_model, "fixture-model:latest")
        self.assertEqual(call.status, "complete")
        self.assertGreaterEqual(call.elapsed_ms, 0)
        self.assertEqual(call.total_duration_ms, 1500.0)
        self.assertEqual(call.load_duration_ms, 250.0)
        self.assertEqual(call.prompt_eval_duration_ms, 500.0)
        self.assertEqual(call.eval_duration_ms, 750.0)
        self.assertEqual(call.prompt_eval_count, 24)
        self.assertEqual(call.eval_count, 8)
        self.assertEqual(call.done_reason, "stop")
        self.assertNotIn("private prompt", repr(call))
        self.assertEqual(post.call_args.args[0], OLLAMA_URL)
        self.assertEqual(post.call_args.kwargs["json"]["messages"], [
            {"role": "user", "content": "private prompt"},
        ])
        self.assertEqual(post.call_args.kwargs["timeout"], 120.0)

    def test_bad_response_metadata_is_ignored_as_unknown(self) -> None:
        call = ModelCall(
            operation="chat", requested_model="requested", elapsed_ms=3.0, status="complete",
        )
        record_metadata(call, {
            "model": 42,
            "done_reason": False,
            "total_duration": -1,
            "load_duration": True,
            "prompt_eval_duration": math.nan,
            "eval_duration": "not a duration",
            "prompt_eval_count": True,
            "eval_count": -1,
        })
        self.assertIsNone(call.response_model)
        self.assertIsNone(call.done_reason)
        self.assertIsNone(call.total_duration_ms)
        self.assertIsNone(call.load_duration_ms)
        self.assertIsNone(call.prompt_eval_duration_ms)
        self.assertIsNone(call.eval_duration_ms)
        self.assertIsNone(call.prompt_eval_count)
        self.assertIsNone(call.eval_count)

    def test_failed_chat_records_duration_without_prompt_or_error_details(self) -> None:
        request = httpx.Request("POST", OLLAMA_URL)
        error = httpx.ConnectError("private provider body and prompt", request=request)
        with patch("app.llm.ollama.httpx.post", side_effect=error), capture_calls() as calls:
            with self.assertRaises(httpx.ConnectError) as raised:
                chat("private prompt")
        self.assertIs(raised.exception, error)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].status, "failed")
        self.assertGreaterEqual(calls[0].elapsed_ms, 0)
        self.assertNotIn("private", repr(calls[0]))

    def test_embedding_capture_records_metadata_and_preserves_request(self) -> None:
        vector = [0.0] * 768
        body = {
            "model": EMBEDDING_MODEL,
            "embeddings": [vector],
            "total_duration": 2_000_000,
            "prompt_eval_count": 5,
        }
        with patch(
            "app.embeddings.httpx.post", return_value=response(OLLAMA_EMBED_URL, payload=body),
        ) as post, capture_calls() as calls:
            result = embed_text("private passage")
        self.assertEqual(len(result), 768)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].operation, "embedding")
        self.assertEqual(calls[0].requested_model, EMBEDDING_MODEL)
        self.assertEqual(calls[0].response_model, EMBEDDING_MODEL)
        self.assertEqual(calls[0].total_duration_ms, 2.0)
        self.assertEqual(calls[0].prompt_eval_count, 5)
        self.assertEqual(calls[0].status, "complete")
        self.assertNotIn("private passage", repr(calls[0]))
        self.assertEqual(post.call_args.args[0], OLLAMA_EMBED_URL)
        self.assertEqual(post.call_args.kwargs["json"], {
            "model": EMBEDDING_MODEL, "input": "private passage",
        })
        self.assertEqual(post.call_args.kwargs["timeout"], 120.0)

    def test_runtime_snapshot_normalizes_latest_and_accepts_only_sha256_digests(self) -> None:
        digest = "a" * 64
        version_response = response("http://localhost:11434/api/version", payload={"version": "0.7.1"})
        tags_response = response("http://localhost:11434/api/tags", payload={"models": [
            {"name": "gpt-oss:20b", "digest": digest},
            {"name": "nomic-embed-text:latest", "digest": "B" * 64},
            {"name": "broken:latest", "digest": "short"},
        ]})
        models = ["gpt-oss:20b", "nomic-embed-text", "missing-model"]
        with patch(
            "app.llm.telemetry.httpx.get", side_effect=[version_response, tags_response],
        ) as get:
            snapshot = runtime_snapshot(models)
        self.assertIsInstance(snapshot, RuntimeSnapshot)
        self.assertEqual(snapshot.ollama_version, "0.7.1")
        self.assertEqual(snapshot.model_digests, {
            "gpt-oss:20b": digest,
            "nomic-embed-text": "b" * 64,
            "missing-model": None,
        })
        self.assertEqual([call.args[0] for call in get.call_args_list], [
            "http://localhost:11434/api/version", "http://localhost:11434/api/tags",
        ])
        self.assertEqual([call.kwargs["timeout"] for call in get.call_args_list], [2.0, 2.0])

    def test_runtime_snapshot_failures_are_independent_and_malformed_data_unknown(self) -> None:
        request = httpx.Request("GET", "http://localhost:11434/api/version")
        cases = [
            (
                httpx.ConnectError("private connection", request=request),
                response("http://localhost:11434/api/tags", payload={"models": []}),
            ),
            (
                response("http://localhost:11434/api/version", payload={"version": 12}),
                response("http://localhost:11434/api/tags", payload={"models": "malformed"}),
            ),
        ]
        for version_result, tags_result in cases:
            with self.subTest(version_result=version_result), patch(
                "app.llm.telemetry.httpx.get", side_effect=[version_result, tags_result],
            ):
                snapshot = runtime_snapshot(["gpt-oss:20b"])
            self.assertIsNone(snapshot.ollama_version)
            self.assertEqual(snapshot.model_digests, {"gpt-oss:20b": None})


if __name__ == "__main__":
    unittest.main()
