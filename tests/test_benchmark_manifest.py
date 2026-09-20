from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import io
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from typing import cast
import unittest
from unittest.mock import patch

import pymupdf
from pydantic import ValidationError

from app.answer_evaluation import AnswerEvaluationCase
from app.judge_calibration import CALIBRATION_VERSION
from scripts.compare_reranking import CorpusSnapshot
from scripts.evaluate_answers import (
    BenchmarkManifest, ReportModel, _new_report, load_benchmark, main,
    validate_resume_consistency,
)


def manifest_data(paper_hash: str) -> dict[str, object]:
    return {
        "schema_version": 1,
        "metadata": {
            "id": "fixture-v1", "title": "Test paper", "authors": ["Test Author"],
            "doi": "10.test/example", "source_url": "https://example.org/paper",
            "license": "CC-BY-4.0", "license_url": "https://creativecommons.org/licenses/by/4.0/",
            "split": "holdout", "document": "fixture.pdf", "paper_sha256": paper_hash,
            "notes": "Synthetic test fixture.",
        },
        "cases": [{"id": "response", "question": "What increased?", "answerable": True,
                   "reference_answer": "The response increased.", "evidence": [
                       {"document": "fixture.pdf", "page": 1, "quote": "response increased"}
                   ]}],
    }


class BenchmarkTests(unittest.TestCase):
    def test_rejects_duplicate_ids_wrong_documents_and_invalid_scope(self) -> None:
        valid = BenchmarkManifest.model_validate(manifest_data("a" * 64))
        for change in ["duplicate", "document", "answerability", "path", "hash"]:
            with self.subTest(change=change):
                value = valid.model_dump()
                if change == "duplicate":
                    value["cases"].append(deepcopy(value["cases"][0]))
                elif change == "document":
                    value["cases"][0]["evidence"][0]["document"] = "other.pdf"
                elif change == "answerability":
                    value["cases"][0]["answerable"] = False
                elif change == "path":
                    value["metadata"]["document"] = "../fixture.pdf"
                else:
                    value["metadata"]["paper_sha256"] = "not-a-hash"
                with self.assertRaises(ValidationError):
                    BenchmarkManifest.model_validate(value)

    def test_pdf_validation_is_offline_and_does_not_write_a_report(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            paper = root / "fixture.pdf"
            with pymupdf.open() as pdf:
                page = pdf.new_page()
                page.insert_text((72, 72), "The response increased.")
                pdf.save(paper)
            manifest = root / "benchmark.json"
            manifest.write_text(json.dumps(manifest_data(sha256(paper.read_bytes()).hexdigest())))
            output = root / "report.json"
            argv = ["evaluate_answers", "--benchmark", str(manifest), "--pdf", str(paper),
                    "--validate-only", "--output", str(output)]
            with patch.object(sys, "argv", argv), patch("scripts.evaluate_answers.snapshot") as snapshot, patch("scripts.evaluate_answers.generate_json") as model, redirect_stdout(io.StringIO()) as printed:
                main()
            snapshot.assert_not_called()
            model.assert_not_called()
            self.assertFalse(output.exists())
            self.assertIn("Validated 1 cases", printed.getvalue())
            # A changed PDF must be rejected before any database access.
            paper.write_bytes(paper.read_bytes() + b"changed")
            with patch.object(sys, "argv", argv), patch("scripts.evaluate_answers.snapshot") as snapshot, self.assertRaisesRegex(ValueError, "fingerprint"):
                main()
            snapshot.assert_not_called()

    def test_unknown_case_is_not_silently_dropped(self) -> None:
        with patch.object(sys, "argv", ["evaluate_answers", "--case", "unknown"]), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            main()

    def test_manifest_requires_explicit_pdf(self) -> None:
        with patch.object(sys, "argv", ["evaluate_answers", "--benchmark", "missing.json"]), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            main()

    def test_custom_provenance_and_judge_model_are_recorded_and_checked_on_resume(self) -> None:
        manifest = BenchmarkManifest.model_validate(manifest_data("a" * 64))
        cases = [cast(AnswerEvaluationCase, c.model_dump()) for c in manifest.cases]
        corpus = CorpusSnapshot(sha256="test-corpus", chunks_by_document={"fixture.pdf": 1})
        with patch("scripts.evaluate_answers.JUDGE_MODEL", "independent-judge:test"):
            report = ReportModel.model_validate(_new_report(
                datetime.now(timezone.utc), corpus, cases, "vector", None,
                paper_sha256=manifest.metadata.paper_sha256, benchmark=manifest.metadata,
            ))
            self.assertEqual(report.judge_model, "independent-judge:test")
            validate_resume_consistency(report, cases, corpus, "vector", None,
                                        paper_sha256="a" * 64, benchmark=manifest.metadata)
            changed = manifest.metadata.model_copy(update={"split": "development"})
            with self.assertRaisesRegex(ValueError, "benchmark"):
                validate_resume_consistency(report, cases, corpus, "vector", None,
                                            paper_sha256="a" * 64, benchmark=changed)
            with self.assertRaisesRegex(ValueError, "paper SHA"):
                validate_resume_consistency(report, cases, corpus, "vector", None,
                                            paper_sha256="b" * 64, benchmark=manifest.metadata)
        with self.assertRaisesRegex(ValueError, "judge model"):
            validate_resume_consistency(report, cases, corpus, "vector", None,
                                        paper_sha256="a" * 64, benchmark=manifest.metadata)

    def test_custom_cli_records_manifest_and_uses_its_document(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            paper = root / "fixture.pdf"
            with pymupdf.open() as pdf:
                page = pdf.new_page()
                page.insert_text((72, 72), "The response increased.")
                pdf.save(paper)
            manifest_path = root / "benchmark.json"
            paper_hash = sha256(paper.read_bytes()).hexdigest()
            manifest_path.write_text(json.dumps(manifest_data(paper_hash)))
            output = root / "report.json"
            failed_calibration = {
                "version": CALIBRATION_VERSION, "passed": False,
                "results": [{"id": "check", "passed": False,
                             "expected": {"correctness": [2]},
                             "actual": {"correctness": 0, "completeness": 0,
                                        "citation_support": 0, "abstained": False,
                                        "explanation": "Synthetic failed calibration."}}],
            }
            with (
                patch.object(sys, "argv", ["evaluate_answers", "--benchmark", str(manifest_path), "--pdf", str(paper), "--output", str(output)]),
                patch("scripts.evaluate_answers.snapshot", return_value={"sha256": "test-corpus", "chunks_by_document": {"fixture.pdf": 1}}) as snapshot,
                patch("scripts.evaluate_answers.indexed_sources", return_value=[{"document": "fixture.pdf", "page": 1, "chunk_index": 0, "text": "The response increased."}]),
                patch("scripts.evaluate_answers.run_calibration", return_value=failed_calibration),
                patch("scripts.evaluate_answers.generate_case_answer") as generate,
                redirect_stdout(io.StringIO()), self.assertRaises(SystemExit),
            ):
                main()
            snapshot.assert_called_once_with("fixture.pdf")
            generate.assert_not_called()
            report = ReportModel.model_validate_json(output.read_text())
            self.assertEqual(report.status, "calibration_failed")
            self.assertEqual(report.paper_sha256, paper_hash)
            self.assertIsNotNone(report.benchmark)
            self.assertEqual(report.requested_case_ids, ["response"])

    def test_committed_holdout_manifest_is_valid_and_includes_requested_author(self) -> None:
        benchmark = load_benchmark(Path(__file__).resolve().parents[1] / "benchmarks/housing-temperature-2025.json")
        self.assertIn("Emma Frank", benchmark.metadata.authors)
        self.assertEqual(benchmark.metadata.split, "holdout")
        self.assertEqual(len(benchmark.cases), 10)
