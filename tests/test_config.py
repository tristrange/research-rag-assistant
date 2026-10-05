import json
import os
from pathlib import Path
from unittest.mock import patch

from app.config import GroundingSampling, load_settings, reasoning_setting, resolve_grounding_sampling
import subprocess
import sys
import unittest


class ConfigTests(unittest.TestCase):
    def test_load_settings_uses_explicit_mapping_without_process_environment_fallback(self) -> None:
        explicit = {"RAG_GENERATOR_MODEL": "from-mapping"}
        with patch.dict(os.environ, {
            "RAG_GENERATOR_MODEL": "from-process",
            "RAG_GROUNDING_MODEL": "process-grounder",
            "RAG_DATABASE_URL": "postgresql://process:secret@localhost/db",
        }, clear=False):
            settings = load_settings(explicit)

        self.assertEqual(settings.generator_model, "from-mapping")
        self.assertEqual(settings.grounding_model, "gpt-oss:20b")
        self.assertEqual(settings.database_url, "postgresql+psycopg://rag@localhost:5432/rag")

    def test_resolved_settings_do_not_change_when_mapping_or_environment_changes(self) -> None:
        source = {
            "RAG_GENERATOR_MODEL": "first-generator",
            "RAG_GROUNDING_MODEL": "qwen3:8b",
            "RAG_DATABASE_URL": "postgresql://first:secret@localhost/db",
        }
        with patch.dict(os.environ, {"RAG_GENERATOR_MODEL": "process-generator"}, clear=False):
            settings = load_settings(source)
            source["RAG_GENERATOR_MODEL"] = "second-generator"
            source["RAG_GROUNDING_MODEL"] = "second-grounder"
            source["RAG_DATABASE_URL"] = "postgresql://second:secret@localhost/db"
            os.environ["RAG_GENERATOR_MODEL"] = "later-process-generator"

        self.assertEqual(settings.generator_model, "first-generator")
        self.assertEqual(settings.grounding_model, "qwen3:8b")
        self.assertEqual(settings.database_url, "postgresql://first:secret@localhost/db")

    def test_settings_and_nested_sampling_are_immutable_and_options_are_fresh(self) -> None:
        settings = load_settings({
            "RAG_GROUNDING_MODEL": "qwen3:8b",
            "RAG_GROUNDING_SAMPLING": '{"top_k": 12}',
        })
        with self.assertRaises((AttributeError, TypeError)):
            settings.generator_model = "changed"  # type: ignore[misc]
        with self.assertRaises((AttributeError, TypeError, ValueError)):
            settings.grounding_sampling.top_k = 99

        options = settings.grounding_sampling.options()
        options["temperature"] = 1.9
        options["top_k"] = 99
        self.assertEqual(settings.grounding_sampling.options()["temperature"], 0.6)
        self.assertEqual(settings.grounding_sampling.options()["top_k"], 12)

    def test_timeout_properties_follow_stage_thinking_and_explicit_override(self) -> None:
        cases = [
            ({"RAG_DRAFT_THINK": "true", "RAG_VERIFIER_THINK": "false"}, 300, 120),
            ({"RAG_DRAFT_THINK": "low", "RAG_VERIFIER_THINK": "high"}, 300, 300),
            ({"RAG_DRAFT_THINK": "false", "RAG_VERIFIER_THINK": "false"}, 120, 120),
            ({"RAG_DRAFT_THINK": "high", "RAG_VERIFIER_THINK": "false"}, 300, 120),
        ]
        for overrides, draft_timeout, verifier_timeout in cases:
            with self.subTest(overrides=overrides):
                settings = load_settings({"RAG_GROUNDING_MODEL": "custom-model", **overrides})
                self.assertIsNone(settings.grounding_timeout_seconds)
                self.assertEqual(settings.grounding_draft_timeout_seconds, draft_timeout)
                self.assertEqual(settings.grounding_verifier_timeout_seconds, verifier_timeout)

        overridden = load_settings({
            "RAG_GROUNDING_MODEL": "custom-model",
            "RAG_DRAFT_THINK": "false",
            "RAG_VERIFIER_THINK": "high",
            "RAG_GROUNDING_TIMEOUT_SECONDS": "450",
        })
        self.assertEqual(overridden.grounding_timeout_seconds, 450.0)
        self.assertEqual(overridden.grounding_draft_timeout_seconds, 450.0)
        self.assertEqual(overridden.grounding_verifier_timeout_seconds, 450.0)

    def test_database_password_is_excluded_from_settings_repr(self) -> None:
        settings = load_settings({"RAG_DATABASE_URL": "postgresql://alice:secret-password@db/rag"})
        self.assertNotIn("secret-password", repr(settings))

    def test_factories_are_independent_and_resolve_mixed_thinking_profiles(self) -> None:
        first = load_settings({
            "RAG_GROUNDING_MODEL": "qwen3:8b",
            "RAG_DRAFT_THINK": "true",
            "RAG_VERIFIER_THINK": "false",
            "RAG_GROUNDING_SAMPLING": "{}",
        })
        second = load_settings({
            "RAG_GROUNDING_MODEL": "qwen3.5:9b",
            "RAG_DRAFT_THINK": "false",
            "RAG_VERIFIER_THINK": "true",
            "RAG_GROUNDING_SAMPLING": '{"temperature": 0}',
        })
        third = load_settings({
            "RAG_GROUNDING_MODEL": "qwen3:8b",
            "RAG_DRAFT_THINK": "false",
            "RAG_VERIFIER_THINK": "false",
        })

        self.assertEqual(first.grounding_sampling.options()["temperature"], 0.6)
        self.assertEqual(first.grounding_sampling.options()["top_k"], 20)
        self.assertEqual(second.grounding_sampling.options()["temperature"], 0.0)
        self.assertEqual(second.grounding_sampling.options()["top_k"], 20)
        self.assertEqual(third.grounding_sampling.options(), {"temperature": 0.0})
        self.assertEqual(first.grounding_draft_timeout_seconds, 300)
        self.assertEqual(first.grounding_verifier_timeout_seconds, 120)

    def test_nullable_sampling_override_does_not_replace_profile_default(self) -> None:
        missing = load_settings({
            "RAG_GROUNDING_MODEL": "qwen3:8b",
            "RAG_GROUNDING_SAMPLING": "{}",
        })
        explicit_null = load_settings({
            "RAG_GROUNDING_MODEL": "qwen3:8b",
            "RAG_GROUNDING_SAMPLING": '{"top_p": null}',
        })
        self.assertEqual(missing.grounding_sampling.options(), explicit_null.grounding_sampling.options())
        self.assertEqual(explicit_null.grounding_sampling.options()["top_p"], 0.95)

    def test_invalid_inputs_are_rejected_by_settings_factory(self) -> None:
        invalid_inputs = [
            {"RAG_GENERATOR_MODEL": "  "},
            {"RAG_DATABASE_URL": ""},
            {"RAG_DRAFT_THINK": "maybe"},
            {"RAG_GROUNDING_MODEL": "qwen3:8b", "RAG_DRAFT_THINK": "low"},
            {"RAG_GROUNDING_SAMPLING": '{"top_k": true}'},
            {"RAG_GROUNDING_SAMPLING": '{"unexpected": 1}'},
            {"RAG_GROUNDING_TIMEOUT_SECONDS": "invalid"},
            {"RAG_GROUNDING_TIMEOUT_SECONDS": "0"},
            {"RAG_GROUNDING_TIMEOUT_SECONDS": "-1"},
            {"RAG_GROUNDING_OUTPUT_TOKENS": "0"},
            {"RAG_GROUNDING_OUTPUT_TOKENS": "1.5"},
        ]
        for values in invalid_inputs:
            with self.subTest(values=values), self.assertRaises(ValueError):
                load_settings(values)

    def test_missing_timeout_and_explicit_null_sampling_remain_distinct_from_zero(self) -> None:
        absent_timeout = load_settings({"RAG_GROUNDING_MODEL": "custom-model"})
        self.assertIsNone(absent_timeout.grounding_timeout_seconds)
        with self.assertRaises(ValueError):
            load_settings({
                "RAG_GROUNDING_MODEL": "custom-model",
                "RAG_GROUNDING_TIMEOUT_SECONDS": "null",
            })

        zero = load_settings({
            "RAG_GROUNDING_MODEL": "qwen3:8b",
            "RAG_GROUNDING_SAMPLING": '{"temperature": 0}',
        })
        self.assertEqual(zero.grounding_sampling.options()["temperature"], 0.0)

    def test_qwen_thinking_profiles_match_recommended_sampling(self) -> None:
        for model, temperature, presence in [("qwen3:8b", 0.6, 0.0), ("qwen3.5:9b", 1.0, 1.5),
                                             ("registry.example/library/qwen3:8b", 0.6, 0.0)]:
            for draft, verifier in [(True, True), (True, False), (False, True)]:
                with self.subTest(model=model, draft=draft, verifier=verifier):
                    self.assertEqual(resolve_grounding_sampling(model, draft, verifier, GroundingSampling()).options(),
                                     {"temperature": temperature, "top_p": 0.95, "top_k": 20, "min_p": 0.0,
                                      "presence_penalty": presence, "repeat_penalty": 1.0})

    def test_gpt_oss_sampling_profile_and_explicit_overrides(self) -> None:
        for model in ["gpt-oss:20b", "registry.example/library/gpt-oss:20b", "GPT-OSS:120b"]:
            with self.subTest(model=model):
                self.assertEqual(resolve_grounding_sampling(model, "low", "medium", GroundingSampling()).options(),
                                 {"temperature": 1.0, "top_p": 1.0})
                self.assertEqual(resolve_grounding_sampling(model, "low", "medium", GroundingSampling(top_k=10)).options(),
                                 {"temperature": 1.0, "top_p": 1.0, "top_k": 10})
                self.assertEqual(resolve_grounding_sampling(model, "low", "medium", GroundingSampling(temperature=0, top_p=0.8)).options(),
                                 {"temperature": 0.0, "top_p": 0.8})
        self.assertEqual(resolve_grounding_sampling("custom:gpt-oss", "low", "medium", GroundingSampling()).options(),
                         {"temperature": 0.0})

    def test_gpt_oss_automatic_sampling_reaches_stages_and_keeps_judge_settings(self) -> None:
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
        for overrides, temperature, top_k in [("{}", 1.0, None), ('{"top_k":10}', 1.0, 10),
                                              ('{"temperature":0}', 0.0, None)]:
            with self.subTest(overrides=overrides):
                result = subprocess.run([sys.executable, "-c", code], cwd=Path(__file__).resolve().parents[1],
                                        env=environment | {"RAG_GROUNDING_MODEL": "gpt-oss:20b", "RAG_GROUNDING_SAMPLING": overrides},
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                draft, verifier, judge = json.loads(result.stdout)
                for request in [draft, verifier]:
                    self.assertEqual(request["model"], "gpt-oss:20b")
                    self.assertEqual(request["options"]["temperature"], temperature)
                    self.assertEqual(request["options"]["top_p"], 1.0)
                    self.assertEqual(request["options"].get("top_k"), top_k)
                self.assertEqual(draft["think"], "low")
                self.assertEqual(verifier["think"], "medium")
                self.assertEqual(judge["options"], {"temperature": 0.0})
                self.assertIs(judge["think"], False)

    def test_nonthinking_and_other_models_keep_existing_sampling(self) -> None:
        cases: list[tuple[str, bool | str, bool | str]] = [
            ("qwen3:8b", False, False), ("qwen3.5:9b", False, False),
            ("qwen3-coder:30b", True, True), ("custom:qwen3", True, True),
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
