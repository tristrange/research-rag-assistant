"""Characterization tests for the public grounding contract.

Each fixture pins the observable result of ``grounded_answer`` for a synthetic,
license-safe question and a fixed sequence of model responses. These are the
contract assertions the grounding module extraction must preserve; see
``docs/architecture.md``.
"""

import hashlib
import json
import unittest
from contextlib import ExitStack
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
    """Replay one stage and record the exact prompt/schema arguments."""

    def __init__(self, stage: str, responses: list[dict[str, Any]]) -> None:
        self.stage = stage
        self.responses = responses
        self.digests: list[str] = []

    def __call__(self, *args: object, **kwargs: object) -> dict[str, object]:
        if not self.responses:
            raise AssertionError(f"unexpected {self.stage} model call")
        self.digests.append(_digest(args, kwargs))
        item = self.responses.pop(0)
        if "error" in item:
            raise ERRORS[str(item["error"])](f"scripted {self.stage} failure")
        return cast(dict[str, object], item["json"])


def _digest(args: tuple[object, ...], kwargs: dict[str, object]) -> str:
    """Hash the model-facing prompt and schema so a byte change fails the case."""
    payload = json.dumps(
        {"args": args, "kwargs": kwargs}, sort_keys=True, ensure_ascii=False
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_payload() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(FIXTURE_PATH.read_text(encoding="utf-8")))


def load_digests() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(DIGESTS_PATH.read_text(encoding="utf-8")))


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
        payload = load_payload()
        self.assertEqual(payload["contract_version"], GROUNDING_CONTRACT_VERSION)
        cases = cast(list[dict[str, Any]], payload["cases"])
        self.assertTrue(cases)
        digests = cast(dict[str, dict[str, list[str]]], load_digests()["cases"])
        for case in cases:
            with self.subTest(case=case["name"]):
                self.run_case(case, digests.get(str(case["name"])))

    def run_case(
        self,
        case: dict[str, Any],
        expected_digests: dict[str, list[str]] | None,
    ) -> None:
        sources = load_sources(case)
        responses = cast(dict[str, list[dict[str, Any]]], case["responses"])
        scripts = {
            stage: _Script(stage, list(responses.get(stage, [])))
            for stage in ("draft", "verification", "proof")
        }
        trace: list[dict[str, object]] = []
        claim_evidence: list[AnswerClaim] = []
        expected = cast(dict[str, Any], case["expected"])

        with ExitStack() as stack:
            stack.enter_context(
                patch("app.grounding.generate_draft_json", scripts["draft"])
            )
            stack.enter_context(
                patch(
                    "app.grounding.generate_verification_json",
                    scripts["verification"],
                )
            )
            stack.enter_context(
                patch(
                    "app.grounding.generate_approved_proof_json",
                    scripts["proof"],
                )
            )
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
        recorded = {stage: script.digests for stage, script in scripts.items()}
        self.assertEqual(
            recorded,
            expected_digests,
            f"{case['name']}: model prompt/schema bytes changed. "
            f"Recorded digests: {json.dumps(recorded, sort_keys=True)}",
        )
        for stage, script in scripts.items():
            self.assertEqual(
                script.responses,
                [],
                f"{case['name']}: fixture declared unused {stage} responses",
            )
