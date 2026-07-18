"""
CPU Metrics Calculator

Calculates CPU usage and utilization metrics with virtualization-aware
steal-time bands, an M/M/1 queueing projection, and %iowait demoted from
health signal to annotation (RESEARCH_12).
"""

from typing import List, Optional

from Asgard.Verdandi.System.models.system_models import CpuMetrics


class CpuMetricsCalculator:
    """
    Calculator for CPU usage metrics.

    Analyzes CPU utilization and provides status assessments.

    Semantics (RESEARCH_12):
    - Steal time: < 2% fine, 2-5% moderate contention, > 5% critical.
      Steal masks itself as *low* guest CPU, so it can dominate the verdict
      even when total utilization looks moderate.
    - Queueing projection: M/M/1 residence R = S / (1 - rho); the 70-80%
      utilization band is the capacity-planning tipping point.
    - %iowait is a CPU-state artifact on multicore systems and never sets
      health status by itself; disk concerns route to await/PSI-io.

    Example:
        calc = CpuMetricsCalculator()
        result = calc.analyze(user_percent=45, system_percent=15, idle_percent=40)
        print(f"Total Usage: {result.usage_percent}%")
    """

    WARNING_THRESHOLD = 80.0
    CRITICAL_THRESHOLD = 95.0

    STEAL_WARNING_PERCENT = 2.0
    STEAL_CRITICAL_PERCENT = 5.0

    HOCKEY_STICK_RHO = 0.8

    def analyze(
        self,
        user_percent: float,
        system_percent: float,
        idle_percent: float,
        core_count: int = 1,
        iowait_percent: Optional[float] = None,
        per_core_usage: Optional[List[float]] = None,
        load_average_1m: Optional[float] = None,
        load_average_5m: Optional[float] = None,
        load_average_15m: Optional[float] = None,
        steal_percent: Optional[float] = None,
    ) -> CpuMetrics:
        """
        Analyze CPU usage.

        Args:
            user_percent: User space CPU percentage
            system_percent: System/kernel CPU percentage
            idle_percent: Idle CPU percentage
            core_count: Number of CPU cores
            iowait_percent: I/O wait percentage (annotation only — never sets
                health status; unreliable on multicore)
            per_core_usage: Per-core usage percentages
            load_average_1m: 1-minute load average
            load_average_5m: 5-minute load average
            load_average_15m: 15-minute load average
            steal_percent: CPU steal percentage (hypervisor contention)

        Returns:
            CpuMetrics with analysis
        """
        usage_percent = 100 - idle_percent

        steal_status = self._steal_band(steal_percent)
        rho = min(max(usage_percent / 100.0, 0.0), 0.999)
        latency_multiplier = 1.0 / (1.0 - rho)

        status = self._determine_status(
            usage_percent, steal_status, load_average_1m, core_count
        )
        recommendations = self._generate_recommendations(
            usage_percent, iowait_percent, load_average_1m, core_count,
            steal_percent, steal_status, rho, latency_multiplier,
        )

        return CpuMetrics(
            usage_percent=round(usage_percent, 2),
            user_percent=round(user_percent, 2),
            system_percent=round(system_percent, 2),
            idle_percent=round(idle_percent, 2),
            iowait_percent=round(iowait_percent, 2) if iowait_percent else None,
            core_count=core_count,
            per_core_usage=per_core_usage,
            load_average_1m=load_average_1m,
            load_average_5m=load_average_5m,
            load_average_15m=load_average_15m,
            steal_percent=round(steal_percent, 2) if steal_percent is not None else None,
            steal_status=steal_status,
            utilization_rho=round(rho, 4),
            latency_multiplier=round(latency_multiplier, 2),
            iowait_unreliable_on_multicore=True,
            status=status,
            recommendations=recommendations,
        )

    def calculate_load_ratio(
        self,
        load_average: float,
        core_count: int,
    ) -> float:
        """
        Calculate load ratio (load average / core count).

        A ratio > 1.0 indicates the system is overloaded.

        Args:
            load_average: Current load average
            core_count: Number of CPU cores

        Returns:
            Load ratio
        """
        if core_count <= 0:
            return 0.0
        return round(load_average / core_count, 2)

    def queueing_latency_multiplier(self, utilization_rho: float) -> float:
        """
        M/M/1 residence-time multiplier: R/S = 1 / (1 - rho).

        At rho=0.5 requests take 2x their service time; at rho=0.9, 10x.
        The 70-80% band is the practical capacity-planning ceiling.

        Args:
            utilization_rho: Per-core utilization as a fraction (0..1)

        Returns:
            Latency multiplier (capped at rho=0.999)
        """
        rho = min(max(utilization_rho, 0.0), 0.999)
        return round(1.0 / (1.0 - rho), 2)

    def _steal_band(self, steal_percent: Optional[float]) -> Optional[str]:
        """RESEARCH_12 steal bands: <2% ok, 2-5% warning, >5% critical."""
        if steal_percent is None:
            return None
        if steal_percent > self.STEAL_CRITICAL_PERCENT:
            return "critical"
        if steal_percent >= self.STEAL_WARNING_PERCENT:
            return "warning"
        return "ok"

    def _determine_status(
        self,
        usage_percent: float,
        steal_status: Optional[str],
        load_average: Optional[float],
        core_count: int,
    ) -> str:
        """Determine CPU status. Steal dominates: it masks itself as low guest CPU."""
        if steal_status == "critical":
            return "critical"

        if usage_percent >= self.CRITICAL_THRESHOLD:
            return "critical"
        if usage_percent >= self.WARNING_THRESHOLD:
            return "warning"

        if steal_status == "warning":
            return "warning"

        if load_average and core_count > 0:
            load_ratio = load_average / core_count
            if load_ratio > 2.0:
                return "critical"
            if load_ratio > 1.0:
                return "warning"

        return "healthy"

    def _generate_recommendations(
        self,
        usage_percent: float,
        iowait_percent: Optional[float],
        load_average: Optional[float],
        core_count: int,
        steal_percent: Optional[float],
        steal_status: Optional[str],
        rho: float,
        latency_multiplier: float,
    ) -> List[str]:
        """Generate CPU recommendations."""
        recommendations = []

        if steal_status == "critical":
            recommendations.append(
                f"Critical: CPU steal is {steal_percent:.1f}% (> {self.STEAL_CRITICAL_PERCENT:.0f}%). "
                "Hypervisor contention — software tuning is futile; migrate to "
                "another host or resize to a less contended instance class. "
                "Note: steal masks itself as low guest CPU."
            )
        elif steal_status == "warning":
            recommendations.append(
                f"CPU steal is {steal_percent:.1f}% (2-5% band): moderate hypervisor "
                "contention. Watch for latency inflation not explained by guest load."
            )

        if usage_percent >= self.CRITICAL_THRESHOLD:
            recommendations.append(
                "Critical: CPU usage is very high. Consider scaling up "
                "or optimizing workload."
            )
        elif usage_percent >= self.WARNING_THRESHOLD:
            recommendations.append(
                f"CPU usage is elevated ({usage_percent:.1f}%). "
                "Monitor for potential bottlenecks."
            )

        if rho > self.HOCKEY_STICK_RHO:
            recommendations.append(
                f"Utilization rho={rho:.2f} is past the ~0.8 hockey-stick point: "
                f"queueing theory (R = S/(1-rho)) projects ~{latency_multiplier:.1f}x "
                "service-time residence. Latency degrades non-linearly from here."
            )

        if iowait_percent and iowait_percent > 20:
            recommendations.append(
                f"%iowait is {iowait_percent:.1f}%, but %iowait is a CPU-state "
                "artifact and unreliable on multicore systems — it does not by "
                "itself indicate a disk problem. Check device await/aqu-sz "
                "(iostat) or PSI io pressure instead."
            )

        if load_average and core_count > 0:
            load_ratio = load_average / core_count
            if load_ratio > 1.0:
                recommendations.append(
                    f"Load average ({load_average:.2f}) exceeds core count ({core_count}). "
                    "System may be overloaded. Prefer run-queue length / scheduler "
                    "latency over load average where available (load includes "
                    "uninterruptible I/O waiters on Linux)."
                )

        return recommendations
