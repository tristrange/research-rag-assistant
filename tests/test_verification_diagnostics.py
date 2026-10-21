import json
import unittest
from typing import cast
from unittest.mock import patch

import httpx

from app.grounding import (
    INSUFFICIENT_EVIDENCE,
    grounded_answer,
    grounding_fingerprint,
)
from app.llm.ollama import OllamaOutputLimitError
from app.llm.telemetry import VerificationTrace
from app.types import ChunkData

SOURCE = ChunkData(
    document="paper.pdf",
    page=10,
    chunk_index=2,
    section="references",
    text=(
        "Asp et al. reported the study. "
        "Treatment delayed weight loss in the zqxsecret cohort."
    ),
)
QUESTION = "What did the cited study report?"
DRAFT: dict[str, object] = {
    "answerable": True,
    "claims": [
        {
            "text": "The cited treatment delayed weight loss.",
            "attribution": "external_publication",
            "citations": [{"source_id": 1}],
        }
    ],
}
UNANSWERABLE: dict[str, object] = {"answerable": False, "claims": []}


def approved() -> dict[str, object]:
    return {
        "requirements": [
            {
                "requirement": "Requested finding",
                "supported": True,
                "reason": "Established by source.",
                "supporting_evidence_ids": [2],
            }
        ],
        "requested_answer": {
            "status": "supported",
            "question_excerpt": QUESTION,
            "supporting_evidence_ids": [2],
            "reason": "Established by source.",
        },
        "answers_question": True,
        "reason": "The requested fact is supported.",
        "verdicts": [
            {
                "claim_index": 1,
                "reason": "Evidence assessment.",
                "supported": True,
                "correct_attribution": True,
                "relevant": True,
                "supporting_evidence_ids": [2],
            }
        ],
    }


PROOF = {"supported": True, "reason": "Complete evidence."}


