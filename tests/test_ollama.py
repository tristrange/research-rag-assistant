import unittest
from unittest.mock import Mock, patch

from app.llm.ollama import generate, generate_json


class OllamaTests(unittest.TestCase):
    @patch("app.llm.ollama.httpx.post")
    def test_generate_preserves_plain_text_behavior(self, post: Mock) -> None:
        post.return_value.json.return_value = {"message": {"content": "Answer"}}
        self.assertEqual(generate("Question"), "Answer")
        post.return_value.raise_for_status.assert_called_once()
        self.assertNotIn("format", post.call_args.kwargs["json"])

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

    @patch("app.llm.ollama.httpx.post")
    def test_generate_json_rejects_non_object(self, post: Mock) -> None:
        post.return_value.json.return_value = {"message": {"content": "[]"}}
        with self.assertRaisesRegex(ValueError, "not an object"):
            generate_json("Judge", {"type": "object"})


if __name__ == "__main__":
    unittest.main()
