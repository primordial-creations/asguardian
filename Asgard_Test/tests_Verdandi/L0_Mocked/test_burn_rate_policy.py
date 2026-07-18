"""
L0 tests for multi-window burn-rate alert policy, threshold derivation,
traffic-validity gating, and detection-limit metadata.

Encodes the DEEPTHINK_05 worked numeric examples as regression tests so the
burn-rate math stays anchored to its sources.
"""

from datetime import datetime, timedelta

import pytest

from Asgard.Verdandi.SLO.models.slo_models import SLIMetric, SLODefinition, SLOType
from Asgard.Verdandi.SLO.services.burn_rate_analyzer import BurnRateAnalyzer
from Asgard.Verdandi.SLO.services._burn_rate_helpers import (
    full_outage_burn_rate,
    min_detectable_outage_seconds,
    minimum_traffic_for_target,
)

_NOW = datetime(2026, 7, 1, 12, 0, 0)


def _slo(target: float = 99.9, window_days: int = 30) -> SLODefinition:
    return SLODefinition(
        name="availability",
        slo_type=SLOType.AVAILABILITY,
        target=target,
        window_days=window_days,
        service_name="svc",
    )


def _metric(minutes_ago: float, good: int, total: int) -> SLIMetric:
    return SLIMetric(
        timestamp=_NOW - timedelta(minutes=minutes_ago),
        service_name="svc",
        slo_type=SLOType.AVAILABILITY,
        good_events=good,
        total_events=total,
    )


def _steady_traffic(hours: float, failure_rate: float, per_minute: int = 200):
    """One metric per minute over `hours` at the given failure rate."""
    metrics = []
    total_minutes = int(hours * 60)
    for i in range(total_minutes):
        total = per_minute
        bad = round(total * failure_rate)
        metrics.append(_metric(i + 0.5, total - bad, total))
    return metrics


class TestBurnRateArithmetic:
    """DEEPTHINK_05 worked examples."""

    def setup_method(self):
        self.analyzer = BurnRateAnalyzer()

    def test_full_outage_burn_rate_is_1000x_for_999(self):
        """99.9% SLO, 100% outage -> burn rate exactly 1000x."""
        metrics = _steady_traffic(hours=1.0, failure_rate=1.0)
        result = self.analyzer.analyze(_slo(), metrics, 1.0, _NOW)
        assert result.burn_rate == pytest.approx(1000.0)

    def test_144x_burn_consumes_2pct_of_budget_in_1h(self):
        """14.4x over 1h on a 30d SLO consumes exactly 2% of total budget."""
        metrics = [_metric(30.0, 100_000 - 1_440, 100_000)]
        result = self.analyzer.analyze(_slo(), metrics, 1.0, _NOW)
        assert result.burn_rate == pytest.approx(14.4, rel=0.01)
        assert result.budget_consumed_in_window == pytest.approx(2.0, rel=0.01)

    def test_deploy_2min_5pct_errors_does_not_page(self):
        """2 min @ 5% errors in a 1h window -> BR ~1.66x, below 14.4."""
        metrics = _steady_traffic(hours=1.0, failure_rate=0.0)
        # Replace the 2 most recent minutes with 5% errors.
        metrics[0] = _metric(0.5, 190, 200)
        metrics[1] = _metric(1.5, 190, 200)
        result = self.analyzer.analyze(_slo(), metrics, 1.0, _NOW)
        assert result.burn_rate == pytest.approx(1.667, rel=0.02)
        assert not result.is_critical

    def test_deploy_2min_50pct_errors_pages(self):
        """2 min @ 50% errors in a 1h window -> BR ~16.6x, page."""
        metrics = _steady_traffic(hours=1.0, failure_rate=0.0)
        metrics[0] = _metric(0.5, 100, 200)
        metrics[1] = _metric(1.5, 100, 200)
        result = self.analyzer.analyze(_slo(), metrics, 1.0, _NOW)
        assert result.burn_rate == pytest.approx(16.67, rel=0.02)
        assert result.is_critical


class TestDetectionLimits:
    def test_full_outage_burn_rate_helper(self):
        assert full_outage_burn_rate(0.999) == pytest.approx(1000.0)
        assert full_outage_burn_rate(0.99) == pytest.approx(100.0)

    def test_min_detectable_outage_1h_window(self):
        """99.9% + 14.4x + 1h -> 51.84 s."""
        assert min_detectable_outage_seconds(0.999, 14.4, 1.0) == pytest.approx(51.84)

    def test_min_detectable_outage_5m_guard(self):
        """99.9% + 14.4x + 5m -> 4.32 s."""
        assert min_detectable_outage_seconds(0.999, 14.4, 5.0 / 60.0) == pytest.approx(4.32)

    def test_alert_carries_detection_limit_metadata(self):
        analyzer = BurnRateAnalyzer()
        alerts = analyzer.evaluate_alert_policy(_slo(), [], _NOW)
        page_fast = alerts[0]
        assert page_fast.min_detectable_outage_seconds == pytest.approx(51.84)
        assert page_fast.min_detectable_outage_seconds_short == pytest.approx(4.32)


