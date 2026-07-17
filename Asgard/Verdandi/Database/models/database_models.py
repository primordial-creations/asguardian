"""
Database Performance Models

Pydantic models for database performance metrics.
"""

from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class QueryType(str, Enum):
    """Database query type."""

    SELECT = "select"
    INSERT = "insert"
    UPDATE = "update"
    DELETE = "delete"
    OTHER = "other"


class QueryMetricsInput(BaseModel):
    """Input data for query metrics analysis."""

    query_id: Optional[str] = Field(default=None, description="Query identifier")
    query_type: QueryType = Field(..., description="Type of query")
    execution_time_ms: float = Field(..., description="Query execution time in ms")
    rows_examined: int = Field(default=0, description="Number of rows examined")
    rows_affected: int = Field(default=0, description="Number of rows affected")
    used_index: bool = Field(default=True, description="Whether query used an index")
    timestamp: Optional[str] = Field(default=None, description="Query timestamp")


class QueryMetricsResult(BaseModel):
    """Result of query metrics analysis."""

    total_queries: int = Field(..., description="Total queries analyzed")
    average_execution_ms: float = Field(..., description="Average execution time")
    median_execution_ms: float = Field(..., description="Median execution time")
    p95_execution_ms: float = Field(..., description="95th percentile execution time")
    p99_execution_ms: float = Field(..., description="99th percentile execution time")
    max_execution_ms: float = Field(..., description="Maximum execution time")
    min_execution_ms: float = Field(..., description="Minimum execution time")
    by_type: Dict[str, Dict[str, float]] = Field(
        default_factory=dict,
        description="Breakdown by query type",
    )
    slow_query_count: int = Field(..., description="Count of slow queries")
    slow_query_threshold_ms: float = Field(..., description="Threshold for slow queries")
    index_usage_rate: float = Field(..., description="Percentage of queries using indexes")
    scan_rate: float = Field(..., description="Avg rows examined per row affected")
    recommendations: List[str] = Field(
        default_factory=list,
        description="Performance recommendations",
    )


class ConnectionPoolMetrics(BaseModel):
    """Connection pool metrics."""

    pool_size: int = Field(..., description="Total pool size")
    active_connections: int = Field(..., description="Currently active connections")
    idle_connections: int = Field(..., description="Idle connections")
    waiting_requests: int = Field(..., description="Requests waiting for connection")
    utilization_percent: float = Field(..., description="Pool utilization percentage")
    average_wait_time_ms: float = Field(..., description="Average wait time for connection")
    max_wait_time_ms: float = Field(..., description="Maximum wait time observed")
    connection_errors: int = Field(default=0, description="Connection error count")
    timeout_count: int = Field(default=0, description="Connection timeout count")
    # Queue-wait vs service-time separation (RESEARCH_14): in-process query
    # timers measure service time only; acquisition wait must be measured
    # separately or the DB looks healthy while requests queue.
    wait_p50_ms: Optional[float] = Field(
        default=None, description="p50 of connection acquisition wait"
    )
    wait_p95_ms: Optional[float] = Field(
        default=None, description="p95 of connection acquisition wait"
    )
    wait_p99_ms: Optional[float] = Field(
        default=None, description="p99 of connection acquisition wait"
    )
    queue_share: Optional[float] = Field(
        default=None,
        description="wait_p95 / (wait_p95 + service_p95): fraction of tail "
        "latency spent waiting for a connection",
    )
    # Little's-law sizing (RESEARCH_12): required L = qps x avg query seconds.
    required_connections: Optional[float] = Field(
        default=None, description="Little's-law required connections (lambda x W)"
    )
    headroom_connections: Optional[float] = Field(
        default=None, description="pool_size - required_connections"
    )
    recommended_pool_size: Optional[int] = Field(
        default=None, description="ceil(required / 0.7) — 70% target utilization"
    )
    leak_suspected: bool = Field(
        default=False,
        description="Timeouts observed at < 70% utilization: connections held, not busy",
    )


class PoolSignatureClass(str, Enum):
    """Classification of a blended latency distribution's shape."""

    POOL_EXHAUSTION = "pool_exhaustion"
    CACHE_ASIDE_PATTERN = "cache_aside_pattern"
    AMBIGUOUS_BIMODAL = "ambiguous_bimodal"
    UNIMODAL = "unimodal"
    INSUFFICIENT_DATA = "insufficient_data"


class PoolModeStats(BaseModel):
    """Per-mode statistics of a bimodal latency distribution."""

    median_ms: float = Field(...)
    mad_ms: float = Field(...)
    count: int = Field(...)
    weight: float = Field(...)


class PoolSignature(BaseModel):
    """
    Pool-exhaustion signature analysis (RESEARCH_11).

    Pool exhaustion produces a bimodal latency distribution with two
    near-equal-variance peaks; the distance between the peaks IS the mean
    queue wait. Cache-aside bimodality instead shows a narrow fast peak and
    a wide slow peak.
    """

    classification: PoolSignatureClass = Field(...)
    mean_queue_wait_ms: Optional[float] = Field(
        default=None, description="m2 - m1 when classified as pool exhaustion"
    )
    modes: List[PoolModeStats] = Field(default_factory=list)
    mad_disparity: Optional[float] = Field(
        default=None, description="|s1 - s2| / max(s1, s2); < 0.35 => equal-variance"
    )
    confidence: str = Field(
        default="medium", description="low | medium | high (high when wait samples corroborate)"
    )
    corroborated_by_wait_samples: bool = Field(default=False)
    warnings: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)


class TransactionMetrics(BaseModel):
    """Transaction performance metrics."""

    total_transactions: int = Field(..., description="Total transactions")
    committed: int = Field(..., description="Successfully committed")
    rolled_back: int = Field(..., description="Rolled back")
    average_duration_ms: float = Field(..., description="Average transaction duration")
    p95_duration_ms: float = Field(..., description="95th percentile duration")
    deadlock_count: int = Field(default=0, description="Deadlock occurrences")
    lock_wait_time_ms: float = Field(default=0, description="Total lock wait time")
    commit_rate: float = Field(..., description="Commit success rate percentage")


class DatabaseHealthResult(BaseModel):
    """Overall database health assessment."""

    health_score: float = Field(..., ge=0, le=100, description="Health score 0-100")
    status: str = Field(..., description="Overall status (healthy, degraded, critical)")
    query_metrics: Optional[QueryMetricsResult] = Field(default=None)
    connection_metrics: Optional[ConnectionPoolMetrics] = Field(default=None)
    transaction_metrics: Optional[TransactionMetrics] = Field(default=None)
    throughput_qps: float = Field(..., description="Queries per second")
    error_rate: float = Field(..., description="Error rate percentage")
    recommendations: List[str] = Field(
        default_factory=list,
        description="Health recommendations",
    )