class VerificationDiagnosticsTests(unittest.TestCase):
    def test_approved_answer_orders_stages_and_excludes_raw_content(self) -> None:
        diagnostics: list[VerificationTrace] = []
        with patch(
            "app.grounding.generate_json",
            side_effect=[DRAFT, approved(), PROOF],
        ):
            answer = grounded_answer(QUESTION, [SOURCE], diagnostics=diagnostics)

        self.assertIn("delayed weight loss", answer)
        self.assertEqual(
            [(item.stage, item.attempt) for item in diagnostics],
            [("draft", 1), ("verification", 1), ("verification_proof", 1)],
        )
        self.assertTrue(all(item.parse_status == "ok" for item in diagnostics))
        self.assertTrue(all(item.reason_category == "none" for item in diagnostics))
        self.assertTrue(
            all(
                item.contract_fingerprint == grounding_fingerprint()
                for item in diagnostics
            )
        )
        self.assertTrue(all(len(item.diagnostic_id) == 32 for item in diagnostics))

        serialized = json.dumps([item.model_dump() for item in diagnostics])
        claim_text = cast(list[dict[str, object]], DRAFT["claims"])[0]["text"]
        for private in (SOURCE["text"], QUESTION, claim_text, "zqxsecret"):
            self.assertNotIn(private, serialized)

    def test_draft_refusal_has_one_stage_and_a_stable_category(self) -> None:
        diagnostics: list[VerificationTrace] = []
        with patch("app.grounding.generate_json", side_effect=[UNANSWERABLE]):
            answer = grounded_answer(QUESTION, [SOURCE], diagnostics=diagnostics)

        self.assertEqual(answer, INSUFFICIENT_EVIDENCE)
        self.assertEqual(
            [(item.stage, item.attempt, item.reason_category) for item in diagnostics],
            [("draft", 1, "draft_unanswerable")],
        )

    def test_malformed_verifier_is_invalid_schema_not_an_evidence_refusal(self) -> None:
        diagnostics: list[VerificationTrace] = []
        with patch(
            "app.grounding.generate_json",
            side_effect=[DRAFT, {}, UNANSWERABLE],
        ):
            answer = grounded_answer(QUESTION, [SOURCE], diagnostics=diagnostics)

        self.assertEqual(answer, INSUFFICIENT_EVIDENCE)
        verification = [item for item in diagnostics if item.stage == "verification"]
        self.assertEqual(len(verification), 1)
        self.assertEqual(verification[0].parse_status, "invalid_schema")
        self.assertEqual(verification[0].reason_category, "schema_mismatch")
        self.assertEqual(
            [item.stage for item in diagnostics],
            ["draft", "verification", "repair_draft"],
        )

    def test_non_object_json_is_a_schema_mismatch_not_malformed_json(self) -> None:
        diagnostics: list[VerificationTrace] = []
        with patch(
            "app.grounding.generate_json",
            side_effect=[
                ValueError("Ollama response JSON is not an object"),
                UNANSWERABLE,
            ],
        ):
            answer = grounded_answer(QUESTION, [SOURCE], diagnostics=diagnostics)

        self.assertEqual(answer, INSUFFICIENT_EVIDENCE)
        self.assertEqual(
            [
                (item.stage, item.parse_status, item.reason_category)
                for item in diagnostics
            ],
            [
                ("draft", "invalid_schema", "schema_mismatch"),
                ("repair_draft", "ok", "repair_unanswerable"),
            ],
        )

    def test_proof_rejection_is_not_reclassified_as_malformed_json(self) -> None:
        diagnostics: list[VerificationTrace] = []
        with patch(
            "app.grounding.generate_json",
            side_effect=[
                DRAFT,
                approved(),
                {"supported": False, "reason": "Does not establish."},
                UNANSWERABLE,
            ],
        ):
            answer = grounded_answer(QUESTION, [SOURCE], diagnostics=diagnostics)

        self.assertEqual(answer, INSUFFICIENT_EVIDENCE)
        proof = [item for item in diagnostics if item.stage == "verification_proof"]
        self.assertEqual(len(proof), 1)
        self.assertEqual(
            (proof[0].parse_status, proof[0].reason_category),
            ("ok", "proof_rejection"),
        )

    def test_malformed_refusal_is_invalid_schema_without_changing_decision(
        self,
    ) -> None:
        malformed = {"answerable": False, "claims": [{"text": "Incomplete."}]}
        diagnostics: list[VerificationTrace] = []
        with patch("app.grounding.generate_json", side_effect=[malformed]) as grounded:
            answer = grounded_answer(QUESTION, [SOURCE], diagnostics=diagnostics)

        self.assertEqual(answer, INSUFFICIENT_EVIDENCE)
        grounded.assert_called_once()
        self.assertEqual(
            [
                (item.stage, item.parse_status, item.reason_category)
                for item in diagnostics
            ],
            [("draft", "invalid_schema", "schema_mismatch")],
        )

    def test_malformed_repair_refusal_is_invalid_schema_without_extra_repair(
        self,
    ) -> None:
        malformed = {"answerable": False, "claims": [{"text": "Incomplete."}]}
        diagnostics: list[VerificationTrace] = []
        with patch(
            "app.grounding.generate_json",
            side_effect=[DRAFT, {}, malformed],
        ) as grounded:
            answer = grounded_answer(QUESTION, [SOURCE], diagnostics=diagnostics)

        self.assertEqual(answer, INSUFFICIENT_EVIDENCE)
        self.assertEqual(grounded.call_count, 3)
        repair = [item for item in diagnostics if item.stage == "repair_draft"]
        self.assertEqual(len(repair), 1)
        self.assertEqual(
            (repair[0].parse_status, repair[0].reason_category),
            ("invalid_schema", "schema_mismatch"),
        )

    def test_structural_draft_rejection_is_classified(self) -> None:
        invalid = {
            "answerable": True,
            "claims": [
                {
                    "text": "The cited treatment delayed weight loss.",
                    "attribution": "external_publication",
                    "citations": [{"source_id": 13}],
                }
            ],
        }
        diagnostics: list[VerificationTrace] = []
        with patch(
            "app.grounding.generate_json",
            side_effect=[invalid, UNANSWERABLE],
        ):
            answer = grounded_answer(QUESTION, [SOURCE], diagnostics=diagnostics)

        self.assertEqual(answer, INSUFFICIENT_EVIDENCE)
        self.assertEqual(
            [item.stage for item in diagnostics],
            ["draft", "draft_validation", "repair_draft"],
        )
        self.assertEqual(diagnostics[1].reason_category, "draft_structure")
        self.assertEqual(diagnostics[1].parse_status, "not_attempted")

    def test_transport_error_is_recorded_and_not_masked(self) -> None:
        diagnostics: list[VerificationTrace] = []
        error = httpx.ReadTimeout("verifier offline")
        with (
            patch("app.grounding.generate_json", side_effect=[DRAFT, error]),
            self.assertRaises(httpx.ReadTimeout) as raised,
        ):
            grounded_answer(QUESTION, [SOURCE], diagnostics=diagnostics)

        self.assertIs(raised.exception, error)
        self.assertEqual(
            (diagnostics[-1].stage, diagnostics[-1].reason_category),
            ("verification", "transport_error"),
        )

    def test_output_limit_records_stage_and_attempt_and_propagates(self) -> None:
        cases: list[tuple[list[object], str, int]] = [
            ([OllamaOutputLimitError("budget exhausted")], "draft", 1),
            ([DRAFT, OllamaOutputLimitError("budget exhausted")], "verification", 1),
            ([{}, OllamaOutputLimitError("budget exhausted")], "repair_draft", 2),
        ]
        for responses, stage, attempt in cases:
            with self.subTest(stage=stage, attempt=attempt):
                diagnostics: list[VerificationTrace] = []
                error = next(
                    item
                    for item in responses
                    if isinstance(item, OllamaOutputLimitError)
                )
                with (
                    patch("app.grounding.generate_json", side_effect=responses),
                    self.assertRaises(OllamaOutputLimitError) as raised,
                ):
                    grounded_answer(QUESTION, [SOURCE], diagnostics=diagnostics)
                self.assertIs(raised.exception, error)
                self.assertEqual(
                    [
                        (item.stage, item.attempt, item.reason_category)
                        for item in diagnostics
                        if item.reason_category == "output_limit"
                    ],
                    [(stage, attempt, "output_limit")],
                )
                self.assertEqual(diagnostics[-1].stage, stage)


if __name__ == "__main__":
    unittest.main()
