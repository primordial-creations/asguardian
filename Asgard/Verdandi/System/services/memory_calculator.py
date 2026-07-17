"""
Memory Metrics Calculator

Calculates memory usage and utilization metrics.
"""

from typing import List, Optional

from Asgard.Verdandi.System.models.system_models import MemoryMetrics


class MemoryMetricsCalculator:
    """
    Calculator for memory usage metrics.

    Analyzes memory utilization and provides status assessments.

    Example:
        calc = MemoryMetricsCalculator()
        result = calc.analyze(used_bytes=8_000_000_000, total_bytes=16_000_000_000)
        print(f"Usage: {result.usage_percent}%")
    """

    WARNING_THRESHOLD = 80.0
    CRITICAL_THRESHOLD = 95.0

    MAJFLT_WARNING_PS = 10.0
    MAJFLT_CRITICAL_PS = 100.0
    THRASHING_CPU_PERCENT = 30.0

    def analyze(
        self,
        used_bytes: int,
        total_bytes: int,
        swap_used_bytes: Optional[int] = None,
        swap_total_bytes: Optional[int] = None,
        available_bytes: Optional[int] = None,
        major_faults_ps: Optional[float] = None,
        swap_in_ps: Optional[float] = None,
        swap_out_ps: Optional[float] = None,
        oom_kills: Optional[int] = None,
        cpu_usage_percent: Optional[float] = None,
    ) -> MemoryMetrics:
        """
        Analyze memory usage.

        Utilization is derived from MemAvailable when supplied ('free' counts
        reclaimable page cache as used; 'available' is the metric that matters
        — RESEARCH_12). Saturation is evidenced by major page faults, swap
        activity, and OOM kills, not by utilization alone.

        Args:
            used_bytes: Used memory in bytes
            total_bytes: Total memory in bytes
            swap_used_bytes: Used swap space in bytes
            swap_total_bytes: Total swap space in bytes
            available_bytes: MemAvailable in bytes (preferred utilization basis)
            major_faults_ps: Major page faults per second
            swap_in_ps: Swap-in pages per second
            swap_out_ps: Swap-out pages per second
            oom_kills: OOM kills observed in the measurement window
            cpu_usage_percent: Concurrent CPU utilization, enabling the
                'idle but slow' thrashing-stall detector

        Returns:
            MemoryMetrics with analysis
        """
        available_based = available_bytes is not None
        if available_bytes is None:
            available_bytes = total_bytes - used_bytes

        if total_bytes > 0:
            if available_based:
                usage_percent = (1 - available_bytes / total_bytes) * 100
            else:
                usage_percent = (used_bytes / total_bytes) * 100
        else:
            usage_percent = 0

        swap_percent = None
        if swap_total_bytes and swap_total_bytes > 0:
            swap_percent = (swap_used_bytes / swap_total_bytes) * 100 if swap_used_bytes else 0

        saturation_signals = self._collect_saturation_signals(
            major_faults_ps, swap_in_ps, swap_out_ps, oom_kills
        )
        thrashing_stall = self._detect_thrashing_stall(
            major_faults_ps, cpu_usage_percent
        )

        status = self._determine_status(
            usage_percent, swap_percent, major_faults_ps, oom_kills, thrashing_stall
        )
        recommendations = self._generate_recommendations(
            usage_percent, swap_percent, major_faults_ps, oom_kills,
            thrashing_stall, swap_in_ps, swap_out_ps,
        )

        return MemoryMetrics(
            total_bytes=total_bytes,
            used_bytes=used_bytes,
            available_bytes=available_bytes,
            usage_percent=round(usage_percent, 2),
            swap_total_bytes=swap_total_bytes,
            swap_used_bytes=swap_used_bytes,
            swap_percent=round(swap_percent, 2) if swap_percent is not None else None,
            major_faults_ps=major_faults_ps,
            swap_in_ps=swap_in_ps,
            swap_out_ps=swap_out_ps,
            oom_kills=oom_kills,
            available_based_usage=available_based,
            thrashing_stall=thrashing_stall,
            saturation_signals=saturation_signals,
            status=status,
            recommendations=recommendations,
        )

    def calculate_usage_percent(
        self,
        used_bytes: int,
        total_bytes: int,
    ) -> float:
        """
        Calculate memory usage percentage.

        Args:
            used_bytes: Used memory in bytes
            total_bytes: Total memory in bytes

        Returns:
            Usage percentage
        """
        if total_bytes <= 0:
            return 0.0
        return round((used_bytes / total_bytes) * 100, 2)

    def bytes_to_human_readable(self, bytes_value: float) -> str:
        """
        Convert bytes to human-readable format.

        Args:
            bytes_value: Value in bytes

        Returns:
            Human-readable string (e.g., "8.5 GB")
        """
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if abs(bytes_value) < 1024:
                return f"{bytes_value:.2f} {unit}"
            bytes_value /= 1024
        return f"{bytes_value:.2f} PB"

    def _collect_saturation_signals(
        self,
        major_faults_ps: Optional[float],
        swap_in_ps: Optional[float],
        swap_out_ps: Optional[float],
        oom_kills: Optional[int],
    ) -> List[str]:
        """Collect memory saturation evidence (RESEARCH_12)."""
        signals = []
        if oom_kills:
            signals.append(f"OOM_KILLS: {oom_kills} kill(s) in window")
        if major_faults_ps is not None and major_faults_ps > self.MAJFLT_CRITICAL_PS:
            signals.append(
                f"MAJOR_FAULTS_CRITICAL: {major_faults_ps:.0f}/s > {self.MAJFLT_CRITICAL_PS:.0f}/s"
            )
        elif major_faults_ps is not None and major_faults_ps > self.MAJFLT_WARNING_PS:
            signals.append(
                f"MAJOR_FAULTS_ELEVATED: {major_faults_ps:.0f}/s > {self.MAJFLT_WARNING_PS:.0f}/s"
            )
        if (swap_in_ps or 0) > 0 and (swap_out_ps or 0) > 0:
            signals.append(
                f"SWAP_CHURN: simultaneous swap-in ({swap_in_ps:.0f}/s) and "
                f"swap-out ({swap_out_ps:.0f}/s)"
            )
        return signals

    def _detect_thrashing_stall(
        self,
        major_faults_ps: Optional[float],
        cpu_usage_percent: Optional[float],
    ) -> bool:
        """
        'Idle but slow' detector: low CPU + high major faults.

        The canonical case is a managed runtime (JVM full GC) walking a
        swapped-out old generation — multi-second stalls with idle CPU.
        """
        return (
            major_faults_ps is not None
            and cpu_usage_percent is not None
            and major_faults_ps > self.MAJFLT_CRITICAL_PS
            and cpu_usage_percent < self.THRASHING_CPU_PERCENT
        )

    def _determine_status(
        self,
        usage_percent: float,
        swap_percent: Optional[float],
        major_faults_ps: Optional[float] = None,
        oom_kills: Optional[int] = None,
        thrashing_stall: bool = False,
    ) -> str:
        """Determine memory status. Saturation evidence outranks utilization."""
        if oom_kills:
            return "critical"
        if thrashing_stall:
            return "critical"
        if major_faults_ps is not None and major_faults_ps > self.MAJFLT_CRITICAL_PS:
            return "critical"
        if usage_percent >= self.CRITICAL_THRESHOLD:
            return "critical"
        if major_faults_ps is not None and major_faults_ps > self.MAJFLT_WARNING_PS:
            return "warning"
        if usage_percent >= self.WARNING_THRESHOLD:
            return "warning"
        if swap_percent and swap_percent > 50:
            return "warning"
        return "healthy"

    def _generate_recommendations(
        self,
        usage_percent: float,
        swap_percent: Optional[float],
        major_faults_ps: Optional[float] = None,
        oom_kills: Optional[int] = None,
        thrashing_stall: bool = False,
        swap_in_ps: Optional[float] = None,
        swap_out_ps: Optional[float] = None,
    ) -> List[str]:
        """Generate memory recommendations."""
        recommendations = []

        if oom_kills:
            recommendations.append(
                f"Critical: {oom_kills} OOM kill(s) observed. The kernel is "
                "already terminating processes; add memory or reduce limits now."
            )

        if thrashing_stall:
            recommendations.append(
                "THRASHING_STALL: low CPU utilization with heavy major page "
                "faults ('idle but slow'). A managed runtime paging its heap "
                "(e.g. JVM full GC over a swapped old generation) stalls for "
                "seconds while CPU stays idle. Disable swap for latency-"
                "sensitive managed runtimes; note swappiness=0 does NOT "
                "disable swap."
            )
        elif major_faults_ps is not None and major_faults_ps > self.MAJFLT_CRITICAL_PS:
            recommendations.append(
                f"Critical: major page faults at {major_faults_ps:.0f}/s — the "
                "working set does not fit in RAM (true memory saturation)."
            )
        elif major_faults_ps is not None and major_faults_ps > self.MAJFLT_WARNING_PS:
            recommendations.append(
                f"Major page faults at {major_faults_ps:.0f}/s indicate early "
                "memory pressure; watch for growth."
            )

        if (swap_in_ps or 0) > 0 and (swap_out_ps or 0) > 0:
            recommendations.append(
                "Simultaneous swap-in and swap-out indicates active swap churn "
                "(thrashing precursor), not just cold pages parked in swap."
            )

        if usage_percent >= self.CRITICAL_THRESHOLD:
            recommendations.append(
                "Critical: Memory usage is very high. Consider adding more RAM "
                "or reducing application memory footprint."
            )
        elif usage_percent >= self.WARNING_THRESHOLD:
            recommendations.append(
                f"Memory usage is elevated ({usage_percent:.1f}%). "
                "Monitor for potential memory pressure."
            )

        if swap_percent and swap_percent > 50:
            recommendations.append(
                f"Swap usage is high ({swap_percent:.1f}%). "
                "System may be experiencing memory pressure."
            )

        if swap_percent and swap_percent > 80:
            recommendations.append(
                "Consider increasing physical memory to reduce swap usage."
            )

        return recommendations
