"""Opt-in monotonic stage timing and small-sample summary statistics."""

from __future__ import annotations

import math
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from statistics import mean, median, pstdev
from time import perf_counter
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

PipelineStage = Literal["embedding", "vector_search", "rerank", "context", "generation"]


class StageTiming(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    stage: PipelineStage
    elapsed_ms: float = Field(ge=0)


class TimingSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    count: int = Field(ge=1)
    mean_ms: float = Field(ge=0)
    median_ms: float = Field(ge=0)
    p90_ms: float = Field(ge=0)
    min_ms: float = Field(ge=0)
    max_ms: float = Field(ge=0)
    stdev_ms: float = Field(ge=0)


class PerformanceTrace:
    """Collect stage durations only when explicitly passed into the answer path."""

    def __init__(self, clock: Callable[[], float] = perf_counter) -> None:
        self._clock = clock
        self._timings: list[StageTiming] = []
        self._failed_stage: PipelineStage | None = None

    @property
    def failed_stage(self) -> PipelineStage | None:
        return self._failed_stage

    @contextmanager
    def measure(self, stage: PipelineStage) -> Iterator[None]:
        started = self._clock()
        try:
            yield
        except BaseException:
            self._failed_stage = stage
            raise
        finally:
            elapsed_ms = (self._clock() - started) * 1000
            if not math.isfinite(elapsed_ms) or elapsed_ms < 0:
                elapsed_ms = 0.0
            self._timings.append(StageTiming(stage=stage, elapsed_ms=elapsed_ms))

    def snapshot(self) -> list[StageTiming]:
        return list(self._timings)


@contextmanager
def measure_stage(
    trace: PerformanceTrace | None, stage: PipelineStage
) -> Iterator[None]:
    """Avoid clock reads and allocation when performance tracing is not requested."""
    if trace is None:
        yield
        return
    with trace.measure(stage):
        yield


def summarize(values: list[float]) -> TimingSummary:
    """Summarize measured samples with a nearest-rank p90."""
    if not values or any(not math.isfinite(value) or value < 0 for value in values):
        raise ValueError("timing samples must be finite, nonnegative and nonempty")
    ordered = sorted(float(value) for value in values)
    return TimingSummary(
        count=len(ordered),
        mean_ms=mean(ordered),
        median_ms=median(ordered),
        p90_ms=ordered[max(0, math.ceil(0.9 * len(ordered)) - 1)],
        min_ms=ordered[0],
        max_ms=ordered[-1],
        stdev_ms=pstdev(ordered),
    )
