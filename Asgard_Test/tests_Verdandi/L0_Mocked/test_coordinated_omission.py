"""
L0 tests for the coordinated-omission toolkit (RESEARCH_14 / Gil Tene).
"""

import pytest

from Asgard.Verdandi.Analysis.services import coordinated_omission as co
from Asgard.Verdandi.Analysis.services.percentile_calculator import (
    PercentileCalculator,
)


class TestExpectedIntervalBackfill:
    def test_hdr_backfill_semantics(self):
        """A 100 ms sample at a 1 ms expected interval backfills
        99, 98, ..., 1 ms (99 synthetic samples)."""
        corrected = co.correct_expected_interval([100.0], 1.0)
        assert len(corrected) == 100
        assert corrected[0] == 100.0
        assert corrected[1] == 99.0
        assert corrected[-1] == 1.0

    def test_fast_samples_are_untouched(self):
        samples = [0.5, 0.8, 1.0]
        assert co.correct_expected_interval(samples, 1.0) == samples

    def test_nonpositive_interval_is_noop(self):
        assert co.correct_expected_interval([100.0], 0) == [100.0]

    def test_ycsb_style_case_corrected_p99_much_higher(self):
        """Directionally reproduces the RESEARCH_14 YCSB discrepancy:
        a closed-loop client targeting 1000 ops/s (1 ms interval) against a
        server that stalls for 10 s records mostly 4 ms samples; correction
        surfaces the hidden queueing and moves p99 dramatically."""
        samples = [4.0] * 590 + [10_000.0]  # ~60 s test, one 10 s stall
        calc = PercentileCalculator()
        uncorrected_p99 = calc.calculate_percentile(samples, 99)
        corrected = co.correct_expected_interval(samples, 1.0)
        corrected_p99 = calc.calculate_percentile(corrected, 99)
        assert uncorrected_p99 < 10.0
        assert corrected_p99 > 100 * uncorrected_p99


class TestTeneHeuristic:
    def test_fires_on_the_plan_example(self):
        """avg=5 ms, max=10 s, duration=60 s -> suspect."""
        assert co.tene_heuristic(avg_ms=5.0, max_ms=10_000.0, duration_ms=60_000.0)

    def test_does_not_fire_on_consistent_data(self):
        # avg 100 ms, max 200 ms over 60 s: 200^2/(2*60000) = 0.33 < 100
        assert not co.tene_heuristic(100.0, 200.0, 60_000.0)

    def test_degenerate_inputs(self):
        assert not co.tene_heuristic(5.0, 100.0, 0.0)
        assert not co.tene_heuristic(5.0, 0.0, 60_000.0)


class TestLittlesLaw:
    def test_consistent_report_passes(self):
        # 100 rps * 0.05 s = 5 in flight <= 10 allowed
        assert co.littles_law_check(100.0, 0.05, 10)

    def test_impossible_report_fails(self):
        # 1000 rps * 2 s = 2000 in flight > 100 allowed -> impossible
        assert not co.littles_law_check(1000.0, 2.0, 100)


class TestAnalyze:
    def test_flags_suspect_dataset(self):
        samples = [4.0] * 590 + [10_000.0]
        report = co.analyze(samples, duration_ms=60_000.0)
        assert report.suspect
        assert co.SUSPECT_COORDINATED_OMISSION in report.quality_flags

    def test_littles_law_violation_flag(self):
        report = co.analyze(
            [2000.0] * 100,
            duration_ms=60_000.0,
            throughput_rps=1000.0,
            max_concurrency=100,
        )
        assert co.LITTLES_LAW_VIOLATION in report.quality_flags
        assert report.implied_concurrency == pytest.approx(2000.0)

    def test_correction_flag_and_samples(self):
        report = co.analyze(
            [100.0],
            duration_ms=1_000.0,
            expected_interval_ms=1.0,
            apply_correction=True,
        )
        assert co.CO_CORRECTED in report.quality_flags
        assert len(report.corrected_samples_ms) == 100

    def test_clean_dataset_has_no_flags(self):
        report = co.analyze([100.0] * 100, duration_ms=60_000.0)
        assert not report.suspect
        assert report.quality_flags == []
