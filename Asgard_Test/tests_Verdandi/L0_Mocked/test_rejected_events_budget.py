"""
Regression test: SLIMetric.rejected_events (valid rejections, e.g. typed
INSUFFICIENT_DATA outcomes) must never consume error budget or inflate
burn rate (DEEPTHINK_01), across both ErrorBudgetCalculator and
BurnRateAnalyzer.
"""

from datetime import datetime, timedelta

import pytest

from Asgard.Verdandi.SLO import (
    BurnRateAnalyzer,
    ErrorBudgetCalculator,
    SLIMetric,
    SLODefinition,
    SLOType,
)


def _slo():
    return SLODefinition(
        name="api", slo_type=SLOType.AVAILABILITY, target=99.0,
        window_days=30, service_name="api",
    )


class TestRejectedEventsExcludedFromBadEvents:
    def test_error_budget_excludes_rejections(self):
        now = datetime.now()
        # 100 total: 90 good, 5 rejected (valid INSUFFICIENT_DATA), 5 bad.
        metrics = [
            SLIMetric(
                timestamp=now - timedelta(hours=1), service_name="api",
                slo_type=SLOType.AVAILABILITY, good_events=90,
                total_events=100, rejected_events=5,
            )
        ]
        budget = ErrorBudgetCalculator().calculate(_slo(), metrics, now)
        assert budget.bad_events == 5
        assert budget.good_events == 90
        assert budget.total_events == 100

    def test_burn_rate_excludes_rejections(self):
        now = datetime.now()
        metrics = [
            SLIMetric(
                timestamp=now - timedelta(minutes=30), service_name="api",
                slo_type=SLOType.AVAILABILITY, good_events=90,
                total_events=100, rejected_events=10,
            )
        ]
        # Without rejections, bad_events would be 10; with 10 rejected, it's 0.
        result = BurnRateAnalyzer().analyze(_slo(), metrics, window_hours=1.0, current_time=now)
        assert result.burn_rate == pytest.approx(0.0)

    def test_sli_metric_bad_events_property(self):
        metric = SLIMetric(
            timestamp=datetime.now(), service_name="api",
            slo_type=SLOType.AVAILABILITY, good_events=90,
            total_events=100, rejected_events=5,
        )
        assert metric.bad_events == 5
