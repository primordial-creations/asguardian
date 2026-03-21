"""
Trace Parser Service

Parses trace data from various formats (OpenTelemetry, Jaeger, etc.).
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence

from Asgard.Verdandi.Tracing.models.tracing_models import (
    DistributedTrace,
    TraceSpan,
)
from Asgard.Verdandi.Tracing.services._span_parsers import (
    calculate_trace_depth,
    detect_format,
    parse_attributes,
    parse_generic_span,
    parse_jaeger_span,
    parse_otlp_span,
    parse_zipkin_span,
)


class TraceParser:
    """
    Parser for distributed trace data from various formats.

    Supports parsing from OpenTelemetry Protocol (OTLP) and Jaeger formats.

    Example:
        parser = TraceParser()

        # Parse OTLP JSON
        traces = parser.parse_otlp(otlp_json)

        # Parse Jaeger format
        traces = parser.parse_jaeger(jaeger_json)

        # Parse generic span list
        trace = parser.build_trace(span_list)
    """

    def __init__(self):
        """Initialize the trace parser."""
        pass

    def parse_otlp(
        self,
        data: Dict[str, Any],
    ) -> List[DistributedTrace]:
        """
        Parse OpenTelemetry Protocol (OTLP) trace data.

        Args:
            data: OTLP JSON data with resourceSpans

        Returns:
            List of parsed DistributedTrace objects
        """
        traces_by_id: Dict[str, List[TraceSpan]] = {}

        resource_spans = data.get("resourceSpans", [])

        for rs in resource_spans:
            resource_attrs = parse_attributes(
                rs.get("resource", {}).get("attributes", [])
            )
            service_name = resource_attrs.get(
                "service.name", resource_attrs.get("service_name", "unknown")
            )

            scope_spans = rs.get("scopeSpans", [])
            for ss in scope_spans:
                scope_name = ss.get("scope", {}).get("name")
                spans = ss.get("spans", [])

                for span_data in spans:
                    span = parse_otlp_span(
                        span_data, service_name, resource_attrs, scope_name
                    )
                    if span.trace_id not in traces_by_id:
                        traces_by_id[span.trace_id] = []
                    traces_by_id[span.trace_id].append(span)

        return [
            self.build_trace(spans, trace_id)
            for trace_id, spans in traces_by_id.items()
        ]

    def parse_jaeger(
        self,
        data: Dict[str, Any],
    ) -> List[DistributedTrace]:
        """
        Parse Jaeger trace data.

        Args:
            data: Jaeger JSON data

        Returns:
            List of parsed DistributedTrace objects
        """
        traces = []

        if "data" in data:
            trace_data_list = data["data"]
        elif "traces" in data:
            trace_data_list = data["traces"]
        else:
            trace_data_list = [data]

        for trace_data in trace_data_list:
            spans = []

            processes = trace_data.get("processes", {})

            for span_data in trace_data.get("spans", []):
                process_id = span_data.get("processID", "p1")
                process = processes.get(process_id, {})
                service_name = process.get("serviceName", "unknown")

                span = parse_jaeger_span(span_data, service_name, process)
                spans.append(span)

            if spans:
                trace = self.build_trace(spans, spans[0].trace_id)
                traces.append(trace)

        return traces

    def parse_zipkin(
        self,
        data: List[Dict[str, Any]],
    ) -> List[DistributedTrace]:
        """
        Parse Zipkin trace data.

        Args:
            data: Zipkin JSON span array

        Returns:
            List of parsed DistributedTrace objects
        """
        traces_by_id: Dict[str, List[TraceSpan]] = {}

        for span_data in data:
            span = parse_zipkin_span(span_data)
            if span.trace_id not in traces_by_id:
                traces_by_id[span.trace_id] = []
            traces_by_id[span.trace_id].append(span)

        return [
            self.build_trace(spans, trace_id)
            for trace_id, spans in traces_by_id.items()
        ]

    def build_trace(
        self,
        spans: Sequence[TraceSpan],
        trace_id: Optional[str] = None,
    ) -> DistributedTrace:
        """
        Build a DistributedTrace from a list of spans.

        Args:
            spans: List of trace spans
            trace_id: Optional trace ID (uses first span's if not provided)

        Returns:
            DistributedTrace with computed properties
        """
        if not spans:
            return DistributedTrace(
                trace_id=trace_id or "unknown",
                spans=[],
            )

        span_list = list(spans)
        trace_id = trace_id or span_list[0].trace_id

        root_span = next(
            (s for s in span_list if s.parent_span_id is None), None
        )

        service_names = list(set(s.service_name for s in span_list))

        start_times = [s.start_time_unix_nano for s in span_list]
        end_times = [s.end_time_unix_nano for s in span_list]
        total_duration_ms = (max(end_times) - min(start_times)) / 1e6

        error_count = sum(1 for s in span_list if s.has_error)

        depth = calculate_trace_depth(span_list)

        start_time = datetime.fromtimestamp(min(start_times) / 1e9)
        end_time = datetime.fromtimestamp(max(end_times) / 1e9)

        return DistributedTrace(
            trace_id=trace_id,
            spans=span_list,
            root_span=root_span,
            service_names=service_names,
            total_duration_ms=total_duration_ms,
            span_count=len(span_list),
            error_count=error_count,
            depth=depth,
            start_time=start_time,
            end_time=end_time,
        )

    def parse_span_dict(
        self,
        span_dict: Dict[str, Any],
        format_hint: str = "auto",
    ) -> TraceSpan:
        """
        Parse a single span from a dictionary.

        Args:
            span_dict: Span data dictionary
            format_hint: Format hint ("otlp", "jaeger", "zipkin", "auto")

        Returns:
            Parsed TraceSpan
        """
        if format_hint == "auto":
            format_hint = detect_format(span_dict)

        if format_hint == "otlp":
            return parse_otlp_span(span_dict, "unknown", {}, None)
        elif format_hint == "jaeger":
            return parse_jaeger_span(span_dict, "unknown", {})
        elif format_hint == "zipkin":
            return parse_zipkin_span(span_dict)
        else:
            return parse_generic_span(span_dict)
