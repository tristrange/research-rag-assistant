from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast
import unittest
from unittest.mock import Mock, patch

from app.llm.telemetry import RuntimeSnapshot
from app.types import AnswerClaim, ChunkData
from scripts.replay_grounding import main


CASE = {
    "id": "known-case",
    "question": "What happened?",
    "answerable": True,
    "reference_answer": "The response increased.",
    "evidence": [{"document": "paper.pdf", "page": 2, "quote": "response increased"}],
}
SOURCE = ChunkData(
    document="paper.pdf",
    page=2,
    chunk_index=1,
    section="results",
    text="The response increased after treatment.",
)


def saved_report() -> Mock:
    saved = Mock()
    saved.corpus.model_dump.return_value = {
        "sha256": "corpus-sha",
        "chunks_by_document": {"paper.pdf": 1},
    }
    saved.settings.strategy = "reranked"
    saved.settings.top_k = 3
    completed = Mock()
    completed.case.id = CASE["id"]
    completed.case.question = CASE["question"]
    completed.case.model_dump.return_value = CASE
    source = Mock()
    source.model_dump.return_value = SOURCE
    completed.sources = [source]
    saved.results = [completed]
    return saved


class ReplayGroundingTests(unittest.TestCase):
    def setUp(self) -> None:
        runtime = patch("scripts.replay_grounding.runtime_snapshot",
                        return_value=RuntimeSnapshot(ollama_version=None, model_digests={}))
        runtime.start()
        self.addCleanup(runtime.stop)

    def test_unknown_case_id_is_rejected_before_output_reservation(self) -> None:
        with TemporaryDirectory() as directory:
            output = Path(directory) / "replay.json"
            with (
                patch("sys.argv", [
                    "replay_grounding", "saved.json", "--case", "unknown-case",
                    "--output", str(output),
                ]),
                patch("scripts.replay_grounding.load_report", return_value=saved_report()),
                patch("scripts.replay_grounding.reserve_output") as reserve,
                patch("scripts.replay_grounding.grounded_answer") as grounded,
                redirect_stderr(io.StringIO()),
                self.assertRaises(SystemExit),
            ):
                main()
            reserve.assert_not_called()
            grounded.assert_not_called()
            self.assertFalse(output.exists())

    def test_existing_output_is_preserved_without_running_grounding(self) -> None:
        with TemporaryDirectory() as directory:
            output = Path(directory) / "replay.json"
            original = "existing report\n"
            output.write_text(original, encoding="utf-8")
            with (
                patch("sys.argv", [
                    "replay_grounding", "saved.json", "--output", str(output),
                ]),
                patch("scripts.replay_grounding.load_report", return_value=saved_report()),
                patch("scripts.replay_grounding.grounded_answer") as grounded,
                self.assertRaisesRegex(ValueError, "Report already exists"),
            ):
                main()
            grounded.assert_not_called()
            self.assertEqual(output.read_text(encoding="utf-8"), original)

    def test_completed_run_retains_trace_and_complete_status(self) -> None:
        trace_entries: list[dict[str, object]] = [
            {"stage": "draft", "output": {"answerable": True, "claims": []}},
            {"stage": "verification", "output": {"answers_question": True}},
        ]

        def ground(
            question: str,
            sources: list[ChunkData],
            *,
            trace: list[dict[str, object]] | None = None,
            claim_evidence: list[AnswerClaim] | None = None,
        ) -> str:
            self.assertEqual(question, CASE["question"])
            self.assertEqual(sources, [SOURCE])
            self.assertIsNotNone(trace)
            cast(list[dict[str, object]], trace).extend(trace_entries)
            self.assertIsNotNone(claim_evidence)
            cast(list[AnswerClaim], claim_evidence).append({
                "text": "The response increased.", "attribution": "this_document_authors",
                "citations": [{"source_index": 0, "quote": SOURCE["text"]}],
            })
            return "The response increased. (paper.pdf, page 2)"

        with TemporaryDirectory() as directory:
            output = Path(directory) / "replay.json"
            with (
                patch("sys.argv", [
                    "replay_grounding", "saved.json", "--output", str(output),
                ]),
                patch("scripts.replay_grounding.load_report", return_value=saved_report()),
                patch("scripts.replay_grounding.grounded_answer", side_effect=ground) as grounded,
                redirect_stdout(io.StringIO()),
            ):
                main()
            grounded.assert_called_once()
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "complete")
            self.assertIn("finished_at", report)
            self.assertEqual(len(report["results"]), 1)
            item = report["results"][0]
            self.assertEqual(item["trace"], trace_entries)
            self.assertEqual(item["answer"], "The response increased. (paper.pdf, page 2)")
            self.assertEqual(item["claim_evidence"][0]["citations"][0]["source_index"], 0)
            self.assertEqual(item["answer_calls"], [])
            self.assertEqual(report["schema_version"], 2)
            self.assertGreaterEqual(item["elapsed_ms"], 0)

    def test_replay_preserves_nondefault_source_cutoffs(self) -> None:
        for strategy, top_k, candidates in [("expanded", 3, 10), ("vector", 5, 5), ("reranked", 7, 10)]:
            with self.subTest(strategy=strategy), TemporaryDirectory() as directory:
                saved = saved_report()
                saved.settings.strategy = strategy
                saved.settings.top_k = top_k
                output = Path(directory) / "replay.json"
                with (
                    patch("sys.argv", ["replay_grounding", "saved.json", "--output", str(output)]),
                    patch("scripts.replay_grounding.load_report", return_value=saved),
                    patch("scripts.replay_grounding.grounded_answer", return_value="Answer") as grounded,
                    redirect_stdout(io.StringIO()),
                ):
                    main()
                report = json.loads(output.read_text())
                self.assertEqual(report["settings"]["top_k"], top_k)
                self.assertEqual(report["settings"]["candidate_count"], candidates)
                self.assertEqual(report["settings"]["answer_mode"], "verified")
                self.assertEqual(grounded.call_args.args[1], [SOURCE])

    def test_interrupted_run_retains_partial_trace_and_failed_status(self) -> None:
        trace_entry: dict[str, object] = {
            "stage": "draft", "output": {"answerable": True, "claims": []}
        }

        def interrupt(
            question: str,
            sources: list[ChunkData],
            *,
            trace: list[dict[str, object]] | None = None,
            claim_evidence: list[AnswerClaim] | None = None,
        ) -> str:
            self.assertIsNotNone(trace)
            cast(list[dict[str, object]], trace).append(trace_entry)
            raise KeyboardInterrupt("operator stopped replay")

        with TemporaryDirectory() as directory:
            output = Path(directory) / "replay.json"
            with (
                patch("sys.argv", [
                    "replay_grounding", "saved.json", "--output", str(output),
                ]),
                patch("scripts.replay_grounding.load_report", return_value=saved_report()),
                patch("scripts.replay_grounding.grounded_answer", side_effect=interrupt),
                redirect_stdout(io.StringIO()),
                self.assertRaisesRegex(KeyboardInterrupt, "operator stopped replay"),
            ):
                main()
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "failed")
            self.assertEqual(report["error"], "KeyboardInterrupt: operator stopped replay")
            self.assertIn("finished_at", report)
            self.assertEqual(len(report["results"]), 1)
            item = report["results"][0]
            self.assertEqual(item["trace"], [trace_entry])
            self.assertNotIn("answer", item)
            self.assertNotIn("claim_evidence", item)
            self.assertEqual(item["answer_calls"], [])
            self.assertGreaterEqual(item["elapsed_ms"], 0)


if __name__ == "__main__":
    unittest.main()
