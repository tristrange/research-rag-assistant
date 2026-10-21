import json
import tempfile
import unittest
from hashlib import sha256
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock, patch

from pydantic import ValidationError

from app.llm.telemetry import RuntimeSnapshot
from app.performance import PerformanceTrace
from scripts.benchmark_pipeline import (
    BenchmarkManifest,
    SampleModel,
    git_commit,
    load_manifest,
    peak_rss_bytes,
    run_benchmark,
    summarize_samples,
)


def raw_manifest(*cases: dict[str, object]) -> dict[str, object]:
    return {
        "schema_version": 1,
        "answer_mode": "verified",
        "cases": list(cases)
        or [{"id": "case", "question": "What changed?", "document": "paper.pdf"}],
    }


class ManifestTests(unittest.TestCase):
    def test_load_manifest_hashes_the_exact_input_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cases.json"
            path.write_text(json.dumps(raw_manifest(), indent=2) + "\n")

            manifest, digest = load_manifest(path)

            self.assertEqual(manifest.cases[0].id, "case")
            self.assertEqual(digest, sha256(path.read_bytes()).hexdigest())

    def test_manifest_rejects_duplicate_ids(self) -> None:
        with self.assertRaises(ValidationError):
            BenchmarkManifest.model_validate(
                raw_manifest(
                    {"id": "same", "question": "One?", "document": "paper.pdf"},
                    {"id": "same", "question": "Two?", "document": "paper.pdf"},
                )
            )

    def test_manifest_rejects_paths_and_non_pdf_documents(self) -> None:
        for document in ("../paper.pdf", "folder/paper.pdf", "paper.txt"):
            with self.subTest(document=document), self.assertRaises(ValidationError):
                BenchmarkManifest.model_validate(
                    raw_manifest(
                        {
                            "id": "case",
                            "question": "What changed?",
                            "document": document,
                        }
                    )
                )

    def test_manifest_rejects_empty_cases(self) -> None:
        with self.assertRaises(ValidationError):
            BenchmarkManifest.model_validate(
                {"schema_version": 1, "answer_mode": "verified", "cases": []}
            )


