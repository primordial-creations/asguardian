"""
Asgard Reporting Analyzer Service

Pure domain service responsible for computing metric trends and directional
classification from a set of analysis snapshots. This service contains only
analytical algorithms and depends on IHistoryRepository to fetch snapshot
data; it performs no direct I/O or database operations itself.
"""

from datetime import datetime
from typing import Dict, List, Optional, Tuple

from Asgard.Reporting.History.models.metric_policy import (
    get_lower_is_better_metrics,
)
from Asgard.Reporting.History.models.history_models import (
    MetricTrend,
    TrendDirection,
    TrendReport,
)
from Asgard.Reporting.History.ports.history_repository import IHistoryRepository


class ReportingAnalyzerService:
    """
    Computes metric trends across successive analysis snapshots.

    Depends on IHistoryRepository for data retrieval, keeping the analytical
    logic decoupled from any specific storage mechanism.
    """

    def __init__(self, repository: IHistoryRepository) -> None:
        self._repository = repository

    def get_trend_report(
        self,
        project_path: str,
        metric_names: Optional[List[str]] = None,
    ) -> TrendReport:
        """
        Compute metric trends for a project from all stored snapshots.

        Args:
            project_path: Absolute path to the project root.
            metric_names: Optional list of metric names to include in the report.
                          If None, all metrics present in the snapshots are included.

        Returns:
            TrendReport containing a MetricTrend for each tracked metric.
        """
        snapshots = self._repository.get_snapshots(project_path, limit=100)
        resolved = project_path

        if not snapshots:
            return TrendReport(
                project_path=resolved,
                metric_trends=[],
                analysis_count=0,
                first_analysis=None,
                last_analysis=None,
                generated_at=datetime.now(),
            )

        chronological = list(reversed(snapshots))
        first_ts = chronological[0].scan_timestamp
        last_ts = chronological[-1].scan_timestamp

        all_metric_names: List[str] = []
        for snap in chronological:
            for m in snap.metrics:
                if m.metric_name not in all_metric_names:
                    all_metric_names.append(m.metric_name)

        if metric_names:
            target_metrics = [n for n in all_metric_names if n in metric_names]
        else:
            target_metrics = all_metric_names

        metric_history: Dict[str, List[Tuple[datetime, float]]] = {
            name: [] for name in target_metrics
        }

        for snap in chronological:
            for name in target_metrics:
                value = snap.get_metric(name)
                if value is not None:
                    metric_history[name].append((snap.scan_timestamp, value))

        trends: List[MetricTrend] = []
        for name in target_metrics:
            history = metric_history[name]
            if len(history) < 2:
                continue

            _current_ts, current_value = history[-1]
            _prev_ts, previous_value = history[-2]
            change = current_value - previous_value

            if previous_value != 0:
                change_percentage = (change / abs(previous_value)) * 100.0
            else:
                change_percentage = 0.0

            direction = self._compute_direction(name, change_percentage)

            trends.append(MetricTrend(
                metric_name=name,
                current_value=current_value,
                previous_value=previous_value,
                change=change,
                change_percentage=change_percentage,
                direction=direction,
                snapshots=history,
            ))

        return TrendReport(
            project_path=resolved,
            metric_trends=trends,
            analysis_count=len(snapshots),
            first_analysis=first_ts,
            last_analysis=last_ts,
            generated_at=datetime.now(),
        )

    def _compute_direction(
        self, metric_name: str, change_percentage: float
    ) -> TrendDirection:
        """
        Determine the trend direction for a metric.

        For higher-is-better metrics: positive change is IMPROVING, negative is DEGRADING.
        For lower-is-better metrics: the logic is inverted.
        Changes within +/-5% are considered STABLE.

        Args:
            metric_name: Name of the metric.
            change_percentage: Percentage change (current - previous) / previous * 100.

        Returns:
            TrendDirection value.
        """
        threshold = 5.0
        lower_is_better = metric_name in get_lower_is_better_metrics()

        if abs(change_percentage) < threshold:
            return TrendDirection.STABLE

        if lower_is_better:
            if change_percentage <= -threshold:
                return TrendDirection.IMPROVING
            return TrendDirection.DEGRADING
        else:
            if change_percentage >= threshold:
                return TrendDirection.IMPROVING
            return TrendDirection.DEGRADING
