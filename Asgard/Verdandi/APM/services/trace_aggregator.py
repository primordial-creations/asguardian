"""
Trace Aggregator Service

Aggregates distributed traces to produce service-level metrics.
"""

from datetime import datetime
from typing import Dict, List, Optional, Sequence

from Asgard.Verdandi.APM.models.apm_models import (
    APMReport,
    ServiceMetrics,
    Span,
    SpanStatus,
    Trace,
)
from Asgard.Verdandi.APM.services._aggregator_helpers import (
    calculate_health_score,
    calculate_service_metrics,
    generate_aggregator_recommendations,
    get_earliest_time,
    get_latest_time,
    group_spans_by_service,
    percentile,
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

        all_spans: List[Span] = []
        for trace in traces:
            all_spans.extend(trace.spans)

        spans_by_service = group_spans_by_service(all_spans)

        service_metrics = [
            calculate_service_metrics(service_name, spans, start_time, end_time)
            for service_name, spans in spans_by_service.items()
        ]

        slow_traces = [
            t for t in traces if t.total_duration_ms > self.slow_trace_threshold_ms
        ]
        error_traces = [t for t in traces if t.has_errors]

        total_errors = sum(t.error_count for t in traces)
        total_span_count = sum(t.span_count for t in traces)
        overall_error_rate = (
            total_errors / total_span_count if total_span_count > 0 else 0.0
        )

        durations = [t.total_duration_ms for t in traces]
        overall_avg_latency = sum(durations) / len(durations) if durations else 0.0
        overall_p99_latency = (
            percentile(sorted(durations), 99) if durations else 0.0
        )

        health_score = calculate_health_score(
            overall_error_rate, overall_avg_latency, overall_p99_latency,
            self.slow_trace_threshold_ms, self.health_error_weight,
            self.health_latency_weight,
        )

        recommendations = generate_aggregator_recommendations(
            service_metrics, slow_traces, error_traces, overall_error_rate,
            self.slow_trace_threshold_ms,
        )

        return APMReport(
            generated_at=datetime.now(),
            analysis_period_start=start_time or get_earliest_time(traces),
            analysis_period_end=end_time or get_latest_time(traces),
            trace_count=len(traces),
            span_count=total_span_count,
            service_metrics=service_metrics,
            slow_traces=list(slow_traces[:10]),
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
        spans_by_service = group_spans_by_service(spans)
        return [
            calculate_service_metrics(service_name, service_spans, None, None)
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
        spans_by_trace: Dict[str, List[Span]] = {}
        for span in spans:
            if span.trace_id not in spans_by_trace:
                spans_by_trace[span.trace_id] = []
            spans_by_trace[span.trace_id].append(span)

        traces = []
        for trace_id, trace_spans in spans_by_trace.items():
            root_span = next(
                (s for s in trace_spans if s.parent_span_id is None), None
            )

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
