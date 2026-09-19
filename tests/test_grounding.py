import unittest
from copy import deepcopy
from typing import cast
from unittest.mock import patch

import httpx

from app.grounding import (
    DRAFT_SCHEMA, DRAFT_THINK, GROUNDING_CONTEXT_TOKENS, GROUNDING_MODEL,
    GROUNDING_OUTPUT_TOKENS, MAX_QUOTE_CHARS, VERIFIER_THINK, GroundedDraft,
    INSUFFICIENT_EVIDENCE, _bounded_draft_schema, _evidence_spans,
    _normalize_whitespace, build_draft_prompt, build_verifier_prompt,
    generate_draft_json, generate_verification_json, grounded_answer, verify_draft,
)
from app.types import ChunkData


SOURCE = ChunkData(document="paper.pdf", page=10, chunk_index=2,
                   section="references", text="Asp et al. Treatment delayed weight loss.")
DRAFT: dict[str, object] = {
    "answerable": True,
    "claims": [{"text": "The cited treatment delayed weight loss.",
                "attribution": "external_publication",
                "citations": [{"source_id": 1, "quote": "Treatment delayed weight loss."}]}],
}
APPROVED: dict[str, object] = {
    "requirements": [{"requirement": "Requested finding", "supported": True, "reason": "Established by source."}], "answers_question": True, "reason": "The requested fact is supported.",
    "verdicts": [{"claim_index": 1, "reason": "Evidence assessment.", "supported": True,
                  "correct_attribution": True, "relevant": True}],
}


def first_citation(draft: dict[str, object]) -> dict[str, object]:
    claims = cast(list[dict[str, object]], draft["claims"])
    citations = cast(list[dict[str, object]], claims[0]["citations"])
    return citations[0]


