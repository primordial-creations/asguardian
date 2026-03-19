"""
Critical Path Analyzer Service

Analyzes distributed traces to identify the critical path.
"""

from collections import defaultdict
from typing import Any, Dict, List, Optional, Sequence, Tuple

from Asgard.Verdandi.Tracing.models.tracing_models import (
    CriticalPathResult,
    CriticalPathSegment,
    DistributedTrace,
    TraceSpan,
)


class CriticalPathAnalyzer:
    """
    Analyzer for critical path in distributed traces.

    The critical path is the sequence of operations that determines
    the total request latency. Optimizing operations on the critical
    path has the most impact on overall performance.

    Example:
        analyzer = CriticalPathAnalyzer()

        # Analyze a single trace
        result = analyzer.analyze(trace)
        for segment in result.segments:
            print(f"{segment.span.operation_name}: {segment.contribution_ms}ms")

        # Find bottlenecks across traces
        bottlenecks = analyzer.find_common_bottlenecks(traces)
    """

    def __init__(
        self,
        min_contribution_percent: float = 5.0,
    ):
        """
        Initialize the critical path analyzer.

        Args:
            min_contribution_percent: Minimum contribution to include in path
        """
        self.min_contribution_percent = min_contribution_percent

    def analyze(
        self,
        trace: DistributedTrace,
    ) -> CriticalPathResult:
        """
        Analyze the critical path in a trace.

        Args:
            trace: The distributed trace to analyze

        Returns:
            CriticalPathResult with path segments and analysis
        """
        if not trace.spans:
            return CriticalPathResult(
                trace_id=trace.trace_id,
                total_duration_ms=0.0,
                critical_path_duration_ms=0.0,
            )

        # Build span lookup and parent-child relationships
        span_lookup = {s.span_id: s for s in trace.spans}
        children: Dict[str, List[TraceSpan]] = defaultdict(list)

        for span in trace.spans:
            if span.parent_span_id:
                children[span.parent_span_id].append(span)

        # Find root span
        root_span = trace.root_span
        if root_span is None:
            root_span = next(
                (s for s in trace.spans if s.parent_span_id is None), None
            )

        if root_span is None:
            # No clear root, use the earliest span
            root_span = min(trace.spans, key=lambda s: s.start_time_unix_nano)

        # Find critical path using DFS
        critical_path_spans = self._find_critical_path(root_span, children)

        # Calculate contributions
        total_duration = trace.total_duration_ms
        segments = []

        for span in critical_path_spans:
            # Calculate this span's contribution
            # Self-time = span duration - sum of child durations on critical path
            child_spans = children.get(span.span_id, [])
            child_duration = sum(
                cs.duration_ms for cs in child_spans if cs in critical_path_spans
            )
            self_time = max(0.0, span.duration_ms - child_duration)

            contribution_percent = (
                self_time / total_duration * 100 if total_duration > 0 else 0
            )

            if contribution_percent >= self.min_contribution_percent or span == root_span:
                segments.append(
                    CriticalPathSegment(
                        span=span,
                        contribution_ms=self_time,
                        contribution_percent=contribution_percent,
                        is_blocking=True,
                    )
                )

        # Calculate critical path duration (should equal trace duration for serial path)
        critical_path_duration = sum(s.contribution_ms for s in segments)

        # Find bottlenecks
        bottleneck_segment = (
            max(segments, key=lambda s: s.contribution_ms) if segments else None
        )
        bottleneck_service = (
            bottleneck_segment.span.service_name if bottleneck_segment else None
        )
        bottleneck_operation = (
            bottleneck_segment.span.operation_name if bottleneck_segment else None
        )

        # Calculate parallelization opportunity
        # (time spent in spans that could potentially run in parallel)
        parallel_opportunity = self._calculate_parallelization_opportunity(
            trace.spans, children
        )

        # Generate recommendations
        recommendations = self._generate_recommendations(
            segments, bottleneck_service, bottleneck_operation, parallel_opportunity
        )

        return CriticalPathResult(
            trace_id=trace.trace_id,
            total_duration_ms=total_duration,
            critical_path_duration_ms=critical_path_duration,
            segments=segments,
            bottleneck_service=bottleneck_service,
            bottleneck_operation=bottleneck_operation,
            parallelization_opportunity_ms=parallel_opportunity,
            recommendations=recommendations,
        )

    def analyze_batch(
        self,
        traces: Sequence[DistributedTrace],
    ) -> List[CriticalPathResult]:
        """
        Analyze critical paths for multiple traces.

        Args:
            traces: List of traces to analyze

        Returns:
            List of CriticalPathResult objects
        """
        return [self.analyze(trace) for trace in traces]

    def find_common_bottlenecks(
        self,
        traces: Sequence[DistributedTrace],
        top_n: int = 5,
    ) -> List[Tuple[str, str, float]]:
        """
        Find the most common bottlenecks across traces.

        Args:
            traces: List of traces to analyze
            top_n: Number of top bottlenecks to return

        Returns:
            List of (service_name, operation_name, avg_contribution_ms) tuples
        """
        bottleneck_stats: Dict[Tuple[str, str], List[float]] = defaultdict(list)

        for trace in traces:
            result = self.analyze(trace)
            for segment in result.segments:
                key = (segment.span.service_name, segment.span.operation_name)
                bottleneck_stats[key].append(segment.contribution_ms)

        # Calculate averages
        averages = [
            (service, op, sum(contribs) / len(contribs))
            for (service, op), contribs in bottleneck_stats.items()
        ]

        # Sort by average contribution
        averages.sort(key=lambda x: x[2], reverse=True)

        return averages[:top_n]

    def find_service_bottlenecks(
        self,
        traces: Sequence[DistributedTrace],
    ) -> Dict[str, Dict[str, float]]:
        """
        Find bottleneck contributions per service.

        Args:
            traces: List of traces to analyze

        Returns:
            Dictionary of service_name to stats dict
        """
        service_stats: Dict[str, List[float]] = defaultdict(list)

        for trace in traces:
            result = self.analyze(trace)
            for segment in result.segments:
                service_stats[segment.span.service_name].append(
                    segment.contribution_ms
                )

        # Calculate statistics per service
        results = {}
        for service, contributions in service_stats.items():
            sorted_contrib = sorted(contributions)
            results[service] = {
                "total_contribution_ms": sum(contributions),
                "avg_contribution_ms": sum(contributions) / len(contributions),
                "max_contribution_ms": max(contributions),
                "occurrence_count": len(contributions),
                "p50_contribution_ms": self._percentile(sorted_contrib, 50),
                "p99_contribution_ms": self._percentile(sorted_contrib, 99),
            }

        return results

    def compare_traces(
        self,
        trace_a: DistributedTrace,
        trace_b: DistributedTrace,
    ) -> Dict[str, Any]:
        """
        Compare critical paths of two traces.

        Args:
            trace_a: First trace
            trace_b: Second trace

        Returns:
            Dictionary with comparison results
        """
        result_a = self.analyze(trace_a)
        result_b = self.analyze(trace_b)

        # Build operation contribution maps
        contrib_a = {
            (s.span.service_name, s.span.operation_name): s.contribution_ms
            for s in result_a.segments
        }
        contrib_b = {
            (s.span.service_name, s.span.operation_name): s.contribution_ms
            for s in result_b.segments
        }

        # Find differences
        all_ops = set(contrib_a.keys()) | set(contrib_b.keys())
        differences = []

        for op in all_ops:
            time_a = contrib_a.get(op, 0.0)
            time_b = contrib_b.get(op, 0.0)
            diff = time_b - time_a
            if abs(diff) > 1.0:  # Only significant differences
                differences.append({
                    "service": op[0],
                    "operation": op[1],
                    "time_a_ms": time_a,
                    "time_b_ms": time_b,
                    "difference_ms": diff,
                    "change_percent": (diff / time_a * 100) if time_a > 0 else 0,
                })

        differences.sort(key=lambda x: abs(x["difference_ms"]), reverse=True)

        return {
            "trace_a_duration_ms": result_a.total_duration_ms,
            "trace_b_duration_ms": result_b.total_duration_ms,
            "duration_difference_ms": (
                result_b.total_duration_ms - result_a.total_duration_ms
            ),
            "trace_a_bottleneck": result_a.bottleneck_operation,
            "trace_b_bottleneck": result_b.bottleneck_operation,
            "operation_differences": differences,
        }

    def _find_critical_path(
        self,
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

            # Find the child that ends latest (determines critical path)
            # For true critical path, we should consider span start/end times
            latest_child = max(
                child_spans, key=lambda s: s.end_time_unix_nano
            )

            # Also consider overlapping spans - the one with most impact
            longest_child = max(child_spans, key=lambda s: s.duration_ms)

            # Use the one that contributes more to total duration
            if latest_child.end_time_unix_nano > longest_child.end_time_unix_nano:
                critical_child = latest_child
            else:
                critical_child = longest_child

            path.append(critical_child)
            current = critical_child

        return path

    def _calculate_parallelization_opportunity(
        self,
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

            # Check if children are sequential (non-overlapping)
            sorted_children = sorted(
                child_spans, key=lambda s: s.start_time_unix_nano
            )

            for i in range(len(sorted_children) - 1):
                current = sorted_children[i]
                next_span = sorted_children[i + 1]

                # If next starts after current ends, they're sequential
                if next_span.start_time_unix_nano >= current.end_time_unix_nano:
                    # Could save time by parallelizing
                    # Savings = min(current.duration, next.duration)
                    potential_savings = min(
                        current.duration_ms, next_span.duration_ms
                    )
                    total_opportunity += potential_savings

        return total_opportunity

    def _percentile(
        self, sorted_values: List[float], percentile: float
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

    def _generate_recommendations(
        self,
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

        # Find segments with high contribution
        high_impact = [
            s for s in segments if s.contribution_percent > 20
        ]
        if len(high_impact) > 1:
            services = list(set(s.span.service_name for s in high_impact))
            recommendations.append(
                f"Multiple high-impact services: {', '.join(services)}. "
                f"Consider optimizing these first."
            )

        # Check for error spans on critical path
        error_segments = [s for s in segments if s.span.has_error]
        if error_segments:
            recommendations.append(
                f"{len(error_segments)} error(s) on critical path. "
                f"Errors may be causing retries and increased latency."
            )

        return recommendations
