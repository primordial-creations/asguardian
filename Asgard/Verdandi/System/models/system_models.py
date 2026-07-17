"""
System Performance Models

Pydantic models for system performance metrics.
"""

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


class ResourceUtilization(BaseModel):
    """Combined resource utilization summary."""

    memory: MemoryMetrics = Field(..., description="Memory metrics")
    cpu: CpuMetrics = Field(..., description="CPU metrics")
    io: Optional[IoMetrics] = Field(default=None, description="I/O metrics")
    overall_health_score: float = Field(..., ge=0, le=100, description="Overall score")
    overall_status: str = Field(..., description="Overall status")
    bottleneck: Optional[str] = Field(default=None, description="Primary bottleneck")
    recommendations: List[str] = Field(default_factory=list)
