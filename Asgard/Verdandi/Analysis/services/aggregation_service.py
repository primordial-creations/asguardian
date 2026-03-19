"""
Aggregation Service

Aggregates metrics over time windows.
"""

from datetime import datetime, timedelta
from typing import Optional, Sequence, Tuple, Union

from Asgard.Verdandi.Analysis.models.analysis_models import (
    AggregationConfig,
    AggregationResult,
    PercentileResult,
)
from Asgard.Verdandi.Analysis.services.percentile_calculator import PercentileCalculator


class AggregationService:
    """
    Service for aggregating performance metrics over time windows.

    Calculates summary statistics, percentiles, and histograms
    for metrics collected over specified time periods.

    Example:
        service = AggregationService()
        result = service.aggregate(
            values=[100, 150, 200, 250],
            timestamps=[...],
            window_seconds=60
        )
    """

    def __init__(self, config: Optional[AggregationConfig] = None):
        """
        Initialize the aggregation service.

        Args:
            config: Optional aggregation configuration
        """
        self.config = config or AggregationConfig()
        self._percentile_calc = PercentileCalculator()

    def aggregate(
        self,
        values: Sequence[Union[int, float]],
        window_start: Optional[datetime] = None,
        window_end: Optional[datetime] = None,
        config: Optional[AggregationConfig] = None,
    ) -> AggregationResult:
        """
        Aggregate values over a time window.

        Args:
            values: Sequence of metric values
            window_start: Start of aggregation window
            window_end: End of aggregation window
            config: Optional config override for this call

        Returns:
            AggregationResult with aggregated statistics
        """
        if not values:
            raise ValueError("Cannot aggregate empty dataset")

        cfg = config or self.config

        now = datetime.now()
        start = window_start or (now - timedelta(seconds=cfg.window_size_seconds))
        end = window_end or now

        window_seconds = (end - start).total_seconds()
        throughput = len(values) / window_seconds if window_seconds > 0 else 0

        percentiles = None
        if cfg.include_percentiles:
            percentiles = self._percentile_calc.calculate(values)

        histogram = None
        if cfg.include_histograms:
            histogram = self._percentile_calc.calculate_histogram(
                values,
                cfg.histogram_buckets,
            )

        return AggregationResult(
            window_start=start.isoformat(),
            window_end=end.isoformat(),
            sample_count=len(values),
            sum_value=sum(values),
            mean=sum(values) / len(values),
            min_value=min(values),
            max_value=max(values),
            percentiles=percentiles,
            histogram=histogram,
            throughput=round(throughput, 2),
        )

    def aggregate_by_windows(
        self,
        values: Sequence[Union[int, float]],
        timestamps: Sequence[datetime],
        window_seconds: Optional[int] = None,
    ) -> list[AggregationResult]:
        """
        Aggregate values into multiple time windows.

        Args:
            values: Sequence of metric values
            timestamps: Corresponding timestamps for each value
            window_seconds: Window size (uses config default if not specified)

        Returns:
            List of AggregationResult, one per window
        """
        if len(values) != len(timestamps):
            raise ValueError("Values and timestamps must have same length")
        if not values:
            return []

        window_size = window_seconds or self.config.window_size_seconds

        paired = sorted(zip(timestamps, values), key=lambda x: x[0])
        timestamps_sorted, values_sorted = zip(*paired)

        results = []
        window_start = timestamps_sorted[0]
        window_values: list[Union[int, float]] = []

        for ts, value in zip(timestamps_sorted, values_sorted):
            window_end = window_start + timedelta(seconds=window_size)

            if ts >= window_end:
                if window_values:
                    results.append(self.aggregate(
                        window_values,
                        window_start,
                        window_end,
                    ))
                window_start = ts
                window_values = [value]
            else:
                window_values.append(value)

        if window_values:
            results.append(self.aggregate(
                window_values,
                window_start,
                window_start + timedelta(seconds=window_size),
            ))

        return results

    def calculate_throughput(
        self,
        request_count: int,
        duration_seconds: float,
    ) -> float:
        """
        Calculate requests per second (RPS).

        Args:
            request_count: Total number of requests
            duration_seconds: Duration in seconds

        Returns:
            Requests per second
        """
        if duration_seconds <= 0:
            return 0.0
        return request_count / duration_seconds

    def calculate_rate(
        self,
        count: int,
        total: int,
    ) -> float:
        """
        Calculate a rate as a percentage.

        Args:
            count: Numerator (e.g., error count)
            total: Denominator (e.g., total requests)

        Returns:
            Rate as percentage (0-100)
        """
        if total <= 0:
            return 0.0
        return (count / total) * 100
