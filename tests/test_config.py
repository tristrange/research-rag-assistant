import json
import os
from pathlib import Path
from unittest.mock import patch

from app.config import reasoning_setting
import subprocess
import sys
import unittest


class ConfigTests(unittest.TestCase):
    def read_settings(self, overrides: dict[str, str]) -> subprocess.CompletedProcess[str]:
        environment = {k: v for k, v in os.environ.items() if not k.startswith("RAG_")}
        return subprocess.run(
            [sys.executable, "-c", "import json; from app import config; print(json.dumps([config.GENERATOR_MODEL, config.GROUNDING_MODEL, config.JUDGE_MODEL, config.DATABASE_URL]))"],
            cwd=Path(__file__).resolve().parents[1], env={**environment, **overrides},
            capture_output=True, text=True, check=False,
        )

    def test_defaults_preserve_existing_roles(self) -> None:
        result = self.read_settings({})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), [
            "qwen3:8b", "gpt-oss:20b", "qwen3:8b",
            "postgresql+psycopg://rag:rag@localhost:5432/rag",
        ])

    def test_roles_and_database_can_be_overridden_independently(self) -> None:
        result = self.read_settings({
            "RAG_GENERATOR_MODEL": " qwen3-coder:30b ",
            "RAG_JUDGE_MODEL": "judge:latest", "RAG_DATABASE_URL": "sqlite://",
        })
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), [
            "qwen3-coder:30b", "gpt-oss:20b", "judge:latest", "sqlite://",
        ])

    def test_explicit_blank_settings_fail_at_startup(self) -> None:
        for name in ["RAG_GENERATOR_MODEL", "RAG_GROUNDING_MODEL", "RAG_JUDGE_MODEL", "RAG_DATABASE_URL"]:
            with self.subTest(name=name):
                result = self.read_settings({name: "  "})
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(f"{name} must not be empty", result.stderr)


class ReasoningConfigTests(unittest.TestCase):
    def test_boolean_and_level_settings_preserve_types(self) -> None:
        for raw, expected in [("true", True), ("false", False), ("low", "low"), ("medium", "medium"), ("high", "high")]:
            with self.subTest(raw=raw), patch.dict(os.environ, {"RAG_TEST_THINK": raw}):
                self.assertEqual(reasoning_setting("RAG_TEST_THINK", "low"), expected)
        with patch.dict(os.environ, {"RAG_TEST_THINK": "maybe"}), self.assertRaises(ValueError):
            reasoning_setting("RAG_TEST_THINK", "low")
