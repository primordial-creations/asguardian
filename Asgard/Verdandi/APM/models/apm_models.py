"""
APM Models

Pydantic models for Application Performance Monitoring including spans, traces,
and service metrics.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class SpanKind(str, Enum):
    """Kind/type of span in a distributed trace."""

    INTERNAL = "internal"
    SERVER = "server"
    CLIENT = "client"
    PRODUCER = "producer"
    CONSUMER = "consumer"


class SpanStatus(str, Enum):
    """Status of a span execution."""

    OK = "ok"
    ERROR = "error"
    UNSET = "unset"


class Span(BaseModel):
    """
    Represents a single span in a distributed trace.

    A span represents a single unit of work within a trace, such as
    an HTTP request, database query, or function call.
    """

    trace_id: str = Field(..., description="Unique trace identifier")
    span_id: str = Field(..., description="Unique span identifier")
    parent_span_id: Optional[str] = Field(
        default=None,
        description="Parent span ID (None for root spans)",
    )
    operation_name: str = Field(..., description="Name of the operation")
    service_name: str = Field(..., description="Name of the service")
    kind: SpanKind = Field(default=SpanKind.INTERNAL, description="Span kind")
    start_time: datetime = Field(..., description="Span start timestamp")
    end_time: datetime = Field(..., description="Span end timestamp")
    duration_ms: float = Field(..., description="Duration in milliseconds")
    status: SpanStatus = Field(default=SpanStatus.UNSET, description="Span status")
    error_message: Optional[str] = Field(
        default=None,
        description="Error message if status is ERROR",
    )
    attributes: Dict[str, Any] = Field(
        default_factory=dict,
        description="Span attributes/tags",
    )
    events: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Events recorded during span execution",
    )

    @property
    def is_root(self) -> bool:
        """Check if this is a root span."""
        return self.parent_span_id is None

    @property
    def has_error(self) -> bool:
        """Check if span has an error."""
        return self.status == SpanStatus.ERROR


class SpanAnalysis(BaseModel):
    """Analysis result for a single span."""

    span: Span = Field(..., description="The analyzed span")
    is_slow: bool = Field(default=False, description="Whether span is considered slow")
    slowness_factor: float = Field(
        default=1.0,
        description="How many times slower than threshold",
    )
    is_error: bool = Field(default=False, description="Whether span has error")
    child_count: int = Field(default=0, description="Number of child spans")
    total_child_duration_ms: float = Field(
        default=0.0,
        description="Total duration of all child spans",
    )
    self_time_ms: float = Field(
        default=0.0,
        description="Time spent in span itself (excluding children)",
    )
    recommendations: List[str] = Field(
        default_factory=list,
        description="Performance recommendations",
    )


class Trace(BaseModel):
    """
    Represents a complete distributed trace.

    A trace contains all spans that belong to a single request or transaction
    as it flows through multiple services.
    """

    trace_id: str = Field(..., description="Unique trace identifier")
    root_span: Optional[Span] = Field(
        default=None,
        description="Root span of the trace",
    )
    spans: List[Span] = Field(default_factory=list, description="All spans in trace")
    service_count: int = Field(default=0, description="Number of unique services")
    total_duration_ms: float = Field(default=0.0, description="Total trace duration")
    error_count: int = Field(default=0, description="Number of spans with errors")

    @property
    def span_count(self) -> int:
        """Get total number of spans."""
        return len(self.spans)

    @property
    def has_errors(self) -> bool:
        """Check if trace has any errors."""
        return self.error_count > 0


class ServiceMetrics(BaseModel):
    """Aggregated metrics for a service."""

    service_name: str = Field(..., description="Name of the service")
    request_count: int = Field(default=0, description="Total number of requests")
    error_count: int = Field(default=0, description="Number of errors")
    error_rate: float = Field(default=0.0, description="Error rate (0-1)")
    total_duration_ms: float = Field(
        default=0.0,
        description="Total duration of all requests",
    )
    avg_duration_ms: float = Field(
        default=0.0,
        description="Average request duration",
    )
    min_duration_ms: float = Field(
        default=0.0,
        description="Minimum request duration",
    )
    max_duration_ms: float = Field(
        default=0.0,
        description="Maximum request duration",
    )
    p50_duration_ms: float = Field(default=0.0, description="50th percentile duration")
    p95_duration_ms: float = Field(default=0.0, description="95th percentile duration")
    p99_duration_ms: float = Field(default=0.0, description="99th percentile duration")
    throughput_per_second: float = Field(
        default=0.0,
        description="Requests per second",
    )
    operations: Dict[str, Dict[str, float]] = Field(
        default_factory=dict,
        description="Per-operation metrics (operation_name -> metrics dict)",
    )


class ServiceDependency(BaseModel):
    """Represents a dependency between two services."""

    source_service: str = Field(..., description="Source/calling service name")
    target_service: str = Field(..., description="Target/called service name")
    call_count: int = Field(default=0, description="Number of calls")
    error_count: int = Field(default=0, description="Number of failed calls")
    avg_latency_ms: float = Field(default=0.0, description="Average call latency")
    p99_latency_ms: float = Field(default=0.0, description="99th percentile latency")
    is_async: bool = Field(
        default=False,
        description="Async/messaging edge (rendered dashed), e.g. producer->topic->consumer",
    )
    ghost: bool = Field(
        default=False,
        description="Edge present in a previous window but absent in the current one",
    )
    traffic_share: float = Field(
        default=0.0,
        description="Fraction of total call volume this edge represents (set by prune())",
    )


class ServiceIdentity(BaseModel):
    """
    Resolved canonical identity for a raw service name (DEEPTHINK_10).

    Composite key ``env:namespace:canonical_name`` when infra resource
    attributes (k8s namespace, deployment env) exist; otherwise lexical
    canonicalization only (lowercase, unify ``_``/space/camelCase -> ``-``).
    Never strips suffixes (``-api``/``-worker``) or version segments.
    """

    raw_name: str = Field(..., description="Original, unresolved service name")
    canonical_name: str = Field(..., description="Lexically canonicalized name")
    composite_key: str = Field(
        ...,
        description=(
            "env:namespace:canonical_name when infra resource attrs are "
            "available; otherwise equal to canonical_name"
        ),
    )
    env: Optional[str] = Field(default=None, description="Deployment environment, if known")
    namespace: Optional[str] = Field(default=None, description="k8s namespace, if known")


class EdgeStats(BaseModel):
    """Windowed traffic statistics for a single dependency edge."""

    model_config = ConfigDict(populate_by_name=True)

    calls: int = Field(default=0, description="Call count in this window")
    errors: int = Field(default=0, description="Error count in this window")
    is_async: bool = Field(default=False, alias="async", description="Async/messaging edge")
    ghost: bool = Field(default=False, description="Present in a previous window, absent now")


class VirtualNode(BaseModel):
    """
    A synthetic node representing a messaging system destination
    (``[system:destination]``) inferred from PRODUCER/CONSUMER span kinds,
    e.g. ``kafka:orders``. Generated/high-cardinality destination names
    (``amq.gen-*``, UUID-like segments) are parameterized to a placeholder
    to avoid cardinality explosion.
    """

    key: str = Field(..., description="'system:destination' composite key")
    system: str = Field(..., description="messaging.system attribute value")
    destination: str = Field(
        ..., description="messaging.destination.name (parameterized if generated)"
    )
    node_type: str = Field(default="messaging", description="Virtual node category")


class ServiceMap(BaseModel):
    """Service dependency map showing all services and their relationships."""

    services: List[str] = Field(
        default_factory=list,
        description="List of all services",
    )
    dependencies: List[ServiceDependency] = Field(
        default_factory=list,
        description="Dependencies between services",
    )
    root_services: List[str] = Field(
        default_factory=list,
        description="Services that are entry points (no inbound calls)",
    )
    leaf_services: List[str] = Field(
        default_factory=list,
        description="Services that are endpoints (no outbound calls)",
    )
    edge_count: int = Field(default=0, description="Total number of dependency edges")
    service_count: int = Field(default=0, description="Total number of services")
    virtual_nodes: List[VirtualNode] = Field(
        default_factory=list,
        description="Synthetic messaging-system nodes, e.g. kafka:orders",
    )
    identities: Dict[str, ServiceIdentity] = Field(
        default_factory=dict,
        description="raw_name -> resolved ServiceIdentity, when identity resolution was used",
    )

    @property
    def has_cycles(self) -> bool:
        """Check if the service map has cycles (not implemented in model)."""
        # This would need proper graph traversal - defer to service
        return False


class APMReport(BaseModel):
    """Comprehensive APM analysis report."""

    generated_at: datetime = Field(
        default_factory=datetime.now,
        description="Report generation timestamp",
    )
    analysis_period_start: Optional[datetime] = Field(
        default=None,
        description="Start of analysis period",
    )
    analysis_period_end: Optional[datetime] = Field(
        default=None,
        description="End of analysis period",
    )
    trace_count: int = Field(default=0, description="Number of traces analyzed")
    span_count: int = Field(default=0, description="Number of spans analyzed")
    service_metrics: List[ServiceMetrics] = Field(
        default_factory=list,
        description="Metrics for each service",
    )
    service_map: Optional[ServiceMap] = Field(
        default=None,
        description="Service dependency map",
    )
    slow_traces: List[Trace] = Field(
        default_factory=list,
        description="Traces that exceeded latency threshold",
    )
    error_traces: List[Trace] = Field(
        default_factory=list,
        description="Traces containing errors",
    )
    overall_error_rate: float = Field(default=0.0, description="Overall error rate")
    overall_avg_latency_ms: float = Field(
        default=0.0,
        description="Overall average latency",
    )
    overall_p99_latency_ms: float = Field(
        default=0.0,
        description="Overall P99 latency",
    )
    recommendations: List[str] = Field(
        default_factory=list,
        description="Performance recommendations",
    )
    health_score: float = Field(
        default=100.0,
        ge=0.0,
        le=100.0,
        description="Overall health score (0-100)",
    )
