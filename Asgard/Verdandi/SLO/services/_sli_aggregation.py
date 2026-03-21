"""
Aggregation helpers for SLITracker.

Contains the aggregation logic extracted from the SLI tracker.
"""

from datetime import datetime
from typing import Dict, List

from Asgard.Verdandi.SLO.models.slo_models import SLIMetric


def aggregate_by_period(
    metrics: List[SLIMetric],
    hours: int,
) -> Dict[datetime, Dict[str, float]]:
    """Aggregate metrics by time period."""
    if not metrics:
        return {}

    aggregated: Dict[datetime, Dict[str, float]] = {}
    period_seconds = hours * 3600

    for metric in metrics:
        ts = metric.timestamp.timestamp()
        period_start_ts = ts - (ts % period_seconds)
        period_start = datetime.fromtimestamp(period_start_ts)

        if period_start not in aggregated:
            aggregated[period_start] = {
                "total_events": 0,
                "good_events": 0,
                "bad_events": 0,
                "measurement_count": 0,
            }

        aggregated[period_start]["total_events"] += metric.total_events
        aggregated[period_start]["good_events"] += metric.good_events
        aggregated[period_start]["bad_events"] += (
            metric.total_events - metric.good_events
        )
        aggregated[period_start]["measurement_count"] += 1

    for period_data in aggregated.values():
        total = period_data["total_events"]
        good = period_data["good_events"]
        period_data["success_rate"] = good / total if total > 0 else 1.0
        period_data["failure_rate"] = 1.0 - period_data["success_rate"]

    return dict(sorted(aggregated.items()))
