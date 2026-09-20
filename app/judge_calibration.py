"""Small synthetic sanity checks for the judge, not proof of its accuracy."""

from dataclasses import dataclass
from typing import TypedDict

from app.answer_evaluation import AnswerEvaluationCase, Judge, score_answer
from app.types import AnswerResult, ChunkData


CALIBRATION_VERSION = "2"


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
    question: str = "What effect did the treatment have, and by what percentage?"
    reference: str | None = None


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
    CalibrationFixture("short_plain_refusal", "I do not have enough information.",
                       "Only mouse outcomes were measured.", False,
                       {"correctness": [2], "completeness": [2], "citation_support": [2], "abstained": True}),
    CalibrationFixture("curly_apostrophe_refusal", "I don’t have enough information to answer that.", FACT, True,
                       {"correctness": [0], "completeness": [0], "citation_support": [2], "abstained": True}),
    CalibrationFixture("explanatory_population_refusal",
                       "The study describes male mice only. It provides no results for female mice, so the requested female outcome cannot be determined.",
                       "The experiments used male mice only.", False,
                       {"correctness": [2], "completeness": [2], "citation_support": [2], "abstained": True},
                       question="How did treatment affect female mice?"),
    CalibrationFixture("missing_retrieval_refusal",
                       "The supplied excerpt describes equipment but no treatment results. I therefore cannot determine the percentage reduction.",
                       "The study describes equipment but reports no treatment outcomes.", True,
                       {"correctness": [0], "completeness": [0], "citation_support": [2], "abstained": True}),
    CalibrationFixture("refusal_followed_by_guess",
                       "I do not have enough information, but I would guess the treatment reduced the response by 56%.",
                       "The study describes equipment but reports no treatment outcomes.", True,
                       {"citation_support": [0], "abstained": False}),
    CalibrationFixture("partial_answer_missing_detail",
                       "The treatment reduced the response, but the percentage is not provided.", FACT, True,
                       {"completeness": [0, 1], "abstained": False}),
    CalibrationFixture("negative_finding_is_an_answer",
                       "The treatment caused no change in the measured response.",
                       "The treatment caused no change in the measured response.", True,
                       {"correctness": [2], "completeness": [2], "citation_support": [2], "abstained": False},
                       reference="The treatment caused no change in the measured response."),
)


def run_calibration(judge: Judge) -> CalibrationReport:
    """Require basic grading distinctions before publishing benchmark metrics.

    The judge gets the normal two-stage evaluation path, without expected scores.
    Transport and schema errors propagate to the runner's failure checkpoint.
    """
    results: list[CalibrationResult] = []
    for fixture in FIXTURES:
        case = AnswerEvaluationCase(
            id=fixture.id,
            question=fixture.question,
            answerable=fixture.answerable,
            reference_answer=fixture.reference or (FACT if fixture.answerable else "The information is not available."),
            evidence=[{"document": "synthetic.pdf", "page": 1, "quote": fixture.reference or FACT}] if fixture.answerable else [],
        )
        response = AnswerResult(answer=fixture.answer, sources=[ChunkData(
            document="synthetic.pdf", page=1, chunk_index=0, text=fixture.source,
        )])
        scores = score_answer(case, response, judge)
        actual: dict[str, object] = scores.model_dump()
        passed = all(
            actual[field] is expected if isinstance(expected, bool) else actual[field] in expected
            for field, expected in fixture.expected.items()
        )
        results.append(CalibrationResult(id=fixture.id, passed=passed,
                                         expected=fixture.expected, actual=actual))
    return CalibrationReport(version=CALIBRATION_VERSION,
                             passed=all(result["passed"] for result in results), results=results)
