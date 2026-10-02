from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast
import unittest
from unittest.mock import patch

from pydantic import ValidationError

from app.answer_evaluation import (
    AnswerEvaluationCase,
    CaseEvaluation,
    GeneratedCaseAnswer,
    generate_case_answer,
    judge_case_answer,
    judge_prompt,
    summarize,
)
from app.llm.telemetry import ModelCall, RuntimeSnapshot, observe_call
from app.types import AnswerClaim, AnswerResult, ChunkData
from scripts.compare_reranking import CorpusSnapshot
from scripts.evaluate_answers import (
    AcceptedClaimModel,
    CompletedResultModel,
    EVALUATOR_PROMPT_SHA256,
    GeneratedAnswerModel,
    ReportModel,
    _new_report,
    validate_resume_consistency,
    validate_runtime,
)
from scripts.evaluate_grounding_replays import (
    ComparisonProtocol,
    CompletedReplay,
    load_inputs,
)
from scripts.prepare_human_review import (
    ReviewManifest,
    ReviewSelection,
    _case_html,
    configuration_hash,
    review_set_hash,
)


CASE = AnswerEvaluationCase(
    id="case-1",
    question="What happened?",
    answerable=True,
    reference_answer="The response increased.",
    evidence=[{"document": "paper.pdf", "page": 1, "quote": "response increased"}],
)
SOURCE: ChunkData = {
    "document": "paper.pdf",
    "page": 1,
    "chunk_index": 0,
    "section": "results",
    "text": "The response increased by 12 percent.",
}
CLAIM: AnswerClaim = {
    "text": "The response increased by 12 percent.",
    "attribution": "this_document_authors",
    "citations": [{"source_index": 0, "quote": "response   increased by 12 percent."}],
}
CORPUS = CorpusSnapshot(sha256="corpus-fixture", chunks_by_document={"paper.pdf": 1})
ANSWER_CALL = ModelCall(
    operation="chat", requested_model="answer-fixture", response_model="answer-fixture",
    elapsed_ms=2.0, status="complete", eval_count=12,
)
JUDGE_CALL = ModelCall(
    operation="chat", requested_model="judge-fixture", response_model="judge-fixture",
    elapsed_ms=1.0, status="complete", done_reason="stop",
)


def generated_answer(*, claim_evidence: list[AnswerClaim] | None = None) -> GeneratedCaseAnswer:
    generated: GeneratedCaseAnswer = {
        "case": CASE,
        "answer": "The response increased by 12 percent.",
        "sources": [SOURCE],
        "evidence_found": [True],
        "evidence_recall": 1.0,
        "answer_ms": 2.0,
        "claim_evidence": claim_evidence,
        "answer_calls": [ANSWER_CALL.model_dump()],
    }
    return generated


def judged_fixture(generated: GeneratedCaseAnswer) -> CaseEvaluation:
    return judge_case_answer(generated, lambda _prompt, schema: {
        "abstained": False,
        "explanation": "A substantive answer was given.",
    } if schema.get("title") == "AbstentionDecision" else {
        "correctness": 2,
        "completeness": 2,
        "citation_support": 2,
        "abstained": False,
        "explanation": "The answer matches the evidence.",
    })


def runtime(version: str | None = "0.7.1", digest: str | None = "a" * 64) -> RuntimeSnapshot:
    return RuntimeSnapshot(ollama_version=version, model_digests={"answer-fixture:latest": digest})


def report_dict(
    *, schema_version: int = 3,
    status: str = "running",
    pending: dict[str, object] | None = None,
    runtime_before: RuntimeSnapshot | None = None,
) -> dict[str, object]:
    report = _new_report(
        datetime(2026, 10, 1, tzinfo=timezone.utc), CORPUS, [CASE],
        "reranked", "fixture-reranker", "verified", runtime=runtime_before,
    )
    report["schema_version"] = schema_version
    report["status"] = status
    report["pending"] = pending
    return report


