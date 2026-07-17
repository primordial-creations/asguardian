"""
Network Performance Models

Pydantic models for network performance metrics.
"""

from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class NetworkOutcome(str, Enum):
    """Typed outcome of a network analysis attempt.

    INSUFFICIENT_DATA is a *success* outcome (DEEPTHINK_01): the analyzer is
    reporting honestly that it cannot answer, and it must never trip alerts.
    """

    OK = "ok"
    INSUFFICIENT_DATA = "insufficient_data"


class LatencyMetrics(BaseModel):
    """Network latency metrics."""

    sample_count: int = Field(..., description="Number of samples")
    min_ms: float = Field(..., description="Minimum latency")
    max_ms: float = Field(..., description="Maximum latency")
    mean_ms: float = Field(..., description="Mean latency")
    median_ms: float = Field(..., description="Median latency")
    p90_ms: float = Field(..., description="90th percentile latency")
    p95_ms: float = Field(..., description="95th percentile latency")
    p99_ms: float = Field(..., description="99th percentile latency")
    std_dev_ms: float = Field(..., description="Standard deviation")
    jitter_ms: float = Field(..., description="Latency jitter (variation)")
    packet_loss_percent: Optional[float] = Field(default=None, description="Packet loss")
    status: str = Field(..., description="Status (good, acceptable, poor)")
    recommendations: List[str] = Field(default_factory=list)


class BandwidthMetrics(BaseModel):
    """Bandwidth utilization metrics."""

    upload_mbps: float = Field(..., description="Upload speed in Mbps")
    download_mbps: float = Field(..., description="Download speed in Mbps")
    total_throughput_mbps: float = Field(..., description="Total throughput")
    utilization_percent: Optional[float] = Field(default=None, description="Link utilization")
    capacity_mbps: Optional[float] = Field(default=None, description="Link capacity")
    bytes_sent: int = Field(..., description="Total bytes sent")
    bytes_received: int = Field(..., description="Total bytes received")
    duration_seconds: float = Field(..., description="Measurement duration")
    status: str = Field(..., description="Status")
    recommendations: List[str] = Field(default_factory=list)


class DnsMetrics(BaseModel):
    """DNS resolution metrics."""

    query_count: int = Field(..., description="Number of DNS queries")
    avg_resolution_ms: float = Field(..., description="Average resolution time")
    p95_resolution_ms: float = Field(..., description="95th percentile resolution time")
    max_resolution_ms: float = Field(..., description="Maximum resolution time")
    cache_hit_rate: float = Field(..., description="DNS cache hit rate percentage")
    failure_rate: float = Field(..., description="DNS failure rate percentage")
    by_record_type: Dict[str, Dict[str, float]] = Field(
        default_factory=dict,
        description="Breakdown by record type",
    )
    status: str = Field(..., description="Status")
    recommendations: List[str] = Field(default_factory=list)


class ConnectionMetrics(BaseModel):
    """TCP/HTTP connection metrics."""

    total_connections: int = Field(..., description="Total connections")
    active_connections: int = Field(..., description="Currently active")
    idle_connections: int = Field(..., description="Idle connections")
    avg_connection_time_ms: float = Field(..., description="Avg time to establish")
    avg_ssl_handshake_ms: Optional[float] = Field(default=None, description="Avg SSL handshake")
    connection_reuse_rate: float = Field(..., description="Connection reuse percentage")
    error_rate: float = Field(..., description="Connection error rate")
    timeout_count: int = Field(default=0, description="Connection timeouts")
    status: str = Field(..., description="Status")
    recommendations: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Plan 05: TTFB phase decomposition
# ---------------------------------------------------------------------------


