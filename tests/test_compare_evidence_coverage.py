from contextlib import ExitStack, redirect_stderr, redirect_stdout
from hashlib import sha256
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from app.db.models import Chunk
from scripts.compare_evidence_coverage import main, sources_for
from app.types import ChunkData, PageData


class CoverageRunnerTests(unittest.TestCase):
    def check_scoped_report(self, library_changed: bool) -> None:
        manifest = json.loads(Path("benchmarks/housing-temperature-2025.json").read_text())
        case = next(case for case in manifest["cases"] if case["id"] == "housing-bat-atp")
        label = case["evidence"][0]
        manifest["metadata"]["paper_sha256"] = sha256(b"paper").hexdigest()
        source = ChunkData(document="housing-temperature.pdf", page=label["page"],
                           chunk_index=0, text=label["quote"], section="abstract")
        foreign = ChunkData(document="other.pdf", page=1, chunk_index=0,
                            text="Other paper", section="methods")
        pages = [PageData(document=source["document"], page=source["page"], text=source["text"])]
        chunk = Chunk(**source)
        with TemporaryDirectory() as directory, ExitStack() as stack:
            root = Path(directory)
            benchmark = root / "benchmark.json"
            benchmark.write_text(json.dumps(manifest))
            paper = root / "housing-temperature.pdf"
            paper.write_bytes(b"paper")
            output = root / "coverage.json"
            stack.enter_context(patch("sys.argv", [
                "compare_evidence_coverage", "--benchmark", str(benchmark), "--pdf", str(paper),
                "--case", case["id"], "--candidates", "30", "--repetitions", "1",
                "--output", str(output),
            ]))
            stack.enter_context(patch("scripts.compare_evidence_coverage.extract_pages", return_value=pages))
            stack.enter_context(patch("scripts.compare_evidence_coverage.indexed_sources", return_value=[foreign, source]))
            stack.enter_context(patch("scripts.compare_evidence_coverage.snapshot", side_effect=[
                {"sha256": "stable", "chunks_by_document": {"other.pdf": 1, source["document"]: 1}},
                {"sha256": "changed" if library_changed else "stable",
                 "chunks_by_document": {"other.pdf": 2 if library_changed else 1, source["document"]: 1}},
            ]))
            search = stack.enter_context(patch("scripts.compare_evidence_coverage.search_chunks", return_value=[chunk]))
            stack.enter_context(patch("scripts.compare_evidence_coverage.rerank_chunks", return_value=[chunk]))
            stack.enter_context(patch("scripts.compare_evidence_coverage.expand_chunks", side_effect=sources_for))
            with redirect_stdout(io.StringIO()):
                if library_changed:
                    with self.assertRaisesRegex(RuntimeError, "Corpus changed"):
                        main()
                else:
                    main()
            report = json.loads(output.read_text())
            self.assertEqual(report["status"], "failed" if library_changed else "complete")
            self.assertEqual(report["candidates"], 30)
            self.assertEqual(report["document"], source["document"])
            self.assertEqual([row["case"]["id"] for row in report["results"]], [case["id"]])
            self.assertEqual(report["results"][0]["candidate_hits"], [True])
            self.assertEqual(report["results"][0]["reranked_sources"], [source])
            for call in search.call_args_list:
                self.assertEqual(call.kwargs["document"], source["document"])
                self.assertEqual(call.args[1], 30)

    def test_selected_case_and_larger_pool_run_in_a_mixed_library(self) -> None:
        self.check_scoped_report(library_changed=False)

    def test_change_in_another_paper_marks_scoped_report_failed(self) -> None:
        self.check_scoped_report(library_changed=True)

    def test_invalid_selection_and_cutoffs_stop_before_services(self) -> None:
        for options, message in (
            (["--case", "unknown"], "Unknown case IDs"),
            (["--case", "c26-body-mass-loss", "--case", "c26-body-mass-loss"], "duplicates"),
            (["--case", "own-rosiglitazone-dose"], "must be answerable"),
            (["--candidates", "5"], "cutoffs"),
        ):
            with self.subTest(options=options), ExitStack() as stack:
                stack.enter_context(patch("sys.argv", ["compare_evidence_coverage", "--output", "unused.json", *options]))
                snapshot = stack.enter_context(patch("scripts.compare_evidence_coverage.snapshot"))
                extract = stack.enter_context(patch("scripts.compare_evidence_coverage.extract_pages"))
                reserve = stack.enter_context(patch("scripts.compare_evidence_coverage.reserve_output"))
                with redirect_stderr(io.StringIO()) as stderr, self.assertRaises(SystemExit):
                    main()
                self.assertIn(message, stderr.getvalue())
                snapshot.assert_not_called()
                extract.assert_not_called()
                reserve.assert_not_called()

    def test_unanswerable_only_benchmark_rejected_before_services_or_output(self) -> None:
        manifest = json.loads(Path("benchmarks/housing-temperature-2025.json").read_text())
        manifest["cases"] = [case for case in manifest["cases"] if not case["answerable"]]
        manifest["metadata"]["paper_sha256"] = sha256(b"paper").hexdigest()
        with TemporaryDirectory() as directory:
            root = Path(directory)
            benchmark = root / "benchmark.json"
            benchmark.write_text(json.dumps(manifest))
            paper = root / "housing-temperature.pdf"
            paper.write_bytes(b"paper")
            output = root / "coverage.json"
            with (
                patch("sys.argv", ["compare_evidence_coverage", "--benchmark", str(benchmark),
                                   "--pdf", str(paper), "--output", str(output)]),
                patch("scripts.compare_evidence_coverage.extract_pages") as extract,
                patch("scripts.compare_evidence_coverage.snapshot") as snapshot,
                patch("scripts.compare_evidence_coverage.compare_case") as compare,
                patch("scripts.compare_evidence_coverage.reserve_output") as reserve,
                redirect_stderr(io.StringIO()) as stderr,
                self.assertRaises(SystemExit) as error,
            ):
                main()
            self.assertEqual(error.exception.code, 2)
            self.assertIn("requires at least one answerable case", stderr.getvalue())
            extract.assert_not_called()
            snapshot.assert_not_called()
            compare.assert_not_called()
            reserve.assert_not_called()
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
