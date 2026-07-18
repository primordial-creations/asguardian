"""
Critical Path Analyzer Service

Analyzes distributed traces to identify the critical path.
"""

from collections import defaultdict
from typing import Any, Dict, List, Optional, Sequence, Tuple

from Asgard.Verdandi.Tracing.models.tracing_models import (
    AnalysisOutcome,
    ConfidenceFlag,
    CriticalPathResult,
    CriticalPathSegment,
    DistributedTrace,
    TraceSpan,
)
from Asgard.Verdandi.Tracing.services._path_helpers import (
    calculate_parallelization_opportunity,
    effective_end_ns,
    find_critical_path,
    generate_path_recommendations,
    percentile,
    sweep_line_credit,
)
from Asgard.Verdandi.Tracing.services.causal_normalizer import normalize_trace

# Threshold above which intermediate-span self-time is flagged as
# HIGH_UNATTRIBUTED_TIME (dark-matter / missing-instrumentation signal).
UNATTRIBUTED_TIME_THRESHOLD = 0.30


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
        strategy: str = "legacy",
    ) -> CriticalPathResult:
        """
        Analyze the critical path in a trace.

        Args:
            trace: The distributed trace to analyze
            strategy: "legacy" (default; naive longest-path + self-time
                subtraction, unchanged behavior) or "sweepline" (causal
                normalization + recursive latest-finisher sweep-line path
                with confidence flags — see analyze_sweepline()).

        Returns:
            CriticalPathResult with path segments and analysis
        """
        if strategy == "sweepline":
            return self.analyze_sweepline(trace)

        if not trace.spans:
            return CriticalPathResult(
                trace_id=trace.trace_id,
                total_duration_ms=0.0,
                critical_path_duration_ms=0.0,
                strategy="legacy",
            )

        span_lookup = {s.span_id: s for s in trace.spans}
        children: Dict[str, List[TraceSpan]] = defaultdict(list)

        for span in trace.spans:
            if span.parent_span_id:
                children[span.parent_span_id].append(span)

        root_span = trace.root_span
        if root_span is None:
            root_span = next(
                (s for s in trace.spans if s.parent_span_id is None), None
            )

        if root_span is None:
            root_span = min(trace.spans, key=lambda s: s.start_time_unix_nano)

        critical_path_spans = find_critical_path(root_span, children)

        total_duration = trace.total_duration_ms
        segments = []

        for span in critical_path_spans:
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

        critical_path_duration = sum(s.contribution_ms for s in segments)

        bottleneck_segment = (
            max(segments, key=lambda s: s.contribution_ms) if segments else None
        )
        bottleneck_service = (
            bottleneck_segment.span.service_name if bottleneck_segment else None
        )
        bottleneck_operation = (
            bottleneck_segment.span.operation_name if bottleneck_segment else None
        )

        parallel_opportunity = calculate_parallelization_opportunity(
            trace.spans, children
        )

        recommendations = generate_path_recommendations(
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
            strategy="legacy",
        )

    def analyze_sweepline(
        self,
        trace: DistributedTrace,
        apply_causal_normalization: bool = True,
    ) -> CriticalPathResult:
        """
        Causal-normalized, sweep-line "latest-finisher" critical path
        analysis (DEEPTHINK_06). Additive alongside the legacy `analyze()`
        naive longest-path algorithm.

        Pipeline: causal_normalizer.normalize_trace() (orphan adoption ->
        clock-skew correction -> async truncation) -> collect unique
        start/effective_end timestamps as slice boundaries -> recursive
        sweep-line credit assignment with latest-finisher dominance at
        fan-out points -> aggregate credited time per span as
        contribution_ms.

        Conservation invariant: sum(contribution_ms for all segments,
        including self-time) equals the root span's effective duration
        exactly (up to nanosecond rounding).

        Args:
            trace: The distributed trace to analyze
            apply_causal_normalization: Run the causal_normalizer pipeline
                first (default True). Set False to sweep-line a trace that
                has already been normalized upstream.

        Returns:
            CriticalPathResult with strategy="sweepline", contribution_ms
            per segment, confidence flags, and documented assumptions.
        """
        if not trace.spans:
            return CriticalPathResult(
                trace_id=trace.trace_id,
                total_duration_ms=0.0,
                critical_path_duration_ms=0.0,
                strategy="sweepline",
                outcome=AnalysisOutcome.INSUFFICIENT_DATA,
                recommendations=["INSUFFICIENT_DATA: trace has no spans."],
            )

        flags: List[ConfidenceFlag] = []
        assumptions: List[str] = []

        if apply_causal_normalization:
            trace, flags, assumptions = normalize_trace(trace)

        spans = trace.spans
        span_lookup = {s.span_id: s for s in spans}
        children: Dict[str, List[TraceSpan]] = defaultdict(list)
        for span in spans:
            if span.parent_span_id:
                children[span.parent_span_id].append(span)

        root_span = trace.root_span
        if root_span is None:
            root_span = next((s for s in spans if s.parent_span_id is None), None)
        if root_span is None:
            root_span = min(spans, key=lambda s: s.start_time_unix_nano)

        root_duration_ns = effective_end_ns(root_span) - root_span.start_time_unix_nano
        if root_duration_ns <= 0:
            return CriticalPathResult(
                trace_id=trace.trace_id,
                total_duration_ms=trace.total_duration_ms,
                critical_path_duration_ms=0.0,
                strategy="sweepline",
                outcome=AnalysisOutcome.INSUFFICIENT_DATA,
                flags=flags,
                assumptions=assumptions,
                recommendations=[
                    "INSUFFICIENT_DATA: root span has zero or negative "
                    "effective duration; cannot compute a sound path."
                ],
            )

        credited_ns = sweep_line_credit(root_span, children)
        total_duration_ms = trace.total_duration_ms or (root_duration_ns / 1e6)

        segments: List[CriticalPathSegment] = []
        for span_id, credit_ns in credited_ns.items():
            span = span_lookup.get(span_id)
            if span is None or credit_ns <= 0:
                continue
            contribution_ms = credit_ns / 1e6
            contribution_percent = (
                contribution_ms / total_duration_ms * 100 if total_duration_ms > 0 else 0.0
            )
            if contribution_percent >= self.min_contribution_percent or span_id == root_span.span_id:
                segments.append(
                    CriticalPathSegment(
                        span=span,
                        contribution_ms=contribution_ms,
                        contribution_percent=contribution_percent,
                        is_blocking=True,
                    )
                )

        segments.sort(key=lambda s: s.contribution_ms, reverse=True)

        # HIGH_UNATTRIBUTED_TIME: self-time credited to spans that have
        # children (i.e. intermediate nodes, not pure leaves) exceeds 30%
        # of the root's total effective duration.
        intermediate_self_ns = sum(
            credit_ns
            for span_id, credit_ns in credited_ns.items()
            if children.get(span_id)
        )
        if root_duration_ns > 0 and (intermediate_self_ns / root_duration_ns) > UNATTRIBUTED_TIME_THRESHOLD:
            if ConfidenceFlag.HIGH_UNATTRIBUTED_TIME not in flags:
                flags.append(ConfidenceFlag.HIGH_UNATTRIBUTED_TIME)

        critical_path_duration = sum(s.contribution_ms for s in segments)

        bottleneck_segment = max(segments, key=lambda s: s.contribution_ms) if segments else None
        bottleneck_service = bottleneck_segment.span.service_name if bottleneck_segment else None
        bottleneck_operation = bottleneck_segment.span.operation_name if bottleneck_segment else None

        parallel_opportunity = calculate_parallelization_opportunity(spans, children)

        recommendations = generate_path_recommendations(
            segments, bottleneck_service, bottleneck_operation, parallel_opportunity
        )
        if ConfidenceFlag.HIGH_UNATTRIBUTED_TIME in flags:
            recommendations.append(
                "High unattributed time: >30% of the path is intermediate-"
                "span self-time. Add instrumentation to narrow the gap."
            )

        return CriticalPathResult(
            trace_id=trace.trace_id,
            total_duration_ms=total_duration_ms,
            critical_path_duration_ms=critical_path_duration,
            segments=segments,
            bottleneck_service=bottleneck_service,
            bottleneck_operation=bottleneck_operation,
            parallelization_opportunity_ms=parallel_opportunity,
            recommendations=recommendations,
            strategy="sweepline",
            flags=flags,
            assumptions=assumptions,
            outcome=AnalysisOutcome.OK,
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

        averages = [
            (service, op, sum(contribs) / len(contribs))
            for (service, op), contribs in bottleneck_stats.items()
        ]

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

        results = {}
        for service, contributions in service_stats.items():
            sorted_contrib = sorted(contributions)
            results[service] = {
                "total_contribution_ms": sum(contributions),
                "avg_contribution_ms": sum(contributions) / len(contributions),
                "max_contribution_ms": max(contributions),
                "occurrence_count": len(contributions),
                "p50_contribution_ms": percentile(sorted_contrib, 50),
                "p99_contribution_ms": percentile(sorted_contrib, 99),
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

        contrib_a = {
            (s.span.service_name, s.span.operation_name): s.contribution_ms
            for s in result_a.segments
        }
        contrib_b = {
            (s.span.service_name, s.span.operation_name): s.contribution_ms
            for s in result_b.segments
        }

        all_ops = set(contrib_a.keys()) | set(contrib_b.keys())
        differences = []

        for op in all_ops:
            time_a = contrib_a.get(op, 0.0)
            time_b = contrib_b.get(op, 0.0)
            diff = time_b - time_a
            if abs(diff) > 1.0:
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
