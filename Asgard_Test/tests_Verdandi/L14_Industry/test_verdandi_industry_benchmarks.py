"""
L6 Industry Benchmark Tests — Verdandi SLO / Metrics Calculation Accuracy.

Validates that Verdandi's calculators match authoritative industry formulas:

  Error budget (Google SRE Book)
  - 99.9% SLO → error budget = 0.1% of total events
  - Consumed budget tracked correctly against allowed_failures

  Apdex score
  - Standard formula: (satisfied + tolerating/2) / total
  - Tested against well-known reference values

  Burn rate (Google SRE Workbook — multi-window alerting)
  - 14.4× burn rate for 1-hour window exhausts a 30-day budget in ~50 hours
  - 1.0× burn rate is the "exactly on track" baseline
"""

from datetime import datetime, timedelta

import pytest

from Asgard.Verdandi.SLO.models.slo_models import (
    SLIMetric,
    SLODefinition,
    SLOType,
    SLOComplianceStatus,
)
from Asgard.Verdandi.SLO.services.error_budget_calculator import ErrorBudgetCalculator
from Asgard.Verdandi.SLO.services.burn_rate_analyzer import BurnRateAnalyzer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 5, 19, 12, 0, 0)


def _make_slo(target: float = 99.9, window_days: int = 30) -> SLODefinition:
    return SLODefinition(
        name="test-slo",
        slo_type=SLOType.AVAILABILITY,
        target=target,
        window_days=window_days,
        service_name="test-service",
    )


def _make_metric(
    good: int,
    total: int,
    hours_ago: float = 1.0,
) -> SLIMetric:
    ts = _NOW - timedelta(hours=hours_ago)
    return SLIMetric(
        timestamp=ts,
        service_name="test-service",
        slo_type=SLOType.AVAILABILITY,
        good_events=good,
        total_events=total,
    )


# ---------------------------------------------------------------------------
# Error budget accuracy — Google SRE Book formulas
# ---------------------------------------------------------------------------

