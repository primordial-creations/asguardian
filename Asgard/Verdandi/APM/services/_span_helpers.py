"""
Helpers for SpanAnalyzer.

Contains private helper functions extracted from the span analyzer.
"""

from typing import Dict, List, Sequence

from Asgard.Verdandi.APM.models.apm_models import (
    Span,
    SpanStatus,
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


def build_parent_map(spans: Sequence[Span]) -> Dict[str, List[Span]]:
    """Build mapping of parent span IDs to child spans."""
    parent_map: Dict[str, List[Span]] = {}
    for span in spans:
        if span.parent_span_id:
            if span.parent_span_id not in parent_map:
                parent_map[span.parent_span_id] = []
            parent_map[span.parent_span_id].append(span)
    return parent_map


def group_spans_by_operation(spans: Sequence[Span]) -> Dict[str, List[Span]]:
    """Group spans by operation name."""
    result: Dict[str, List[Span]] = {}
    for span in spans:
        if span.operation_name not in result:
            result[span.operation_name] = []
        result[span.operation_name].append(span)
    return result


def group_spans_by_service(spans: Sequence[Span]) -> Dict[str, List[Span]]:
    """Group spans by service name."""
    result: Dict[str, List[Span]] = {}
    for span in spans:
        if span.service_name not in result:
            result[span.service_name] = []
        result[span.service_name].append(span)
    return result


def generate_span_recommendations(
    span: Span,
    is_slow: bool,
    slowness_factor: float,
    is_error: bool,
    self_time_ms: float,
    child_count: int,
    slow_threshold_ms: float,
) -> List[str]:
    """Generate recommendations based on span analysis."""
    recommendations = []

    if is_error:
        recommendations.append(
            f"Span '{span.operation_name}' has error status. "
            f"Error: {span.error_message or 'Unknown error'}"
        )

    if is_slow:
        if slowness_factor > 5:
            recommendations.append(
                f"CRITICAL: Span '{span.operation_name}' is {slowness_factor:.1f}x "
                f"slower than threshold ({span.duration_ms:.0f}ms vs {slow_threshold_ms}ms)"
            )
        elif slowness_factor > 2:
            recommendations.append(
                f"Span '{span.operation_name}' is {slowness_factor:.1f}x "
                f"slower than threshold"
            )

    if child_count > 0 and self_time_ms > span.duration_ms * 0.8:
        recommendations.append(
            f"Span '{span.operation_name}' has high self-time ({self_time_ms:.0f}ms) "
            f"despite having {child_count} child spans"
        )

    if child_count > 10:
        recommendations.append(
            f"Span '{span.operation_name}' has many child spans ({child_count}). "
            f"Consider batching operations"
        )

    return recommendations
