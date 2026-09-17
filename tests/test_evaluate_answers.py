from collections.abc import Callable
from contextlib import ExitStack, redirect_stderr, redirect_stdout
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import io
import inspect
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import FrameType
from typing import Any, cast
import unittest
from unittest.mock import Mock, patch

from app.answer_evaluation import (
    AnswerEvaluationCase,
    CaseEvaluation,
    GeneratedCaseAnswer,
    judge_case_answer,
)
from app.judge_calibration import CALIBRATION_VERSION
from app.retrieval.rerank import MODEL_NAME
from app.types import ChunkData, PageData
from scripts.answer_quality_cases import ANSWER_CASES
from scripts.compare_reranking import CorpusSnapshot
from scripts.evaluate_answers import (
    ReportModel,
    _new_report,
    load_report,
    main,
    reserve_output,
    save_report,
    settings_for,
    validate_index,
    validate_labels,
    validate_resume_consistency,
)


CORPUS = CorpusSnapshot(sha256="corpus-sha", chunks_by_document={"sample.pdf": 1})


def calibration(*, passed: bool = True) -> dict[str, object]:
    return {
        "version": CALIBRATION_VERSION,
        "passed": passed,
        "results": [{
            "id": "fixture",
            "passed": passed,
            "expected": {"correctness": [2], "abstained": False},
            "actual": {
                "correctness": 2 if passed else 0,
                "completeness": 2,
                "citation_support": 2,
                "abstained": False,
                "explanation": "Synthetic calibration result.",
            },
        }],
    }


def pending_answer(case: AnswerEvaluationCase) -> GeneratedCaseAnswer:
    found = [False for _ in case["evidence"]]
    return {
        "case": case,
        "answer": "Unknown",
        "sources": [],
        "evidence_found": found,
        "evidence_recall": 0.0 if found else None,
        "answer_ms": 12.5,
    }


def judged_answer(generated: GeneratedCaseAnswer) -> CaseEvaluation:
    return judge_case_answer(generated, lambda prompt, schema: {
        "correctness": 0,
        "completeness": 0,
        "citation_support": 0,
        "abstained": False,
        "explanation": "The answer does not match the reference.",
    })


class AnswerRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.case = AnswerEvaluationCase(
            id="test", question="What increased?", answerable=True,
            reference_answer="The response increased.",
            evidence=[{"document": "paper.pdf", "page": 1, "quote": "response increased"}],
        )
        self.pages = [PageData(document="paper.pdf", page=1, text="The response increased.")]

    def patch_preflight(self, stack: ExitStack, *, calibration_passed: bool = True) -> Mock:
        stack.enter_context(patch("pathlib.Path.read_bytes", return_value=b"paper"))
        stack.enter_context(patch("scripts.evaluate_answers.PAPER_SHA256", sha256(b"paper").hexdigest()))
        stack.enter_context(patch("scripts.evaluate_answers.extract_pages", return_value=self.pages))
        stack.enter_context(patch("scripts.evaluate_answers.validate_labels"))
        stack.enter_context(patch("scripts.evaluate_answers.validate_index"))
        stack.enter_context(patch("scripts.evaluate_answers.indexed_sources", return_value=[]))
        stack.enter_context(patch("scripts.evaluate_answers.snapshot", return_value=CORPUS))
        calibration_mock = stack.enter_context(patch(
            "scripts.evaluate_answers.run_calibration",
            return_value=calibration(passed=calibration_passed),
        ))
        return calibration_mock

    def base_report(self, cases: list[AnswerEvaluationCase]) -> dict[str, object]:
        return _new_report(
            datetime(2026, 1, 1, tzinfo=timezone.utc), CORPUS, cases, "reranked", MODEL_NAME,
        )

    def test_labels_are_validated_against_pages_not_chunk_boundaries(self) -> None:
        validate_labels([self.case], self.pages)
        validate_index([
            ChunkData(document="paper.pdf", page=1, chunk_index=0, text="The response")
        ], self.pages)

    def test_invalid_dataset_and_stale_index_are_rejected(self) -> None:
        invalid_sets: list[list[AnswerEvaluationCase]] = [
            [], [self.case, self.case], [{**self.case, "answerable": False}],
            [{**self.case, "evidence": []}],
        ]
        for cases in invalid_sets:
            with self.subTest(cases=cases), self.assertRaises(ValueError):
                validate_labels(cases, self.pages)
        with self.assertRaisesRegex(ValueError, "another PDF"):
            validate_index([
                ChunkData(document="paper.pdf", page=1, chunk_index=0, text="The response decreased.")
            ], self.pages)

    def test_judge_failure_checkpoints_generated_answer_before_judging(self) -> None:
        case = ANSWER_CASES[0]
        generated = pending_answer(case)
        with TemporaryDirectory() as directory, ExitStack() as stack:
            output = Path(directory) / "answers.json"
            stack.enter_context(patch("sys.argv", [
                "evaluate_answers", "--case", case["id"], "--output", str(output),
            ]))
            self.patch_preflight(stack)
            stack.enter_context(patch("scripts.evaluate_answers.generate_case_answer", return_value=generated))

            def fail_judging(*args: object) -> None:
                # Verify durable ordering, not just the final exception handler's save.
                self.assertEqual(json.loads(output.read_text())["pending"], generated)
                raise RuntimeError("judge offline")

            stack.enter_context(patch(
                "scripts.evaluate_answers.judge_case_answer", side_effect=fail_judging
            ))
            with redirect_stdout(io.StringIO()), self.assertRaisesRegex(RuntimeError, "judge offline"):
                main()
            report = json.loads(output.read_text())
            self.assertEqual(report["status"], "failed")
            self.assertEqual(report["pending"], generated)
            self.assertEqual(report["results"], [])
            self.assertIsNone(report["metrics"])

    def test_resume_reuses_pending_answer_and_preserves_original_report(self) -> None:
        first, second = ANSWER_CASES[:2]
        first_result = judged_answer(pending_answer(first))
        generated = pending_answer(second)
        completed = judged_answer(generated)
        with TemporaryDirectory() as directory, ExitStack() as stack:
            source = Path(directory) / "failed.json"
            output = Path(directory) / "resumed.json"
            report = self.base_report([first, second])
            report.update({
                "status": "failed", "finished_at": "2026-01-01T00:01:00+00:00",
                "error": "RuntimeError: judge offline", "calibration": calibration(),
                "results": [first_result], "pending": generated,
                "paper_sha256": sha256(b"paper").hexdigest(),
            })
            source.write_text(json.dumps(report, indent=2) + "\n")
            original = source.read_text()
            stack.enter_context(patch("sys.argv", [
                "evaluate_answers", "--resume", str(source), "--output", str(output),
            ]))
            calibration_mock = self.patch_preflight(stack)
            generate_mock = stack.enter_context(patch("scripts.evaluate_answers.generate_case_answer"))
            stack.enter_context(patch("scripts.evaluate_answers.judge_case_answer", return_value=completed))
            with redirect_stdout(io.StringIO()):
                main()
            resumed = json.loads(output.read_text())
            self.assertEqual(source.read_text(), original)
            self.assertEqual(resumed["status"], "complete")
            self.assertIsNone(resumed["pending"])
            self.assertEqual(len(resumed["results"]), 2)
            self.assertIsNotNone(resumed["metrics"])
            generate_mock.assert_not_called()
            calibration_mock.assert_called_once()

    def test_interrupt_around_atomic_transitions_produces_resumable_reports(self) -> None:
        case = ANSWER_CASES[0]
        generated = pending_answer(case)
        completed = judged_answer(generated)

        source_lines, first_line = inspect.getsourcelines(main)

        def line_containing(fragment: str) -> int:
            matches = [
                first_line + offset for offset, line in enumerate(source_lines)
                if fragment in line
            ]
            self.assertEqual(len(matches), 1)
            return matches[0]

        result_transition = line_containing(
            'report = {**report, "results": results, "pending": None}'
        )
        completion_transition = line_containing(
            'report = {**report, "metrics": summarize(results), "status": "complete"}'
        )
        finish_transition = line_containing(
            'report = {**report, "finished_at": datetime.now(timezone.utc).isoformat()}'
        )
        phases = [
            ("before-result", result_transition, "failed", True, 0, 1),
            ("after-result", result_transition + 1, "failed", False, 1, 0),
            ("before-completion", completion_transition, "failed", False, 1, 0),
            ("after-completion", finish_transition, "running", False, 1, 0),
        ]

        with TemporaryDirectory() as directory:
            for name, target_line, status, has_pending, result_count, judge_calls in phases:
                with self.subTest(phase=name):
                    source = Path(directory) / f"{name}-interrupted.json"
                    output = Path(directory) / f"{name}-resumed.json"
                    interrupted = False

                    def interrupt_at_line(
                        frame: FrameType, event: str, argument: object,
                    ) -> Any:
                        nonlocal interrupted
                        if (frame.f_code is main.__code__ and event == "line"
                                and frame.f_lineno == target_line):
                            interrupted = True
                            raise KeyboardInterrupt(f"interrupted {name}")
                        return interrupt_at_line

                    with ExitStack() as stack:
                        stack.enter_context(patch("sys.argv", [
                            "evaluate_answers", "--case", case["id"], "--output", str(source),
                        ]))
                        self.patch_preflight(stack)
                        stack.enter_context(patch(
                            "scripts.evaluate_answers.generate_case_answer", return_value=generated,
                        ))
                        stack.enter_context(patch(
                            "scripts.evaluate_answers.judge_case_answer", return_value=completed,
                        ))
                        previous_trace = sys.gettrace()
                        sys.settrace(interrupt_at_line)
                        try:
                            with redirect_stdout(io.StringIO()), self.assertRaises(KeyboardInterrupt):
                                main()
                        finally:
                            sys.settrace(previous_trace)

                    self.assertTrue(interrupted)
                    interrupted_report = load_report(source)
                    self.assertEqual(interrupted_report.status, status)
                    self.assertEqual(interrupted_report.pending is not None, has_pending)
                    self.assertEqual(len(interrupted_report.results), result_count)
                    self.assertIsNone(interrupted_report.metrics)

                    with ExitStack() as stack:
                        stack.enter_context(patch("sys.argv", [
                            "evaluate_answers", "--resume", str(source), "--output", str(output),
                        ]))
                        self.patch_preflight(stack)
                        generate_mock = stack.enter_context(patch(
                            "scripts.evaluate_answers.generate_case_answer"
                        ))
                        judge_mock = stack.enter_context(patch(
                            "scripts.evaluate_answers.judge_case_answer", return_value=completed,
                        ))
                        with redirect_stdout(io.StringIO()):
                            main()

                    resumed = load_report(output)
                    self.assertEqual(resumed.status, "complete")
                    self.assertEqual(
                        [result.case.id for result in resumed.results], [case["id"]]
                    )
                    generate_mock.assert_not_called()
                    self.assertEqual(judge_mock.call_count, judge_calls)

    def test_calibration_failure_stops_before_answers_and_has_no_metrics(self) -> None:
        case = ANSWER_CASES[0]
        with TemporaryDirectory() as directory, ExitStack() as stack:
            output = Path(directory) / "answers.json"
            stack.enter_context(patch("sys.argv", [
                "evaluate_answers", "--case", case["id"], "--output", str(output),
            ]))
            self.patch_preflight(stack, calibration_passed=False)
            generate_mock = stack.enter_context(patch("scripts.evaluate_answers.generate_case_answer"))
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main()
            report = json.loads(output.read_text())
            self.assertEqual(report["status"], "calibration_failed")
            self.assertFalse(report["calibration"]["passed"])
            self.assertIsNone(report["metrics"])
            generate_mock.assert_not_called()

    def test_expanded_strategy_is_recorded_and_passed_to_answer_generation(self) -> None:
        case = ANSWER_CASES[0]
        with TemporaryDirectory() as directory, ExitStack() as stack:
            output = Path(directory) / "expanded.json"
            stack.enter_context(patch("sys.argv", [
                "evaluate_answers", "--case", case["id"], "--strategy", "expanded",
                "--output", str(output),
            ]))
            self.patch_preflight(stack)
            answer = stack.enter_context(patch("app.rag.answer_question", return_value={
                "answer": "Unknown", "sources": [],
            }))

            def judge(generated: GeneratedCaseAnswer, ignored: object) -> CaseEvaluation:
                return judged_answer(generated)

            stack.enter_context(patch("scripts.evaluate_answers.judge_case_answer", side_effect=judge))
            with redirect_stdout(io.StringIO()):
                main()
            answer.assert_called_once_with(case["question"], use_reranking=True, expand_context=True)
            report = load_report(output)
            self.assertEqual(report.settings.strategy, "expanded")
            self.assertEqual(report.settings.candidate_count, 10)
            self.assertEqual(report.settings.neighbor_radius, 2)
            self.assertEqual(report.settings.max_context_chars, 6000)
            self.assertEqual(report.reranker_model, MODEL_NAME)

    def test_schema_v1_resume_is_rejected_before_services(self) -> None:
        with TemporaryDirectory() as directory, ExitStack() as stack:
            source = Path(directory) / "old.json"
            output = Path(directory) / "new.json"
            source.write_text('{"schema_version": 1, "results": []}')
            stack.enter_context(patch("sys.argv", [
                "evaluate_answers", "--resume", str(source), "--output", str(output),
            ]))
            snapshot_mock = stack.enter_context(patch("scripts.evaluate_answers.snapshot"))
            with redirect_stderr(io.StringIO()) as stderr, self.assertRaises(SystemExit):
                main()
            self.assertIn("did not save pending generated answers", stderr.getvalue())
            self.assertFalse(output.exists())
            snapshot_mock.assert_not_called()

    def test_resume_rejects_reports_without_explicit_thinking_settings(self) -> None:
        report = self.base_report([ANSWER_CASES[0]])
        settings = cast(dict[str, object], report["settings"])
        settings.pop("generator_think")
        settings.pop("judge_think")
        with TemporaryDirectory() as directory:
            source = Path(directory) / "old.json"
            source.write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError, r"(?s)generator_think.*judge_think"):
                load_report(source)

    def test_loaded_report_rejects_invalid_order_duplicates_pending_and_timings(self) -> None:
        first, second = ANSWER_CASES[:2]
        baseline = self.base_report([first, second])
        variants: list[tuple[str, dict[str, object]]] = []

        duplicate_ids = deepcopy(baseline)
        duplicate_ids["requested_case_ids"] = [first["id"], first["id"]]
        variants.append(("unique", duplicate_ids))

        wrong_order = deepcopy(baseline)
        wrong_order["results"] = [judged_answer(pending_answer(second))]
        variants.append(("ordered prefix", wrong_order))

        wrong_pending = deepcopy(baseline)
        wrong_pending["pending"] = pending_answer(second)
        variants.append(("next requested case", wrong_pending))

        bad_timing = deepcopy(baseline)
        bad_timing["pending"] = pending_answer(first)
        bad_timing["pending"]["answer_ms"] = float("nan")  # type: ignore[index]
        variants.append(("finite number", bad_timing))

        duplicate_results = deepcopy(baseline)
        duplicate_results["results"] = [
            judged_answer(pending_answer(first)), judged_answer(pending_answer(first)),
        ]
        variants.append(("duplicates", duplicate_results))

        with TemporaryDirectory() as directory:
            for index, (message, raw) in enumerate(variants):
                with self.subTest(message=message):
                    path = Path(directory) / f"invalid-{index}.json"
                    path.write_text(json.dumps(raw))
                    with self.assertRaisesRegex(ValueError, message):
                        load_report(path)

    def test_real_completed_result_matches_persisted_schema(self) -> None:
        case = ANSWER_CASES[0]
        report = self.base_report([case])
        report["results"] = [judged_answer(pending_answer(case))]
        validated = ReportModel.model_validate(report)
        self.assertEqual(validated.results[0].judge.correctness, 0)

    def test_rendering_changes_invalidate_generator_prompt_fingerprint(self) -> None:
        before = settings_for("reranked")
        with patch("scripts.evaluate_answers.render_context", return_value="Changed headers"):
            after = settings_for("reranked")
        self.assertNotEqual(before["generator_prompt_sha256"], after["generator_prompt_sha256"])
        saved = ReportModel.model_validate(self.base_report([ANSWER_CASES[0]]))
        with patch("scripts.evaluate_answers.render_context", return_value="Changed headers"):
            with self.assertRaisesRegex(ValueError, "settings"):
                validate_resume_consistency(saved, [ANSWER_CASES[0]], CORPUS, "reranked", MODEL_NAME)

    def test_resume_checks_all_reproducibility_fields(self) -> None:
        case = ANSWER_CASES[0]
        baseline = self.base_report([case])
        mutations: dict[str, Callable[[dict[str, object]], None]] = {
            "corpus": lambda raw: cast(dict[str, object], raw["corpus"]).update({"sha256": "changed"}),
            "paper SHA-256": lambda raw: raw.update({"paper_sha256": "changed"}),
            "cases": lambda raw: raw.update({"cases_sha256": "changed"}),
            "generator model": lambda raw: raw.update({"generator_model": "changed"}),
            "judge model": lambda raw: raw.update({"judge_model": "changed"}),
            "embedding model": lambda raw: raw.update({"embedding_model": "changed"}),
            "reranker model": lambda raw: raw.update({"reranker_model": "changed"}),
            "settings": lambda raw: cast(dict[str, object], raw["settings"]).update({"top_k": 4}),
            "evaluator version": lambda raw: raw.update({"evaluator_version": "changed"}),
            "evaluator prompt": lambda raw: raw.update({"evaluator_prompt_sha256": "changed"}),
            "calibration version": lambda raw: raw.update({"calibration_version": "changed"}),
        }
        for expected, mutate in mutations.items():
            with self.subTest(field=expected):
                raw = deepcopy(baseline)
                mutate(raw)
                saved = ReportModel.model_validate(raw)
                with self.assertRaisesRegex(ValueError, expected):
                    validate_resume_consistency(saved, [case], CORPUS, "reranked", MODEL_NAME)

    def test_existing_report_is_preserved_before_services_are_called(self) -> None:
        with TemporaryDirectory() as directory:
            output = Path(directory) / "answers.json"
            output.write_text("existing report")
            with patch("sys.argv", ["evaluate_answers", "--output", str(output)]), \
                    patch("scripts.evaluate_answers.snapshot") as snapshot_mock, \
                    patch("sys.stderr", new_callable=io.StringIO):
                with self.assertRaises(SystemExit):
                    main()
                snapshot_mock.assert_not_called()
            self.assertEqual(output.read_text(), "existing report")

    def test_checkpoint_write_is_atomic_and_leaves_no_temporary_file(self) -> None:
        with TemporaryDirectory() as directory:
            output = Path(directory) / "answers.json"
            reserve_output(output)
            save_report(output, {"status": "running"})
            self.assertEqual(json.loads(output.read_text()), {"status": "running"})
            self.assertEqual(list(Path(directory).glob(".answers.json.*")), [])

    def test_failed_atomic_replace_preserves_previous_checkpoint(self) -> None:
        with TemporaryDirectory() as directory:
            output = Path(directory) / "answers.json"
            reserve_output(output)
            save_report(output, {"status": "running"})
            previous = output.read_text()
            with patch("scripts.evaluate_answers.os.replace", side_effect=OSError("disk error")), \
                    self.assertRaisesRegex(OSError, "disk error"):
                save_report(output, {"status": "complete"})
            self.assertEqual(output.read_text(), previous)
            self.assertEqual(list(Path(directory).glob(".answers.json.*")), [])


if __name__ == "__main__":
    unittest.main()