class BenchmarkRunTests(unittest.TestCase):
    def test_run_preserves_failures_and_redacts_error_messages(self) -> None:
        manifest = BenchmarkManifest.model_validate(
            raw_manifest(
                {"id": "ok", "question": "What changed?", "document": "paper.pdf"},
                {"id": "fail", "question": "Fail?", "document": "paper.pdf"},
            )
        )
        corpus = {"sha256": "b" * 64, "chunks_by_document": {"paper.pdf": 1}}
        runtime = RuntimeSnapshot(
            ollama_version="0.40.6",
            model_digests={"gpt-oss:20b": "c" * 64, "qwen3:8b": "d" * 64},
        )

        def fake_query(question: str, **kwargs: object) -> dict[str, object]:
            trace = cast(PerformanceTrace, kwargs["performance"])
            with trace.measure("vector_search"):
                pass
            if question == "Fail?":
                raise RuntimeError("secret passage text")
            return {"answer": "ok", "sources": []}

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "baseline.json"
            with (
                patch(
                    "scripts.benchmark_pipeline.list_documents",
                    return_value=["paper.pdf"],
                ),
                patch(
                    "scripts.benchmark_pipeline.snapshot",
                    side_effect=[corpus, corpus],
                ),
                patch(
                    "scripts.benchmark_pipeline.runtime_snapshot",
                    side_effect=[runtime, runtime],
                ),
                patch(
                    "scripts.benchmark_pipeline.git_commit",
                    return_value="e" * 40,
                ),
                patch(
                    "scripts.benchmark_pipeline.answer_question",
                    side_effect=fake_query,
                ) as query,
            ):
                report = run_benchmark(manifest, "a" * 64, output, runs=2, warmup=1)

            persisted = output.read_text(encoding="utf-8")
            self.assertNotIn("secret passage text", persisted)
            self.assertNotIn("What changed?", persisted)
            query.assert_called()

        self.assertEqual(report.status, "complete")
        self.assertEqual(len(report.samples), 6)
        self.assertEqual([sample.phase for sample in report.samples].count("warmup"), 2)
        self.assertEqual(
            [sample.phase for sample in report.samples].count("measured"), 4
        )
        self.assertEqual(report.summaries["ok"].completed, 2)
        self.assertEqual(report.summaries["ok"].failed, 0)
        ok_total = report.summaries["ok"].total
        self.assertIsNotNone(ok_total)
        assert ok_total is not None
        self.assertEqual(ok_total.count, 2)
        self.assertEqual(report.summaries["ok"].stages["vector_search"].count, 2)
        self.assertEqual(report.summaries["fail"].completed, 0)
        self.assertEqual(report.summaries["fail"].failed, 2)
        self.assertEqual(report.summaries["fail"].warmup_failed, 1)
        self.assertIsNone(report.summaries["fail"].total)
        overall = report.overall
        self.assertIsNotNone(overall)
        assert overall is not None
        self.assertEqual(overall.count, 2)
        failed_samples = [
            sample for sample in report.samples if sample.status == "failed"
        ]
        self.assertEqual(len(failed_samples), 3)
        self.assertTrue(
            all(sample.error_type == "RuntimeError" for sample in failed_samples)
        )
        self.assertEqual(report.runtime_before, report.runtime_after)
        self.assertEqual(report.corpus_before, report.corpus_after)
        self.assertEqual(report.environment.commit, "e" * 40)
        self.assertEqual(report.manifest_sha256, "a" * 64)
        self.assertEqual(report.reranker_cache, "warmed_by_warmup")

    def test_run_fails_when_the_index_changes_during_the_run(self) -> None:
        manifest = BenchmarkManifest.model_validate(raw_manifest())
        corpus = {"sha256": "b" * 64, "chunks_by_document": {"paper.pdf": 1}}
        changed = {"sha256": "f" * 64, "chunks_by_document": {"paper.pdf": 1}}
        runtime = RuntimeSnapshot(
            ollama_version="0.40.6",
            model_digests={"gpt-oss:20b": "c" * 64, "qwen3:8b": "d" * 64},
        )

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "baseline.json"
            with (
                patch(
                    "scripts.benchmark_pipeline.list_documents",
                    return_value=["paper.pdf"],
                ),
                patch(
                    "scripts.benchmark_pipeline.snapshot",
                    side_effect=[corpus, changed],
                ),
                patch(
                    "scripts.benchmark_pipeline.runtime_snapshot",
                    side_effect=[runtime, runtime],
                ),
                patch(
                    "scripts.benchmark_pipeline.git_commit",
                    return_value="e" * 40,
                ),
                patch(
                    "scripts.benchmark_pipeline.answer_question",
                    return_value={"answer": "ok", "sources": []},
                ),
            ):
                with self.assertRaisesRegex(RuntimeError, "index changed"):
                    run_benchmark(manifest, "a" * 64, output, runs=1, warmup=0)

            persisted = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(persisted["status"], "failed")
        self.assertEqual(persisted["error_type"], "RuntimeError")
        self.assertEqual(persisted["corpus_after"]["sha256"], "f" * 64)

    def test_run_fails_when_the_model_runtime_changes_during_the_run(self) -> None:
        manifest = BenchmarkManifest.model_validate(raw_manifest())
        corpus = {"sha256": "b" * 64, "chunks_by_document": {"paper.pdf": 1}}
        before = RuntimeSnapshot(
            ollama_version="0.40.6",
            model_digests={"gpt-oss:20b": "c" * 64, "qwen3:8b": "d" * 64},
        )
        after = RuntimeSnapshot(
            ollama_version="0.40.6",
            model_digests={"gpt-oss:20b": "f" * 64, "qwen3:8b": "d" * 64},
        )

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "baseline.json"
            with (
                patch(
                    "scripts.benchmark_pipeline.list_documents",
                    return_value=["paper.pdf"],
                ),
                patch(
                    "scripts.benchmark_pipeline.snapshot",
                    side_effect=[corpus, corpus],
                ),
                patch(
                    "scripts.benchmark_pipeline.runtime_snapshot",
                    side_effect=[before, after],
                ),
                patch(
                    "scripts.benchmark_pipeline.git_commit",
                    return_value="e" * 40,
                ),
                patch(
                    "scripts.benchmark_pipeline.answer_question",
                    return_value={"answer": "ok", "sources": []},
                ),
            ):
                with self.assertRaisesRegex(ValueError, "identity changed"):
                    run_benchmark(manifest, "a" * 64, output, runs=1, warmup=0)

            persisted = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(persisted["status"], "failed")
        self.assertEqual(persisted["error_type"], "ValueError")

    def test_run_refuses_existing_output_before_calling_services(self) -> None:
        manifest = BenchmarkManifest.model_validate(raw_manifest())
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "baseline.json"
            output.write_text("keep", encoding="utf-8")
            with (
                patch("scripts.benchmark_pipeline.snapshot") as snapshot,
                patch("scripts.benchmark_pipeline.answer_question") as query,
            ):
                with self.assertRaisesRegex(ValueError, "already exists"):
                    run_benchmark(manifest, "a" * 64, output, runs=1, warmup=0)
            self.assertEqual(output.read_text(encoding="utf-8"), "keep")
        snapshot.assert_not_called()
        query.assert_not_called()

    def test_summaries_omit_stages_that_did_not_run(self) -> None:
        base = {
            "case_id": "case",
            "phase": "measured",
            "status": "complete",
            "total_ms": 10.0,
            "calls": [],
            "verification": [],
            "prompt_eval_tokens": None,
            "eval_tokens": None,
            "error_type": None,
            "failed_stage": None,
        }
        with_stage = SampleModel.model_validate(
            {
                **base,
                "stages": [{"stage": "embedding", "elapsed_ms": 5.0}],
            }
        )
        without_stage = SampleModel.model_validate({**base, "stages": []})

        summaries, overall = summarize_samples([with_stage, without_stage], ["case"])

        self.assertEqual(summaries["case"].stages["embedding"].count, 1)
        self.assertNotIn("vector_search", summaries["case"].stages)
        self.assertIsNotNone(overall)
        assert overall is not None
        self.assertEqual(overall.count, 2)


class EnvironmentTests(unittest.TestCase):
    def test_peak_rss_normalizes_linux_kilobytes(self) -> None:
        usage = MagicMock()
        usage.ru_maxrss = 2048
        with (
            patch("scripts.benchmark_pipeline.sys.platform", "linux"),
            patch(
                "scripts.benchmark_pipeline.resource.getrusage",
                return_value=usage,
            ),
        ):
            self.assertEqual(peak_rss_bytes(), 2048 * 1024)

    def test_git_commit_is_unknown_when_git_is_unavailable(self) -> None:
        with patch(
            "scripts.benchmark_pipeline.subprocess.run",
            side_effect=OSError("missing git"),
        ):
            self.assertIsNone(git_commit())