class ConnectionPhases(BaseModel):
    """Per-request phase timings feeding TTFB decomposition (RESEARCH_11).

    Shape mirrors Web/navigation_timing so batch-mode callers can reuse the
    same raw records.
    """

    dns_ms: float = Field(default=0.0, ge=0.0, description="DNS resolution time")
    tcp_ms: float = Field(default=0.0, ge=0.0, description="TCP connect time (~1 RTT)")
    tls_ms: float = Field(default=0.0, ge=0.0, description="TLS handshake time")
    request_ms: float = Field(default=0.0, ge=0.0, description="Time to send the request")
    response_ms: float = Field(default=0.0, ge=0.0, description="Server processing / wait time")
    ttfb_ms: Optional[float] = Field(
        default=None, description="Observed TTFB; derived from phases when absent"
    )
    protocol: Optional[str] = Field(
        default=None, description="http/1.1, h2, h3 (QUIC)"
    )
    tls_version: Optional[str] = Field(
        default=None, description="1.2, 1.3, or None (plaintext/resumed)"
    )
    resumed: bool = Field(default=False, description="TLS session resumption / 0-RTT")


class PhaseStats(BaseModel):
    """Percentile summary for a single TTFB phase."""

    p50_ms: float = Field(default=0.0)
    p75_ms: float = Field(default=0.0)
    p95_ms: float = Field(default=0.0)
    mean_ms: float = Field(default=0.0)
    share_of_ttfb_percent: float = Field(
        default=0.0, description="Mean share of total TTFB attributable to this phase"
    )


#: Flag: TLS phase duration exceeds 1.5x the expected handshake-RTT budget.
HANDSHAKE_OVERHEAD = "HANDSHAKE_OVERHEAD"


class PhaseAnalysisResult(BaseModel):
    """Result of TTFB phase decomposition + protocol-expectation check."""

    outcome: NetworkOutcome = Field(default=NetworkOutcome.OK)
    sample_count: int = Field(default=0)
    dns: PhaseStats = Field(default_factory=PhaseStats)
    tcp: PhaseStats = Field(default_factory=PhaseStats)
    tls: PhaseStats = Field(default_factory=PhaseStats)
    request: PhaseStats = Field(default_factory=PhaseStats)
    response: PhaseStats = Field(default_factory=PhaseStats)
    ttfb_p50_ms: float = Field(default=0.0)
    ttfb_p95_ms: float = Field(default=0.0)
    ttfb_dominant_phase: str = Field(
        default="", description="Phase contributing the largest mean share of TTFB"
    )
    protocol_flags: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Plan 05: Topology baseline profiles
# ---------------------------------------------------------------------------


class TopologyProfile(str, Enum):
    """Named cloud/network topology baselines (RESEARCH_11)."""

    INTRA_AZ = "intra_az"
    INTER_AZ = "inter_az"
    SAME_REGION_PUBLIC = "same_region_public"
    CROSS_REGION = "cross_region"
    INTERNET_EDGE = "internet_edge"
    #: The pre-Plan-05 absolute health bands, kept for backward compatibility.
    LEGACY_DEFAULT = "legacy_default"


class TopologyRating(str, Enum):
    """Rating of observed latency against a topology baseline."""

    GOOD = "good"
    DEGRADED = "degraded"
    POOR = "poor"
    INSUFFICIENT_DATA = "insufficient_data"


class ProfileLatencyResult(BaseModel):
    """Latency rated against a named topology baseline instead of absolute bands."""

    profile: TopologyProfile
    rating: TopologyRating = Field(default=TopologyRating.INSUFFICIENT_DATA)
    sample_count: int = Field(default=0)
    p50_ms: float = Field(default=0.0)
    p95_ms: float = Field(default=0.0)
    p99_ms: float = Field(default=0.0)
    expected_rtt_low_ms: float = Field(default=0.0)
    expected_rtt_high_ms: float = Field(default=0.0)
    degraded_above_ms: float = Field(default=0.0)
    packet_loss_percent: Optional[float] = Field(default=None)
    packet_loss_baseline_percent: float = Field(default=0.0)
    warnings: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Plan 05: USE method for cloud NICs / DNS quotas
# ---------------------------------------------------------------------------


