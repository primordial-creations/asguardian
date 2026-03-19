"""
Trace Aggregator Service

Aggregates distributed traces to produce service-level metrics.
"""

import math
from datetime import datetime
from typing import Dict, List, Optional, Sequence, cast

from Asgard.Verdandi.APM.models.apm_models import (
    APMReport,
    ServiceMetrics,
    Span,
    SpanStatus,
    Trace,
)


class TraceAggregator:
    """
    Aggregator for distributed traces.

    Processes traces to produce service-level metrics including latency
    distributions, error rates, and throughput.

    Example:
        aggregator = TraceAggregator()
        traces = [trace1, trace2, ...]
        report = aggregator.aggregate(traces)
        for service in report.service_metrics:
            print(f"{service.service_name}: {service.avg_duration_ms}ms")
    """

    def __init__(
        self,
        slow_trace_threshold_ms: float = 1000.0,
        health_error_weight: float = 30.0,
        health_latency_weight: float = 20.0,
    ):
        """
        Initialize the trace aggregator.

        Args:
            slow_trace_threshold_ms: Threshold for classifying traces as slow
            health_error_weight: Weight of error rate in health score
            health_latency_weight: Weight of latency in health score
        """
        self.slow_trace_threshold_ms = slow_trace_threshold_ms
        self.health_error_weight = health_error_weight
        self.health_latency_weight = health_latency_weight

    def aggregate(
        self,
        traces: Sequence[Trace],
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> APMReport:
        """
        Aggregate traces into a comprehensive APM report.

        Args:
            traces: List of traces to aggregate
            start_time: Optional analysis period start
            end_time: Optional analysis period end

        Returns:
            APMReport with aggregated metrics
        """
        if not traces:
            return APMReport(
                generated_at=datetime.now(),
                analysis_period_start=start_time,
                analysis_period_end=end_time,
            )

        # Collect all spans
        all_spans: List[Span] = []
        for trace in traces:
            all_spans.extend(trace.spans)

        # Group spans by service
        spans_by_service = self._group_spans_by_service(all_spans)

        # Calculate service metrics
        service_metrics = [
            self._calculate_service_metrics(service_name, spans, start_time, end_time)
            for service_name, spans in spans_by_service.items()
        ]

        # Identify slow and error traces
        slow_traces = [
            t for t in traces if t.total_duration_ms > self.slow_trace_threshold_ms
        ]
        error_traces = [t for t in traces if t.has_errors]

        # Calculate overall metrics
        total_errors = sum(t.error_count for t in traces)
        total_span_count = sum(t.span_count for t in traces)
        overall_error_rate = (
            total_errors / total_span_count if total_span_count > 0 else 0.0
        )

        durations = [t.total_duration_ms for t in traces]
        overall_avg_latency = sum(durations) / len(durations) if durations else 0.0
        overall_p99_latency = (
            self._percentile(sorted(durations), 99) if durations else 0.0
        )

        # Calculate health score
        health_score = self._calculate_health_score(
            overall_error_rate, overall_avg_latency, overall_p99_latency
        )

        # Generate recommendations
        recommendations = self._generate_recommendations(
            service_metrics, slow_traces, error_traces, overall_error_rate
        )

        return APMReport(
            generated_at=datetime.now(),
            analysis_period_start=start_time or self._get_earliest_time(traces),
            analysis_period_end=end_time or self._get_latest_time(traces),
            trace_count=len(traces),
            span_count=total_span_count,
            service_metrics=service_metrics,
            slow_traces=list(slow_traces[:10]),  # Limit to top 10
            error_traces=list(error_traces[:10]),
            overall_error_rate=overall_error_rate,
            overall_avg_latency_ms=overall_avg_latency,
            overall_p99_latency_ms=overall_p99_latency,
            recommendations=recommendations,
            health_score=health_score,
        )

    def aggregate_spans(
        self,
        spans: Sequence[Span],
    ) -> List[ServiceMetrics]:
        """
        Aggregate spans directly into service metrics.

        Args:
            spans: List of spans to aggregate

        Returns:
            List of ServiceMetrics, one per service
        """
        spans_by_service = self._group_spans_by_service(spans)
        return [
            self._calculate_service_metrics(service_name, service_spans, None, None)
            for service_name, service_spans in spans_by_service.items()
        ]

    def build_traces_from_spans(
        self,
        spans: Sequence[Span],
    ) -> List[Trace]:
        """
        Build trace objects from a flat list of spans.

        Args:
            spans: List of spans

        Returns:
            List of Trace objects
        """
        # Group spans by trace_id
        spans_by_trace: Dict[str, List[Span]] = {}
        for span in spans:
            if span.trace_id not in spans_by_trace:
                spans_by_trace[span.trace_id] = []
            spans_by_trace[span.trace_id].append(span)

        traces = []
        for trace_id, trace_spans in spans_by_trace.items():
            # Find root span
            root_span = next(
                (s for s in trace_spans if s.parent_span_id is None), None
            )

            # Calculate metrics
            services = set(s.service_name for s in trace_spans)
            error_count = sum(1 for s in trace_spans if s.status == SpanStatus.ERROR)
            total_duration = (
                root_span.duration_ms if root_span else max(s.duration_ms for s in trace_spans)
            )

            traces.append(
                Trace(
                    trace_id=trace_id,
                    root_span=root_span,
                    spans=trace_spans,
                    service_count=len(services),
                    total_duration_ms=total_duration,
                    error_count=error_count,
                )
            )

        return traces

    def _group_spans_by_service(
        self,
        spans: Sequence[Span],
    ) -> Dict[str, List[Span]]:
        """Group spans by service name."""
        result: Dict[str, List[Span]] = {}
        for span in spans:
            if span.service_name not in result:
                result[span.service_name] = []
            result[span.service_name].append(span)
        return result

    def _calculate_service_metrics(
        self,
        service_name: str,
        spans: List[Span],
        start_time: Optional[datetime],
        end_time: Optional[datetime],
    ) -> ServiceMetrics:
        """Calculate metrics for a single service."""
        if not spans:
            return ServiceMetrics(service_name=service_name)

        durations = [s.duration_ms for s in spans]
        sorted_durations = sorted(durations)
        error_count = sum(1 for s in spans if s.status == SpanStatus.ERROR)

        # Calculate throughput
        if start_time and end_time:
            period_seconds = (end_time - start_time).total_seconds()
        else:
            period_seconds = self._estimate_period_seconds(spans)

        throughput = len(spans) / period_seconds if period_seconds > 0 else 0.0

        # Group by operation
        operations: Dict[str, Dict[str, float]] = {}
        ops_by_name: Dict[str, List[Span]] = {}
        for span in spans:
            if span.operation_name not in ops_by_name:
                ops_by_name[span.operation_name] = []
            ops_by_name[span.operation_name].append(span)

        for op_name, op_spans in ops_by_name.items():
            op_durations = [s.duration_ms for s in op_spans]
            op_errors = sum(1 for s in op_spans if s.status == SpanStatus.ERROR)
            operations[op_name] = {
                "count": len(op_spans),
                "avg_ms": sum(op_durations) / len(op_durations),
                "min_ms": min(op_durations),
                "max_ms": max(op_durations),
                "error_count": op_errors,
                "error_rate": op_errors / len(op_spans) if op_spans else 0.0,
            }

        return ServiceMetrics(
            service_name=service_name,
            request_count=len(spans),
            error_count=error_count,
            error_rate=error_count / len(spans) if spans else 0.0,
            total_duration_ms=sum(durations),
            avg_duration_ms=sum(durations) / len(durations),
            min_duration_ms=min(durations),
            max_duration_ms=max(durations),
            p50_duration_ms=self._percentile(sorted_durations, 50),
            p95_duration_ms=self._percentile(sorted_durations, 95),
            p99_duration_ms=self._percentile(sorted_durations, 99),
            throughput_per_second=throughput,
            operations=operations,
        )

    def _percentile(
        self,
        sorted_values: List[float],
        percentile: float,
    ) -> float:
        """Calculate percentile from sorted values."""
        if not sorted_values:
            return 0.0

        n = len(sorted_values)
        if n == 1:
            return sorted_values[0]

        rank = (percentile / 100) * (n - 1)
        lower_idx = int(rank)
        upper_idx = min(lower_idx + 1, n - 1)
        fraction = rank - lower_idx

        return sorted_values[lower_idx] + fraction * (
            sorted_values[upper_idx] - sorted_values[lower_idx]
        )

    def _estimate_period_seconds(self, spans: Sequence[Span]) -> float:
        """Estimate the time period covered by spans."""
        if not spans:
            return 0.0

        start_times = [s.start_time for s in spans]
        end_times = [s.end_time for s in spans]

        min_start = min(start_times)
        max_end = max(end_times)

        return cast(float, max((cast(datetime, max_end) - cast(datetime, min_start)).total_seconds(), 1.0))

    def _get_earliest_time(self, traces: Sequence[Trace]) -> Optional[datetime]:
        """Get earliest timestamp from traces."""
        all_times = []
        for trace in traces:
            for span in trace.spans:
                all_times.append(span.start_time)
        return min(all_times) if all_times else None

    def _get_latest_time(self, traces: Sequence[Trace]) -> Optional[datetime]:
        """Get latest timestamp from traces."""
        all_times = []
        for trace in traces:
            for span in trace.spans:
                all_times.append(span.end_time)
        return max(all_times) if all_times else None

    def _calculate_health_score(
        self,
        error_rate: float,
        avg_latency_ms: float,
        p99_latency_ms: float,
    ) -> float:
        """
        Calculate overall health score (0-100).

        Lower error rates and latencies result in higher scores.
        """
        # Error penalty (0-30 points lost for high error rates)
        error_penalty = min(error_rate * 100 * self.health_error_weight, 30)

        # Latency penalty based on thresholds
        latency_penalty = 0.0
        if p99_latency_ms > self.slow_trace_threshold_ms * 5:
            latency_penalty = self.health_latency_weight
        elif p99_latency_ms > self.slow_trace_threshold_ms * 2:
            latency_penalty = self.health_latency_weight * 0.5
        elif p99_latency_ms > self.slow_trace_threshold_ms:
            latency_penalty = self.health_latency_weight * 0.25

        score = 100.0 - error_penalty - latency_penalty
        return max(0.0, min(100.0, score))

    def _generate_recommendations(
        self,
        service_metrics: List[ServiceMetrics],
        slow_traces: List[Trace],
        error_traces: List[Trace],
        overall_error_rate: float,
    ) -> List[str]:
        """Generate recommendations based on analysis."""
        recommendations = []

        # High error rate
        if overall_error_rate > 0.05:
            recommendations.append(
                f"High overall error rate ({overall_error_rate * 100:.1f}%). "
                f"Investigate error sources and implement retry mechanisms."
            )

        # Services with high error rates
        for metrics in service_metrics:
            if metrics.error_rate > 0.1:
                recommendations.append(
                    f"Service '{metrics.service_name}' has {metrics.error_rate * 100:.1f}% error rate. "
                    f"Review error handling and service health."
                )

        # Services with high latency
        for metrics in service_metrics:
            if metrics.p99_duration_ms > self.slow_trace_threshold_ms:
                recommendations.append(
                    f"Service '{metrics.service_name}' has P99 latency of {metrics.p99_duration_ms:.0f}ms. "
                    f"Consider caching, query optimization, or scaling."
                )

        # Too many slow traces
        if len(slow_traces) > 0:
            recommendations.append(
                f"{len(slow_traces)} traces exceeded {self.slow_trace_threshold_ms}ms threshold. "
                f"Profile the slowest operations to identify bottlenecks."
            )

        return recommendations
