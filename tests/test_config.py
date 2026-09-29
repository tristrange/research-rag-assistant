import json
import os
from pathlib import Path
from unittest.mock import patch

from app.config import GroundingSampling, reasoning_setting
import subprocess
import sys
import unittest


class ConfigTests(unittest.TestCase):
    def test_invalid_inference_overrides_fail_at_startup(self) -> None:
        for name, values in {
            "RAG_GROUNDING_SAMPLING": ['{"temperature": "0.6"}', '{"temperature": -1}', '{"temperature": NaN}',
                                      '{"temperature": 3}', '{"top_p": 0}', '{"top_k": true}',
                                      '{"top_k": 1.5}', '{"min_p": 2}', '{"presence_penalty": 3}',
                                      '{"repeat_penalty": 0}', '{"num_ctx": 100000}', '[]', ''],
            "RAG_GROUNDING_TIMEOUT_SECONDS": ["0", "-1", "nan", "inf", "601", ""],
            "RAG_GROUNDING_OUTPUT_TOKENS": ["0", "-1", "8193", "1.5", ""],
        }.items():
            for value in values:
                with self.subTest(name=name, value=value):
                    result = self.read_settings({name: value})
                    self.assertNotEqual(result.returncode, 0)

    def test_sampling_keeps_defaults_and_accepts_explicit_filters(self) -> None:
        self.assertEqual(GroundingSampling().options(), {"temperature": 0.0})
        self.assertEqual(GroundingSampling.model_validate_json(
            '{"temperature": 0.6, "top_p": 0.95, "top_k": 20, "min_p": 0}'
        ).options(), {"temperature": 0.6, "top_p": 0.95, "top_k": 20, "min_p": 0.0})
        result = self.read_settings({"RAG_GROUNDING_TIMEOUT_SECONDS": "450", "RAG_GROUNDING_OUTPUT_TOKENS": "2048"})
        self.assertEqual(result.returncode, 0, result.stderr)

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
            "postgresql+psycopg://rag@localhost:5432/rag",
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
