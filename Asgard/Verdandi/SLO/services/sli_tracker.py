"""
SLI Tracker Service

Tracks SLI metrics over time and provides history analysis.
"""

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Sequence

from Asgard.Verdandi.SLO.models.slo_models import (
    SLIMetric,
    SLOType,
)
from Asgard.Verdandi.SLO.services._sli_aggregation import aggregate_by_period


class SLITracker:
    """
    Tracker for SLI metrics over time.

    Provides methods to record SLI measurements, retrieve historical data,
    and calculate aggregated metrics over time periods.

    Example:
        tracker = SLITracker()

        # Record metrics
        tracker.record(SLIMetric(timestamp=now, service_name="api", ...))

        # Get history
        history = tracker.get_history("api", SLOType.AVAILABILITY, days=7)

        # Get aggregated metrics
        hourly = tracker.aggregate_by_hour("api", days=1)
    """

    def __init__(self):
        """Initialize the SLI tracker."""
        self._metrics: List[SLIMetric] = []
        self._metrics_by_service: Dict[str, List[SLIMetric]] = defaultdict(list)
        self._metrics_by_type: Dict[SLOType, List[SLIMetric]] = defaultdict(list)

    def record(self, metric: SLIMetric) -> None:
        """
        Record a single SLI metric.

        Args:
            metric: The SLI metric to record
        """
        self._metrics.append(metric)
        self._metrics_by_service[metric.service_name].append(metric)
        self._metrics_by_type[metric.slo_type].append(metric)

    def record_batch(self, metrics: Sequence[SLIMetric]) -> None:
        """
        Record multiple SLI metrics.

        Args:
            metrics: List of SLI metrics to record
        """
        for metric in metrics:
            self.record(metric)

    def get_history(
        self,
        service_name: Optional[str] = None,
        slo_type: Optional[SLOType] = None,
        days: Optional[int] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[SLIMetric]:
        """
        Get historical SLI metrics with optional filters.

        Args:
            service_name: Filter by service name
            slo_type: Filter by SLO type
            days: Get metrics from last N days (overrides start_time)
            start_time: Start of time range
            end_time: End of time range (default: now)

        Returns:
            List of matching SLI metrics
        """
        end_time = end_time or datetime.now()

        if days is not None:
            start_time = end_time - timedelta(days=days)

        if service_name and slo_type:
            metrics = [
                m
                for m in self._metrics_by_service.get(service_name, [])
                if m.slo_type == slo_type
            ]
        elif service_name:
            metrics = self._metrics_by_service.get(service_name, [])
        elif slo_type:
            metrics = self._metrics_by_type.get(slo_type, [])
        else:
            metrics = self._metrics

        if start_time:
            metrics = [
                m for m in metrics if m.timestamp >= start_time and m.timestamp <= end_time
            ]

        return sorted(metrics, key=lambda m: m.timestamp)

    def get_latest(
        self,
        service_name: str,
        slo_type: Optional[SLOType] = None,
    ) -> Optional[SLIMetric]:
        """
        Get the most recent SLI metric for a service.

        Args:
            service_name: Service name to query
            slo_type: Optional SLO type filter

        Returns:
            Most recent SLI metric or None
        """
        metrics = self._metrics_by_service.get(service_name, [])
        if slo_type:
            metrics = [m for m in metrics if m.slo_type == slo_type]

        if not metrics:
            return None

        return max(metrics, key=lambda m: m.timestamp)

    def aggregate_by_hour(
        self,
        service_name: Optional[str] = None,
        slo_type: Optional[SLOType] = None,
        days: int = 1,
    ) -> Dict[datetime, Dict[str, float]]:
        """
        Aggregate metrics by hour.

        Args:
            service_name: Filter by service name
            slo_type: Filter by SLO type
            days: Number of days to aggregate

        Returns:
            Dictionary mapping hour timestamp to aggregated metrics
        """
        metrics = self.get_history(service_name, slo_type, days=days)
        return aggregate_by_period(metrics, hours=1)

    def aggregate_by_day(
        self,
        service_name: Optional[str] = None,
        slo_type: Optional[SLOType] = None,
        days: int = 30,
    ) -> Dict[datetime, Dict[str, float]]:
        """
        Aggregate metrics by day.

        Args:
            service_name: Filter by service name
            slo_type: Filter by SLO type
            days: Number of days to aggregate

        Returns:
            Dictionary mapping day timestamp to aggregated metrics
        """
        metrics = self.get_history(service_name, slo_type, days=days)
        return aggregate_by_period(metrics, hours=24)

    def calculate_sli(
        self,
        service_name: Optional[str] = None,
        slo_type: Optional[SLOType] = None,
        days: Optional[int] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> Dict[str, float]:
        """
        Calculate aggregated SLI for a time period.

        Args:
            service_name: Filter by service name
            slo_type: Filter by SLO type
            days: Get metrics from last N days
            start_time: Start of time range
            end_time: End of time range

        Returns:
            Dictionary with calculated SLI statistics
        """
        metrics = self.get_history(service_name, slo_type, days, start_time, end_time)

        if not metrics:
            return {
                "total_events": 0,
                "good_events": 0,
                "bad_events": 0,
                "success_rate": 1.0,
                "failure_rate": 0.0,
                "measurement_count": 0,
            }

        total_events = sum(m.total_events for m in metrics)
        good_events = sum(m.good_events for m in metrics)
        bad_events = total_events - good_events

        success_rate = good_events / total_events if total_events > 0 else 1.0

        return {
            "total_events": total_events,
            "good_events": good_events,
            "bad_events": bad_events,
            "success_rate": success_rate,
            "failure_rate": 1.0 - success_rate,
            "measurement_count": len(metrics),
        }

    def get_services(self) -> List[str]:
        """Get list of all tracked services."""
        return list(self._metrics_by_service.keys())

    def get_slo_types(self, service_name: Optional[str] = None) -> List[SLOType]:
        """
        Get list of SLO types with recorded metrics.

        Args:
            service_name: Optional filter by service name

        Returns:
            List of SLO types
        """
        if service_name:
            metrics = self._metrics_by_service.get(service_name, [])
            return list(set(m.slo_type for m in metrics))
        return list(self._metrics_by_type.keys())

    def get_metric_count(
        self,
        service_name: Optional[str] = None,
        slo_type: Optional[SLOType] = None,
    ) -> int:
        """
        Get count of recorded metrics.

        Args:
            service_name: Filter by service name
            slo_type: Filter by SLO type

        Returns:
            Count of metrics
        """
        if service_name and slo_type:
            return sum(
                1
                for m in self._metrics_by_service.get(service_name, [])
                if m.slo_type == slo_type
            )
        elif service_name:
            return len(self._metrics_by_service.get(service_name, []))
        elif slo_type:
            return len(self._metrics_by_type.get(slo_type, []))
        return len(self._metrics)

    def clear(self, service_name: Optional[str] = None) -> None:
        """
        Clear recorded metrics.

        Args:
            service_name: If provided, only clear metrics for this service
        """
        if service_name:
            self._metrics = [
                m for m in self._metrics if m.service_name != service_name
            ]
            if service_name in self._metrics_by_service:
                for metric in self._metrics_by_service[service_name]:
                    self._metrics_by_type[metric.slo_type] = [
                        m
                        for m in self._metrics_by_type[metric.slo_type]
                        if m.service_name != service_name
                    ]
                del self._metrics_by_service[service_name]
        else:
            self._metrics = []
            self._metrics_by_service = defaultdict(list)
            self._metrics_by_type = defaultdict(list)
