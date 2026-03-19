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

    def analyze(
        self,
        used_bytes: int,
        total_bytes: int,
        swap_used_bytes: Optional[int] = None,
        swap_total_bytes: Optional[int] = None,
    ) -> MemoryMetrics:
        """
        Analyze memory usage.

        Args:
            used_bytes: Used memory in bytes
            total_bytes: Total memory in bytes
            swap_used_bytes: Used swap space in bytes
            swap_total_bytes: Total swap space in bytes

        Returns:
            MemoryMetrics with analysis
        """
        available_bytes = total_bytes - used_bytes
        usage_percent = (used_bytes / total_bytes) * 100 if total_bytes > 0 else 0

        swap_percent = None
        if swap_total_bytes and swap_total_bytes > 0:
            swap_percent = (swap_used_bytes / swap_total_bytes) * 100 if swap_used_bytes else 0

        status = self._determine_status(usage_percent, swap_percent)
        recommendations = self._generate_recommendations(usage_percent, swap_percent)

        return MemoryMetrics(
            total_bytes=total_bytes,
            used_bytes=used_bytes,
            available_bytes=available_bytes,
            usage_percent=round(usage_percent, 2),
            swap_total_bytes=swap_total_bytes,
            swap_used_bytes=swap_used_bytes,
            swap_percent=round(swap_percent, 2) if swap_percent is not None else None,
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

    def _determine_status(
        self,
        usage_percent: float,
        swap_percent: Optional[float],
    ) -> str:
        """Determine memory status."""
        if usage_percent >= self.CRITICAL_THRESHOLD:
            return "critical"
        if usage_percent >= self.WARNING_THRESHOLD:
            return "warning"
        if swap_percent and swap_percent > 50:
            return "warning"
        return "healthy"

    def _generate_recommendations(
        self,
        usage_percent: float,
        swap_percent: Optional[float],
    ) -> List[str]:
        """Generate memory recommendations."""
        recommendations = []

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
