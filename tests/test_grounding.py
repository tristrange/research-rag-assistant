import unittest
from unittest.mock import patch

import httpx

from app.grounding import (
    GroundedDraft, INSUFFICIENT_EVIDENCE, build_verifier_prompt,
    grounded_answer, verify_draft,
)
from app.types import ChunkData


SOURCE = ChunkData(document="paper.pdf", page=10, chunk_index=2,
                   section="references", text="Asp et al. Treatment delayed weight loss.")
DRAFT: dict[str, object] = {
    "answerable": True,
    "claims": [{"text": "The cited treatment delayed weight loss.",
                "attribution": "cited_work",
                "citations": [{"source_id": 1, "quote": "Treatment delayed weight loss."}]}],
}
APPROVED: dict[str, object] = {
    "answers_question": True,
    "verdicts": [{"claim_index": 1, "supported": True,
                  "correct_attribution": True, "relevant": True}],
}


class GroundingTests(unittest.TestCase):
    def test_supported_cited_claim_gets_application_owned_page(self) -> None:
        with patch("app.grounding.generate_json", side_effect=[DRAFT, APPROVED]) as model:
            result = grounded_answer("What did the cited study report?", [SOURCE])
        self.assertEqual(result, "Cited literature: The cited treatment delayed weight loss. (paper.pdf, page 10)")
        self.assertEqual(model.call_count, 2)

    def test_valid_current_study_claim_and_whitespace_quote(self) -> None:
        source = ChunkData(document="methods.pdf", page=2, chunk_index=0,
                           section="methods", text="We measured grip strength\nthree times.")
        draft = {"answerable": True, "claims": [{
            "text": "The authors measured grip strength three times.",
            "attribution": "current_study", "citations": [{
                "source_id": 1, "quote": "We measured grip strength three times.",
            }],
        }]}
        with patch("app.grounding.generate_json", side_effect=[draft, APPROVED]):
            self.assertEqual(grounded_answer("How many times?", [source]),
                             "The authors measured grip strength three times. (methods.pdf, page 2)")

    def test_bad_quotes_ids_and_reference_attribution_stop_before_verifier(self) -> None:
        for changes in [
            {"text": "   "},
            {"citations": [{"source_id": 2, "quote": "Treatment delayed weight loss."}]},
            {"citations": [{"source_id": 1, "quote": "Treatment reversed cachexia."}]},
            {"citations": [{"source_id": 1, "quote": "  "}]},
            {"attribution": "current_study"},
            {"text": "The treatment delayed weight loss (page 4)."},
            {"text": "The treatment delayed weight loss [paper.pdf]."},
            {"text": "The treatment delayed weight loss on pages four and five."},
        ]:
            with self.subTest(changes=changes):
                draft = GroundedDraft.model_validate(DRAFT)
                raw = draft.model_dump()
                raw["claims"][0].update(changes)
                with patch("app.grounding.generate_json", return_value=raw) as model:
                    self.assertEqual(grounded_answer("Question", [SOURCE]), INSUFFICIENT_EVIDENCE)
                self.assertEqual(model.call_count, 1)

    def test_semantic_rejection_discards_whole_answer(self) -> None:
        for field in ["supported", "correct_attribution", "relevant"]:
            verdict = {"answers_question": True, "verdicts": [{
                "claim_index": 1, "supported": True, "correct_attribution": True,
                "relevant": True, field: False,
            }]}
            with self.subTest(field=field), patch("app.grounding.generate_json", side_effect=[DRAFT, verdict]):
                self.assertEqual(grounded_answer("Question", [SOURCE]), INSUFFICIENT_EVIDENCE)

    def test_incomplete_duplicated_wrong_index_or_malformed_verdict_fails_closed(self) -> None:
        good = {"claim_index": 1, "supported": True, "correct_attribution": True, "relevant": True}
        cases = [
            {"answers_question": True, "verdicts": []},
            {"answers_question": True, "verdicts": [good, good]},
            {"answers_question": True, "verdicts": [{**good, "claim_index": 2}]},
            {"answers_question": False, "verdicts": [good]},
            {"answers_question": True, "verdicts": [{**good, "supported": "true"}]},
            {},
        ]
        for verdict in cases:
            with self.subTest(verdict=verdict), patch("app.grounding.generate_json", side_effect=[DRAFT, verdict]):
                self.assertEqual(grounded_answer("Question", [SOURCE]), INSUFFICIENT_EVIDENCE)

    def test_invalid_drafts_and_unanswerability_do_not_call_verifier(self) -> None:
        for draft in [{}, {"answerable": True, "claims": []},
                      {"answerable": False, "claims": []},
                      {**DRAFT, "answerable": False}]:
            with self.subTest(draft=draft), patch("app.grounding.generate_json", return_value=draft) as model:
                self.assertEqual(grounded_answer("Question", [SOURCE]), INSUFFICIENT_EVIDENCE)
                self.assertEqual(model.call_count, 1)

    def test_no_sources_skips_model_and_transport_failures_propagate(self) -> None:
        with patch("app.grounding.generate_json") as model:
            self.assertEqual(grounded_answer("Question", []), INSUFFICIENT_EVIDENCE)
            model.assert_not_called()
        for responses in [[httpx.ReadTimeout("offline")], [DRAFT, httpx.ReadTimeout("offline")]]:
            with patch("app.grounding.generate_json", side_effect=responses):
                with self.assertRaises(httpx.ReadTimeout):
                    grounded_answer("Question", [SOURCE])

    def test_verifier_sees_only_cited_passages(self) -> None:
        draft = GroundedDraft.model_validate(DRAFT)
        extra = ChunkData(document="other.pdf", page=3, chunk_index=0, text="Uncited secret detail.")
        prompt = build_verifier_prompt("Question", draft.claims, [SOURCE, extra])
        self.assertIn(SOURCE["text"], prompt)
        self.assertNotIn(extra["text"], prompt)

    def test_one_rejected_claim_prevents_partial_answer(self) -> None:
        draft = GroundedDraft.model_validate(DRAFT)
        draft.claims.append(draft.claims[0].model_copy())
        verdict = {"answers_question": True, "verdicts": [
            {"claim_index": 1, "supported": True, "correct_attribution": True, "relevant": True},
            {"claim_index": 2, "supported": False, "correct_attribution": True, "relevant": True},
        ]}
        with patch("app.grounding.generate_json", return_value=verdict):
            self.assertFalse(verify_draft("Question", draft, [SOURCE]))
