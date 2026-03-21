"""
Span parsing helpers for TraceParser.

Contains private methods for parsing spans from OTLP, Jaeger, Zipkin, and generic formats.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, cast

from Asgard.Verdandi.Tracing.models.tracing_models import (
    SpanLink,
    TraceSpan,
)


def parse_attributes(attrs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Parse OTLP attribute array to dictionary."""
    result: Dict[str, Any] = {}
    for attr in attrs:
        key = cast(str, attr.get("key", ""))
        value = attr.get("value", {})
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
                parse_attribute_value(v)
                for v in value["arrayValue"].get("values", [])
            ]
        else:
            result[key] = str(value)
    return result


def parse_attribute_value(value: Dict[str, Any]) -> Any:
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


def parse_span_kind(kind: int) -> str:
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


def jaeger_kind_to_string(kind: Optional[str]) -> str:
    """Convert Jaeger span kind to standard string."""
    if kind is None:
        return "INTERNAL"
    return kind.upper()


def detect_format(span_dict: Dict[str, Any]) -> str:
    """Detect span format from dictionary structure."""
    if "traceId" in span_dict and "spanId" in span_dict:
        if "startTimeUnixNano" in span_dict:
            return "otlp"
        elif "startTime" in span_dict:
            return "jaeger"
    if "localEndpoint" in span_dict:
        return "zipkin"
    return "generic"


def calculate_trace_depth(spans: List[TraceSpan]) -> int:
    """Calculate the maximum depth of the span tree."""
    if not spans:
        return 0

    span_lookup = {s.span_id: s for s in spans}

    def get_depth(span: TraceSpan, visited: set) -> int:
        if span.span_id in visited:
            return 0
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


def parse_otlp_span(
    span_data: Dict[str, Any],
    service_name: str,
    resource_attrs: Dict[str, Any],
    scope_name: Optional[str],
) -> TraceSpan:
    """Parse OTLP format span."""
    trace_id = span_data.get("traceId", "")
    span_id = span_data.get("spanId", "")
    parent_id = span_data.get("parentSpanId")

    if parent_id == "":
        parent_id = None

    start_nano = int(span_data.get("startTimeUnixNano", 0))
    end_nano = int(span_data.get("endTimeUnixNano", 0))
    duration_ms = (end_nano - start_nano) / 1e6

    status = span_data.get("status", {})
    status_code = status.get("code", "UNSET")
    if isinstance(status_code, int):
        status_code = {0: "UNSET", 1: "OK", 2: "ERROR"}.get(status_code, "UNSET")

    attributes = parse_attributes(span_data.get("attributes", []))

    events = []
    for event in span_data.get("events", []):
        events.append({
            "name": event.get("name"),
            "timestamp": event.get("timeUnixNano"),
            "attributes": parse_attributes(event.get("attributes", [])),
        })

    links = []
    for link in span_data.get("links", []):
        links.append(SpanLink(
            trace_id=link.get("traceId", ""),
            span_id=link.get("spanId", ""),
            attributes=parse_attributes(link.get("attributes", [])),
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
        kind=parse_span_kind(span_data.get("kind", 0)),
        attributes=attributes,
        events=events,
        links=links,
        resource_attributes=resource_attrs,
        instrumentation_scope=scope_name,
    )


def parse_jaeger_span(
    span_data: Dict[str, Any],
    service_name: str,
    process: Dict[str, Any],
) -> TraceSpan:
    """Parse Jaeger format span."""
    trace_id = span_data.get("traceID", "")
    span_id = span_data.get("spanID", "")

    parent_id = None
    for ref in span_data.get("references", []):
        if ref.get("refType") == "CHILD_OF":
            parent_id = ref.get("spanID")
            break

    start_micro = span_data.get("startTime", 0)
    duration_micro = span_data.get("duration", 0)
    start_nano = start_micro * 1000
    end_nano = start_nano + (duration_micro * 1000)

    attributes = {}
    for tag in span_data.get("tags", []):
        attributes[tag.get("key")] = tag.get("value")

    status_code = "UNSET"
    if attributes.get("error") is True:
        status_code = "ERROR"
    elif attributes.get("otel.status_code") == "ERROR":
        status_code = "ERROR"

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
        kind=jaeger_kind_to_string(attributes.get("span.kind")),
        attributes=attributes,
        events=events,
        resource_attributes=resource_attrs,
    )


def parse_zipkin_span(span_data: Dict[str, Any]) -> TraceSpan:
    """Parse Zipkin format span."""
    trace_id = span_data.get("traceId", "")
    span_id = span_data.get("id", "")
    parent_id = span_data.get("parentId")

    start_micro = span_data.get("timestamp", 0)
    duration_micro = span_data.get("duration", 0)
    start_nano = start_micro * 1000
    end_nano = start_nano + (duration_micro * 1000)

    local_endpoint = span_data.get("localEndpoint", {})
    service_name = local_endpoint.get("serviceName", "unknown")

    attributes = span_data.get("tags", {})

    status_code = "UNSET"
    if attributes.get("error"):
        status_code = "ERROR"

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


def parse_generic_span(span_data: Dict[str, Any]) -> TraceSpan:
    """Parse generic span format."""
    trace_id = span_data.get("trace_id", span_data.get("traceId", ""))
    span_id = span_data.get("span_id", span_data.get("spanId", ""))
    parent_id = span_data.get("parent_span_id", span_data.get("parentSpanId"))

    start_nano = span_data.get("start_time_unix_nano", 0)
    end_nano = span_data.get("end_time_unix_nano", 0)

    if start_nano == 0 and "start_time" in span_data:
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
