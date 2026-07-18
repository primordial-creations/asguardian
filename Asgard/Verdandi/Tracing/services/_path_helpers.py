"""
Helpers for CriticalPathAnalyzer.

Contains private helper functions extracted from the critical path analyzer.
"""

from collections import defaultdict
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


def effective_end_ns(span: TraceSpan) -> int:
    """Effective end for sweep-line purposes: normalized end, or raw end."""
    return (
        span.effective_end_ns
        if span.effective_end_ns is not None
        else span.end_time_unix_nano
    )


def build_slice_boundaries(
    root: TraceSpan,
    children: Dict[str, List[TraceSpan]],
) -> List[int]:
    """
    Collect all unique start/effective_end timestamps in the subtree rooted
    at ``root``, restricted to ``root``'s own active window, and return them
    sorted. Consecutive pairs form the sweep-line's time slices.
    """
    boundaries = set()
    stack = [root]
    visited = set()
    while stack:
        s = stack.pop()
        if s.span_id in visited:
            continue
        visited.add(s.span_id)
        boundaries.add(s.start_time_unix_nano)
        boundaries.add(effective_end_ns(s))
        for child in children.get(s.span_id, []):
            stack.append(child)

    root_start = root.start_time_unix_nano
    root_end = effective_end_ns(root)
    return sorted(b for b in boundaries if root_start <= b <= root_end)


def latest_finisher(active_children: List[TraceSpan]) -> TraceSpan:
    """Select the child with the maximum effective_end (dominance rule)."""
    return max(active_children, key=effective_end_ns)


def _active_children(
    span: TraceSpan,
    children: Dict[str, List[TraceSpan]],
    slice_start: int,
    slice_end: int,
) -> List[TraceSpan]:
    return [
        c
        for c in children.get(span.span_id, [])
        if c.start_time_unix_nano <= slice_start and effective_end_ns(c) >= slice_end
    ]


def _credit_slice(
    span: TraceSpan,
    children: Dict[str, List[TraceSpan]],
    slice_start: int,
    slice_end: int,
    credited: Dict[str, int],
) -> None:
    active = _active_children(span, children, slice_start, slice_end)
    duration = slice_end - slice_start

    if not active:
        credited[span.span_id] = credited.get(span.span_id, 0) + duration
    elif len(active) == 1:
        _credit_slice(active[0], children, slice_start, slice_end, credited)
    else:
        dominant = latest_finisher(active)
        _credit_slice(dominant, children, slice_start, slice_end, credited)


def sweep_line_credit(
    root: TraceSpan,
    children: Dict[str, List[TraceSpan]],
) -> Dict[str, int]:
    """
    Recursive sweep-line "latest-finisher" credit assignment.

    For every time slice between consecutive slice boundaries, recurse from
    ``root``: 0 active children -> credit the slice to the current span's
    self-time; 1 active child -> recurse into it; > 1 active children ->
    recurse only into the child with the maximum effective_end (latest-
    finisher dominance, no gap thresholds).

    Returns a dict of span_id -> credited nanoseconds. The values sum
    exactly to ``root``'s effective duration (conservation invariant).
    """
    boundaries = build_slice_boundaries(root, children)
    credited: Dict[str, int] = defaultdict(int)

    for i in range(len(boundaries) - 1):
        slice_start, slice_end = boundaries[i], boundaries[i + 1]
        if slice_end <= slice_start:
            continue
        _credit_slice(root, children, slice_start, slice_end, credited)

    return dict(credited)


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
