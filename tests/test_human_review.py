import csv
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.answer_evaluation import AnswerEvaluationCase, CaseEvaluation, summarize
from scripts.compare_reranking import CorpusSnapshot
from scripts.evaluate_answers import ReportModel, _new_report
from scripts.prepare_human_review import (
    REVIEW_COLUMNS, ReviewManifest, ReviewSelection, configuration_hash, prepare_packet, summarize_review,
)


class HumanReviewTests(unittest.TestCase):
    def test_legacy_configuration_hash_keeps_unknown_inference_fields_absent(self) -> None:
        raw = json.loads(self.path.read_text())
        for field in ("grounding_sampling", "grounding_draft_timeout_seconds", "grounding_verifier_timeout_seconds"):
            del raw["settings"][field]
        legacy = ReportModel.model_validate(raw)
        original_configuration = {"settings": raw["settings"],
                                  "generator_model": raw["generator_model"], "judge_model": raw["judge_model"],
                                  "embedding_model": raw["embedding_model"], "reranker_model": raw["reranker_model"]}
        self.assertEqual(configuration_hash(legacy), sha256(json.dumps(original_configuration, sort_keys=True).encode()).hexdigest())
        self.assertIsNone(legacy.settings.grounding_sampling)
        self.assertNotEqual(configuration_hash(legacy), self.manifest.configuration_sha256)

    def setUp(self) -> None:
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "evaluation-results").mkdir()
        (self.root / "data").mkdir()
        self.pdf = self.root / "data/paper.pdf"
        self.pdf.write_bytes(b"synthetic PDF fixture")
        case = AnswerEvaluationCase(
            id="control", question="What happened?", answerable=True,
            reference_answer="A synthetic response increased.",
            evidence=[{"document": "paper.pdf", "page": 2, "quote": "Evidence."}],
        )
        result = CaseEvaluation(
            case=case, answer="</pre><script>alert(1)</script>",
            sources=[{"document": "paper.pdf", "page": 2, "chunk_index": 0,
                      "section": "results", "text": "<img src=x onerror=alert(1)>"}],
            evidence_found=[True], evidence_recall=1.0, abstained=False,
            judge={"correctness": 2, "completeness": 2, "citation_support": 2,
                   "explanation": "HIDDEN_JUDGE_SCORE"},
            answer_ms=1.0, judge_ms=1.0, passed=True,
        )
        report = _new_report(datetime.now(timezone.utc),
                             CorpusSnapshot(sha256="corpus", chunks_by_document={"paper.pdf": 1}),
                             [case], "reranked", "reranker", "verified",
                             paper_sha256=sha256(self.pdf.read_bytes()).hexdigest())
        report.update(status="complete", results=[result], metrics=summarize([result]),
                      calibration={"version": report["calibration_version"], "passed": True,
                                   "results": [{"id": "test", "passed": True,
                                                "expected": {"abstained": False},
                                                "actual": {**result["judge"], "abstained": False}}]})
        self.path = self.root / "evaluation-results/report.json"
        self.path.write_text(json.dumps(report))
        self.manifest = ReviewManifest(schema_version=1, purpose="development",
                                      configuration_sha256=configuration_hash(ReportModel.model_validate(report)), selections=[
            ReviewSelection(id="paper", report="evaluation-results/report.json",
                            sha256=sha256(self.path.read_bytes()).hexdigest(), case_ids=["control"]),
        ])
        self.output = self.root / "evaluation-results/packet"

    def prepare(self) -> Path:
        prepare_packet(self.manifest, self.root, self.output)
        return self.output / "review.csv"

    def edit_review(self, decision: str, notes: str = "") -> None:
        path = self.output / "review.csv"
        with path.open(newline="") as handle:
            rows = list(csv.DictReader(handle))
        rows[0].update(decision=decision, notes=notes)
        with path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=REVIEW_COLUMNS)
            writer.writeheader()
            writer.writerows(rows)

    def test_packet_escapes_untrusted_text_and_omits_model_scores(self) -> None:
        csv_path = self.prepare()
        html = (self.output / "packet.html").read_text()
        self.assertNotIn("<script>", html)
        self.assertNotIn("<img ", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn(self.pdf.resolve().as_uri() + "#page=2", html)
        self.assertNotIn("HIDDEN_JUDGE_SCORE", html)
        self.assertEqual(summarize_review(self.manifest, csv_path)["pending"], 1)
        self.assertTrue((self.output / "provenance.json").is_file())

    def test_changed_source_report_is_rejected_before_output_creation(self) -> None:
        self.path.write_text(self.path.read_text() + " ")
        with self.assertRaisesRegex(ValueError, "hash changed"):
            self.prepare()
        self.assertFalse(self.output.exists())

    def test_existing_packet_is_not_overwritten(self) -> None:
        self.prepare()
        self.edit_review("pass")
        before = (self.output / "review.csv").read_bytes()
        with self.assertRaises(FileExistsError):
            self.prepare()
        self.assertEqual((self.output / "review.csv").read_bytes(), before)

    def test_changed_paper_is_rejected_before_output_creation(self) -> None:
        self.pdf.write_bytes(b"different paper version")
        with self.assertRaisesRegex(ValueError, "PDF hash changed"):
            self.prepare()
        self.assertFalse(self.output.exists())

    def test_incomplete_or_plain_reports_are_not_substituted(self) -> None:
        original = self.path.read_text()
        for status, mode in (("failed", "verified"), ("complete", "plain")):
            with self.subTest(status=status, mode=mode):
                report = json.loads(original)
                report["status"] = status
                report["settings"]["answer_mode"] = mode
                if status != "complete":
                    report["metrics"] = None
                self.path.write_text(json.dumps(report))
                self.manifest.selections[0].sha256 = sha256(self.path.read_bytes()).hexdigest()
                with self.assertRaisesRegex(ValueError, "completed verified"):
                    self.prepare()
                self.assertFalse(self.output.exists())

    def test_completed_and_disputed_reviews_are_counted_separately(self) -> None:
        path = self.prepare()
        self.edit_review("pass")
        self.assertEqual(summarize_review(self.manifest, path)["pass"], 1)
        path.write_text("\ufeff" + path.read_text())
        self.assertEqual(summarize_review(self.manifest, path)["pass"], 1)
        path.write_text(path.read_text(encoding="utf-8-sig"))
        self.edit_review("label_issue", "The population is not established by this label.")
        self.assertEqual(summarize_review(self.manifest, path)["label_issue"], 1)
        self.edit_review("needs_fix")
        with self.assertRaisesRegex(ValueError, "requires notes"):
            summarize_review(self.manifest, path)

    def test_other_settings_are_rejected_even_with_a_matching_report_hash(self) -> None:
        report = json.loads(self.path.read_text())
        report["settings"]["top_k"] += 1
        self.path.write_text(json.dumps(report))
        self.manifest.selections[0].sha256 = sha256(self.path.read_bytes()).hexdigest()
        with self.assertRaisesRegex(ValueError, "configuration differs"):
            self.prepare()
        self.assertFalse(self.output.exists())

    def test_review_cannot_be_reused_after_selection_changes(self) -> None:
        path = self.prepare()
        changed = self.manifest.model_copy(deep=True)
        changed.selections[0].sha256 = "0" * 64
        with self.assertRaisesRegex(ValueError, "different frozen selection"):
            summarize_review(changed, path)

    def test_missing_and_duplicate_review_rows_are_rejected(self) -> None:
        path = self.prepare()
        content = path.read_text()
        path.write_text(content.splitlines()[0] + "\n")
        with self.assertRaisesRegex(ValueError, "missing selected cases"):
            summarize_review(self.manifest, path)
        path.write_text(content + content.splitlines()[1] + "\n")
        with self.assertRaisesRegex(ValueError, "duplicate cases"):
            summarize_review(self.manifest, path)

    def test_paths_must_stay_in_ignored_report_directory(self) -> None:
        with self.assertRaisesRegex(ValueError, "output must"):
            prepare_packet(self.manifest, self.root, self.root / "tracked")
        with self.assertRaises(ValueError):
            ReviewSelection(id="paper", report="../report.json", sha256="0" * 64,
                            case_ids=["control"])