class UseCounterSnapshot(BaseModel):
    """Point-in-time counter snapshot for the USE analyzer."""

    sent_bytes_ps: float = Field(default=0.0, ge=0.0)
    recv_bytes_ps: float = Field(default=0.0, ge=0.0)
    pps: float = Field(default=0.0, ge=0.0)
    instance_bw_limit_mbps: Optional[float] = Field(default=None)
    instance_pps_limit: Optional[float] = Field(default=None)
    tcp_retransmits: int = Field(default=0, ge=0)
    listen_overflows: int = Field(default=0, ge=0)
    conntrack_allowance_exceeded: int = Field(default=0, ge=0)
    pps_allowance_exceeded: int = Field(default=0, ge=0)
    bw_in_allowance_exceeded: int = Field(default=0, ge=0)
    linklocal_allowance_exceeded: int = Field(
        default=0, ge=0, description="AWS's silent 1,024-PPS link-local DNS quota"
    )
    active_connections: int = Field(default=0, ge=0)
    ephemeral_port_range: Optional[int] = Field(default=None)
    dns_qps: Optional[float] = Field(default=None)


class UseResourceColumn(BaseModel):
    """One row (utilization / saturation / errors) of a USE report."""

    resource: str
    utilization_percent: Optional[float] = Field(default=None)
    saturated: bool = Field(default=False)
    saturation_notes: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    severity: str = Field(default="ok", description="ok | warning | critical")
    remediation: List[str] = Field(default_factory=list)


class USEReport(BaseModel):
    """USE-method report for cloud NICs, TCP stack, and DNS resolver."""

    outcome: NetworkOutcome = Field(default=NetworkOutcome.OK)
    nic: UseResourceColumn = Field(
        default_factory=lambda: UseResourceColumn(resource="nic")
    )
    tcp_stack: UseResourceColumn = Field(
        default_factory=lambda: UseResourceColumn(resource="tcp_stack")
    )
    dns_resolver: UseResourceColumn = Field(
        default_factory=lambda: UseResourceColumn(resource="dns_resolver")
    )
    overall_severity: str = Field(default="ok")
    recommendations: List[str] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Plan 05: BGP/DNS-hijack anomaly signatures + clock-skew guard
# ---------------------------------------------------------------------------


class NetworkSignatureType(str, Enum):
    """Classified network anomaly signature (annotation only, never an alert)."""

    NONE = "none"
    ROUTE_CHANGE = "route_change"
    DNS_HIJACK_SUSPECT = "dns_hijack_suspect"
    CONGESTION = "congestion"
    CLOCK_SKEW = "clock_skew"
    INSUFFICIENT_DATA = "insufficient_data"


class NetworkSignature(BaseModel):
    """Result of the anomaly-signature classifier. An annotation, not an alert."""

    signature: NetworkSignatureType = Field(default=NetworkSignatureType.NONE)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    change_index: Optional[int] = Field(default=None)
    details: str = Field(default="")
    is_data_quality_issue: bool = Field(
        default=False,
        description="True for CLOCK_SKEW: a measurement artifact, not a network event",
    )
    notes: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Plan 05: DNS quota / environment bands
# ---------------------------------------------------------------------------


class DnsQuotaResult(BaseModel):
    """USE-style quota/error columns and environment expectation bands for DNS."""

    outcome: NetworkOutcome = Field(default=NetworkOutcome.OK)
    environment: str = Field(default="public", description="in_vpc | public")
    queries_ps: float = Field(default=0.0)
    linklocal_quota_utilization_percent: float = Field(default=0.0)
    quota_exceeded: bool = Field(default=False)
    nxdomain_rate_percent: float = Field(default=0.0)
    servfail_rate_percent: float = Field(default=0.0)
    timeout_rate_percent: float = Field(default=0.0)
    expected_band_low_ms: float = Field(default=0.0)
    expected_band_high_ms: float = Field(default=0.0)
    status: str = Field(default="ok")
    recommendations: List[str] = Field(default_factory=list)