def complete_report(result: CaseEvaluation, *, runtime_before: RuntimeSnapshot | None = None) -> dict[str, object]:
    report = report_dict(runtime_before=runtime_before)
    report.update({
        "status": "complete",
        "finished_at": "2026-10-01T00:01:00+00:00",
        "results": [result],
        "metrics": summarize([result]),
        "calibration": {
            "version": report["calibration_version"],
            "passed": True,
            "results": [{
                "id": "fixture-calibration",
                "passed": True,
                "expected": {"correctness": [2], "abstained": False},
                "actual": {**result["judge"], "abstained": result["abstained"]},
            }],
        },
    })
    return report


class ReportProvenanceTests(unittest.TestCase):
    def test_schema_two_legacy_missing_fields_remain_unknown_and_schema_three_empty_is_known(self) -> None:
        legacy_pending: dict[str, object] = {
            "case": CASE,
            "answer": "The response increased by 12 percent.",
            "sources": [SOURCE],
            "evidence_found": [True],
            "evidence_recall": 1.0,
            "answer_ms": 2.0,
        }
        legacy = ReportModel.model_validate(report_dict(schema_version=2, pending=legacy_pending))
        self.assertEqual(legacy.schema_version, 2)
        self.assertIsNone(legacy.pending.claim_evidence if legacy.pending else None)
        self.assertIsNone(legacy.pending.answer_calls if legacy.pending else None)
        self.assertIsNone(legacy.runtime_before)

        captured_pending = legacy_pending | {"claim_evidence": [], "answer_calls": []}
        current = ReportModel.model_validate(report_dict(schema_version=3, pending=captured_pending))
        self.assertEqual(current.schema_version, 3)
        self.assertEqual(current.pending.claim_evidence if current.pending else None, [])
        self.assertEqual(current.pending.answer_calls if current.pending else None, [])

        generated = GeneratedAnswerModel.model_validate(captured_pending)
        completed = CompletedResultModel.model_validate({
            **captured_pending,
            "abstained": False,
            "judge": {
                "correctness": 2, "completeness": 2, "citation_support": 2,
                "explanation": "Supported.",
            },
            "judge_ms": 1.0,
            "passed": True,
            "judge_calls": [],
        })
        self.assertEqual(generated.claim_evidence, [])
        self.assertEqual(completed.claim_evidence, [])
        self.assertEqual(completed.judge_calls, [])

    def test_claim_citations_validate_source_bounds_and_whitespace_normalized_case_sensitive_quotes(self) -> None:
        accepted = GeneratedAnswerModel.model_validate(generated_answer(claim_evidence=[CLAIM]))
        accepted_claims = accepted.claim_evidence
        if accepted_claims is None:
            self.fail("validated claim evidence should be present")
        self.assertEqual(accepted_claims[0].citations[0].quote, "response   increased by 12 percent.")

        invalid_claims = [
            {**CLAIM, "citations": [{"source_index": 1, "quote": "response increased"}]},
            {**CLAIM, "citations": [{"source_index": 0, "quote": "Response increased"}]},
            {**CLAIM, "citations": []},
        ]
        for claim in invalid_claims:
            with self.subTest(claim=claim), self.assertRaises((ValidationError, ValueError)):
                GeneratedAnswerModel.model_validate(generated_answer(claim_evidence=cast(list[AnswerClaim], [claim])))

        self.assertIsNone(GeneratedAnswerModel.model_validate(generated_answer()).claim_evidence)

    def test_generation_and_judging_capture_calls_without_changing_prompt_fingerprint_or_grading(self) -> None:
        answer_result: AnswerResult = {
            "answer": "The response increased by 12 percent.",
            "sources": [SOURCE],
            "claim_evidence": [CLAIM],
        }

        def answer(_question: str) -> AnswerResult:
            with observe_call("chat", "answer-fixture"):
                pass
            return answer_result

        generated = generate_case_answer(CASE, answer)
        self.assertEqual(generated["claim_evidence"], [CLAIM])
        answer_calls = generated["answer_calls"]
        if answer_calls is None:
            self.fail("captured answer calls should be present")
        self.assertEqual(len(answer_calls), 1)
        self.assertEqual(answer_calls[0]["operation"], "chat")

        expected_prompt = judge_prompt(CASE, {
            "answer": answer_result["answer"], "sources": answer_result["sources"],
        })
        prompts: list[str] = []

        def judge(prompt: str, schema: dict[str, object]) -> dict[str, object]:
            prompts.append(prompt)
            with observe_call("chat", "judge-fixture"):
                pass
            if schema.get("title") == "AbstentionDecision":
                return {"abstained": False, "explanation": "Substantive answer."}
            return {
                "correctness": 2, "completeness": 2, "citation_support": 2,
                "abstained": False, "explanation": "Supported by source.",
            }

        evaluated = judge_case_answer(generated, judge)
        self.assertEqual(prompts[1], expected_prompt)
        self.assertEqual(EVALUATOR_PROMPT_SHA256, "b9c68934238f422d44debca5ab4cc7f1668e961edbad49f93cbfe0a2ec0a3e73")
        self.assertEqual(evaluated["judge"]["correctness"], 2)
        self.assertTrue(evaluated["passed"])
        self.assertEqual(evaluated["claim_evidence"], [CLAIM])
        self.assertEqual(evaluated["answer_calls"], generated["answer_calls"])
        self.assertEqual(len(evaluated["judge_calls"] or []), 2)

    def test_runtime_identity_checks_allow_unknown_only_when_not_resuming(self) -> None:
        before = runtime()
        changed = runtime(version="0.8.0", digest="b" * 64)
        unknown = runtime(version=None, digest=None)
        validate_runtime(before, unknown)
        with self.assertRaisesRegex(ValueError, "identity changed"):
            validate_runtime(before, changed)
        with self.assertRaisesRegex(ValueError, "could not be rechecked"):
            validate_runtime(before, unknown, require_known=True)
        with self.assertRaises(ValidationError):
            RuntimeSnapshot(ollama_version="", model_digests={"model": "bad-digest"})

        saved = ReportModel.model_validate(report_dict(runtime_before=before))
        validate_resume_consistency(
            saved, [CASE], CORPUS, "reranked", "fixture-reranker", "verified", runtime=before,
        )
        with self.assertRaisesRegex(ValueError, "identity changed|rechecked"):
            validate_resume_consistency(
                saved, [CASE], CORPUS, "reranked", "fixture-reranker", "verified", runtime=unknown,
            )

    def test_runtime_before_changes_configuration_hash_but_legacy_hash_does_not(self) -> None:
        legacy = ReportModel.model_validate(report_dict(schema_version=2))
        settings = legacy.settings.model_dump()
        expected_legacy = {
            "settings": settings,
            "generator_model": legacy.generator_model,
            "judge_model": legacy.judge_model,
            "embedding_model": legacy.embedding_model,
            "reranker_model": legacy.reranker_model,
        }
        expected_digest = sha256(json.dumps(expected_legacy, sort_keys=True).encode()).hexdigest()
        self.assertEqual(configuration_hash(legacy), expected_digest)

        with_runtime = ReportModel.model_validate(report_dict(runtime_before=runtime()))
        self.assertNotEqual(configuration_hash(with_runtime), configuration_hash(legacy))

    def test_review_html_escapes_claims_and_distinguishes_unknown_from_no_approved_claims(self) -> None:
        generated = generated_answer(claim_evidence=[{
            "text": "<claim>",
            "attribution": "this_document_authors",
            "citations": [{"source_index": 0, "quote": "<quote>"}],
        }])
        generated["sources"] = [SOURCE | {"text": "A <quote> appears here."}]
        result = judged_fixture(generated)
        completed = CompletedResultModel.model_validate(result)
        html = _case_html("fixture/case-1", completed, 1, "paper.pdf", "file:///paper.pdf")
        self.assertIn("&lt;claim&gt;", html)
        self.assertIn("&lt;quote&gt;", html)
        self.assertNotIn("<claim>", html)
        self.assertNotIn("<quote>", html)

        legacy = CompletedResultModel.model_validate({
            **result, "claim_evidence": None, "answer_calls": None, "judge_calls": None,
        })
        no_claims = CompletedResultModel.model_validate({**result, "claim_evidence": []})
        self.assertIn("Unknown: this report did not capture", _case_html("k", legacy, 1, "paper.pdf", "file:///p"))
        self.assertIn("No claims were approved", _case_html("k", no_claims, 1, "paper.pdf", "file:///p"))

    def test_completed_replay_defaults_old_schema_and_preserves_replay_provenance(self) -> None:
        old = {
            "status": "complete", "started_at": "start", "finished_at": "finish",
            "source_report": "evaluation-results/source.json", "corpus": CORPUS,
            "settings": report_dict()["settings"], "methodology": "Fixed sources",
            "results": [{"case": CASE, "sources": [SOURCE], "trace": [],
                         "answer": "The response increased.", "elapsed_ms": 1.0}],
        }
        legacy_replay = CompletedReplay.model_validate(old)
        self.assertEqual(legacy_replay.schema_version, 1)
        self.assertIsNone(legacy_replay.results[0].claim_evidence)
        self.assertIsNone(legacy_replay.results[0].answer_calls)

        original = judged_fixture(generated_answer(claim_evidence=[CLAIM]))
        original["answer_calls"] = [ANSWER_CALL.model_dump()]
        original["judge_calls"] = [JUDGE_CALL.model_dump()]
        source_report = complete_report(original)

        replay_claim = {
            "text": "Replay says the result increased.",
            "attribution": "this_document_authors",
            "citations": [{"source_index": 0, "quote": "response increased"}],
        }
        replay_call = ModelCall(
            operation="chat", requested_model="replay-model", elapsed_ms=4.0, status="complete",
        ).model_dump()
        with TemporaryDirectory() as directory:
            root = Path(directory)
            results_dir = root / "evaluation-results"
            results_dir.mkdir()
            source_path = results_dir / "source.json"
            source_path.write_text(json.dumps(source_report))
            manifest = ReviewManifest(
                schema_version=1,
                purpose="development",
                configuration_sha256=configuration_hash(ReportModel.model_validate(source_report)),
                selections=[ReviewSelection(
                    id="paper", report="evaluation-results/source.json",
                    sha256=sha256(source_path.read_bytes()).hexdigest(), case_ids=[CASE["id"]],
                )],
            )
            settings = cast(dict[str, object], source_report["settings"])
            protocol = ComparisonProtocol.model_validate({
                "schema_version": 2,
                "review_set_sha256": review_set_hash(manifest),
                "ollama_version": "0.7.1",
                "judge_model": source_report["judge_model"],
                "judge_digest": "c" * 64,
                "grounding_code_sha256": "d" * 64,
                "evaluator_prompt_sha256": EVALUATOR_PROMPT_SHA256,
                "candidates": [{
                    "model": settings["verifier_model"], "digest": "a" * 64,
                    "draft_think": "low", "verifier_think": "medium",
                    "grounding_sha256": settings["generator_prompt_sha256"],
                }],
            })
            replay_data = old | {
                "schema_version": 2,
                "source_report": "evaluation-results/source.json",
                "results": [{
                    "case": CASE, "sources": [SOURCE], "trace": [],
                    "answer": "Replay answer.", "elapsed_ms": 4.0,
                    "claim_evidence": [replay_claim], "answer_calls": [replay_call],
                }],
            }
            replay_path = results_dir / "replay.json"
            replay_path.write_text(json.dumps(replay_data))
            generated, _provenance, _settings = load_inputs(
                manifest, root, [replay_path], protocol=protocol,
            )

        self.assertEqual(generated[0]["claim_evidence"], [replay_claim])
        self.assertEqual(generated[0]["answer_calls"], [replay_call])
        self.assertNotEqual(generated[0]["claim_evidence"], original["claim_evidence"])
        self.assertNotEqual(generated[0]["answer_calls"], original["answer_calls"])


if __name__ == "__main__":
    unittest.main()
