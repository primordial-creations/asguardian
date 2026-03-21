"""
Helpers for TraceAggregator.

Contains private helper functions extracted from the trace aggregator.
"""

from datetime import datetime
from typing import Dict, List, Optional, Sequence, cast

from Asgard.Verdandi.APM.models.apm_models import (
    ServiceMetrics,
    Span,
    SpanStatus,
    Trace,
)


def percentile(sorted_values: List[float], pct: float) -> float:
    """Calculate percentile from sorted values."""
    if not sorted_values:
        return 0.0

    n = len(sorted_values)
    if n == 1:
        return sorted_values[0]

    rank = (pct / 100) * (n - 1)
    lower_idx = int(rank)
    upper_idx = min(lower_idx + 1, n - 1)
    fraction = rank - lower_idx

    return sorted_values[lower_idx] + fraction * (
        sorted_values[upper_idx] - sorted_values[lower_idx]
    )


def group_spans_by_service(spans: Sequence[Span]) -> Dict[str, List[Span]]:
    """Group spans by service name."""
    result: Dict[str, List[Span]] = {}
    for span in spans:
        if span.service_name not in result:
            result[span.service_name] = []
        result[span.service_name].append(span)
    return result


def estimate_period_seconds(spans: Sequence[Span]) -> float:
    """Estimate the time period covered by spans."""
    if not spans:
        return 0.0

    start_times = [s.start_time for s in spans]
    end_times = [s.end_time for s in spans]

    min_start = min(start_times)
    max_end = max(end_times)

    return cast(float, max((cast(datetime, max_end) - cast(datetime, min_start)).total_seconds(), 1.0))


def get_earliest_time(traces: Sequence[Trace]) -> Optional[datetime]:
    """Get earliest timestamp from traces."""
    all_times = []
    for trace in traces:
        for span in trace.spans:
            all_times.append(span.start_time)
    return min(all_times) if all_times else None


def get_latest_time(traces: Sequence[Trace]) -> Optional[datetime]:
    """Get latest timestamp from traces."""
    all_times = []
    for trace in traces:
        for span in trace.spans:
            all_times.append(span.end_time)
    return max(all_times) if all_times else None


def calculate_health_score(
    error_rate: float,
    avg_latency_ms: float,
    p99_latency_ms: float,
    slow_trace_threshold_ms: float,
    health_error_weight: float,
    health_latency_weight: float,
) -> float:
    """
    Calculate overall health score (0-100).

    Lower error rates and latencies result in higher scores.
    """
    error_penalty = min(error_rate * 100 * health_error_weight, 30)

    latency_penalty = 0.0
    if p99_latency_ms > slow_trace_threshold_ms * 5:
        latency_penalty = health_latency_weight
    elif p99_latency_ms > slow_trace_threshold_ms * 2:
        latency_penalty = health_latency_weight * 0.5
    elif p99_latency_ms > slow_trace_threshold_ms:
        latency_penalty = health_latency_weight * 0.25

    score = 100.0 - error_penalty - latency_penalty
    return max(0.0, min(100.0, score))


def calculate_service_metrics(
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

    if start_time and end_time:
        period_seconds = (end_time - start_time).total_seconds()
    else:
        period_seconds = estimate_period_seconds(spans)

    throughput = len(spans) / period_seconds if period_seconds > 0 else 0.0

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
        p50_duration_ms=percentile(sorted_durations, 50),
        p95_duration_ms=percentile(sorted_durations, 95),
        p99_duration_ms=percentile(sorted_durations, 99),
        throughput_per_second=throughput,
        operations=operations,
    )


def generate_aggregator_recommendations(
    service_metrics: List[ServiceMetrics],
    slow_traces: List[Trace],
    error_traces: List[Trace],
    overall_error_rate: float,
    slow_trace_threshold_ms: float,
) -> List[str]:
    """Generate recommendations based on analysis."""
    recommendations = []

    if overall_error_rate > 0.05:
        recommendations.append(
            f"High overall error rate ({overall_error_rate * 100:.1f}%). "
            f"Investigate error sources and implement retry mechanisms."
        )

    for metrics in service_metrics:
        if metrics.error_rate > 0.1:
            recommendations.append(
                f"Service '{metrics.service_name}' has {metrics.error_rate * 100:.1f}% error rate. "
                f"Review error handling and service health."
            )

    for metrics in service_metrics:
        if metrics.p99_duration_ms > slow_trace_threshold_ms:
            recommendations.append(
                f"Service '{metrics.service_name}' has P99 latency of {metrics.p99_duration_ms:.0f}ms. "
                f"Consider caching, query optimization, or scaling."
            )

    if len(slow_traces) > 0:
        recommendations.append(
            f"{len(slow_traces)} traces exceeded {slow_trace_threshold_ms}ms threshold. "
            f"Profile the slowest operations to identify bottlenecks."
        )

    return recommendations
