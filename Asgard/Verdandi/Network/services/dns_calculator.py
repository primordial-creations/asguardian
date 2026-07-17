"""
DNS Metrics Calculator

Calculates DNS resolution performance metrics.
"""

from typing import Dict, List, Optional

from Asgard.Verdandi.Analysis import PercentileCalculator
from Asgard.Verdandi.Network.models.network_models import (
    DnsMetrics,
    DnsQuotaResult,
    NetworkOutcome,
)

#: AWS's silent link-local DNS resolver quota, in queries/sec (RESEARCH_11).
LINKLOCAL_DNS_QUOTA_PPS = 1024

#: Expected resolution-time bands, in ms, by environment.
_ENVIRONMENT_BANDS = {
    "in_vpc": (0.0, 2.0),
    "public": (0.0, 100.0),
}


class DnsCalculator:
    """
    Calculator for DNS resolution metrics.

    Analyzes DNS query performance and cache effectiveness.

    Example:
        calc = DnsCalculator()
        result = calc.analyze(
            resolution_times=[5, 10, 8, 150, 7],
            cache_hits=45,
            total_queries=50
        )
        print(f"Cache Hit Rate: {result.cache_hit_rate}%")
    """

    def __init__(self):
        """Initialize the calculator."""
        self._percentile_calc = PercentileCalculator()

    def analyze(
        self,
        resolution_times_ms: List[float],
        cache_hits: int = 0,
        total_queries: Optional[int] = None,
        failures: int = 0,
        by_record_type: Optional[Dict[str, List[float]]] = None,
    ) -> DnsMetrics:
        """
        Analyze DNS metrics.

        Args:
            resolution_times_ms: List of DNS resolution times in ms
            cache_hits: Number of cache hits
            total_queries: Total queries (defaults to len(resolution_times_ms))
            failures: Number of failed queries
            by_record_type: Breakdown of times by record type

        Returns:
            DnsMetrics with analysis
        """
        if not resolution_times_ms:
            raise ValueError("Cannot analyze empty resolution times list")

        total = total_queries or len(resolution_times_ms)
        percentiles = self._percentile_calc.calculate(resolution_times_ms)

        cache_hit_rate = (cache_hits / total) * 100 if total > 0 else 0
        failure_rate = (failures / total) * 100 if total > 0 else 0

        type_breakdown = {}
        if by_record_type:
            for record_type, times in by_record_type.items():
                if times:
                    type_percentiles = self._percentile_calc.calculate(times)
                    type_breakdown[record_type] = {
                        "count": len(times),
                        "avg_ms": round(type_percentiles.mean, 2),
                        "p95_ms": round(type_percentiles.p95, 2),
                    }

        status = self._determine_status(percentiles.p95, failure_rate)
        recommendations = self._generate_recommendations(
            percentiles.p95, cache_hit_rate, failure_rate
        )

        return DnsMetrics(
            query_count=total,
            avg_resolution_ms=round(percentiles.mean, 2),
            p95_resolution_ms=round(percentiles.p95, 2),
            max_resolution_ms=round(percentiles.max_value, 2),
            cache_hit_rate=round(cache_hit_rate, 2),
            failure_rate=round(failure_rate, 2),
            by_record_type=type_breakdown,
            status=status,
            recommendations=recommendations,
        )

    def _determine_status(
        self,
        p95: float,
        failure_rate: float,
    ) -> str:
        """Determine DNS status."""
        if failure_rate > 5:
            return "critical"
        if p95 > 100:
            return "slow"
        if p95 > 50:
            return "acceptable"
        return "good"

    def _generate_recommendations(
        self,
        p95: float,
        cache_hit_rate: float,
        failure_rate: float,
    ) -> List[str]:
        """Generate DNS recommendations."""
        recommendations = []

        if p95 > 100:
            recommendations.append(
                f"DNS resolution is slow (P95: {p95:.1f}ms). "
                "Consider using faster DNS servers or local caching."
            )

        if cache_hit_rate < 50:
            recommendations.append(
                f"DNS cache hit rate is low ({cache_hit_rate:.1f}%). "
                "Consider increasing cache TTL or size."
            )

        if failure_rate > 1:
            recommendations.append(
                f"DNS failure rate ({failure_rate:.1f}%) is elevated. "
                "Check DNS server health and network connectivity."
            )

        return recommendations

    def analyze_quota(
        self,
        queries_ps: Optional[float],
        nxdomain_count: int = 0,
        servfail_count: int = 0,
        timeout_count: int = 0,
        total_queries: Optional[int] = None,
        environment: str = "public",
    ) -> DnsQuotaResult:
        """
        USE-style quota/error-rate analysis + environment expectation bands.

        Args:
            queries_ps: Observed DNS query rate (queries/sec)
            nxdomain_count: NXDOMAIN response count
            servfail_count: SERVFAIL response count
            timeout_count: Resolution timeout count
            total_queries: Total queries observed (for rate denominators)
            environment: "in_vpc" (< 2 ms expected) or "public" (< 100 ms)

        Returns:
            DnsQuotaResult; INSUFFICIENT_DATA when queries_ps is None.
        """
        if queries_ps is None:
            return DnsQuotaResult(
                outcome=NetworkOutcome.INSUFFICIENT_DATA,
                environment=environment,
            )

        utilization = round(queries_ps / LINKLOCAL_DNS_QUOTA_PPS * 100, 2)
        quota_exceeded = queries_ps > LINKLOCAL_DNS_QUOTA_PPS

        total = total_queries if total_queries else None
        nxdomain_rate = (
            round(nxdomain_count / total * 100, 3) if total else 0.0
        )
        servfail_rate = (
            round(servfail_count / total * 100, 3) if total else 0.0
        )
        timeout_rate = (
            round(timeout_count / total * 100, 3) if total else 0.0
        )

        low, high = _ENVIRONMENT_BANDS.get(environment, _ENVIRONMENT_BANDS["public"])

        recommendations: List[str] = []
        status = "ok"
        if quota_exceeded:
            status = "critical"
            recommendations.append(
                f"DNS query rate ({queries_ps:.0f} qps) exceeds the "
                f"{LINKLOCAL_DNS_QUOTA_PPS} PPS link-local quota: deploy a "
                "node-local DNS cache to absorb repeated lookups."
            )
        elif servfail_rate > 1 or timeout_rate > 1:
            status = "degraded"
            recommendations.append(
                "SERVFAIL/timeout rate elevated. Check upstream resolver "
                "health."
            )

        return DnsQuotaResult(
            outcome=NetworkOutcome.OK,
            environment=environment,
            queries_ps=queries_ps,
            linklocal_quota_utilization_percent=utilization,
            quota_exceeded=quota_exceeded,
            nxdomain_rate_percent=nxdomain_rate,
            servfail_rate_percent=servfail_rate,
            timeout_rate_percent=timeout_rate,
            expected_band_low_ms=low,
            expected_band_high_ms=high,
            status=status,
            recommendations=recommendations,
        )
