import math
import unittest

from app.performance import (
    PerformanceTrace,
    StageTiming,
    TimingSummary,
    measure_stage,
    summarize,
)


class PerformanceTraceTests(unittest.TestCase):
    def test_measure_records_stage_duration_from_injected_clock(self) -> None:
        ticks = iter([10.0, 10.25])
        trace = PerformanceTrace(clock=lambda: next(ticks))

        with trace.measure("embedding"):
            pass

        self.assertEqual(
            trace.snapshot(), [StageTiming(stage="embedding", elapsed_ms=250.0)]
        )
        self.assertIsNone(trace.failed_stage)

    def test_measure_records_failed_stage_and_reraises_same_exception(self) -> None:
        error = RuntimeError("private prompt text")
        ticks = iter([1.0, 1.5])
        trace = PerformanceTrace(clock=lambda: next(ticks))

        with self.assertRaises(RuntimeError) as raised:
            with trace.measure("rerank"):
                raise error

        self.assertIs(raised.exception, error)
        self.assertEqual(trace.failed_stage, "rerank")
        self.assertEqual(trace.snapshot()[0].elapsed_ms, 500.0)

    def test_invalid_clock_delta_is_clamped_to_zero(self) -> None:
        for ending in (math.inf, math.nan, -1.0):
            with self.subTest(ending=ending):
                ticks = iter([1.0, ending])
                trace = PerformanceTrace(clock=lambda: next(ticks))
                with trace.measure("context"):
                    pass
                self.assertEqual(trace.snapshot()[0].elapsed_ms, 0.0)

    def test_measure_stage_without_a_trace_is_a_noop(self) -> None:
        with measure_stage(None, "generation"):
            pass


class TimingSummaryTests(unittest.TestCase):
    def test_summary_reports_median_nearest_rank_p90_and_population_spread(
        self,
    ) -> None:
        summary = summarize([100.0, 200.0, 300.0, 400.0, 500.0])

        self.assertEqual(summary.count, 5)
        self.assertEqual(summary.mean_ms, 300.0)
        self.assertEqual(summary.median_ms, 300.0)
        self.assertEqual(summary.p90_ms, 500.0)
        self.assertEqual(summary.min_ms, 100.0)
        self.assertEqual(summary.max_ms, 500.0)
        self.assertAlmostEqual(summary.stdev_ms, math.sqrt(20000.0))

    def test_p90_uses_nearest_rank_for_ten_samples(self) -> None:
        summary = summarize([float(value) for value in range(1, 11)])

        self.assertEqual(summary.p90_ms, 9.0)

    def test_summary_rejects_empty_nonfinite_or_negative_samples(self) -> None:
        for values in ([], [math.nan], [math.inf], [-1.0]):
            with self.subTest(values=values), self.assertRaises(ValueError):
                summarize(values)

    def test_summary_accepts_one_sample(self) -> None:
        summary: TimingSummary = summarize([12.5])

        self.assertEqual(summary.count, 1)
        self.assertEqual(summary.median_ms, 12.5)
        self.assertEqual(summary.stdev_ms, 0.0)
