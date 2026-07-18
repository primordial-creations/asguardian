"""
System Performance Models

Pydantic models for system performance metrics.
"""

from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class MemoryMetrics(BaseModel):
    """Memory usage metrics."""

    total_bytes: int = Field(..., description="Total memory in bytes")
    used_bytes: int = Field(..., description="Used memory in bytes")
    available_bytes: int = Field(..., description="Available memory in bytes")
    usage_percent: float = Field(..., description="Usage percentage")
    swap_total_bytes: Optional[int] = Field(default=None, description="Total swap space")
    swap_used_bytes: Optional[int] = Field(default=None, description="Used swap space")
    swap_percent: Optional[float] = Field(default=None, description="Swap usage percentage")
    major_faults_ps: Optional[float] = Field(
        default=None, description="Major page faults per second (saturation signal)"
    )
    swap_in_ps: Optional[float] = Field(default=None, description="Swap-in pages/sec")
    swap_out_ps: Optional[float] = Field(default=None, description="Swap-out pages/sec")
    oom_kills: Optional[int] = Field(default=None, description="OOM kills observed in window")
    available_based_usage: bool = Field(
        default=False,
        description="True when usage_percent was derived from MemAvailable (not 'free')",
    )
    thrashing_stall: bool = Field(
        default=False,
        description="THRASHING_STALL: low CPU + high major faults ('idle but slow')",
    )
    saturation_signals: List[str] = Field(
        default_factory=list,
        description="Memory saturation evidence (majflt/swap activity/OOM kills)",
    )
    status: str = Field(..., description="Status (healthy, warning, critical)")
    recommendations: List[str] = Field(default_factory=list)


class CpuMetrics(BaseModel):
    """CPU usage metrics."""

    usage_percent: float = Field(..., description="Overall CPU usage percentage")
    user_percent: float = Field(..., description="User space CPU percentage")
    system_percent: float = Field(..., description="System/kernel CPU percentage")
    idle_percent: float = Field(..., description="Idle CPU percentage")
    iowait_percent: Optional[float] = Field(default=None, description="I/O wait percentage")
    core_count: int = Field(..., description="Number of CPU cores")
    per_core_usage: Optional[List[float]] = Field(default=None, description="Per-core usage")
    load_average_1m: Optional[float] = Field(default=None, description="1-minute load average")
    load_average_5m: Optional[float] = Field(default=None, description="5-minute load average")
    load_average_15m: Optional[float] = Field(default=None, description="15-minute load average")
    steal_percent: Optional[float] = Field(
        default=None, description="CPU steal percentage (hypervisor contention)"
    )
    steal_status: Optional[str] = Field(
        default=None, description="Steal band: ok (<2%), warning (2-5%), critical (>5%)"
    )
    utilization_rho: Optional[float] = Field(
        default=None, description="Utilization as a fraction (rho) used for queueing projection"
    )
    latency_multiplier: Optional[float] = Field(
        default=None,
        description="M/M/1 residence-time multiplier 1/(1-rho); >5x means the hockey stick",
    )
    iowait_unreliable_on_multicore: bool = Field(
        default=True,
        description="%iowait is a CPU-state artifact, not a disk-health signal; "
        "route disk concerns to await/PSI-io",
    )
    status: str = Field(..., description="Status (healthy, warning, critical)")
    recommendations: List[str] = Field(default_factory=list)


class IoMetrics(BaseModel):
    """I/O performance metrics."""

    read_bytes_per_sec: float = Field(..., description="Read throughput in bytes/sec")
    write_bytes_per_sec: float = Field(..., description="Write throughput in bytes/sec")
    read_ops_per_sec: float = Field(..., description="Read operations per second")
    write_ops_per_sec: float = Field(..., description="Write operations per second")
    total_iops: float = Field(..., description="Total IOPS")
    total_throughput_mbps: float = Field(..., description="Total throughput in MB/s")
    avg_read_latency_ms: Optional[float] = Field(default=None, description="Avg read latency")
    avg_write_latency_ms: Optional[float] = Field(default=None, description="Avg write latency")
    queue_depth: Optional[float] = Field(default=None, description="Average queue depth")
    utilization_percent: Optional[float] = Field(default=None, description="Disk utilization")
    device_type: Optional[str] = Field(
        default=None, description="Device class: hdd, ssd, or nvme"
    )
    aqu_sz: Optional[float] = Field(
        default=None, description="Average queue size (iostat aqu-sz)"
    )
    r_await_ms: Optional[float] = Field(
        default=None, description="Average read wait incl. queueing (iostat r_await)"
    )
    w_await_ms: Optional[float] = Field(
        default=None, description="Average write wait incl. queueing (iostat w_await)"
    )
    utilization_misleading_for_parallel_devices: bool = Field(
        default=False,
        description="True for SSD/NVMe: %util means 'device busy', not saturated; "
        "it is excluded from health rating",
    )
    status: str = Field(..., description="Status (healthy, warning, critical)")
    recommendations: List[str] = Field(default_factory=list)


