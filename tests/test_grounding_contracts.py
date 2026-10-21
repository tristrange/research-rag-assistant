"""Characterization tests for the public grounding contract.

Each fixture pins the observable result of ``grounded_answer`` for a synthetic,
license-safe question and one ordered script of model calls. The script is
replayed at ``app.grounding.generate_json``, the single model boundary, so the
recorded SHA-256 digests cover the exact prompt and schema every stage sends,
including the generated proof prompt. These are the contract assertions the
grounding module extraction must preserve; see ``docs/architecture.md``.
"""

import hashlib
import json
import unittest
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

from app.grounding import (
    GROUNDING_CONTRACT_VERSION,
    INSUFFICIENT_EVIDENCE,
    grounded_answer,
)
from app.llm.ollama import OllamaOutputLimitError
from app.types import AnswerClaim, ChunkData

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "grounding_contracts" / "cases.json"
DIGESTS_PATH = (
    Path(__file__).parent / "fixtures" / "grounding_contracts" / "call_digests.json"
)
ERRORS = {"OllamaOutputLimitError": OllamaOutputLimitError}


class _Script:
    """Replay the scripted model calls in order and record what the model saw."""

    def __init__(self, model_calls: list[dict[str, Any]]) -> None:
        self.model_calls = model_calls
        self.digests: list[str] = []

    def __call__(
        self, prompt: str, schema: dict[str, object], **kwargs: object
    ) -> dict[str, object]:
        if not self.model_calls:
            raise AssertionError("unexpected model call")
        self.digests.append(_digest(prompt, schema))
        item = self.model_calls.pop(0)
        if "error" in item:
            raise ERRORS[str(item["error"])]("scripted model call failure")
        return cast(dict[str, object], item["json"])


def _digest(prompt: str, schema: dict[str, object]) -> str:
    """Hash the model-facing prompt and schema so a byte change fails the case."""
    payload = json.dumps(
        {"prompt": prompt, "schema": schema}, sort_keys=True, ensure_ascii=False
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def load_sources(case: dict[str, Any]) -> list[ChunkData]:
    sources: list[ChunkData] = []
    for raw in cast(list[dict[str, Any]], case["sources"]):
        source = ChunkData(
            document=str(raw["document"]),
            page=int(raw["page"]),
            chunk_index=int(raw["chunk_index"]),
            text=str(raw["text"]),
        )
        if "section" in raw:
            source["section"] = str(raw["section"])
        sources.append(source)
    return sources


class GroundingContractTests(unittest.TestCase):
    def test_fixture_cases_pin_public_grounding_contract(self) -> None:
        payload = load_json(FIXTURE_PATH)
        self.assertEqual(payload["contract_version"], GROUNDING_CONTRACT_VERSION)
        cases = cast(list[dict[str, Any]], payload["cases"])
        self.assertTrue(cases)
        digests = cast(dict[str, list[str]], load_json(DIGESTS_PATH)["cases"])
        for case in cases:
            with self.subTest(case=case["name"]):
                self.run_case(case, digests.get(str(case["name"])))

    def run_case(
        self,
        case: dict[str, Any],
        expected_digests: list[str] | None,
    ) -> None:
        sources = load_sources(case)
        script = _Script(list(cast(list[dict[str, Any]], case["model_calls"])))
        trace: list[dict[str, object]] = []
        claim_evidence: list[AnswerClaim] = []
        expected = cast(dict[str, Any], case["expected"])

        with patch("app.grounding.generate_json", script):
            if "error" in expected:
                with self.assertRaises(ERRORS[str(expected["error"])]):
                    grounded_answer(
                        case["question"],
                        sources,
                        trace=trace,
                        claim_evidence=claim_evidence,
                    )
            else:
                answer = grounded_answer(
                    case["question"],
                    sources,
                    trace=trace,
                    claim_evidence=claim_evidence,
                )
                if expected["refused"]:
                    self.assertEqual(answer, INSUFFICIENT_EVIDENCE)
                else:
                    self.assertEqual(answer, expected["answer"])

        self.assertEqual([entry["stage"] for entry in trace], expected["trace_stages"])
        self.assertEqual(claim_evidence, expected["claim_evidence"])
        self.assertEqual(
            script.digests,
            expected_digests,
            f"{case['name']}: model prompt/schema bytes changed. "
            f"Recorded digests: {json.dumps(script.digests)}",
        )
        self.assertEqual(
            script.model_calls,
            [],
            f"{case['name']}: fixture declared unused model responses",
        )