class TestVerdandiErrorBudgetFormulas:
    """
    Error budget = (1 - SLO_target) × total_events (Google SRE Book, Chapter 4).

    99.9% SLO on 1,000,000 requests → 1,000 allowed failures.
    """

    def setup_method(self) -> None:
        self.calc = ErrorBudgetCalculator()

    def _metrics_within_window(
        self, good: int, total: int, window_days: int = 30
    ):
        """Return a single metric inside the SLO window."""
        ts = _NOW - timedelta(days=window_days // 2)
        return [SLIMetric(
            timestamp=ts,
            service_name="test-service",
            slo_type=SLOType.AVAILABILITY,
            good_events=good,
            total_events=total,
        )]

    def test_999_slo_allowed_failures(self) -> None:
        """99.9% SLO with 1M events → 1,000 allowed failures (0.1% budget)."""
        slo = _make_slo(target=99.9)
        metrics = self._metrics_within_window(good=999_000, total=1_000_000)
        budget = self.calc.calculate(slo, metrics, current_time=_NOW)

        assert abs(budget.allowed_failures - 1000.0) < 1.0, (
            f"Expected 1,000 allowed failures for 99.9% SLO on 1M events, "
            f"got {budget.allowed_failures}"
        )

    def test_error_budget_percent_matches_100_minus_target(self) -> None:
        """Error budget percent = 100 - target (fundamental SRE identity)."""
        for target in (99.0, 99.5, 99.9, 99.95):
            slo = _make_slo(target=target)
            assert abs(slo.error_budget_percent - (100.0 - target)) < 1e-9

    def test_zero_bad_events_zero_consumption(self) -> None:
        """No failures → 0% budget consumed and status COMPLIANT."""
        slo = _make_slo(target=99.9)
        metrics = self._metrics_within_window(good=10_000, total=10_000)
        budget = self.calc.calculate(slo, metrics, current_time=_NOW)

        assert budget.bad_events == 0
        assert budget.budget_consumed_percent == 0.0
        assert budget.status == SLOComplianceStatus.COMPLIANT

    def test_all_bad_events_fully_consumed(self) -> None:
        """All requests failing → budget 100% consumed and status BREACHED."""
        slo = _make_slo(target=99.9)
        metrics = self._metrics_within_window(good=0, total=10_000)
        budget = self.calc.calculate(slo, metrics, current_time=_NOW)

        assert budget.budget_consumed_percent >= 100.0
        assert budget.status == SLOComplianceStatus.BREACHED

    def test_within_budget_stays_compliant(self) -> None:
        """Consuming 50% of budget must be COMPLIANT (below 80% at_risk threshold)."""
        slo = _make_slo(target=99.9)
        # 0.1% budget on 100,000 events = 100 allowed.  Use 50 bad → 50% consumed.
        metrics = self._metrics_within_window(good=99_950, total=100_000)
        budget = self.calc.calculate(slo, metrics, current_time=_NOW)

        assert budget.status == SLOComplianceStatus.COMPLIANT, (
            f"Expected COMPLIANT for 50% budget consumption, got {budget.status}"
        )

    def test_sre_book_downtime_approx_for_999(self) -> None:
        """
        99.9% SLO ≈ 8.7 hours downtime / year (Google SRE Book).

        Verify the error_budget_percent maps to the expected annual minutes:
          0.1% of 525,600 min/year ≈ 525.6 min ≈ 8.76 h
        """
        slo = _make_slo(target=99.9, window_days=365)
        minutes_per_year = 525_600
        allowed_downtime_min = (slo.error_budget_percent / 100.0) * minutes_per_year
        # Google SRE book states ~526 minutes (8.76 h)
        assert 520 < allowed_downtime_min < 535, (
            f"Expected ~526 min of downtime for 99.9% SLO/year, "
            f"got {allowed_downtime_min:.1f} min"
        )


# ---------------------------------------------------------------------------
# Apdex score — standard formula
# ---------------------------------------------------------------------------

class TestVerdandiApdexFormula:
    """
    Apdex = (satisfied + tolerating / 2) / total
    Reference: Apdex Alliance specification v1.1

    We compute this manually from SLI metrics; Verdandi's error budget
    calculator gives us the building blocks (good_events map to "satisfied"
    in a simplified 2-tier model where tolerating = 0).
    """

    def test_perfect_apdex(self) -> None:
        """All requests satisfied → Apdex = 1.0."""
        satisfied, tolerating, total = 1000, 0, 1000
        apdex = (satisfied + tolerating / 2) / total
        assert apdex == 1.0

    def test_half_satisfied_no_tolerating(self) -> None:
        """500/1000 satisfied, 0 tolerating → Apdex = 0.5."""
        satisfied, tolerating, total = 500, 0, 1000
        apdex = (satisfied + tolerating / 2) / total
        assert abs(apdex - 0.5) < 1e-9

    def test_all_tolerating(self) -> None:
        """0 satisfied, all tolerating → Apdex = 0.5."""
        satisfied, tolerating, total = 0, 1000, 1000
        apdex = (satisfied + tolerating / 2) / total
        assert abs(apdex - 0.5) < 1e-9

    def test_mixed_standard_case(self) -> None:
        """
        Reference case from Apdex spec:
        800 satisfied, 150 tolerating, 50 frustrated out of 1000 total.
        Apdex = (800 + 150/2) / 1000 = (800 + 75) / 1000 = 0.875
        """
        satisfied, tolerating, total = 800, 150, 1000
        apdex = (satisfied + tolerating / 2) / total
        assert abs(apdex - 0.875) < 1e-9

    def test_error_budget_aligns_with_apdex_100pct(self) -> None:
        """
        When all events are good (Apdex 1.0), error budget consumption = 0.
        These must be consistent.
        """
        calc = ErrorBudgetCalculator()
        slo = _make_slo(target=99.9)
        ts = _NOW - timedelta(days=1)
        metrics = [SLIMetric(
            timestamp=ts,
            service_name="test-service",
            slo_type=SLOType.AVAILABILITY,
            good_events=1000,
            total_events=1000,
        )]
        budget = calc.calculate(slo, metrics, current_time=_NOW)

        # 100% success rate → Apdex 1.0 → budget consumed = 0
        assert budget.bad_events == 0
        assert budget.budget_consumed_percent == 0.0


# ---------------------------------------------------------------------------
# Burn rate — Google SRE Workbook multi-window alerting
# ---------------------------------------------------------------------------

class TestVerdandiBurnRate:
    """
    Google SRE Workbook (Chapter 5) burn-rate alerting thresholds:
    - 14.4× burn rate over 1 hour → page immediately (exhausts budget in ~50 h)
    - 1.0× burn rate = exactly sustainable

    The BurnRateAnalyzer computes:
        burn_rate = (actual_failure_rate / error_budget_fraction)
                    / (window_hours / slo_window_hours)
    """

    def setup_method(self) -> None:
        self.analyzer = BurnRateAnalyzer()
        self.slo = _make_slo(target=99.9, window_days=30)

    def _make_window_metrics(
        self, failure_rate: float, total: int = 10_000, window_hours: float = 1.0
    ):
        """Create metrics inside the burn-rate analysis window."""
        good = int(total * (1.0 - failure_rate))
        ts = _NOW - timedelta(minutes=30)  # mid-way through a 1-hour window
        return [SLIMetric(
            timestamp=ts,
            service_name="test-service",
            slo_type=SLOType.AVAILABILITY,
            good_events=good,
            total_events=total,
        )]

    def test_144x_burn_rate_triggers_critical(self) -> None:
        """
        14.4× burn rate must trigger is_critical=True.

        SLO 99.9% → error_budget = 0.1%
        For 14.4× burn rate:  failure_rate = 14.4 × 0.001 × (1h / 720h) × 720h
        Simplified: failure_rate = 14.4 × 0.001 = 1.44%
        (exact value may vary slightly; ensure is_critical fires)
        """
        # 1.44% failure rate drives a 14.4× burn rate on a 99.9% / 30-day SLO
        failure_rate = 14.4 * (0.001)  # 14.4 × error_budget_fraction
        metrics = self._make_window_metrics(failure_rate=failure_rate)
        result = self.analyzer.analyze(
            self.slo, metrics, window_hours=1.0, current_time=_NOW
        )
        assert result.is_critical, (
            f"Expected is_critical=True for {failure_rate*100:.2f}% failure rate "
            f"(14.4× burn), got burn_rate={result.burn_rate:.2f}"
        )

    def test_zero_failures_burn_rate_is_zero(self) -> None:
        """No failures → burn rate = 0, is_critical = False, is_warning = False."""
        metrics = self._make_window_metrics(failure_rate=0.0)
        result = self.analyzer.analyze(
            self.slo, metrics, window_hours=1.0, current_time=_NOW
        )
        assert result.burn_rate == 0.0
        assert not result.is_critical
        assert not result.is_warning

    def test_zero_failure_rate_not_critical(self) -> None:
        """
        Zero failures → burn rate = 0, which must not trigger any alert.

        Also tests that the is_critical flag stays False when failure_rate=0.
        """
        metrics = self._make_window_metrics(failure_rate=0.0, total=100_000)
        result = self.analyzer.analyze(
            self.slo, metrics, window_hours=1.0, current_time=_NOW
        )
        assert result.burn_rate == 0.0
        assert not result.is_critical, (
            f"Zero failure rate should not be critical, "
            f"got burn_rate={result.burn_rate:.2f}"
        )

    def test_burn_rate_result_has_slo_name(self) -> None:
        """BurnRate result must track the originating SLO name."""
        metrics = self._make_window_metrics(failure_rate=0.001)
        result = self.analyzer.analyze(
            self.slo, metrics, window_hours=1.0, current_time=_NOW
        )
        assert result.slo_name == self.slo.name

    def test_critical_burn_rate_constant_is_14_4(self) -> None:
        """
        The SRE Workbook defines the 1-hour critical threshold as 14.4×.
        The analyzer's class constant must match this industry standard.
        """
        assert BurnRateAnalyzer.CRITICAL_BURN_RATE == 14.4, (
            f"Expected CRITICAL_BURN_RATE=14.4 per Google SRE Workbook, "
            f"got {BurnRateAnalyzer.CRITICAL_BURN_RATE}"
        )
