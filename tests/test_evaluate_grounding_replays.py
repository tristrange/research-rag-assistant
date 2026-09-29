from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast
import unittest
from unittest.mock import Mock, patch

from app.answer_evaluation import AnswerEvaluationCase, CaseEvaluation, summarize
from app.judge_calibration import CalibrationReport
from scripts.compare_reranking import CorpusSnapshot
from scripts.evaluate_answers import ReportModel, _new_report
from scripts.evaluate_grounding_replays import ComparisonProtocol, evaluate, judge_runtime as inspect_judge_runtime, load_inputs
from scripts.prepare_human_review import ReviewManifest, ReviewSelection, configuration_hash, review_set_hash


class EvaluateReplayTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "evaluation-results").mkdir()
        case = AnswerEvaluationCase(id="control", question="What happened?", answerable=True,
                                    reference_answer="The response increased.", evidence=[
                                        {"document": "paper.pdf", "page": 2, "quote": "response increased"}])
        self.result = CaseEvaluation(
            case=case, answer="The response increased. (paper.pdf, page 2)",
            sources=[{"document": "paper.pdf", "page": 2, "chunk_index": 0,
                      "section": "results", "text": "The response increased."}],
            evidence_found=[True], evidence_recall=1.0, abstained=False,
            judge={"correctness": 2, "completeness": 2, "citation_support": 2, "explanation": "Supported"},
            answer_ms=1.0, judge_ms=1.0, passed=True)
        report = _new_report(datetime.now(timezone.utc),
                             CorpusSnapshot(sha256="corpus", chunks_by_document={"paper.pdf": 1}),
                             [case], "reranked", "reranker", "verified")
        report.update(status="complete", results=[self.result], metrics=summarize([self.result]),
                      calibration={"version": report["calibration_version"], "passed": True,
                                   "results": [{"id": "control", "passed": True,
                                                "expected": {"abstained": False},
                                                "actual": {**self.result["judge"], "abstained": False}}]})
        self.source = self.root / "evaluation-results/source.json"
        self.source.write_text(json.dumps(report))
        self.manifest = ReviewManifest(schema_version=1, purpose="development",
            configuration_sha256=configuration_hash(ReportModel.model_validate(report)), selections=[
                ReviewSelection(id="paper", report="evaluation-results/source.json",
                                sha256=sha256(self.source.read_bytes()).hexdigest(), case_ids=["control"])])
        self.replay: dict[str, object] = dict(
            status="complete", started_at="start", finished_at="finish", source_report=str(self.source),
            corpus=report["corpus"], settings=report["settings"], methodology="Fixed sources",
            results=[dict(case=case, answer=self.result["answer"], sources=self.result["sources"],
                          trace=[], elapsed_ms=10.0)])
        self.path = self.root / "evaluation-results/replay.json"
        self.output = self.root / "evaluation-results/judged.json"
        self.write()
        runtime_patch = patch("scripts.evaluate_grounding_replays.judge_runtime", return_value={"ollama_version": "test"})
        runtime_patch.start()
        self.addCleanup(runtime_patch.stop)
        self.record = self.root / "run.json"
        record = dict(status="complete", server_version={"version": "test"}, models=[dict(name="gpt-oss:20b", digest="a" * 64)],
                      grounding_code_sha256=sha256(Path("app/grounding.py").read_bytes()).hexdigest(),
                      steps=[dict(report=str(self.path), returncode=0)])
        self.record.write_text(json.dumps(record))
        settings = cast(dict[str, object], report["settings"])
        self.protocol = ComparisonProtocol.model_validate(dict(
            schema_version=1, review_set_sha256=review_set_hash(self.manifest),
            ollama_version="test", judge_model="qwen3:8b", judge_digest="c" * 64, candidates=[dict(
                model=settings["verifier_model"], digest="a" * 64,
                draft_think="low", verifier_think="medium",
                grounding_sha256=settings["generator_prompt_sha256"],
            )]))

    def write(self) -> None:
        self.path.write_text(json.dumps(self.replay))

    def test_fixed_sources_are_scored_without_retrieving_or_generating(self) -> None:
        generated, provenance, settings = load_inputs(self.manifest, self.root, [self.path], protocol=self.protocol)
        self.assertEqual(generated[0]["case"]["id"], "paper/control")
        self.assertEqual(generated[0]["answer_ms"], 10.0)
        self.assertEqual(generated[0]["sources"], self.result["sources"])
        self.assertEqual(generated[0]["evidence_found"], [True])
        self.assertEqual(provenance[0]["source_report_sha256"], self.manifest.selections[0].sha256)
        self.assertEqual(settings.answer_mode, "verified")

    def test_changed_passage_or_label_is_rejected(self) -> None:
        for field, changed in [("sources", []), ("case", {**self.result["case"], "reference_answer": "Wrong"})]:
            with self.subTest(field=field):
                original = dict(case=self.result["case"], answer=self.result["answer"],
                                sources=self.result["sources"], trace=[], elapsed_ms=10.0)
                self.replay["results"] = [{**original, field: changed}]
                self.write()
                with self.assertRaisesRegex(ValueError, "changed a question, label, or source"):
                    load_inputs(self.manifest, self.root, [self.path], protocol=self.protocol)

    def test_changed_source_hash_is_rejected(self) -> None:
        self.source.write_text(self.source.read_text() + " ")
        with self.assertRaisesRegex(ValueError, "hash changed"):
            load_inputs(self.manifest, self.root, [self.path], protocol=self.protocol)

    def test_missing_duplicate_or_incomplete_runs_are_rejected(self) -> None:
        for paths in [[], [self.path, self.path]]:
            with self.subTest(paths=paths), self.assertRaises(ValueError):
                load_inputs(self.manifest, self.root, paths, protocol=self.protocol)
        self.replay["status"] = "failed"
        self.write()
        with self.assertRaises(ValueError):
            load_inputs(self.manifest, self.root, [self.path], protocol=self.protocol)

    def test_changed_budget_is_rejected(self) -> None:
        settings = cast(dict[str, object], self.replay["settings"])
        settings["grounding_output_tokens"] = 8192
        self.write()
        with self.assertRaisesRegex(ValueError, "changed frozen setting"):
            load_inputs(self.manifest, self.root, [self.path], protocol=self.protocol)

    def test_existing_output_is_preserved_without_judging(self) -> None:
        self.output.write_text("preserve")
        with patch("scripts.evaluate_grounding_replays.run_calibration") as calibrate, self.assertRaises(ValueError):
            evaluate(self.manifest, self.root, [self.path], self.output, protocol=self.protocol, generation_record=self.record)
        calibrate.assert_not_called()
        self.assertEqual(self.output.read_text(), "preserve")

    def test_calibration_failure_does_not_publish_metrics_or_judge_answers(self) -> None:
        calibration = CalibrationReport(version="2", passed=False, results=[])
        with (patch("scripts.evaluate_grounding_replays.run_calibration", return_value=calibration),
              patch("scripts.evaluate_grounding_replays.judge_case_answer") as judge,
              self.assertRaises(SystemExit)):
            evaluate(self.manifest, self.root, [self.path], self.output, protocol=self.protocol, generation_record=self.record)
        judge.assert_not_called()
        saved = json.loads(self.output.read_text())
        self.assertEqual(saved["status"], "calibration_failed")
        self.assertIsNone(saved["metrics"])
        self.assertEqual(saved["results"], [])

    def test_judge_failure_preserves_input_answers_and_failure_report(self) -> None:
        original = self.path.read_bytes()
        calibration = CalibrationReport(version="2", passed=True, results=[])
        with (patch("scripts.evaluate_grounding_replays.run_calibration", return_value=calibration),
              patch("scripts.evaluate_grounding_replays.judge_case_answer", side_effect=RuntimeError("judge failed")),
              self.assertRaisesRegex(RuntimeError, "judge failed")):
            evaluate(self.manifest, self.root, [self.path], self.output, protocol=self.protocol, generation_record=self.record)
        saved = json.loads(self.output.read_text())
        self.assertEqual(saved["status"], "failed")
        self.assertIsNone(saved["metrics"])
        self.assertEqual(self.path.read_bytes(), original)

    def test_changed_prompt_or_candidate_is_rejected(self) -> None:
        for key, value in [("generator_prompt_sha256", "b" * 64),
                           ("verifier_model", "other-model"), ("generator_think", "false")]:
            with self.subTest(key=key):
                settings = cast(dict[str, object], self.replay["settings"])
                original = settings[key]
                settings[key] = value
                self.write()
                with self.assertRaisesRegex(ValueError, "frozen candidate"):
                    load_inputs(self.manifest, self.root, [self.path], protocol=self.protocol)
                settings[key] = original

    def test_relative_source_paths_use_source_root(self) -> None:
        self.replay["source_report"] = "evaluation-results/source.json"
        self.write()
        generated, _, _ = load_inputs(self.manifest, self.root, [self.path], protocol=self.protocol)
        self.assertEqual(len(generated), 1)

    def test_different_selection_and_judge_are_rejected_before_calls(self) -> None:
        different = self.protocol.model_copy(update={"review_set_sha256": "b" * 64})
        with self.assertRaisesRegex(ValueError, "different frozen selection"):
            load_inputs(self.manifest, self.root, [self.path], protocol=different)
        with (patch("scripts.evaluate_grounding_replays.JUDGE_MODEL", "other-judge"),
              patch("scripts.evaluate_grounding_replays.run_calibration") as calibrate,
              self.assertRaisesRegex(ValueError, "judge differs")):
            evaluate(self.manifest, self.root, [self.path], self.output, protocol=self.protocol, generation_record=self.record)
        calibrate.assert_not_called()
        self.assertFalse(self.output.exists())

    def test_wrong_generation_identity_is_rejected_before_judging(self) -> None:
        record = json.loads(self.record.read_text())
        record["models"][0]["digest"] = "b" * 64
        self.record.write_text(json.dumps(record))
        with (patch("scripts.evaluate_grounding_replays.run_calibration") as calibrate,
              self.assertRaisesRegex(ValueError, "attest the frozen model")):
            evaluate(self.manifest, self.root, [self.path], self.output, protocol=self.protocol,
                     generation_record=self.record)
        calibrate.assert_not_called()
        self.assertFalse(self.output.exists())

    def test_runtime_check_rejects_changed_judge_digest(self) -> None:
        version = Mock()
        version.json.return_value = {"version": "test"}
        tags = Mock()
        tags.json.return_value = {"models": [{"name": "qwen3:8b", "digest": "wrong"}]}
        with (patch("scripts.evaluate_grounding_replays.httpx.get", side_effect=[version, tags]),
              self.assertRaisesRegex(ValueError, "installed judge/runtime")):
            inspect_judge_runtime(self.protocol)

    def test_runtime_change_during_grading_preserves_grades_without_metrics(self) -> None:
        calibration = CalibrationReport(version="2", passed=True, results=[])
        with (patch("scripts.evaluate_grounding_replays.run_calibration", return_value=calibration),
              patch("scripts.evaluate_grounding_replays.judge_case_answer", return_value=self.result),
              patch("scripts.evaluate_grounding_replays.judge_runtime", side_effect=[{"version": "one"}, {"version": "two"}]),
              self.assertRaisesRegex(ValueError, "changed while grading")):
            evaluate(self.manifest, self.root, [self.path], self.output, protocol=self.protocol,
                     generation_record=self.record)
        saved = json.loads(self.output.read_text())
        self.assertEqual(saved["status"], "failed")
        self.assertEqual(len(saved["results"]), 1)
        self.assertIsNone(saved["metrics"])
