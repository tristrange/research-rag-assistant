import json
import unittest
from copy import deepcopy
from typing import cast
from unittest.mock import patch

import httpx

from app.grounding import (
    DRAFT_SCHEMA, DRAFT_THINK, GROUNDING_CONTEXT_TOKENS, GROUNDING_MODEL,
    GROUNDING_OUTPUT_TOKENS, MAX_QUOTE_CHARS, VERIFIER_THINK, VERIFIER_SCHEMA, GroundedDraft, VerificationResult,
    INSUFFICIENT_EVIDENCE, _bounded_draft_schema, _evidence_spans,
    _normalize_whitespace, build_draft_prompt, build_verifier_prompt,
    build_verifier_evidence, _bounded_verifier_schema, validate_verification_structure,
    generate_draft_json, generate_verification_json, grounded_answer, grounding_fingerprint, verify_draft,
)
from app.config import GroundingSampling
from app.llm.ollama import OllamaOutputLimitError
from app.types import AnswerClaim, ChunkData


SOURCE = ChunkData(document="paper.pdf", page=10, chunk_index=2,
                   section="references", text="Asp et al. Treatment delayed weight loss.")
DRAFT: dict[str, object] = {
    "answerable": True,
    "claims": [{"text": "The cited treatment delayed weight loss.",
                "attribution": "external_publication",
                "citations": [{"source_id": 1, "quote": "Treatment delayed weight loss."}]}],
}
def approved(question: str = "What did the cited study report?") -> dict[str, object]:
    requested_answer = {
        "status": "supported", "question_excerpt": question,
        "supporting_evidence_ids": [2], "reason": "Established by source.",
    }
    return {
        "requirements": [{"requirement": "Requested finding", "supported": True,
                          "reason": "Established by source."}],
        "requested_answer": requested_answer, "answers_question": True,
        "reason": "The requested fact is supported.",
        "verdicts": [{"claim_index": 1, "reason": "Evidence assessment.",
                      "supported": True, "correct_attribution": True,
                      "relevant": True, "supporting_evidence_ids": [2]}],
    }


APPROVED = approved()


def first_citation(draft: dict[str, object]) -> dict[str, object]:
    claims = cast(list[dict[str, object]], draft["claims"])
    citations = cast(list[dict[str, object]], claims[0]["citations"])
    return citations[0]


