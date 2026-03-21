"""
Helpers for CriticalPathAnalyzer.

Contains private helper functions extracted from the critical path analyzer.
"""

from typing import Dict, List, Optional

from Asgard.Verdandi.Tracing.models.tracing_models import (
    CriticalPathSegment,
    TraceSpan,
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


def find_critical_path(
    root: TraceSpan,
    children: Dict[str, List[TraceSpan]],
) -> List[TraceSpan]:
    """
    Find the critical path starting from root span.

    Uses a DFS approach following the longest child at each level.
    """
    path = [root]
    current = root

    while current.span_id in children:
        child_spans = children[current.span_id]
        if not child_spans:
            break

        latest_child = max(
            child_spans, key=lambda s: s.end_time_unix_nano
        )

        longest_child = max(child_spans, key=lambda s: s.duration_ms)

        if latest_child.end_time_unix_nano > longest_child.end_time_unix_nano:
            critical_child = latest_child
        else:
            critical_child = longest_child

        path.append(critical_child)
        current = critical_child

    return path


def calculate_parallelization_opportunity(
    spans: List[TraceSpan],
    children: Dict[str, List[TraceSpan]],
) -> float:
    """
    Calculate potential time savings from parallelization.

    Looks for sequential children that could run in parallel.
    """
    total_opportunity = 0.0

    for parent_id, child_spans in children.items():
        if len(child_spans) <= 1:
            continue

        sorted_children = sorted(
            child_spans, key=lambda s: s.start_time_unix_nano
        )

        for i in range(len(sorted_children) - 1):
            current = sorted_children[i]
            next_span = sorted_children[i + 1]

            if next_span.start_time_unix_nano >= current.end_time_unix_nano:
                potential_savings = min(
                    current.duration_ms, next_span.duration_ms
                )
                total_opportunity += potential_savings

    return total_opportunity


def generate_path_recommendations(
    segments: List[CriticalPathSegment],
    bottleneck_service: Optional[str],
    bottleneck_operation: Optional[str],
    parallel_opportunity: float,
) -> List[str]:
    """Generate optimization recommendations."""
    recommendations = []

    if bottleneck_service and bottleneck_operation:
        bottleneck_segment = max(segments, key=lambda s: s.contribution_ms)
        recommendations.append(
            f"Primary bottleneck: {bottleneck_service}/{bottleneck_operation} "
            f"({bottleneck_segment.contribution_ms:.0f}ms, "
            f"{bottleneck_segment.contribution_percent:.1f}% of critical path)"
        )

    if parallel_opportunity > 10:
        recommendations.append(
            f"Parallelization opportunity: {parallel_opportunity:.0f}ms could be "
            f"saved by running sequential operations in parallel"
        )

    high_impact = [
        s for s in segments if s.contribution_percent > 20
    ]
    if len(high_impact) > 1:
        services = list(set(s.span.service_name for s in high_impact))
        recommendations.append(
            f"Multiple high-impact services: {', '.join(services)}. "
            f"Consider optimizing these first."
        )

    error_segments = [s for s in segments if s.span.has_error]
    if error_segments:
        recommendations.append(
            f"{len(error_segments)} error(s) on critical path. "
            f"Errors may be causing retries and increased latency."
        )

    return recommendations
