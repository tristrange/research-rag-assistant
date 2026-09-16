"""Small synthetic sanity checks for the judge, not proof of its accuracy."""

from dataclasses import dataclass
from typing import TypedDict

from app.answer_evaluation import AnswerEvaluationCase, Judge, JudgeScores, judge_prompt
from app.types import AnswerResult, ChunkData


CALIBRATION_VERSION = "1"


class CalibrationResult(TypedDict):
    id: str
    passed: bool
    expected: dict[str, list[int] | bool]
    actual: dict[str, object]


class CalibrationReport(TypedDict):
    version: str
    passed: bool
    results: list[CalibrationResult]


@dataclass(frozen=True)
class CalibrationFixture:
    id: str
    answer: str
    source: str
    answerable: bool
    expected: dict[str, list[int] | bool]


FACT = "The treatment reduced the measured response by 56%."
FIXTURES = (
    CalibrationFixture("complete_answer", FACT, FACT, True,
                       {"correctness": [2], "completeness": [2],
                        "citation_support": [2], "abstained": False}),
    CalibrationFixture("missing_number", "The treatment reduced the measured response.", FACT, True,
                       {"completeness": [0, 1], "abstained": False}),
    CalibrationFixture("contradictory_answer", "The treatment increased the measured response by 56%.", FACT, True,
                       {"correctness": [0, 1], "citation_support": [0, 1], "abstained": False}),
    CalibrationFixture("answerable_refusal", "I do not have enough information to answer this question.", FACT, True,
                       {"correctness": [0], "completeness": [0], "abstained": True}),
    CalibrationFixture("unanswerable_refusal", "I do not have enough information to answer this question.",
                       "The study describes equipment but reports no treatment outcomes.", False,
                       {"correctness": [2], "completeness": [2], "citation_support": [2], "abstained": True}),
    CalibrationFixture("unsupported_answer", FACT,
                       "The study describes equipment but reports no treatment outcomes.", True,
                       {"citation_support": [0], "abstained": False}),
)


def run_calibration(judge: Judge) -> CalibrationReport:
    """Require basic grading distinctions before publishing benchmark metrics.

    The judge gets the normal grading prompt, without the expected scores.
    Transport and schema errors propagate to the runner's failure checkpoint.
    """
    results: list[CalibrationResult] = []
    for fixture in FIXTURES:
        case = AnswerEvaluationCase(
            id=fixture.id,
            question="What effect did the treatment have, and by what percentage?",
            answerable=fixture.answerable,
            reference_answer=FACT if fixture.answerable else "The information is not available.",
            evidence=[{"document": "synthetic.pdf", "page": 1, "quote": FACT}] if fixture.answerable else [],
        )
        response = AnswerResult(answer=fixture.answer, sources=[ChunkData(
            document="synthetic.pdf", page=1, chunk_index=0, text=fixture.source,
        )])
        scores = JudgeScores.model_validate(judge(judge_prompt(case, response), JudgeScores.model_json_schema()))
        actual: dict[str, object] = scores.model_dump()
        passed = all(
            actual[field] is expected if isinstance(expected, bool) else actual[field] in expected
            for field, expected in fixture.expected.items()
        )
        results.append(CalibrationResult(id=fixture.id, passed=passed,
                                         expected=fixture.expected, actual=actual))
    return CalibrationReport(version=CALIBRATION_VERSION,
                             passed=all(result["passed"] for result in results), results=results)