class GroundingTests(unittest.TestCase):
    def test_display_evidence_uses_verifier_selections_and_exact_source_indexes(self) -> None:
        source = ChunkData(document="study.pdf", page=2, chunk_index=7, section="results",
                           text="Ten mice received treatment. Treatment delayed weight loss.")
        draft = deepcopy(DRAFT)
        first_citation(draft)["source_id"] = 2
        verdict = approved()
        cast(dict[str, object], verdict["requested_answer"])["supporting_evidence_ids"] = [2]
        cast(list[dict[str, object]], verdict["verdicts"])[0]["supporting_evidence_ids"] = [2, 1]
        evidence: list[AnswerClaim] = []
        with patch("app.grounding.generate_json", side_effect=[draft, verdict]) as model:
            answer = grounded_answer("What did the cited study report?", [SOURCE, source], claim_evidence=evidence)
        self.assertIn("study.pdf, page 2", answer)
        self.assertEqual(model.call_count, 2)
        self.assertEqual(evidence, [{
            "text": "The cited treatment delayed weight loss.", "attribution": "external_publication",
            "citations": [
                {"source_index": 1, "quote": "Treatment delayed weight loss."},
                {"source_index": 1, "quote": "Ten mice received treatment."},
            ],
        }])

    def test_only_accepted_repair_exposes_evidence(self) -> None:
        evidence: list[AnswerClaim] = []
        with patch("app.grounding.generate_json", side_effect=[{}, DRAFT, APPROVED]):
            answer = grounded_answer("What did the cited study report?", [SOURCE], claim_evidence=evidence)
        self.assertNotEqual(answer, INSUFFICIENT_EVIDENCE)
        self.assertEqual(evidence[0]["citations"], [{"source_index": 0, "quote": "Treatment delayed weight loss."}])

    def test_display_evidence_binds_reordered_verdicts_to_their_claims(self) -> None:
        source = ChunkData(document="study.pdf", page=2, chunk_index=0,
                           text="Treatment reduced body mass. Glucose uptake was unchanged.")
        draft = {"answerable": True, "claims": [
            {"text": "Treatment reduced body mass.", "attribution": "this_document_authors",
             "citations": [{"source_id": 1, "quote": "Treatment reduced body mass."}]},
            {"text": "Glucose uptake was unchanged.", "attribution": "this_document_authors",
             "citations": [{"source_id": 1, "quote": "Glucose uptake was unchanged."}]},
        ]}
        question = "What happened to body mass and glucose uptake?"
        verdict = approved(question)
        first = cast(list[dict[str, object]], verdict["verdicts"])[0]
        verdict["verdicts"] = [
            {**first, "claim_index": 2, "supporting_evidence_ids": [2]},
            {**first, "claim_index": 1, "supporting_evidence_ids": [1]},
        ]
        cast(dict[str, object], verdict["requested_answer"])["supporting_evidence_ids"] = [1, 2]
        evidence: list[AnswerClaim] = []
        with patch("app.grounding.generate_json", side_effect=[draft, verdict]):
            grounded_answer(question, [source], claim_evidence=evidence)
        self.assertEqual([claim["citations"][0]["quote"] for claim in evidence],
                         ["Treatment reduced body mass.", "Glucose uptake was unchanged."])

    def test_refusals_and_rejected_drafts_never_expose_claim_evidence(self) -> None:
        rejected = deepcopy(APPROVED)
        rejected["answers_question"] = False
        for responses in [
            [{"answerable": False, "claims": []}],
            [DRAFT, rejected, {"answerable": False, "claims": []}],
            [{}, {},],
        ]:
            evidence: list[AnswerClaim] = [{"text": "Old claim", "attribution": "this_document_authors", "citations": []}]
            with self.subTest(responses=responses), patch("app.grounding.generate_json", side_effect=responses):
                self.assertEqual(grounded_answer("What did the cited study report?", [SOURCE], claim_evidence=evidence), INSUFFICIENT_EVIDENCE)
            self.assertEqual(evidence, [])

    @staticmethod
    def approval_for_single_span(question: str) -> dict[str, object]:
        result = approved(question)
        cast(dict[str, object], result["requested_answer"])["supporting_evidence_ids"] = [1]
        cast(list[dict[str, object]], result["verdicts"])[0]["supporting_evidence_ids"] = [1]
        return result

    def test_inference_settings_change_grounding_fingerprint(self) -> None:
        original = grounding_fingerprint()
        for setting, value in [
            ("GROUNDING_SAMPLING", GroundingSampling(temperature=0.6, top_k=20)),
            ("GROUNDING_DRAFT_TIMEOUT_SECONDS", 450.0),
            ("GROUNDING_VERIFIER_TIMEOUT_SECONDS", 450.0),
            ("GROUNDING_OUTPUT_TOKENS", 2048),
        ]:
            with self.subTest(setting=setting), patch(f"app.grounding.{setting}", value):
                self.assertNotEqual(grounding_fingerprint(), original)

    def test_budget_exhaustion_propagates_without_repair_or_safe_refusal(self) -> None:
        for responses, expected_calls in [
            ([OllamaOutputLimitError("budget exhausted")], 1),
            ([DRAFT, OllamaOutputLimitError("budget exhausted")], 2),
        ]:
            with self.subTest(expected_calls=expected_calls), patch(
                "app.grounding.generate_json", side_effect=responses,
            ) as model, self.assertRaises(OllamaOutputLimitError):
                grounded_answer("What did the cited study report?", [SOURCE])
            self.assertEqual(model.call_count, expected_calls)

    def test_repair_and_verification_share_explicit_sampling_and_timeouts(self) -> None:
        with patch("app.grounding.GROUNDING_SAMPLING", GroundingSampling(temperature=0.6, top_k=20)), patch(
            "app.grounding.GROUNDING_DRAFT_TIMEOUT_SECONDS", 450.0,
        ), patch("app.grounding.GROUNDING_VERIFIER_TIMEOUT_SECONDS", 240.0), patch(
            "app.grounding.generate_json", side_effect=[{}, DRAFT, APPROVED],
        ) as model:
            result = grounded_answer("What did the cited study report?", [SOURCE])
        self.assertIn("delayed weight loss", result)
        self.assertEqual(model.call_count, 3)
        self.assertEqual([call.kwargs["timeout_seconds"] for call in model.call_args_list], [450.0, 450.0, 240.0])
        for call in model.call_args_list:
            self.assertEqual(call.kwargs["sampling"], {"temperature": 0.6, "top_k": 20})

    def test_grounding_calls_use_explicit_model_and_reasoning_settings(self) -> None:
        with patch("app.grounding.generate_json", return_value={}) as model:
            generate_draft_json("Draft", {})
            generate_verification_json("Verify", {})
        self.assertEqual(model.call_count, 2)
        self.assertEqual(model.call_args_list[0].kwargs, {
            "think": DRAFT_THINK, "model": GROUNDING_MODEL,
            "num_ctx": GROUNDING_CONTEXT_TOKENS, "num_predict": GROUNDING_OUTPUT_TOKENS,
            "sampling": {"temperature": 1.0, "top_p": 1.0}, "timeout_seconds": 300.0,
        })
        self.assertEqual(model.call_args_list[1].kwargs, {
            "think": VERIFIER_THINK, "model": GROUNDING_MODEL,
            "num_ctx": GROUNDING_CONTEXT_TOKENS, "num_predict": GROUNDING_OUTPUT_TOKENS,
            "sampling": {"temperature": 1.0, "top_p": 1.0}, "timeout_seconds": 300.0,
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
        with patch("app.grounding.generate_json", side_effect=[draft, self.approval_for_single_span("How many times?")]):
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
            verdict = approved("Question")
            cast(list[dict[str, object]], verdict["verdicts"])[0][field] = False
            with self.subTest(field=field), patch(
                "app.grounding.generate_json",
                side_effect=[DRAFT, verdict, {"answerable": False, "claims": []}],
            ):
                self.assertEqual(grounded_answer("Question", [SOURCE]), INSUFFICIENT_EVIDENCE)

    def test_incomplete_duplicated_wrong_index_or_malformed_verdict_fails_closed(self) -> None:
        good = cast(list[dict[str, object]], approved("Question")["verdicts"])[0]
        cases = [
            {**approved("Question"), "verdicts": []},
            {**approved("Question"), "verdicts": [good, good]},
            {**approved("Question"), "verdicts": [{**good, "claim_index": 2}]},
            {**approved("Question"), "answers_question": False},
            {**approved("Question"), "verdicts": [{**good, "supported": "true"}]},
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
        with patch("app.grounding.generate_json", side_effect=[DRAFT, approved("Question")]):
            grounded_answer("Question", [SOURCE], trace=trace)
        self.assertEqual([entry["stage"] for entry in trace], ["draft", "verification"])
        self.assertEqual(trace[1]["output"], approved("Question"))
        self.assertIn("evidence_catalogue", trace[1])

    def test_present_but_non_catalogue_quotes_cannot_bypass_generation_schema(self) -> None:
        for quote in ["Treatment", "Treatment  delayed weight loss."]:
            with self.subTest(quote=quote):
                invalid = GroundedDraft.model_validate(DRAFT).model_dump()
                invalid["claims"][0]["citations"][0]["quote"] = quote
                with patch("app.grounding.generate_json", side_effect=[invalid, invalid]) as model:
                    self.assertEqual(grounded_answer("Question", [SOURCE]), INSUFFICIENT_EVIDENCE)
                self.assertEqual(model.call_count, 2)

    def test_unsupported_question_requirement_overrides_positive_claim_verdict(self) -> None:
        question = "What happened in female mice?"
        verdict = approved(question)
        cast(list[dict[str, object]], verdict["requirements"]).append({
            "requirement": "Female mice", "supported": False,
            "reason": "The source only establishes male mice.",
        })
        draft = GroundedDraft.model_validate(DRAFT)
        with patch("app.grounding.generate_json", return_value=verdict):
            self.assertFalse(verify_draft(question, draft, [SOURCE]))
        with patch("app.grounding.generate_json", side_effect=[DRAFT, verdict, DRAFT, verdict]):
            self.assertEqual(grounded_answer(question, [SOURCE]), INSUFFICIENT_EVIDENCE)

    def test_missing_requirements_or_full_question_check_fail_closed(self) -> None:
        for field in ["requested_answer", "requirements"]:
            verdict = approved("At what dose did treatment delay weight loss?")
            del verdict[field]
            with self.subTest(field=field):
                self.assertFalse(verify_draft(
                    "At what dose did treatment delay weight loss?",
                    GroundedDraft.model_validate(DRAFT), [SOURCE],
                    verifier=lambda _prompt, _schema: verdict,
                ))

    def test_evidence_and_question_anchors_are_validated_before_acceptance(self) -> None:
        question = "At what dose did treatment delay weight loss?"
        base = approved(question)
        cases: list[dict[str, object]] = []
        for update in cast(list[dict[str, object]], [
            {"supporting_evidence_ids": []}, {"supporting_evidence_ids": [999]},
            {"supporting_evidence_ids": [2, 2]}, {"question_excerpt": "What effect did treatment have?"},
            {"question_excerpt": "dose"}, {"question_excerpt": ""},
            {"question_excerpt": " \n"}, {"question_excerpt": None},
            {"status": "not_requested"}, {"extra": True},
        ]):
            verdict = deepcopy(base)
            cast(dict[str, object], verdict["requested_answer"]).update(update)
            cases.append(verdict)
        for update in cast(list[dict[str, object]], [
            {"requirement": None}, {"supported": "true"}, {"category": "dose"},
        ]):
            verdict = deepcopy(base)
            cast(list[dict[str, object]], verdict["requirements"])[0].update(update)
            cases.append(verdict)
        for requirements in cast(list[object], [None, False, {}, [], "Not requested"]):
            verdict = deepcopy(base)
            verdict["requirements"] = requirements
            cases.append(verdict)
        for ids in [[], [999], [2, 2]]:
            verdict = deepcopy(base)
            cast(list[dict[str, object]], verdict["verdicts"])[0]["supporting_evidence_ids"] = ids
            cases.append(verdict)
        for verdict in cases:
            with self.subTest(verdict=verdict):
                self.assertFalse(verify_draft(question, GroundedDraft.model_validate(DRAFT), [SOURCE],
                                            verifier=lambda _prompt, _schema: verdict))

    def test_full_question_cannot_borrow_an_unclaimed_measurement(self) -> None:
        question = "By what percentage did total fat mass decrease?"
        source = ChunkData(document="paper.pdf", page=1, chunk_index=0,
                           text="Total fat mass decreased by 35%. Regional tissue weight decreased by 24%.")
        draft_data = {
            "answerable": True,
            "claims": [{"text": "Regional tissue weight decreased by 24%.",
                        "attribution": "this_document_authors",
                        "citations": [{"source_id": 1,
                                       "quote": "Regional tissue weight decreased by 24%."}]}],
        }
        verdict = approved(question)
        cast(dict[str, object], verdict["requested_answer"])["supporting_evidence_ids"] = [1]
        draft = GroundedDraft.model_validate(draft_data)
        # Both IDs exist in the cited source, but coverage must come from the answer's claims.
        validate_verification_structure(question, VerificationResult.model_validate(verdict),
                                        draft.claims, [source])
        self.assertFalse(verify_draft(question, draft, [source],
                                     verifier=lambda _p, _s: verdict))
        with patch("app.grounding.generate_json",
                   side_effect=[draft_data, verdict, draft_data, verdict]) as model:
            self.assertEqual(grounded_answer(question, [source]), INSUFFICIENT_EVIDENCE)
        self.assertEqual(model.call_count, 4)

    def test_full_question_gate_rejects_when_sparse_requirements_omit_a_requested_detail(self) -> None:
        question = "At what dose did treatment delay weight loss?"
        verdict = approved(question)
        cast(dict[str, object], verdict["requested_answer"]).update(
            status="unsupported", supporting_evidence_ids=[], reason="The dose was not reported.",
        )
        self.assertFalse(verify_draft(question, GroundedDraft.model_validate(DRAFT), [SOURCE],
                                     verifier=lambda _p, _s: verdict))

    def test_valid_negative_verdict_is_structurally_complete_but_not_accepted(self) -> None:
        question = "At what dose did treatment delay weight loss?"
        draft = GroundedDraft.model_validate(DRAFT)
        for evidence_ids in [[], [2]]:
            verdict = approved(question)
            cast(dict[str, object], verdict["requested_answer"]).update(
                status="unsupported", supporting_evidence_ids=evidence_ids,
            )
            verdict["requirements"] = [{"requirement": "Requested dose", "supported": False,
                                        "reason": "The title does not report a dose."}]
            with self.subTest(evidence_ids=evidence_ids):
                result = VerificationResult.model_validate(verdict)
                validate_verification_structure(question, result, draft.claims, [SOURCE])
                self.assertFalse(verify_draft(question, draft, [SOURCE], verifier=lambda _p, _s: verdict))

    def test_evidence_catalogue_includes_scope_sentences_only_from_cited_sources(self) -> None:
        source = ChunkData(document="study.pdf", page=1, chunk_index=0, section="results",
                           text="We studied male mice. Uptake increased.")
        extra = ChunkData(document="other.pdf", page=1, chunk_index=0, text="Female mice.")
        draft = GroundedDraft.model_validate({"answerable": True, "claims": [{
            "text": "Uptake increased.", "attribution": "this_document_authors",
            "citations": [{"source_id": 1, "quote": "Uptake increased."}],
        }]})
        evidence = build_verifier_evidence(draft.claims, [source, extra])
        self.assertEqual(evidence, [
            {"evidence_id": 1, "claim_indexes": [1], "source_id": 1, "quote": "We studied male mice."},
            {"evidence_id": 2, "claim_indexes": [1], "source_id": 1, "quote": "Uptake increased."},
        ])
        question = "How did uptake change in male mice?"
        verdict = approved(question)
        cast(list[dict[str, object]], verdict["requirements"]).append({
            "requirement": "Male mice", "supported": True,
            "reason": "The studied population was male.",
        })
        self.assertTrue(verify_draft(question, draft, [source, extra], verifier=lambda _p, _s: verdict))

    def test_claims_citing_the_same_source_share_evidence_ids(self) -> None:
        draft = GroundedDraft.model_validate(DRAFT)
        draft.claims.append(draft.claims[0].model_copy())
        verdict = approved("Question")
        cast(list[dict[str, object]], verdict["verdicts"]).append({
            "claim_index": 2, "supported": True, "correct_attribution": True, "relevant": True,
            "supporting_evidence_ids": [2], "reason": "Both claims cite the same source.",
        })
        self.assertTrue(verify_draft("Question", draft, [SOURCE], verifier=lambda _p, _s: verdict))
        evidence = build_verifier_evidence(draft.claims, [SOURCE])
        self.assertEqual(len(evidence), 2)
        self.assertTrue(all(entry["claim_indexes"] == [1, 2] for entry in evidence))

    def test_identical_quotes_from_other_sources_cannot_be_borrowed(self) -> None:
        other = ChunkData(document="another.pdf", page=7, chunk_index=0,
                          section="references", text=SOURCE["text"])
        draft = GroundedDraft.model_validate(DRAFT)
        second = draft.claims[0].model_copy(deep=True)
        second.citations[0].source_id = 2
        draft.claims.append(second)
        verdict = approved("Question")
        cast(list[dict[str, object]], verdict["verdicts"]).append({
            "claim_index": 2, "supported": True, "correct_attribution": True, "relevant": True,
            "supporting_evidence_ids": [2], "reason": "Wrong source despite identical wording.",
        })
        self.assertFalse(verify_draft("Question", draft, [SOURCE, other], verifier=lambda _p, _s: verdict))
        cast(list[dict[str, object]], verdict["verdicts"])[1]["supporting_evidence_ids"] = [4]
        self.assertTrue(verify_draft("Question", draft, [SOURCE, other], verifier=lambda _p, _s: verdict))
        evidence = build_verifier_evidence(draft.claims, [SOURCE, other])
        self.assertEqual([entry["source_id"] for entry in evidence], [1, 1, 2, 2])
        self.assertEqual(evidence[1]["quote"], evidence[3]["quote"])
        self.assertNotEqual(evidence[1]["evidence_id"], evidence[3]["evidence_id"])

    def test_multiclaim_methods_answer_accepts_shared_ids_without_repair(self) -> None:
        question = "How long were mice fasted, and when was glucose measured?"
        source = ChunkData(document="methods.pdf", page=2, chunk_index=0, section="methods",
                           text="Mice were fasted for six hours. Glucose was measured at 0, 15 and 30 minutes.")
        draft = {"answerable": True, "claims": [
            {"text": "Mice were fasted for six hours.", "attribution": "this_document_authors",
             "citations": [{"source_id": 1, "quote": "Mice were fasted for six hours."}]},
            {"text": "Glucose was measured at 0, 15 and 30 minutes.", "attribution": "this_document_authors",
             "citations": [{"source_id": 1, "quote": "Glucose was measured at 0, 15 and 30 minutes."}]},
        ]}
        verdict = approved(question)
        cast(dict[str, object], verdict["requested_answer"])["supporting_evidence_ids"] = [1, 2]
        verdicts = cast(list[dict[str, object]], verdict["verdicts"])
        verdicts[0]["supporting_evidence_ids"] = [1]
        verdicts.append({"claim_index": 2, "supported": True, "correct_attribution": True,
                         "relevant": True, "supporting_evidence_ids": [2], "reason": "Source specifies timing."})
        trace: list[dict[str, object]] = []
        with patch("app.grounding.generate_json", side_effect=[draft, verdict]) as model:
            answer = grounded_answer(question, [source], trace=trace)
        self.assertEqual(model.call_count, 2)
        self.assertIn("six hours", answer)
        self.assertIn("0, 15 and 30", answer)
        self.assertEqual([entry["stage"] for entry in trace], ["draft", "verification"])

    def test_shared_source_ids_are_stable_across_claim_and_citation_order(self) -> None:
        other = ChunkData(document="other.pdf", page=1, chunk_index=0, section="results", text="Uptake increased.")
        draft = GroundedDraft.model_validate(DRAFT)
        second = draft.claims[0].model_copy(deep=True)
        second.citations[0].source_id = 2
        second.citations[0].quote = other["text"]
        draft.claims.append(second)
        first = build_verifier_evidence(draft.claims, [SOURCE, other])
        reordered = build_verifier_evidence(list(reversed(draft.claims)), [SOURCE, other])
        def identities(entries: list[dict[str, object]]) -> list[tuple[object, object, object]]:
            return [(entry["evidence_id"], entry["source_id"], entry["quote"]) for entry in entries]
        self.assertEqual(identities(cast(list[dict[str, object]], first)),
                         identities(cast(list[dict[str, object]], reordered)))
        draft.claims[0].citations.append(draft.claims[0].citations[0].model_copy())
        self.assertEqual(build_verifier_evidence(draft.claims, [SOURCE, other]), first)

    def test_whole_question_anchor_allows_normalized_whitespace(self) -> None:
        verdict = approved("What did the cited study report?")
        self.assertTrue(verify_draft("What did  the cited study\nreport?", GroundedDraft.model_validate(DRAFT),
                                     [SOURCE], verifier=lambda _p, _s: verdict))

    def test_whole_question_anchor_supports_api_maximum_question_length(self) -> None:
        question = "Q" * 2000
        self.assertTrue(verify_draft(question, GroundedDraft.model_validate(DRAFT), [SOURCE],
                                     verifier=lambda _p, _s: approved(question)))

    def test_verifier_sees_only_cited_passages(self) -> None:
        draft = GroundedDraft.model_validate(DRAFT)
        extra = ChunkData(document="other.pdf", page=3, chunk_index=0, text="Uncited secret detail.")
        prompt = build_verifier_prompt("Question", draft.claims, [SOURCE, extra])
        self.assertIn(SOURCE["text"], prompt)
        self.assertNotIn(extra["text"], prompt)

    def test_one_rejected_claim_prevents_partial_answer(self) -> None:
        draft = GroundedDraft.model_validate(DRAFT)
        draft.claims.append(draft.claims[0].model_copy())
        verdict = approved("Question")
        cast(list[dict[str, object]], verdict["verdicts"]).append({
            "claim_index": 2, "reason": "Evidence assessment.", "supported": False,
            "correct_attribution": True, "relevant": True, "supporting_evidence_ids": [],
        })
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

    def test_verifier_schema_limits_evidence_ids_and_preserves_global_schema(self) -> None:
        baseline = deepcopy(VERIFIER_SCHEMA)
        draft = GroundedDraft.model_validate(DRAFT)
        first = _bounded_verifier_schema("Question", draft.claims, [SOURCE])
        second = _bounded_verifier_schema("Question", draft.claims, [SOURCE])
        self.assertIsNot(first, second)
        definitions = cast(dict[str, dict[str, object]], first["$defs"])
        self.assertEqual(definitions["QuestionRequirement"],
                         cast(dict[str, object], baseline["$defs"])["QuestionRequirement"])
        for name in ["ClaimVerdict", "RequestedAnswerCoverage"]:
            variants = cast(list[dict[str, object]], definitions[name]["anyOf"])
            self.assertEqual(len(variants), 2)
            for variant in variants:
                properties = cast(dict[str, dict[str, object]], variant["properties"])
                self.assertEqual(properties["supporting_evidence_ids"]["items"],
                                 {"type": "integer", "enum": [1, 2]})
                state = properties["supported" if name == "ClaimVerdict" else "status"]["const"]
                if state is True or state == "supported":
                    self.assertEqual(properties["supporting_evidence_ids"]["minItems"], 1)
                if name == "RequestedAnswerCoverage":
                    self.assertEqual(properties["question_excerpt"], {"type": "string", "const": "Question"})
        self.assertEqual(VERIFIER_SCHEMA, baseline)
        with self.assertRaises(ValueError):
            _bounded_verifier_schema("Question", [], [])
        with self.assertRaises(ValueError):
            _bounded_verifier_schema(" \n", draft.claims, [SOURCE])

    def test_verifier_prompt_exposes_response_shape_before_input(self) -> None:
        draft = GroundedDraft.model_validate(DRAFT)
        prompt = build_verifier_prompt("Question", draft.claims, [SOURCE])
        schema_text = prompt.split("Response shape JSON schema:\n", 1)[1].split(
            "\n\nVerification input JSON:", 1)[0]
        self.assertEqual(json.loads(schema_text),
                         _bounded_verifier_schema("Question", draft.claims, [SOURCE]))
        payload = json.loads(prompt.split("Verification input JSON:\n", 1)[1])
        self.assertEqual(payload["question"], "Question")
        self.assertEqual(payload["claims"][0]["eligible_evidence_ids"], [1, 2])

    def test_verifier_schema_binds_each_claim_to_only_its_cited_sources(self) -> None:
        other = ChunkData(document="other.pdf", page=1, chunk_index=0,
                          section="references", text="A separate study reported improved uptake.")
        draft = GroundedDraft.model_validate(DRAFT)
        second = draft.claims[0].model_copy(deep=True)
        second.citations[0].source_id = 2
        second.citations[0].quote = other["text"]
        draft.claims.append(second)
        schema = _bounded_verifier_schema("Question", draft.claims, [SOURCE, other])
        definitions = cast(dict[str, dict[str, object]], schema["$defs"])
        variants = cast(list[dict[str, object]], definitions["ClaimVerdict"]["anyOf"])
        self.assertEqual(len(variants), 4)
        for variant in variants:
            props = cast(dict[str, dict[str, object]], variant["properties"])
            index = props["claim_index"]["const"]
            self.assertEqual(props["supporting_evidence_ids"]["items"],
                             {"type": "integer", "enum": [1, 2] if index == 1 else [3]})
        prompt = build_verifier_prompt("Question", draft.claims, [SOURCE, other])
        self.assertIn('"eligible_evidence_ids": [1, 2]', prompt)
        self.assertIn('"eligible_evidence_ids": [3]', prompt)
        # A supported full-question assessment can combine evidence across claims.
        for variant in cast(list[dict[str, object]], definitions["RequestedAnswerCoverage"]["anyOf"]):
            props = cast(dict[str, dict[str, object]], variant["properties"])
            self.assertEqual(props["supporting_evidence_ids"]["items"],
                             {"type": "integer", "enum": [1, 2, 3]})

    def test_verifier_preserves_original_reasoning_shape_and_appends_full_question_check(self) -> None:
        draft = GroundedDraft.model_validate(DRAFT)
        schema = _bounded_verifier_schema("Question", draft.claims, [SOURCE])
        self.assertEqual(list(cast(dict[str, object], schema["properties"])),
                         ["requirements", "answers_question", "reason", "verdicts", "requested_answer"])
        definitions = cast(dict[str, dict[str, object]], schema["$defs"])
        requirement = cast(dict[str, dict[str, object]], definitions["QuestionRequirement"]["properties"])
        self.assertEqual(list(requirement), ["requirement", "supported", "reason"])
        self.assertEqual(requirement["requirement"]["maxLength"], 200)
        self.assertEqual(requirement["reason"]["maxLength"], 300)
        for variant in cast(list[dict[str, object]], definitions["ClaimVerdict"]["anyOf"]):
            properties = cast(dict[str, dict[str, object]], variant["properties"])
            self.assertEqual(list(properties), ["claim_index", "supported", "correct_attribution",
                                               "relevant", "reason", "supporting_evidence_ids"])
            self.assertEqual(properties["reason"]["maxLength"], 300)

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
