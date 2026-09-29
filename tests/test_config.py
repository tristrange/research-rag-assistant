import json
import os
from pathlib import Path
from unittest.mock import patch

from app.config import GroundingSampling, reasoning_setting, resolve_grounding_sampling
import subprocess
import sys
import unittest


class ConfigTests(unittest.TestCase):
    def test_qwen_thinking_profiles_match_recommended_sampling(self) -> None:
        for model, temperature, presence in [("qwen3:8b", 0.6, 0.0), ("qwen3.5:9b", 1.0, 1.5),
                                             ("registry.example/library/qwen3:8b", 0.6, 0.0)]:
            for draft, verifier in [(True, True), (True, False), (False, True)]:
                with self.subTest(model=model, draft=draft, verifier=verifier):
                    self.assertEqual(resolve_grounding_sampling(model, draft, verifier, GroundingSampling()).options(),
                                     {"temperature": temperature, "top_p": 0.95, "top_k": 20, "min_p": 0.0,
                                      "presence_penalty": presence, "repeat_penalty": 1.0})

    def test_nonthinking_and_other_models_keep_existing_sampling(self) -> None:
        cases: list[tuple[str, bool | str, bool | str]] = [
            ("qwen3:8b", False, False), ("qwen3.5:9b", False, False),
            ("gpt-oss:20b", "low", "medium"), ("qwen3-coder:30b", True, True), ("custom:qwen3", True, True),
        ]
        for model, draft, verifier in cases:
            with self.subTest(model=model):
                self.assertEqual(resolve_grounding_sampling(model, draft, verifier, GroundingSampling()).options(),
                                 {"temperature": 0.0})

    def test_partial_override_inherits_profile_and_explicit_zero_is_preserved(self) -> None:
        options = resolve_grounding_sampling("qwen3:8b", True, True, GroundingSampling(top_k=10)).options()
        self.assertEqual(options["temperature"], 0.6)
        self.assertEqual(options["top_k"], 10)
        explicit_zero = resolve_grounding_sampling("qwen3.5:9b", True, True, GroundingSampling(temperature=0)).options()
        self.assertEqual(explicit_zero["temperature"], 0.0)

    def test_qwen_model_selection_uses_boolean_thinking_and_records_resolved_settings(self) -> None:
        environment = {k: v for k, v in os.environ.items() if not k.startswith("RAG_")}
        code = "import json; from scripts.evaluate_answers import settings_for; print(json.dumps(settings_for('vector', 'verified', 1)))"
        for model, temperature in [("qwen3:8b", 0.6), ("qwen3.5:9b", 1.0)]:
            result = subprocess.run([sys.executable, "-c", code], cwd=Path(__file__).resolve().parents[1],
                                    env=environment | {"RAG_GROUNDING_MODEL": model}, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            settings = json.loads(result.stdout)
            self.assertEqual(settings["generator_think"], "true")
            self.assertIs(settings["verifier_think"], True)
            self.assertEqual(settings["generator_temperature"], str(temperature))
            self.assertEqual(settings["verifier_temperature"], temperature)
            self.assertEqual(settings["grounding_sampling"]["temperature"], temperature)

    def test_qwen_rejects_named_thinking_levels_at_startup(self) -> None:
        for name in ("RAG_DRAFT_THINK", "RAG_VERIFIER_THINK"):
            result = self.read_settings({"RAG_GROUNDING_MODEL": "qwen3:8b", name: "low"})
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Qwen grounding requires true or false", result.stderr)

    def test_automatic_sampling_reaches_ollama_and_does_not_change_judge(self) -> None:
        environment = {k: v for k, v in os.environ.items() if not k.startswith("RAG_")}
        code = """
import json
from unittest.mock import patch
from app.grounding import generate_draft_json, generate_verification_json
from app.llm.ollama import generate_json
with patch('app.llm.ollama.httpx.post') as post:
    post.return_value.json.return_value = {'message': {'content': '{}'}, 'done_reason': 'stop'}
    generate_draft_json('Draft', {})
    generate_verification_json('Verify', {})
    generate_json('Judge', {})
    print(json.dumps([call.kwargs['json'] for call in post.call_args_list]))
"""
        for model, expected in [("qwen3:8b", 0.6), ("qwen3.5:9b", 1.0)]:
            for overrides, temperature, top_k in [("{}", expected, 20), ('{"top_k":10}', expected, 10),
                                                  ('{"temperature":0}', 0.0, 20)]:
                with self.subTest(model=model, overrides=overrides):
                    result = subprocess.run([sys.executable, "-c", code], cwd=Path(__file__).resolve().parents[1],
                                            env=environment | {"RAG_GROUNDING_MODEL": model, "RAG_GROUNDING_SAMPLING": overrides},
                                            capture_output=True, text=True)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    draft, verifier, judge = json.loads(result.stdout)
                    for request in (draft, verifier):
                        self.assertEqual(request["model"], model)
                        self.assertIs(request["think"], True)
                        self.assertEqual(request["options"]["temperature"], temperature)
                        self.assertEqual(request["options"]["top_k"], top_k)
                    self.assertEqual(judge["options"], {"temperature": 0.0})
                    self.assertIs(judge["think"], False)

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
