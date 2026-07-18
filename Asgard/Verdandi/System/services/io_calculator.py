"""
I/O Metrics Calculator

Calculates I/O throughput and performance metrics.
"""

from typing import List, Optional

from Asgard.Verdandi.System.models.system_models import IoMetrics


class IoMetricsCalculator:
    """
    Calculator for I/O performance metrics.

    Analyzes disk I/O throughput, IOPS, and latency.

    Example:
        calc = IoMetricsCalculator()
        result = calc.analyze(
            read_bytes=1_000_000_000,
            write_bytes=500_000_000,
            duration_seconds=60
        )
        print(f"Total IOPS: {result.total_iops}")
    """

    # Device-class semantics (RESEARCH_12): %util and svctm are meaningless on
    # parallel devices (SSD/NVMe); saturation there is await + aqu-sz ballooning.
    PARALLEL_DEVICE_TYPES = ("ssd", "nvme")
    AWAIT_PROBLEM_MS = 20.0
    AWAIT_SEVERE_MS = 50.0
    HDD_QUEUE_HEAVY = 4.0
    AQU_SZ_BALLOON_FACTOR = 3.0

    def analyze(
        self,
        read_bytes: int,
        write_bytes: int,
        read_ops: int,
        write_ops: int,
        duration_seconds: float,
        avg_read_latency_ms: Optional[float] = None,
        avg_write_latency_ms: Optional[float] = None,
        queue_depth: Optional[float] = None,
        utilization_percent: Optional[float] = None,
        device_type: Optional[str] = None,
        aqu_sz: Optional[float] = None,
        r_await_ms: Optional[float] = None,
        w_await_ms: Optional[float] = None,
        aqu_sz_baseline: Optional[float] = None,
        svctm_ms: Optional[float] = None,
    ) -> IoMetrics:
        """
        Analyze I/O metrics with device-class-correct iostat semantics.

        For SSD/NVMe, %util means "the device had at least one request in
        flight" — a parallel device at %util=100 with sub-millisecond awaits
        is healthy. Saturation on parallel devices = aqu-sz ballooning while
        throughput plateaus, and r_await/w_await (> 20 ms problem, > 50 ms
        severe). For HDD, %util and queue depth remain valid. `svctm` is
        deprecated and ignored if supplied.

        Args:
            read_bytes: Total bytes read
            write_bytes: Total bytes written
            read_ops: Total read operations
            write_ops: Total write operations
            duration_seconds: Duration of measurement
            avg_read_latency_ms: Average read latency
            avg_write_latency_ms: Average write latency
            queue_depth: Average queue depth
            utilization_percent: Disk utilization percentage (%util)
            device_type: Device class ("hdd", "ssd", or "nvme"); when omitted,
                legacy %util-based rating is retained
            aqu_sz: iostat average queue size
            r_await_ms: Average read wait including queueing (iostat r_await)
            w_await_ms: Average write wait including queueing (iostat w_await)
            aqu_sz_baseline: Healthy-period aqu-sz baseline for balloon detection
            svctm_ms: Deprecated; accepted and discarded with a note

        Returns:
            IoMetrics with analysis
        """
        read_bytes_per_sec = read_bytes / duration_seconds if duration_seconds > 0 else 0
        write_bytes_per_sec = write_bytes / duration_seconds if duration_seconds > 0 else 0
        read_ops_per_sec = read_ops / duration_seconds if duration_seconds > 0 else 0
        write_ops_per_sec = write_ops / duration_seconds if duration_seconds > 0 else 0

        total_iops = read_ops_per_sec + write_ops_per_sec
        total_throughput_mbps = (read_bytes_per_sec + write_bytes_per_sec) / (1024 * 1024)

        device_class = device_type.lower() if device_type else None
        is_parallel = device_class in self.PARALLEL_DEVICE_TYPES

        if is_parallel:
            status = self._determine_status_parallel(
                r_await_ms, w_await_ms, avg_read_latency_ms, avg_write_latency_ms,
                aqu_sz, aqu_sz_baseline,
            )
        else:
            status = self._determine_status(
                total_iops, avg_read_latency_ms, avg_write_latency_ms,
                utilization_percent,
                r_await_ms=r_await_ms, w_await_ms=w_await_ms,
            )

        recommendations = self._generate_recommendations(
            total_iops, avg_read_latency_ms, avg_write_latency_ms,
            utilization_percent, queue_depth,
            device_class=device_class, is_parallel=is_parallel,
            aqu_sz=aqu_sz, aqu_sz_baseline=aqu_sz_baseline,
            r_await_ms=r_await_ms, w_await_ms=w_await_ms,
            svctm_supplied=svctm_ms is not None,
        )

        return IoMetrics(
            read_bytes_per_sec=round(read_bytes_per_sec, 2),
            write_bytes_per_sec=round(write_bytes_per_sec, 2),
            read_ops_per_sec=round(read_ops_per_sec, 2),
            write_ops_per_sec=round(write_ops_per_sec, 2),
            total_iops=round(total_iops, 2),
            total_throughput_mbps=round(total_throughput_mbps, 2),
            avg_read_latency_ms=avg_read_latency_ms,
            avg_write_latency_ms=avg_write_latency_ms,
            queue_depth=queue_depth,
            utilization_percent=utilization_percent,
            device_type=device_class,
            aqu_sz=aqu_sz,
            r_await_ms=r_await_ms,
            w_await_ms=w_await_ms,
            utilization_misleading_for_parallel_devices=is_parallel,
            status=status,
            recommendations=recommendations,
        )

    def calculate_iops(
        self,
        operations: int,
        duration_seconds: float,
    ) -> float:
        """
        Calculate operations per second.

        Args:
            operations: Total operations
            duration_seconds: Duration in seconds

        Returns:
            Operations per second
        """
        if duration_seconds <= 0:
            return 0.0
        return round(operations / duration_seconds, 2)

    def calculate_throughput_mbps(
        self,
        bytes_transferred: int,
        duration_seconds: float,
    ) -> float:
        """
        Calculate throughput in MB/s.

        Args:
            bytes_transferred: Total bytes transferred
            duration_seconds: Duration in seconds

        Returns:
            Throughput in MB/s
        """
        if duration_seconds <= 0:
            return 0.0
        return round((bytes_transferred / (1024 * 1024)) / duration_seconds, 2)

    def _determine_status(
        self,
        iops: float,
        read_latency: Optional[float],
        write_latency: Optional[float],
        utilization: Optional[float],
        r_await_ms: Optional[float] = None,
        w_await_ms: Optional[float] = None,
    ) -> str:
        """Determine I/O status for serial devices (HDD) / legacy path."""
        if utilization and utilization >= 95:
            return "critical"
        if utilization and utilization >= 80:
            return "warning"

        worst_await = max(r_await_ms or 0.0, w_await_ms or 0.0)
        if worst_await > self.AWAIT_SEVERE_MS:
            return "critical"
        if worst_await > self.AWAIT_PROBLEM_MS:
            return "warning"

        if read_latency and read_latency > 50:
            return "warning"
        if write_latency and write_latency > 50:
            return "warning"

        return "healthy"

    def _determine_status_parallel(
        self,
        r_await_ms: Optional[float],
        w_await_ms: Optional[float],
        read_latency: Optional[float],
        write_latency: Optional[float],
        aqu_sz: Optional[float],
        aqu_sz_baseline: Optional[float],
    ) -> str:
        """
        Determine I/O status for parallel devices (SSD/NVMe).

        %util is deliberately excluded: an NVMe at %util=100 with 0.3 ms
        awaits is healthy. Primary metric is await; corroborating signal is
        aqu-sz ballooning versus a healthy baseline.
        """
        worst_await = max(
            r_await_ms if r_await_ms is not None else 0.0,
            w_await_ms if w_await_ms is not None else 0.0,
            read_latency if read_latency is not None else 0.0,
            write_latency if write_latency is not None else 0.0,
        )

        if worst_await > self.AWAIT_SEVERE_MS:
            return "critical"

        ballooning = (
            aqu_sz is not None
            and aqu_sz_baseline is not None
            and aqu_sz_baseline > 0
            and aqu_sz > self.AQU_SZ_BALLOON_FACTOR * aqu_sz_baseline
        )
        if worst_await > self.AWAIT_PROBLEM_MS or ballooning:
            return "warning"

        return "healthy"

    def _generate_recommendations(
        self,
        iops: float,
        read_latency: Optional[float],
        write_latency: Optional[float],
        utilization: Optional[float],
        queue_depth: Optional[float],
        device_class: Optional[str] = None,
        is_parallel: bool = False,
        aqu_sz: Optional[float] = None,
        aqu_sz_baseline: Optional[float] = None,
        r_await_ms: Optional[float] = None,
        w_await_ms: Optional[float] = None,
        svctm_supplied: bool = False,
    ) -> List[str]:
        """Generate I/O recommendations."""
        recommendations = []

        if svctm_supplied:
            recommendations.append(
                "svctm was supplied but is deprecated and meaningless on modern "
                "kernels/devices; it has been ignored."
            )

        if is_parallel:
            if utilization and utilization >= 80:
                recommendations.append(
                    f"%util is {utilization:.0f}% but this is a {device_class.upper()} "
                    "(parallel device): %util only means the device had >= 1 request "
                    "in flight and is NOT a saturation signal. Health is rated on "
                    "r_await/w_await and aqu-sz instead."
                )
            worst_await = max(r_await_ms or 0.0, w_await_ms or 0.0)
            if worst_await > self.AWAIT_SEVERE_MS:
                recommendations.append(
                    f"Severe: device await is {worst_await:.1f}ms (> "
                    f"{self.AWAIT_SEVERE_MS:.0f}ms) on a {device_class.upper()} — "
                    "requests are queueing well beyond device service time."
                )
            elif worst_await > self.AWAIT_PROBLEM_MS:
                recommendations.append(
                    f"Device await is {worst_await:.1f}ms (> "
                    f"{self.AWAIT_PROBLEM_MS:.0f}ms) — investigate workload or "
                    "device health."
                )
            if (
                aqu_sz is not None
                and aqu_sz_baseline is not None
                and aqu_sz_baseline > 0
                and aqu_sz > self.AQU_SZ_BALLOON_FACTOR * aqu_sz_baseline
            ):
                recommendations.append(
                    f"aqu-sz ballooned to {aqu_sz:.1f} vs baseline "
                    f"{aqu_sz_baseline:.1f} — if throughput has plateaued, the "
                    "device is saturated."
                )
        else:
            if utilization and utilization >= 95:
                recommendations.append(
                    "Critical: Disk utilization is very high. "
                    "Consider adding storage capacity or faster disks."
                )
            elif utilization and utilization >= 80:
                recommendations.append(
                    f"Disk utilization is elevated ({utilization:.1f}%). "
                    "Monitor for potential bottlenecks."
                )
            if device_class == "hdd" and queue_depth and queue_depth > self.HDD_QUEUE_HEAVY:
                recommendations.append(
                    f"HDD queue depth {queue_depth:.1f} > {self.HDD_QUEUE_HEAVY:.0f}: "
                    "heavy load for a serial device."
                )

        if read_latency and read_latency > 20:
            recommendations.append(
                f"Read latency is high ({read_latency:.1f}ms). "
                "Consider SSD storage or caching."
            )

        if write_latency and write_latency > 20:
            recommendations.append(
                f"Write latency is high ({write_latency:.1f}ms). "
                "Consider write-back caching or faster storage."
            )

        if queue_depth and queue_depth > 32:
            recommendations.append(
                f"High I/O queue depth ({queue_depth:.1f}). "
                "Storage may be a bottleneck."
            )

        return recommendations
