"""
Tracing Models

Pydantic models for distributed tracing including spans, traces,
and analysis results.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SpanLink(BaseModel):
    """Link between spans in different traces."""

    trace_id: str = Field(..., description="Linked trace ID")
    span_id: str = Field(..., description="Linked span ID")
    link_type: str = Field(default="child_of", description="Type of link relationship")
    attributes: Dict[str, Any] = Field(
        default_factory=dict, description="Link attributes"
    )


class TraceSpan(BaseModel):
    """
    Represents a span in a distributed trace.

    Enhanced model with additional tracing-specific fields.
    """

    trace_id: str = Field(..., description="Unique trace identifier")
    span_id: str = Field(..., description="Unique span identifier")
    parent_span_id: Optional[str] = Field(
        default=None, description="Parent span ID"
    )
    operation_name: str = Field(..., description="Name of the operation")
    service_name: str = Field(..., description="Name of the service")
    start_time_unix_nano: int = Field(
        ..., description="Start time in Unix nanoseconds"
    )
    end_time_unix_nano: int = Field(
        ..., description="End time in Unix nanoseconds"
    )
    duration_ms: float = Field(..., description="Duration in milliseconds")
    status_code: str = Field(default="UNSET", description="Status code (OK, ERROR, UNSET)")
    status_message: Optional[str] = Field(
        default=None, description="Status message for errors"
    )
    kind: str = Field(default="INTERNAL", description="Span kind")
    attributes: Dict[str, Any] = Field(
        default_factory=dict, description="Span attributes"
    )
    events: List[Dict[str, Any]] = Field(
        default_factory=list, description="Span events"
    )
    links: List[SpanLink] = Field(
        default_factory=list, description="Links to other spans"
    )
    resource_attributes: Dict[str, Any] = Field(
        default_factory=dict, description="Resource attributes"
    )
    instrumentation_scope: Optional[str] = Field(
        default=None, description="Name of instrumentation library"
    )
    effective_end_ns: Optional[int] = Field(
        default=None,
        description=(
            "Causally-normalized end timestamp (Unix nanoseconds), set by the "
            "async-truncation pass in causal_normalizer.py. min(span.end, "
            "parent.effective_end). None until normalization has run; falls "
            "back to end_time_unix_nano when unset."
        ),
    )

    @property
    def start_time(self) -> datetime:
        """Get start time as datetime."""
        return datetime.fromtimestamp(self.start_time_unix_nano / 1e9)

    @property
    def end_time(self) -> datetime:
        """Get end time as datetime."""
        return datetime.fromtimestamp(self.end_time_unix_nano / 1e9)

    @property
    def is_root(self) -> bool:
        """Check if this is a root span."""
        return self.parent_span_id is None

    @property
    def has_error(self) -> bool:
        """Check if span has error status."""
        return self.status_code == "ERROR"

    @property
    def effective_end_time_unix_nano(self) -> int:
        """Effective end (post async-truncation), falling back to raw end."""
        return (
            self.effective_end_ns
            if self.effective_end_ns is not None
            else self.end_time_unix_nano
        )


class DistributedTrace(BaseModel):
    """
    Represents a complete distributed trace.
    """

    trace_id: str = Field(..., description="Unique trace identifier")
    spans: List[TraceSpan] = Field(default_factory=list, description="All spans")
    root_span: Optional[TraceSpan] = Field(default=None, description="Root span")
    service_names: List[str] = Field(
        default_factory=list, description="Unique services in trace"
    )
    total_duration_ms: float = Field(default=0.0, description="Total trace duration")
    span_count: int = Field(default=0, description="Number of spans")
    error_count: int = Field(default=0, description="Number of error spans")
    depth: int = Field(default=0, description="Maximum depth of span tree")
    start_time: Optional[datetime] = Field(
        default=None, description="Trace start time"
    )
    end_time: Optional[datetime] = Field(default=None, description="Trace end time")

    @property
    def has_errors(self) -> bool:
        """Check if trace has any errors."""
        return self.error_count > 0


class ConfidenceFlag(str, Enum):
    """
    Confidence annotations emitted by causal normalization and the
    sweep-line critical path analyzer.

    These are epistemic annotations, not alert severities (anomalies are
    not alerts): they tell a reader how much to trust a specific result,
    they never trigger paging/alerting on their own.
    """

    ORPHANED_SUBTREE_RECOVERED = "orphaned_subtree_recovered"
    HEAVY_CLOCK_SKEW_ADJUSTED = "heavy_clock_skew_adjusted"
    SEVERE_ASYNC_TRUNCATION = "severe_async_truncation"
    HIGH_UNATTRIBUTED_TIME = "high_unattributed_time"


class AnalysisOutcome(str, Enum):
    """
    Typed outcome of an analysis attempt.

    INSUFFICIENT_DATA is a *success* outcome (DEEPTHINK_01): the analyzer is
    reporting honestly that it cannot produce a sound result (no spans, no
    determinable root, degenerate/zero-length trace), and it must never
    trip alerts.
    """

    OK = "ok"
    INSUFFICIENT_DATA = "insufficient_data"


class CriticalPathSegment(BaseModel):
    """A segment of the critical path."""

    span: TraceSpan = Field(..., description="The span in this segment")
    contribution_ms: float = Field(
        ..., description="Time contribution to critical path"
    )
    contribution_percent: float = Field(
        ..., description="Percentage of total critical path time"
    )
    is_blocking: bool = Field(
        default=True, description="Whether this segment blocks the path"
    )


class CriticalPathResult(BaseModel):
    """Result of critical path analysis."""

    trace_id: str = Field(..., description="Trace ID analyzed")
    total_duration_ms: float = Field(..., description="Total trace duration")
    critical_path_duration_ms: float = Field(
        ..., description="Critical path duration"
    )
    segments: List[CriticalPathSegment] = Field(
        default_factory=list, description="Critical path segments"
    )
    bottleneck_service: Optional[str] = Field(
        default=None, description="Service contributing most to latency"
    )
    bottleneck_operation: Optional[str] = Field(
        default=None, description="Operation contributing most to latency"
    )
    parallelization_opportunity_ms: float = Field(
        default=0.0, description="Potential savings from parallelization"
    )
    recommendations: List[str] = Field(
        default_factory=list, description="Optimization recommendations"
    )
    strategy: str = Field(
        default="legacy",
        description=(
            "Algorithm used: 'legacy' (naive longest-path + self-time "
            "subtraction) or 'sweepline' (causal-normalized latest-finisher "
            "sweep-line critical path)."
        ),
    )
    flags: List[ConfidenceFlag] = Field(
        default_factory=list,
        description=(
            "Confidence/anomaly annotations (not alerts) raised while "
            "computing this result, e.g. clock-skew corrections or "
            "unattributed self-time above the 30% threshold."
        ),
    )
    assumptions: List[str] = Field(
        default_factory=list,
        description=(
            "Human-readable assumptions this result relies on (populated "
            "for strategy='sweepline'), e.g. symmetric network latency."
        ),
    )
    outcome: AnalysisOutcome = Field(
        default=AnalysisOutcome.OK,
        description="Typed outcome; INSUFFICIENT_DATA is a success signal, not a failure.",
    )


class TracingReport(BaseModel):
    """Comprehensive tracing analysis report."""

    generated_at: datetime = Field(
        default_factory=datetime.now, description="Report generation timestamp"
    )
    trace_count: int = Field(default=0, description="Number of traces analyzed")
    total_span_count: int = Field(default=0, description="Total spans across traces")
    unique_services: List[str] = Field(
        default_factory=list, description="Unique services observed"
    )
    unique_operations: List[str] = Field(
        default_factory=list, description="Unique operations observed"
    )
    avg_trace_duration_ms: float = Field(
        default=0.0, description="Average trace duration"
    )
    avg_span_count: float = Field(
        default=0.0, description="Average spans per trace"
    )
    error_rate: float = Field(default=0.0, description="Percentage of traces with errors")
    latency_percentiles: Dict[str, float] = Field(
        default_factory=dict, description="Trace latency percentiles"
    )
    service_latencies: Dict[str, Dict[str, float]] = Field(
        default_factory=dict, description="Per-service latency stats"
    )
    critical_paths: List[CriticalPathResult] = Field(
        default_factory=list, description="Critical path analyses"
    )
    slowest_traces: List[DistributedTrace] = Field(
        default_factory=list, description="Slowest traces observed"
    )
    error_traces: List[DistributedTrace] = Field(
        default_factory=list, description="Traces containing errors"
    )
    recommendations: List[str] = Field(
        default_factory=list, description="Overall recommendations"
    )
