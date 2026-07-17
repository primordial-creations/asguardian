"""
Connection Pool Analyzer

Analyzes database connection pool performance with queue-wait vs
service-time separation (RESEARCH_14) and Little's-law sizing (RESEARCH_12).
"""

import math
from typing import List, Optional

from Asgard.Verdandi.Database.models.database_models import ConnectionPoolMetrics


class ConnectionAnalyzer:
    """
    Analyzer for database connection pool metrics.

    Calculates utilization, wait times, and provides recommendations.

    Example:
        analyzer = ConnectionAnalyzer()
        metrics = analyzer.analyze(
            pool_size=20,
            active=15,
            waiting=3,
            wait_times=[10, 20, 15, 25]
        )
        print(f"Utilization: {metrics.utilization_percent}%")
    """

    def analyze(
        self,
        pool_size: int,
        active_connections: int,
        idle_connections: Optional[int] = None,
        waiting_requests: int = 0,
        wait_times_ms: Optional[List[float]] = None,
        connection_errors: int = 0,
        timeout_count: int = 0,
        acquisition_wait_samples: Optional[List[float]] = None,
        qps: Optional[float] = None,
        avg_query_ms: Optional[float] = None,
        service_p95_ms: Optional[float] = None,
    ) -> ConnectionPoolMetrics:
        """
        Analyze connection pool metrics.

        Queue-wait vs service-time separation (RESEARCH_14): in-process query
        timers measure service time only — pass acquisition-wait samples
        separately or the DB looks healthy while requests queue for a
        connection. With qps and avg_query_ms, Little's law (L = lambda x W)
        sizes the pool.

        Args:
            pool_size: Total pool size
            active_connections: Currently active connections
            idle_connections: Idle connections (calculated if not provided)
            waiting_requests: Requests waiting for connection
            wait_times_ms: List of wait times for connections (legacy avg/max)
            connection_errors: Count of connection errors
            timeout_count: Count of connection timeouts
            acquisition_wait_samples: Per-request connection acquisition waits
                in ms (the `wait_for_connection` child-span pattern)
            qps: Query throughput (lambda) for Little's-law sizing
            avg_query_ms: Average query service time (W) for Little's-law sizing
            service_p95_ms: p95 query service time, enabling queue_share

        Returns:
            ConnectionPoolMetrics with analysis
        """
        if idle_connections is None:
            idle_connections = max(0, pool_size - active_connections)

        utilization = (active_connections / pool_size) * 100 if pool_size > 0 else 0

        avg_wait = 0.0
        max_wait = 0.0
        if wait_times_ms:
            avg_wait = sum(wait_times_ms) / len(wait_times_ms)
            max_wait = max(wait_times_ms)

        wait_p50 = wait_p95 = wait_p99 = None
        queue_share = None
        if acquisition_wait_samples:
            s = sorted(acquisition_wait_samples)
            wait_p50 = self._percentile(s, 50)
            wait_p95 = self._percentile(s, 95)
            wait_p99 = self._percentile(s, 99)
            if not wait_times_ms:
                avg_wait = sum(s) / len(s)
                max_wait = s[-1]
            if service_p95_ms is not None and (wait_p95 + service_p95_ms) > 0:
                queue_share = wait_p95 / (wait_p95 + service_p95_ms)

        required = headroom = None
        recommended = None
        if qps is not None and avg_query_ms is not None:
            required = qps * (avg_query_ms / 1000.0)
            headroom = pool_size - required
            recommended = math.ceil(required / 0.7) if required > 0 else pool_size

        leak_suspected = timeout_count > 0 and utilization < 70.0

        return ConnectionPoolMetrics(
            pool_size=pool_size,
            active_connections=active_connections,
            idle_connections=idle_connections,
            waiting_requests=waiting_requests,
            utilization_percent=round(utilization, 2),
            average_wait_time_ms=round(avg_wait, 2),
            max_wait_time_ms=round(max_wait, 2),
            connection_errors=connection_errors,
            timeout_count=timeout_count,
            wait_p50_ms=round(wait_p50, 3) if wait_p50 is not None else None,
            wait_p95_ms=round(wait_p95, 3) if wait_p95 is not None else None,
            wait_p99_ms=round(wait_p99, 3) if wait_p99 is not None else None,
            queue_share=round(queue_share, 4) if queue_share is not None else None,
            required_connections=round(required, 2) if required is not None else None,
            headroom_connections=round(headroom, 2) if headroom is not None else None,
            recommended_pool_size=recommended,
            leak_suspected=leak_suspected,
        )

    @staticmethod
    def _percentile(sorted_values: List[float], pct: float) -> float:
        if not sorted_values:
            return 0.0
        n = len(sorted_values)
        if n == 1:
            return float(sorted_values[0])
        rank = (pct / 100) * (n - 1)
        lower = int(rank)
        upper = min(lower + 1, n - 1)
        frac = rank - lower
        return sorted_values[lower] + frac * (sorted_values[upper] - sorted_values[lower])

    def calculate_optimal_pool_size(
        self,
        concurrent_requests: int,
        avg_query_time_ms: float,
        target_wait_time_ms: float = 50.0,
    ) -> int:
        """
        Calculate optimal pool size based on workload.

        Uses Little's Law: L = lambda * W
        Where L = connections needed, lambda = arrival rate, W = service time

        Args:
            concurrent_requests: Average concurrent requests
            avg_query_time_ms: Average query execution time
            target_wait_time_ms: Target maximum wait time

        Returns:
            Recommended pool size
        """
        avg_query_seconds = avg_query_time_ms / 1000

        base_connections = concurrent_requests * avg_query_seconds

        buffer_factor = 1.5
        optimal = int(base_connections * buffer_factor)

        return max(optimal, concurrent_requests, 5)

    def get_recommendations(
        self,
        metrics: ConnectionPoolMetrics,
    ) -> List[str]:
        """
        Generate recommendations based on connection metrics.

        Args:
            metrics: Connection pool metrics

        Returns:
            List of recommendations
        """
        recommendations = []

        if metrics.utilization_percent > 90:
            recommendations.append(
                f"Pool utilization is high ({metrics.utilization_percent:.1f}%). "
                "Consider increasing pool size."
            )

        if metrics.utilization_percent < 20 and metrics.pool_size > 10:
            recommendations.append(
                f"Pool utilization is low ({metrics.utilization_percent:.1f}%). "
                "Consider reducing pool size to free resources."
            )

        if metrics.waiting_requests > 0:
            recommendations.append(
                f"{metrics.waiting_requests} requests waiting for connections. "
                "Pool size may be insufficient for current load."
            )

        if metrics.average_wait_time_ms > 100:
            recommendations.append(
                f"Average connection wait time is {metrics.average_wait_time_ms:.1f}ms. "
                "Consider increasing pool size or optimizing queries."
            )

        if metrics.connection_errors > 0:
            recommendations.append(
                f"{metrics.connection_errors} connection errors detected. "
                "Check database server health and network connectivity."
            )

        if metrics.timeout_count > 0:
            recommendations.append(
                f"{metrics.timeout_count} connection timeouts detected. "
                "Review timeout settings and connection pool configuration."
            )

        if metrics.leak_suspected:
            recommendations.append(
                f"Timeouts at only {metrics.utilization_percent:.0f}% utilization "
                "suggest a connection leak: connections are held (not returned) "
                "rather than busy. Audit checkout/return paths and transaction "
                "scoping."
            )

        if metrics.queue_share is not None and metrics.queue_share > 0.5:
            recommendations.append(
                f"{metrics.queue_share:.0%} of tail latency is connection-"
                "acquisition wait, not query service time — the pool, not the "
                "database, is the bottleneck."
            )

        if (
            metrics.required_connections is not None
            and metrics.headroom_connections is not None
            and metrics.headroom_connections < 0
        ):
            recommendations.append(
                f"Little's law requires ~{metrics.required_connections:.1f} "
                f"connections but the pool has {metrics.pool_size}; queueing is "
                f"guaranteed. Recommended size: {metrics.recommended_pool_size} "
                "(70% target utilization)."
            )

        return recommendations
