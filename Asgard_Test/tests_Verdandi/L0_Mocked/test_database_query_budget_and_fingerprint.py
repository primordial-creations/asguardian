"""
Tests for the work-normalized query budget adapter and query-fingerprint
segmentation (Plan 07 C/D).
"""

import random

import pytest

from Asgard.Verdandi.Database import (
    QueryBudgetAnalyzer,
    QueryBudgetConfig,
    QueryMetricsCalculator,
    QueryMetricsInput,
    fingerprint_query,
)
from Asgard.Verdandi.Database.models.database_models import QueryType


class TestQueryBudgetAnalyzer:
    def setup_method(self):
        self.analyzer = QueryBudgetAnalyzer()

    def test_deepthink09_canonical_example(self):
        # Plan 07 L0: rows=0 -> budget 50ms (cache-hit path); rows=10000 -> 5050ms;
        # 300ms zero-row query fails, 4900ms 10k-row query passes.
        config = QueryBudgetConfig(base_ms=50.0, cost_per_unit_ms=0.5)

        assert self.analyzer.budget_for(config, 0) == 50.0
        assert self.analyzer.budget_for(config, 10_000) == 5050.0

        result = self.analyzer.evaluate(
            config,
            durations_ms=[300.0, 4900.0],
            units=[0, 10_000],
        )

        assert result.total == 2
        assert result.good == 1
        assert 0 in result.violations
        assert 1 not in result.violations

    def test_calibration_recovers_base_and_cost(self):
        # Plan 07 L0: duration = 40 + 0.6*rows + noise -> base~=40, cost~=0.6 within 15%.
        rng = random.Random(42)
        units = [float(rng.randint(0, 5000)) for _ in range(200)]
        durations = [40.0 + 0.6 * u + rng.uniform(-5, 5) for u in units]

        config = self.analyzer.calibrate(durations, units)

        assert config.base_ms == pytest.approx(40.0, rel=0.15)
        assert config.cost_per_unit_ms == pytest.approx(0.6, rel=0.15)


class TestFingerprinting:
    def test_collapses_literals(self):
        fp1 = fingerprint_query("SELECT * FROM users WHERE id = 1")
        fp2 = fingerprint_query("SELECT * FROM users WHERE id = 42")
        assert fp1 == fp2

    def test_collapses_string_literals_and_whitespace(self):
        fp1 = fingerprint_query("SELECT * FROM t WHERE name = 'alice'   AND x=1")
        fp2 = fingerprint_query("SELECT * FROM t WHERE name = 'bob' AND x=2")
        assert fp1 == fp2

    def test_different_shape_queries_differ(self):
        fp1 = fingerprint_query("SELECT * FROM users WHERE id = 1")
        fp2 = fingerprint_query("SELECT * FROM orders WHERE id = 1")
        assert fp1 != fp2


class TestQueryMetricsAnalyzeByFingerprint:
    def setup_method(self):
        self.calc = QueryMetricsCalculator()

    def _q(self, text, ms):
        return QueryMetricsInput(
            query_type=QueryType.SELECT,
            execution_time_ms=ms,
            query_text=text,
        )

    def test_segments_by_fingerprint(self):
        queries = [
            self._q("SELECT * FROM users WHERE id = 1", 5.0),
            self._q("SELECT * FROM users WHERE id = 2", 6.0),
            self._q("SELECT * FROM orders WHERE total > 100", 500.0),
        ]

        classes = self.calc.analyze_by_fingerprint(queries)

        assert len(classes) == 2
        users_class = next(c for c in classes if "USERS" in c.fingerprint)
        assert users_class.count == 2

    def test_flags_shift_vs_baseline(self):
        baseline_durations = [10.0 + (i % 5) for i in range(50)]
        current = [
            self._q("SELECT * FROM t WHERE id = 1", 80.0 + (i % 5)) for i in range(20)
        ]
        fp = fingerprint_query("SELECT * FROM t WHERE id = 1")

        classes = self.calc.analyze_by_fingerprint(
            current, baseline={fp: baseline_durations}
        )

        assert classes[0].shift_detected is True