class TestMinimumTrafficGate:
    def test_minimum_traffic_for_999_target(self):
        assert minimum_traffic_for_target(0.999) == 10_000

    def test_minimum_traffic_for_99_target(self):
        assert minimum_traffic_for_target(0.99) == 1_000

    def test_rejects_non_fraction_target(self):
        with pytest.raises(ValueError):
            minimum_traffic_for_target(99.9)

    def test_low_traffic_never_fires_even_at_full_outage(self):
        """100% outage on 60 events/h: burn is huge but traffic is invalid."""
        analyzer = BurnRateAnalyzer()
        metrics = _steady_traffic(hours=72.0, failure_rate=1.0, per_minute=1)
        alerts = analyzer.evaluate_alert_policy(_slo(), metrics, _NOW)
        page_fast = alerts[0]
        assert page_fast.long_burn_rate == pytest.approx(1000.0)
        assert page_fast.insufficient_traffic
        assert page_fast.severity == "insufficient_traffic"
        assert not page_fast.fired
        assert page_fast.min_events_required == 10_000
        assert any("synthetic" in r for r in page_fast.recommendations)


class TestAlertPolicyTiers:
    def setup_method(self):
        self.analyzer = BurnRateAnalyzer()

    def test_policy_uses_reference_window_pairs(self):
        """1h/5m, 6h/30m, 72h/6h per the 1/12 rule."""
        pairs = [
            (a[1], a[2], a[3]) for a in BurnRateAnalyzer.ALERT_POLICY
        ]
        assert pairs == [
            (1.0, 5.0 / 60.0, 14.4),
            (6.0, 0.5, 6.0),
            (72.0, 6.0, 1.0),
        ]
        for long_h, short_h, _ in pairs:
            assert short_h == pytest.approx(long_h / 12.0)

    def test_multi_window_default_pair_is_1h_5m(self):
        metrics = _steady_traffic(hours=1.0, failure_rate=0.02)
        result = self.analyzer.multi_window_analyze(_slo(), metrics, current_time=_NOW)
        assert result.window_hours == 1.0

    def test_sustained_full_outage_fires_page_fast(self):
        metrics = _steady_traffic(hours=1.0, failure_rate=1.0)
        alerts = self.analyzer.evaluate_alert_policy(_slo(), metrics, _NOW)
        page_fast = alerts[0]
        assert page_fast.fired
        assert page_fast.severity == "page"

    def test_recovered_burn_does_not_page_thanks_to_guard_window(self):
        """Burn happened 30-55 min ago but the last 5 min are clean:
        the 1h window is still hot but the 5m guard resets the page."""
        metrics = _steady_traffic(hours=1.0, failure_rate=0.0)
        for i in range(30, 55):
            metrics[i] = _metric(i + 0.5, 0, 200)  # 100% errors, 30-55m ago
        alerts = self.analyzer.evaluate_alert_policy(_slo(), metrics, _NOW)
        page_fast = alerts[0]
        assert page_fast.long_burn_rate >= 14.4
        assert page_fast.short_burn_rate < 14.4
        assert not page_fast.fired

    def test_sawtooth_evades_page_fast_but_fires_ticket(self):
        """30 s outage every 61 min: never pages, but the 72h TICKET tier
        catches the sustained overspend (the documented blind spot)."""
        metrics = []
        minute = 0.0
        while minute < 72 * 60:
            in_outage = (minute % 61.0) < 0.5  # 30 s of each 61-min cycle
            total = 200
            bad = total if in_outage else 0
            metrics.append(_metric(minute + 0.25, total - bad, total))
            minute += 0.5
        alerts = self.analyzer.evaluate_alert_policy(_slo(), metrics, _NOW)
        page_fast, page_slow, ticket = alerts
        assert not page_fast.fired, (
            f"PAGE_FAST must not fire: long={page_fast.long_burn_rate:.1f}"
        )
        assert ticket.fired, (
            f"TICKET must fire: 72h={ticket.long_burn_rate:.2f}, "
            f"6h={ticket.short_burn_rate:.2f}"
        )

    def test_no_traffic_reports_insufficient_not_none(self):
        alerts = self.analyzer.evaluate_alert_policy(_slo(), [], _NOW)
        assert all(a.severity == "insufficient_traffic" for a in alerts)
        assert all(not a.fired for a in alerts)

    def test_blind_spot_note_only_when_evaluated_with_valid_data(self):
        """Regression: the ticket-tier sub-critical-bleed note must not be
        appended when the policy ran with no/insufficient traffic, and must
        be present when evaluated with valid data."""
        no_data = self.analyzer.evaluate_alert_policy(_slo(), [], _NOW)
        ticket_empty = no_data[2]
        assert not any("safety net" in r for r in ticket_empty.recommendations)

        metrics = _steady_traffic(hours=72.0, failure_rate=0.0, per_minute=200)
        with_data = self.analyzer.evaluate_alert_policy(_slo(), metrics, _NOW)
        ticket = with_data[2]
        assert not ticket.insufficient_traffic
        assert any("safety net" in r for r in ticket.recommendations)


class TestThresholdDerivation:
    def setup_method(self):
        self.analyzer = BurnRateAnalyzer()

    @pytest.mark.parametrize(
        "window_days,expected",
        [(30, 14.4), (28, 13.44), (14, 6.72), (7, 3.36)],
    )
    def test_rescaled_thresholds(self, window_days, expected):
        derivation = self.analyzer.derive_thresholds(window_days)
        assert derivation.derived_threshold == pytest.approx(expected)

    def test_recommendation_keeps_default_with_noise_floor_caveat(self):
        derivation = self.analyzer.derive_thresholds(7)
        assert derivation.recommended_threshold == 14.4
        assert any("noise floor" in r for r in derivation.recommendations)

    def test_invalid_inputs_raise(self):
        with pytest.raises(ValueError):
            self.analyzer.derive_thresholds(0)
        with pytest.raises(ValueError):
            self.analyzer.derive_thresholds(30, budget_fraction=1.5)
