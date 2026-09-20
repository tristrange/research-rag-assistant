import unittest
from unittest.mock import Mock, patch

from app.llm.ollama import generate, generate_json


class OllamaTests(unittest.TestCase):
    @patch("app.llm.ollama.httpx.post")
    def test_generate_preserves_plain_text_behavior(self, post: Mock) -> None:
        post.return_value.json.return_value = {"message": {"content": "Answer"}}
        self.assertEqual(generate("Question"), "Answer")
        post.return_value.raise_for_status.assert_called_once()
        payload = post.call_args.kwargs["json"]
        self.assertNotIn("format", payload)
        self.assertNotIn("think", payload)

    @patch("app.llm.ollama.httpx.post")
    def test_generate_json_sends_schema_and_parses_object(self, post: Mock) -> None:
        schema: dict[str, object] = {"type": "object"}
        post.return_value.json.return_value = {
            "message": {"content": '{"correctness": 2}'},
        }
        self.assertEqual(generate_json("Judge", schema), {"correctness": 2})
        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["format"], schema)
        self.assertEqual(payload["options"], {"temperature": 0.0})
        self.assertIs(payload["think"], False)

    @patch("app.llm.ollama.httpx.post")
    def test_explicit_reasoning_has_a_bounded_longer_timeout(self, post: Mock) -> None:
        post.return_value.json.return_value = {"message": {"content": "{}"}}
        generate_json("Question", {}, think=True, num_ctx=12288, num_predict=4096)
        self.assertEqual(post.call_args.kwargs["timeout"], 300.0)
        self.assertIs(post.call_args.kwargs["json"]["think"], True)
        self.assertEqual(post.call_args.kwargs["json"]["options"],
                         {"temperature": 0.0, "num_ctx": 12288, "num_predict": 4096})
        generate_json("Question", {}, think=False)
        self.assertEqual(post.call_args.kwargs["timeout"], 120.0)

    @patch("app.llm.ollama.httpx.post")
    def test_model_and_reasoning_level_are_request_specific(self, post: Mock) -> None:
        post.return_value.json.return_value = {"message": {"content": "{}"}}
        generate_json("Question", {}, model="gpt-oss:20b", think="low")
        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["model"], "gpt-oss:20b")
        self.assertEqual(payload["think"], "low")
        self.assertEqual(post.call_args.kwargs["timeout"], 300.0)
        generate("Question")
        self.assertEqual(post.call_args.kwargs["json"]["model"], "qwen3:8b")

    @patch("app.llm.ollama.httpx.post")
    def test_distinct_model_roles_reach_ollama(self, post: Mock) -> None:
        post.return_value.json.return_value = {"message": {"content": "{}"}}
        with patch("app.llm.ollama.MODEL", "generator:test"), patch("app.llm.ollama.JUDGE_MODEL", "judge:test"):
            generate("Question")
            self.assertEqual(post.call_args.kwargs["json"]["model"], "generator:test")
            generate_json("Judge", {})
            self.assertEqual(post.call_args.kwargs["json"]["model"], "judge:test")
            generate_json("Verify", {}, model="grounding:test")
            self.assertEqual(post.call_args.kwargs["json"]["model"], "grounding:test")

    @patch("app.llm.ollama.httpx.post")
    def test_generate_json_rejects_non_object(self, post: Mock) -> None:
        post.return_value.json.return_value = {"message": {"content": "[]"}}
        with self.assertRaisesRegex(ValueError, "not an object"):
            generate_json("Judge", {"type": "object"})


if __name__ == "__main__":
    unittest.main()