class GroundingTests(unittest.TestCase):
    def test_grounding_calls_use_explicit_model_and_reasoning_settings(self) -> None:
        with patch("app.grounding.generate_json", return_value={}) as model:
            generate_draft_json("Draft", {})
            generate_verification_json("Verify", {})
        self.assertEqual(model.call_count, 2)
        self.assertEqual(model.call_args_list[0].kwargs, {
            "think": DRAFT_THINK, "model": GROUNDING_MODEL,
            "num_ctx": GROUNDING_CONTEXT_TOKENS, "num_predict": GROUNDING_OUTPUT_TOKENS,
        })
        self.assertEqual(model.call_args_list[1].kwargs, {
            "think": VERIFIER_THINK, "model": GROUNDING_MODEL,
            "num_ctx": GROUNDING_CONTEXT_TOKENS, "num_predict": GROUNDING_OUTPUT_TOKENS,
        })

    def test_supported_cited_claim_gets_application_owned_page(self) -> None:
        with patch("app.grounding.generate_json", side_effect=[DRAFT, APPROVED]) as model:
            result = grounded_answer("What did the cited study report?", [SOURCE])
        self.assertEqual(result, "Cited literature: The cited treatment delayed weight loss. (paper.pdf, page 10)")
        self.assertEqual(model.call_count, 2)

    def test_valid_this_document_authors_claim_and_whitespace_quote(self) -> None:
        source = ChunkData(document="methods.pdf", page=2, chunk_index=0,
                           section="methods", text="We measured grip strength\nthree times.")
        draft = {"answerable": True, "claims": [{
            "text": "The authors measured grip strength three times.",
            "attribution": "this_document_authors", "citations": [{
                "source_id": 1, "quote": "We measured grip strength three times.",
            }],
        }]}
        with patch("app.grounding.generate_json", side_effect=[draft, APPROVED]):
            self.assertEqual(grounded_answer("How many times?", [source]),
                             "The authors measured grip strength three times. (methods.pdf, page 2)")

    def test_bad_quotes_ids_and_reference_attribution_get_one_repair_attempt(self) -> None:
        for changes in [
            {"text": "   "},
            {"citations": [{"source_id": 2, "quote": "Treatment delayed weight loss."}]},
            {"citations": [{"source_id": 1, "quote": "Treatment reversed cachexia."}]},
            {"citations": [{"source_id": 1, "quote": "  "}]},
            {"attribution": "this_document_authors"},
            {"text": "The treatment delayed weight loss (page 4)."},
            {"text": "The treatment delayed weight loss [paper.pdf]."},
            {"text": "The treatment delayed weight loss on pages four and five."},
        ]:
            with self.subTest(changes=changes):
                draft = GroundedDraft.model_validate(DRAFT)
                raw = draft.model_dump()
                raw["claims"][0].update(changes)
                unanswerable = {"answerable": False, "claims": []}
                with patch("app.grounding.generate_json", side_effect=[raw, unanswerable]) as model:
                    self.assertEqual(grounded_answer("Question", [SOURCE]), INSUFFICIENT_EVIDENCE)
                self.assertEqual(model.call_count, 2)

    def test_semantic_rejection_discards_whole_answer(self) -> None:
        for field in ["supported", "correct_attribution", "relevant"]:
            verdict = {"requirements": [{"requirement": "Requested finding", "supported": True, "reason": "Established by source."}], "answers_question": True, "reason": "The requested fact is supported.", "verdicts": [{
                "claim_index": 1, "reason": "Evidence assessment.", "supported": True, "correct_attribution": True,
                "relevant": True, field: False,
            }]}
            with self.subTest(field=field), patch(
                "app.grounding.generate_json",
                side_effect=[DRAFT, verdict, {"answerable": False, "claims": []}],
            ):
                self.assertEqual(grounded_answer("Question", [SOURCE]), INSUFFICIENT_EVIDENCE)

    def test_incomplete_duplicated_wrong_index_or_malformed_verdict_fails_closed(self) -> None:
        good = {"claim_index": 1, "reason": "Evidence assessment.", "supported": True, "correct_attribution": True, "relevant": True}
        cases = [
            {"requirements": [{"requirement": "Requested finding", "supported": True, "reason": "Established by source."}], "answers_question": True, "reason": "The requested fact is supported.", "verdicts": []},
            {"requirements": [{"requirement": "Requested finding", "supported": True, "reason": "Established by source."}], "answers_question": True, "reason": "The requested fact is supported.", "verdicts": [good, good]},
            {"requirements": [{"requirement": "Requested finding", "supported": True, "reason": "Established by source."}], "answers_question": True, "reason": "The requested fact is supported.", "verdicts": [{**good, "claim_index": 2}]},
            {"requirements": [{"requirement": "Requested finding", "supported": True, "reason": "Established by source."}], "answers_question": False, "reason": "Missing requested evidence.", "verdicts": [good]},
            {"requirements": [{"requirement": "Requested finding", "supported": True, "reason": "Established by source."}], "answers_question": True, "reason": "The requested fact is supported.", "verdicts": [{**good, "supported": "true"}]},
            {},
        ]
        for verdict in cases:
            with self.subTest(verdict=verdict), patch(
                "app.grounding.generate_json",
                side_effect=[DRAFT, verdict, {"answerable": False, "claims": []}],
            ):
                self.assertEqual(grounded_answer("Question", [SOURCE]), INSUFFICIENT_EVIDENCE)

    def test_model_declared_unanswerability_does_not_repair_or_call_verifier(self) -> None:
        for draft in [{"answerable": False, "claims": []},
                      {**DRAFT, "answerable": False}]:
            with self.subTest(draft=draft), patch("app.grounding.generate_json", return_value=draft) as model:
                self.assertEqual(grounded_answer("Question", [SOURCE]), INSUFFICIENT_EVIDENCE)
                self.assertEqual(model.call_count, 1)

    def test_malformed_draft_gets_one_repair_attempt(self) -> None:
        for draft in [{}, {"answerable": True, "claims": []}]:
            with self.subTest(draft=draft), patch(
                "app.grounding.generate_json",
                side_effect=[draft, {"answerable": False, "claims": []}],
            ) as model:
                self.assertEqual(grounded_answer("Question", [SOURCE]), INSUFFICIENT_EVIDENCE)
                self.assertEqual(model.call_count, 2)

    def test_initial_json_parse_failure_can_be_repaired(self) -> None:
        with patch(
            "app.grounding.generate_json",
            side_effect=[ValueError("invalid JSON"), DRAFT, APPROVED],
        ) as model:
            answer = grounded_answer("What did the cited study report?", [SOURCE])
        self.assertIn("Cited literature:", answer)
        self.assertEqual(model.call_count, 3)
        repair_prompt = model.call_args_list[1].args[0]
        self.assertIn('"previous_draft": null', repair_prompt)
        self.assertIn("invalid JSON", repair_prompt)

    def test_repair_json_parse_failure_fails_closed_without_a_third_attempt(self) -> None:
        invalid = deepcopy(DRAFT)
        first_citation(invalid)["source_id"] = 13
        with patch(
            "app.grounding.generate_json",
            side_effect=[invalid, ValueError("invalid repair JSON")],
        ) as model:
            self.assertEqual(grounded_answer("Question", [SOURCE]), INSUFFICIENT_EVIDENCE)
        self.assertEqual(model.call_count, 2)

    def test_no_sources_skips_model_and_transport_failures_propagate(self) -> None:
        with patch("app.grounding.generate_json") as model:
            self.assertEqual(grounded_answer("Question", []), INSUFFICIENT_EVIDENCE)
            model.assert_not_called()
        for responses in [[httpx.ReadTimeout("offline")], [DRAFT, httpx.ReadTimeout("offline")]]:
            with patch("app.grounding.generate_json", side_effect=responses):
                with self.assertRaises(httpx.ReadTimeout):
                    grounded_answer("Question", [SOURCE])

    def test_transport_failure_during_repair_propagates_without_retry(self) -> None:
        invalid = deepcopy(DRAFT)
        first_citation(invalid)["source_id"] = 13
        with patch(
            "app.grounding.generate_json",
            side_effect=[invalid, httpx.ReadTimeout("repair offline")],
        ) as model, self.assertRaises(httpx.ReadTimeout):
            grounded_answer("Question", [SOURCE])
        self.assertEqual(model.call_count, 2)

    def test_trace_preserves_draft_and_reason_for_deterministic_rejection(self) -> None:
        draft = GroundedDraft.model_validate(DRAFT).model_dump()
        first_citation(draft)["quote"] = "Not in the source"
        trace: list[dict[str, object]] = []
        with patch("app.grounding.generate_json", return_value=draft) as model:
            self.assertEqual(grounded_answer("Question", [SOURCE], trace=trace), INSUFFICIENT_EVIDENCE)
        self.assertEqual(
            [entry["stage"] for entry in trace],
            ["draft", "rejected", "repair_draft", "repair_rejected"],
        )
        self.assertEqual(trace[0]["output"], draft)
        self.assertEqual(model.call_count, 2)

    def test_trace_preserves_semantic_verdict(self) -> None:
        trace: list[dict[str, object]] = []
        with patch("app.grounding.generate_json", side_effect=[DRAFT, APPROVED]):
            grounded_answer("Question", [SOURCE], trace=trace)
        self.assertEqual(trace, [{"stage": "draft", "output": DRAFT},
                                 {"stage": "verification", "output": APPROVED}])

    def test_present_but_non_catalogue_quotes_cannot_bypass_generation_schema(self) -> None:
        for quote in ["Treatment", "Treatment  delayed weight loss."]:
            with self.subTest(quote=quote):
                invalid = GroundedDraft.model_validate(DRAFT).model_dump()
                invalid["claims"][0]["citations"][0]["quote"] = quote
                with patch("app.grounding.generate_json", side_effect=[invalid, invalid]) as model:
                    self.assertEqual(grounded_answer("Question", [SOURCE]), INSUFFICIENT_EVIDENCE)
                self.assertEqual(model.call_count, 2)

    def test_unsupported_question_requirement_overrides_positive_claim_verdict(self) -> None:
        verdict = deepcopy(APPROVED)
        verdict["requirements"] = [{"requirement": "Female mice", "supported": False,
                                    "reason": "The source only establishes male mice."}]
        draft = GroundedDraft.model_validate(DRAFT)
        with patch("app.grounding.generate_json", return_value=verdict):
            self.assertFalse(verify_draft("What happened in female mice?", draft, [SOURCE]))
        with patch("app.grounding.generate_json", side_effect=[DRAFT, verdict, DRAFT, verdict]):
            self.assertEqual(grounded_answer("What happened in female mice?", [SOURCE]), INSUFFICIENT_EVIDENCE)

    def test_verifier_sees_only_cited_passages(self) -> None:
        draft = GroundedDraft.model_validate(DRAFT)
        extra = ChunkData(document="other.pdf", page=3, chunk_index=0, text="Uncited secret detail.")
        prompt = build_verifier_prompt("Question", draft.claims, [SOURCE, extra])
        self.assertIn(SOURCE["text"], prompt)
        self.assertNotIn(extra["text"], prompt)

    def test_one_rejected_claim_prevents_partial_answer(self) -> None:
        draft = GroundedDraft.model_validate(DRAFT)
        draft.claims.append(draft.claims[0].model_copy())
        verdict = {"requirements": [{"requirement": "Requested finding", "supported": True, "reason": "Established by source."}], "answers_question": True, "reason": "The requested fact is supported.", "verdicts": [
            {"claim_index": 1, "reason": "Evidence assessment.", "supported": True, "correct_attribution": True, "relevant": True},
            {"claim_index": 2, "reason": "Evidence assessment.", "supported": False, "correct_attribution": True, "relevant": True},
        ]}
        with patch("app.grounding.generate_json", return_value=verdict):
            self.assertFalse(verify_draft("Question", draft, [SOURCE]))

    def test_invalid_id_and_dehyphenated_quote_are_repaired_and_fully_verified(self) -> None:
        bad_id = deepcopy(DRAFT)
        first_citation(bad_id)["source_id"] = 13
        split_source = ChunkData(
            document="paper.pdf", page=10, chunk_index=2, section="references",
            text="Asp et al. Treatment delayed weight-\nloss.",
        )
        bad_quote = deepcopy(DRAFT)
        first_citation(bad_quote)["quote"] = "Treatment delayed weight loss."
        repaired_quote = deepcopy(DRAFT)
        first_citation(repaired_quote)["quote"] = "Treatment delayed weight- loss."
        for initial, repaired, source in [
            (bad_id, DRAFT, SOURCE),
            (bad_quote, repaired_quote, split_source),
        ]:
            with self.subTest(initial=initial), patch(
                "app.grounding.generate_json", side_effect=[initial, repaired, APPROVED],
            ) as model:
                result = grounded_answer("What did the cited study report?", [source])
                self.assertIn("Cited literature:", result)
                self.assertEqual(model.call_count, 3)
                repair_prompt = model.call_args_list[1].args[0]
                self.assertIn("previous_draft", repair_prompt)
                self.assertIn("rejection_feedback", repair_prompt)
                self.assertIn("bibliography labels, not source IDs", repair_prompt)

    def test_semantically_rejected_draft_can_be_repaired_once(self) -> None:
        rejected = deepcopy(APPROVED)
        rejected["answers_question"] = False
        rejected["reason"] = "The draft omitted the requested comparison."
        trace: list[dict[str, object]] = []
        with patch(
            "app.grounding.generate_json",
            side_effect=[DRAFT, rejected, DRAFT, APPROVED],
        ) as model:
            answer = grounded_answer("What did the cited study report?", [SOURCE], trace=trace)
        self.assertIn("Cited literature:", answer)
        self.assertEqual(model.call_count, 4)
        self.assertEqual(
            [entry["stage"] for entry in trace],
            ["draft", "verification", "rejected", "repair_draft", "repair_verification"],
        )
        repair_prompt = model.call_args_list[2].args[0]
        self.assertIn("The draft omitted the requested comparison.", repair_prompt)
        self.assertIn('"answers_question": false', repair_prompt)

    def test_rejected_repair_refuses_without_a_third_attempt(self) -> None:
        rejected = deepcopy(APPROVED)
        rejected["answers_question"] = False
        rejected["reason"] = "The requested fact is still missing."
        with patch(
            "app.grounding.generate_json",
            side_effect=[DRAFT, rejected, DRAFT, rejected],
        ) as model:
            self.assertEqual(
                grounded_answer("What did the cited study report?", [SOURCE]),
                INSUFFICIENT_EVIDENCE,
            )
        self.assertEqual(model.call_count, 4)

    def test_invalid_repair_refuses_without_a_third_attempt(self) -> None:
        invalid = deepcopy(DRAFT)
        first_citation(invalid)["source_id"] = 13
        with patch("app.grounding.generate_json", side_effect=[invalid, invalid]) as model:
            self.assertEqual(grounded_answer("Question", [SOURCE]), INSUFFICIENT_EVIDENCE)
        self.assertEqual(model.call_count, 2)

    def test_evidence_spans_are_exact_normalized_substrings(self) -> None:
        text = "  Alpha  weight-\nloss.\nBeta?   Gamma!  "
        spans = _evidence_spans(text)
        normalized = _normalize_whitespace(text)
        self.assertEqual(spans, ["Alpha weight- loss.", "Beta?", "Gamma!"])
        self.assertTrue(all(span in normalized for span in spans))
        self.assertTrue(all(0 < len(span) <= MAX_QUOTE_CHARS for span in spans))

    def test_long_evidence_span_is_split_contiguously_without_loss(self) -> None:
        text = "".join(f"{index:05d}" for index in range(1604)) + "tail-marker-1234567"
        spans = _evidence_spans(text)
        self.assertEqual([len(span) for span in spans], [MAX_QUOTE_CHARS, MAX_QUOTE_CHARS, 39])
        self.assertEqual("".join(spans), text)

    def test_schema_pairs_original_source_ids_with_source_specific_quote_enums(self) -> None:
        baseline = deepcopy(DRAFT_SCHEMA)
        blank = ChunkData(document="blank.pdf", page=1, chunk_index=0, text="  \n")
        third = ChunkData(document="other.pdf", page=3, chunk_index=0,
                          text="Gamma finding! Delta result.")
        schema = _bounded_draft_schema([SOURCE, blank, third])
        definitions = cast(dict[str, object], schema["$defs"])
        citation = cast(dict[str, object], definitions["ClaimCitation"])
        variants = cast(list[dict[str, object]], citation["anyOf"])
        self.assertEqual(len(variants), 2)
        first_properties = cast(dict[str, dict[str, object]], variants[0]["properties"])
        third_properties = cast(dict[str, dict[str, object]], variants[1]["properties"])
        self.assertEqual(first_properties["source_id"]["const"], 1)
        self.assertEqual(first_properties["quote"]["enum"], _evidence_spans(SOURCE["text"]))
        self.assertEqual(third_properties["source_id"]["const"], 3)
        self.assertEqual(third_properties["quote"]["enum"], _evidence_spans(third["text"]))
        self.assertEqual(DRAFT_SCHEMA, baseline)

        prompt = build_draft_prompt("Question", [SOURCE, blank, third])
        self.assertIn(
            '"evidence_quotes": ["Asp et al.", "Treatment delayed weight loss."]',
            prompt,
        )
        self.assertIn('"evidence_quotes": []', prompt)

    def test_schema_calls_are_fresh_and_do_not_mutate_global_schema(self) -> None:
        baseline = deepcopy(DRAFT_SCHEMA)
        first = _bounded_draft_schema([SOURCE])
        second_source = ChunkData(document="paper.pdf", page=11, chunk_index=0,
                                  text="Jones et al. Another study.")
        second = _bounded_draft_schema([SOURCE, second_source])
        self.assertIsNot(first, second)
        self.assertEqual(DRAFT_SCHEMA, baseline)

    def test_blank_sources_refuse_without_model_or_empty_anyof_schema(self) -> None:
        blank_sources = [
            ChunkData(document="blank.pdf", page=1, chunk_index=0, text=""),
            ChunkData(document="space.pdf", page=2, chunk_index=0, text=" \n\t "),
        ]
        with patch("app.grounding.generate_json") as model:
            self.assertEqual(grounded_answer("Question", blank_sources), INSUFFICIENT_EVIDENCE)
            model.assert_not_called()
        with self.assertRaisesRegex(ValueError, "nonempty source"):
            _bounded_draft_schema(blank_sources)
