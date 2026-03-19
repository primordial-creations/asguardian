"""
Trace Parser Service

Parses trace data from various formats (OpenTelemetry, Jaeger, etc.).
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, cast

from Asgard.Verdandi.Tracing.models.tracing_models import (
    DistributedTrace,
    SpanLink,
    TraceSpan,
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
            resource_attrs = self._parse_attributes(
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
                    span = self._parse_otlp_span(
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

        # Handle both single trace and multiple traces
        if "data" in data:
            trace_data_list = data["data"]
        elif "traces" in data:
            trace_data_list = data["traces"]
        else:
            trace_data_list = [data]

        for trace_data in trace_data_list:
            spans = []

            # Build process lookup
            processes = trace_data.get("processes", {})

            for span_data in trace_data.get("spans", []):
                process_id = span_data.get("processID", "p1")
                process = processes.get(process_id, {})
                service_name = process.get("serviceName", "unknown")

                span = self._parse_jaeger_span(span_data, service_name, process)
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
            span = self._parse_zipkin_span(span_data)
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

        # Find root span
        root_span = next(
            (s for s in span_list if s.parent_span_id is None), None
        )

        # Collect unique services
        service_names = list(set(s.service_name for s in span_list))

        # Calculate trace duration
        start_times = [s.start_time_unix_nano for s in span_list]
        end_times = [s.end_time_unix_nano for s in span_list]
        total_duration_ms = (max(end_times) - min(start_times)) / 1e6

        # Count errors
        error_count = sum(1 for s in span_list if s.has_error)

        # Calculate depth
        depth = self._calculate_trace_depth(span_list)

        # Get start/end times
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
            format_hint = self._detect_format(span_dict)

        if format_hint == "otlp":
            return self._parse_otlp_span(span_dict, "unknown", {}, None)
        elif format_hint == "jaeger":
            return self._parse_jaeger_span(span_dict, "unknown", {})
        elif format_hint == "zipkin":
            return self._parse_zipkin_span(span_dict)
        else:
            return self._parse_generic_span(span_dict)

    def _parse_otlp_span(
        self,
        span_data: Dict[str, Any],
        service_name: str,
        resource_attrs: Dict[str, Any],
        scope_name: Optional[str],
    ) -> TraceSpan:
        """Parse OTLP format span."""
        trace_id = span_data.get("traceId", "")
        span_id = span_data.get("spanId", "")
        parent_id = span_data.get("parentSpanId")

        # Convert parent ID if empty string
        if parent_id == "":
            parent_id = None

        start_nano = int(span_data.get("startTimeUnixNano", 0))
        end_nano = int(span_data.get("endTimeUnixNano", 0))
        duration_ms = (end_nano - start_nano) / 1e6

        # Parse status
        status = span_data.get("status", {})
        status_code = status.get("code", "UNSET")
        if isinstance(status_code, int):
            status_code = {0: "UNSET", 1: "OK", 2: "ERROR"}.get(status_code, "UNSET")

        # Parse attributes
        attributes = self._parse_attributes(span_data.get("attributes", []))

        # Parse events
        events = []
        for event in span_data.get("events", []):
            events.append({
                "name": event.get("name"),
                "timestamp": event.get("timeUnixNano"),
                "attributes": self._parse_attributes(event.get("attributes", [])),
            })

        # Parse links
        links = []
        for link in span_data.get("links", []):
            links.append(SpanLink(
                trace_id=link.get("traceId", ""),
                span_id=link.get("spanId", ""),
                attributes=self._parse_attributes(link.get("attributes", [])),
            ))

        return TraceSpan(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_id,
            operation_name=span_data.get("name", "unknown"),
            service_name=service_name,
            start_time_unix_nano=start_nano,
            end_time_unix_nano=end_nano,
            duration_ms=duration_ms,
            status_code=status_code,
            status_message=status.get("message"),
            kind=self._parse_span_kind(span_data.get("kind", 0)),
            attributes=attributes,
            events=events,
            links=links,
            resource_attributes=resource_attrs,
            instrumentation_scope=scope_name,
        )

    def _parse_jaeger_span(
        self,
        span_data: Dict[str, Any],
        service_name: str,
        process: Dict[str, Any],
    ) -> TraceSpan:
        """Parse Jaeger format span."""
        trace_id = span_data.get("traceID", "")
        span_id = span_data.get("spanID", "")

        # Handle references for parent
        parent_id = None
        for ref in span_data.get("references", []):
            if ref.get("refType") == "CHILD_OF":
                parent_id = ref.get("spanID")
                break

        # Jaeger uses microseconds
        start_micro = span_data.get("startTime", 0)
        duration_micro = span_data.get("duration", 0)
        start_nano = start_micro * 1000
        end_nano = start_nano + (duration_micro * 1000)

        # Parse tags as attributes
        attributes = {}
        for tag in span_data.get("tags", []):
            attributes[tag.get("key")] = tag.get("value")

        # Check for error
        status_code = "UNSET"
        if attributes.get("error") is True:
            status_code = "ERROR"
        elif attributes.get("otel.status_code") == "ERROR":
            status_code = "ERROR"

        # Parse logs as events
        events = []
        for log in span_data.get("logs", []):
            event_attrs = {}
            for field in log.get("fields", []):
                event_attrs[field.get("key")] = field.get("value")
            events.append({
                "name": event_attrs.get("event", "log"),
                "timestamp": log.get("timestamp", 0) * 1000,
                "attributes": event_attrs,
            })

        # Resource attributes from process
        resource_attrs = {}
        for tag in process.get("tags", []):
            resource_attrs[tag.get("key")] = tag.get("value")

        return TraceSpan(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_id,
            operation_name=span_data.get("operationName", "unknown"),
            service_name=service_name,
            start_time_unix_nano=start_nano,
            end_time_unix_nano=end_nano,
            duration_ms=duration_micro / 1000,
            status_code=status_code,
            kind=self._jaeger_kind_to_string(attributes.get("span.kind")),
            attributes=attributes,
            events=events,
            resource_attributes=resource_attrs,
        )

    def _parse_zipkin_span(
        self,
        span_data: Dict[str, Any],
    ) -> TraceSpan:
        """Parse Zipkin format span."""
        trace_id = span_data.get("traceId", "")
        span_id = span_data.get("id", "")
        parent_id = span_data.get("parentId")

        # Zipkin uses microseconds
        start_micro = span_data.get("timestamp", 0)
        duration_micro = span_data.get("duration", 0)
        start_nano = start_micro * 1000
        end_nano = start_nano + (duration_micro * 1000)

        # Get service name from endpoints
        local_endpoint = span_data.get("localEndpoint", {})
        service_name = local_endpoint.get("serviceName", "unknown")

        # Tags as attributes
        attributes = span_data.get("tags", {})

        # Check for error
        status_code = "UNSET"
        if attributes.get("error"):
            status_code = "ERROR"

        # Annotations as events
        events = []
        for ann in span_data.get("annotations", []):
            events.append({
                "name": ann.get("value"),
                "timestamp": ann.get("timestamp", 0) * 1000,
            })

        return TraceSpan(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_id,
            operation_name=span_data.get("name", "unknown"),
            service_name=service_name,
            start_time_unix_nano=start_nano,
            end_time_unix_nano=end_nano,
            duration_ms=duration_micro / 1000,
            status_code=status_code,
            kind=span_data.get("kind", "INTERNAL").upper(),
            attributes=attributes,
            events=events,
        )

    def _parse_generic_span(
        self,
        span_data: Dict[str, Any],
    ) -> TraceSpan:
        """Parse generic span format."""
        trace_id = span_data.get("trace_id", span_data.get("traceId", ""))
        span_id = span_data.get("span_id", span_data.get("spanId", ""))
        parent_id = span_data.get("parent_span_id", span_data.get("parentSpanId"))

        # Try various time formats
        start_nano = span_data.get("start_time_unix_nano", 0)
        end_nano = span_data.get("end_time_unix_nano", 0)

        if start_nano == 0 and "start_time" in span_data:
            # Try parsing as datetime
            start_time = span_data["start_time"]
            if isinstance(start_time, datetime):
                start_nano = int(start_time.timestamp() * 1e9)

        if end_nano == 0 and "end_time" in span_data:
            end_time = span_data["end_time"]
            if isinstance(end_time, datetime):
                end_nano = int(end_time.timestamp() * 1e9)

        duration_ms = span_data.get("duration_ms", (end_nano - start_nano) / 1e6)

        return TraceSpan(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_id,
            operation_name=span_data.get(
                "operation_name", span_data.get("name", "unknown")
            ),
            service_name=span_data.get("service_name", "unknown"),
            start_time_unix_nano=start_nano,
            end_time_unix_nano=end_nano,
            duration_ms=duration_ms,
            status_code=span_data.get("status_code", span_data.get("status", "UNSET")),
            kind=span_data.get("kind", "INTERNAL"),
            attributes=span_data.get("attributes", {}),
        )

    def _parse_attributes(
        self,
        attrs: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Parse OTLP attribute array to dictionary."""
        result: Dict[str, Any] = {}
        for attr in attrs:
            key = cast(str, attr.get("key", ""))
            value = attr.get("value", {})
            # Handle OTLP value types
            if "stringValue" in value:
                result[key] = value["stringValue"]
            elif "intValue" in value:
                result[key] = int(value["intValue"])
            elif "boolValue" in value:
                result[key] = value["boolValue"]
            elif "doubleValue" in value:
                result[key] = value["doubleValue"]
            elif "arrayValue" in value:
                result[key] = [
                    self._parse_attribute_value(v)
                    for v in value["arrayValue"].get("values", [])
                ]
            else:
                result[key] = str(value)
        return result

    def _parse_attribute_value(self, value: Dict[str, Any]) -> Any:
        """Parse a single OTLP attribute value."""
        if "stringValue" in value:
            return value["stringValue"]
        elif "intValue" in value:
            return int(value["intValue"])
        elif "boolValue" in value:
            return value["boolValue"]
        elif "doubleValue" in value:
            return value["doubleValue"]
        return str(value)

    def _parse_span_kind(self, kind: int) -> str:
        """Convert OTLP span kind integer to string."""
        kind_map = {
            0: "UNSPECIFIED",
            1: "INTERNAL",
            2: "SERVER",
            3: "CLIENT",
            4: "PRODUCER",
            5: "CONSUMER",
        }
        return kind_map.get(kind, "INTERNAL")

    def _jaeger_kind_to_string(self, kind: Optional[str]) -> str:
        """Convert Jaeger span kind to standard string."""
        if kind is None:
            return "INTERNAL"
        return kind.upper()

    def _detect_format(self, span_dict: Dict[str, Any]) -> str:
        """Detect span format from dictionary structure."""
        if "traceId" in span_dict and "spanId" in span_dict:
            if "startTimeUnixNano" in span_dict:
                return "otlp"
            elif "startTime" in span_dict:
                return "jaeger"
        if "localEndpoint" in span_dict:
            return "zipkin"
        return "generic"

    def _calculate_trace_depth(self, spans: List[TraceSpan]) -> int:
        """Calculate the maximum depth of the span tree."""
        if not spans:
            return 0

        # Build parent lookup
        span_lookup = {s.span_id: s for s in spans}

        def get_depth(span: TraceSpan, visited: set) -> int:
            if span.span_id in visited:
                return 0  # Cycle detection
            visited.add(span.span_id)

            if span.parent_span_id is None:
                return 1

            parent = span_lookup.get(span.parent_span_id)
            if parent:
                return 1 + get_depth(parent, visited)
            return 1

        max_depth = 0
        for span in spans:
            depth = get_depth(span, set())
            max_depth = max(max_depth, depth)

        return max_depth
