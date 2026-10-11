"""Drafts select sources; approved evidence text stays application-owned."""

import json
import unittest
from typing import cast
from unittest.mock import patch

from pydantic import ValidationError

from app.grounding import (
    GroundedDraft, INSUFFICIENT_EVIDENCE, _bounded_draft_schema, _validate_draft,
    build_verifier_evidence, grounded_answer,
)
from app.types import AnswerClaim, ChunkData


class DraftSourceTests(unittest.TestCase):
    def test_draft_and_repair_prompts_match_the_bounded_api_schema(self) -> None:
        sources = [ChunkData(document="study.pdf", page=1, chunk_index=0, text="First result."),
                   ChunkData(document="blank.pdf", page=2, chunk_index=0, text="  "),
                   ChunkData(document="study.pdf", page=3, chunk_index=0, text="Third result.")]
        malformed = {"answerable": True, "claims": [{
            "text": "Result.", "attribution": "this_document_authors", "source_ids": [1],
        }]}
        with patch("app.grounding.generate_json", side_effect=[
            malformed, {"answerable": False, "claims": []},
        ]) as model:
            self.assertEqual(grounded_answer("What happened?", sources), INSUFFICIENT_EVIDENCE)
        self.assertEqual(model.call_count, 2)
        for call in model.call_args_list:
            prompt, api_schema = call.args
            schema_text = prompt.split("Response shape JSON schema:\n", 1)[1].split("\n\n", 1)[0]
            prompt_schema = json.loads(schema_text)
            self.assertEqual(prompt_schema, api_schema)
            citations = prompt_schema["$defs"]["ClaimCitation"]["anyOf"]
            self.assertEqual([item["properties"]["source_id"]["const"] for item in citations], [1, 3])
            for item in citations:
                self.assertEqual(item["required"], ["source_id"])
                self.assertFalse(item["additionalProperties"])

    def test_source_only_draft_preserves_exact_approved_text_and_locations(self) -> None:
        question = "What happened?"
        sources = [ChunkData(document="unused.pdf", page=1, chunk_index=0, text="We measured uptake."),
                   ChunkData(document="study.pdf", page=4, chunk_index=0,
                             text="Insulin\u2011stimulated uptake was un- changed.")]
        draft = {"answerable": True, "claims": [{
            "text": "Insulin-stimulated uptake was unchanged.", "attribution": "this_document_authors",
            "citations": [{"source_id": 1}, {"source_id": 2}],
        }]}
        verdict = {
            "requirements": [{"requirement": "Uptake result", "supported": True,
                              "reason": "Supported.", "supporting_evidence_ids": [2]}],
            "requested_answer": {"status": "supported", "question_excerpt": question,
                                 "reason": "Supported.", "supporting_evidence_ids": [2]},
            "answers_question": True, "reason": "Supported.",
            "verdicts": [{"claim_index": 1, "supported": True, "correct_attribution": True,
                          "relevant": True, "reason": "Supported.", "supporting_evidence_ids": [2]}],
        }
        evidence: list[AnswerClaim] = []
        expected = [{"source_index": 1, "quote": sources[1]["text"]}]
        for capture in (None, evidence):
            with self.subTest(capture=capture), patch("app.grounding.generate_json", side_effect=[
                draft, verdict, {"supported": True, "reason": "Complete proof."},
            ]) as model:
                answer = grounded_answer(question, sources, claim_evidence=capture)
            self.assertEqual(answer, "Insulin-stimulated uptake was unchanged. (study.pdf, page 4)")
            proof = json.loads(model.call_args_list[2].args[0].split("Untrusted input JSON:\n", 1)[1])
            self.assertEqual(proof["claims"][0]["citations"], expected)
            if capture is not None:
                self.assertEqual(capture[0]["citations"], expected)
            self.assertNotIn("unused.pdf", answer)

    def test_draft_cannot_supply_evidence_text_or_select_an_empty_source(self) -> None:
        source = ChunkData(document="study.pdf", page=1, chunk_index=0, text="Exact result.")
        draft = {"answerable": True, "claims": [{
            "text": "Result.", "attribution": "this_document_authors", "citations": [{"source_id": 1}],
        }]}
        parsed = GroundedDraft.model_validate(draft)
        _validate_draft(parsed, [source])
        self.assertEqual(build_verifier_evidence(parsed.claims, [source])[0]["quote"], source["text"])
        citation = cast(list[dict[str, object]], cast(list[dict[str, object]], draft["claims"])[0]["citations"])[0]
        citation["quote"] = "Fabricated evidence."
        with self.assertRaises(ValidationError):
            GroundedDraft.model_validate(draft)
        citation.pop("quote")
        blank = ChunkData(document="blank.pdf", page=1, chunk_index=0, text="  ")
        with self.assertRaises(ValueError):
            _validate_draft(parsed, [blank])
        schema = _bounded_draft_schema([blank, source])
        variants = cast(dict[str, dict[str, object]], schema["$defs"])["ClaimCitation"]["anyOf"]
        self.assertEqual(variants, [{"type": "object", "additionalProperties": False,
                                    "properties": {"source_id": {"type": "integer", "const": 2}},
                                    "required": ["source_id"]}])


if __name__ == "__main__":
    unittest.main()