class PsiResource(str, Enum):
    """Pressure Stall Information resource kind."""

    CPU = "cpu"
    MEMORY = "memory"
    IO = "io"


class PsiSnapshot(BaseModel):
    """A single /proc/pressure/{resource} reading."""

    resource: PsiResource = Field(...)
    some_avg10: float = Field(default=0.0)
    some_avg60: float = Field(default=0.0)
    some_avg300: float = Field(default=0.0)
    full_avg10: float = Field(default=0.0)
    full_avg60: float = Field(default=0.0)
    full_avg300: float = Field(default=0.0)
    total_us: int = Field(default=0, description="Cumulative stalled microseconds")
    cgroup_id: Optional[str] = Field(default=None)
    timestamp: Optional[float] = Field(default=None)


class PsiReport(BaseModel):
    """PSI severity/trajectory analysis, optionally across multiple resources."""

    resource: Optional[PsiResource] = Field(default=None)
    severity: str = Field(
        default="healthy",
        description="healthy | warning | severe | critical (full_avg10 > 0)",
    )
    trajectory: Optional[str] = Field(
        default=None, description="'fresh_spike' | 'sustained_bottleneck' | None"
    )
    micro_burst_detected: bool = Field(
        default=False,
        description="Delta total_us between snapshots >> avg10 implies sub-10s "
        "stalls smoothed out of the rolling averages",
    )
    cross_resource_diagnosis: Optional[str] = Field(
        default=None,
        description="Diagnosis string when multiple resources are supplied "
        "(pure disk bottleneck | thrashing | run-queue contention)",
    )
    notes: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)


class CgroupCpuStats(BaseModel):
    """Raw CFS bandwidth-control counters for a cgroup."""

    cpu_quota_us: Optional[int] = Field(default=None, description="-1 or None means unlimited")
    cpu_period_us: int = Field(default=100_000)
    nr_periods: int = Field(default=0)
    nr_throttled: int = Field(default=0)
    throttled_time_ns: int = Field(default=0)
    usage_ns: Optional[int] = Field(default=None)
    limit_cores: Optional[float] = Field(default=None)
    request_cores: Optional[float] = Field(default=None)
    idle_cores_available: Optional[bool] = Field(
        default=None, description="Whether the node has idle cores despite throttling"
    )


class ThrottleReport(BaseModel):
    """CFS throttling analysis (RESEARCH_12 sec 2.3)."""

    throttle_ratio: Optional[float] = Field(
        default=None, description="nr_throttled / nr_periods"
    )
    avg_stall_ms: Optional[float] = Field(
        default=None, description="throttled_time_ns / nr_throttled / 1e6"
    )
    max_injected_latency_ms: Optional[float] = Field(
        default=None, description="Worst-case per-period stall: period - quota"
    )
    verdict: str = Field(
        default="healthy", description="healthy | warning | critical"
    )
    limit_induced_latency: bool = Field(
        default=False,
        description="Throttling observed while the node has idle cores: "
        "the limit itself, not real contention, causes the latency",
    )
    notes: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)


class UseRedCorrelation(BaseModel):
    """USE (saturation) <-> RED (p99 duration) causal correlation."""

    best_lag: Optional[int] = Field(
        default=None, description="Lag (buckets) at which saturation leads p99 duration"
    )
    best_correlation: Optional[float] = Field(
        default=None, description="Pearson r at best_lag"
    )
    correlations_by_lag: Dict[int, float] = Field(default_factory=dict)
    verdict: str = Field(
        default="insufficient_data",
        description="capacity_bound | regression_suspected | insufficient_data",
    )
    ordering_confirmed: bool = Field(
        default=False,
        description="Rate up -> Saturation up -> p99 up -> Errors up observed in order",
    )
    notes: List[str] = Field(default_factory=list)


class ResourceUtilization(BaseModel):
    """Combined resource utilization summary."""

    memory: MemoryMetrics = Field(..., description="Memory metrics")
    cpu: CpuMetrics = Field(..., description="CPU metrics")
    io: Optional[IoMetrics] = Field(default=None, description="I/O metrics")
    overall_health_score: float = Field(..., ge=0, le=100, description="Overall score")
    overall_status: str = Field(..., description="Overall status")
    bottleneck: Optional[str] = Field(default=None, description="Primary bottleneck")
    recommendations: List[str] = Field(default_factory=list)
