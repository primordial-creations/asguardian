"""
CFS Throttling Analyzer

CFS bandwidth control (quota/period, default period 100ms) can cause
up-to-period-length stop-the-world stalls even at low *average* utilization
(RESEARCH_12): 0.5% throttled time can degrade ~40% of requests, because
throttling clusters around request bursts rather than spreading evenly.
"""

from typing import List, Optional

from Asgard.Verdandi.System.models.system_models import CgroupCpuStats, ThrottleReport


class CgroupAnalyzer:
    """
    Analyzer for cgroup CFS throttling statistics.

    Example:
        analyzer = CgroupAnalyzer()
        stats = CgroupCpuStats(
            cpu_quota_us=50_000, cpu_period_us=100_000,
            nr_periods=1000, nr_throttled=300, throttled_time_ns=15_000_000_000,
        )
        report = analyzer.analyze(stats)
        print(report.verdict, report.max_injected_latency_ms)
    """

    CRITICAL_RATIO = 0.25
    WARNING_RATIO = 0.05

    def analyze(self, stats: CgroupCpuStats) -> ThrottleReport:
        """
        Analyze CFS throttling counters.

        Args:
            stats: Raw cgroup CPU bandwidth-control counters

        Returns:
            ThrottleReport
        """
        notes: List[str] = []
        recommendations: List[str] = []

        if stats.nr_periods <= 0:
            return ThrottleReport(
                verdict="healthy",
                notes=["No CFS periods observed yet; insufficient data."],
            )

        throttle_ratio = stats.nr_throttled / stats.nr_periods

        avg_stall_ms: Optional[float] = None
        if stats.nr_throttled > 0:
            avg_stall_ms = (stats.throttled_time_ns / stats.nr_throttled) / 1e6

        max_injected_latency_ms: Optional[float] = None
        if stats.cpu_quota_us and stats.cpu_quota_us > 0 and stats.cpu_period_us > 0:
            max_injected_latency_ms = (stats.cpu_period_us - stats.cpu_quota_us) / 1000.0

        if throttle_ratio > self.CRITICAL_RATIO:
            verdict = "critical"
        elif throttle_ratio > self.WARNING_RATIO:
            verdict = "warning"
        else:
            verdict = "healthy"

        if verdict in ("warning", "critical"):
            notes.append(
                f"throttle_ratio={throttle_ratio:.1%} of periods hit their quota. "
                "Throttling clusters around request bursts, so user-facing "
                "impact is likely several times the raw ratio (RESEARCH_12 sec2.3)."
            )
            if avg_stall_ms is not None:
                notes.append(f"avg_stall_ms={avg_stall_ms:.1f}ms per throttled period.")
            recommendations.append(
                "Raise or remove the CPU limit, or pin the workload to Guaranteed "
                "QoS, to eliminate limit-induced stalls."
            )

        limit_induced = False
        if throttle_ratio > 0 and stats.idle_cores_available:
            limit_induced = True
            notes.append(
                "Throttling observed while the node has idle cores: this is "
                "limit-induced latency, not real contention — the CPU limit "
                "itself is the bottleneck."
            )
            recommendations.append(
                "Node has idle capacity; the container's own CPU limit is "
                "throttling it. Raise limit or remove it."
            )

        if max_injected_latency_ms is not None:
            notes.append(
                f"Worst-case per-period stall (period - quota): "
                f"{max_injected_latency_ms:.0f}ms."
            )

        return ThrottleReport(
            throttle_ratio=round(throttle_ratio, 4),
            avg_stall_ms=round(avg_stall_ms, 3) if avg_stall_ms is not None else None,
            max_injected_latency_ms=(
                round(max_injected_latency_ms, 2) if max_injected_latency_ms is not None else None
            ),
            verdict=verdict,
            limit_induced_latency=limit_induced,
            notes=notes,
            recommendations=recommendations,
        )
