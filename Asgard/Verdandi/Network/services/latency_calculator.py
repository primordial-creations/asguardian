"""
Latency Calculator

Calculates network latency metrics.
"""

from typing import Dict, List, Optional

from Asgard.Verdandi.Analysis import PercentileCalculator
from Asgard.Verdandi.Network.models.network_models import (
    LatencyMetrics,
    ProfileLatencyResult,
    TopologyProfile,
    TopologyRating,
)

#: Named topology baselines (RESEARCH_11): (rtt_low_ms, rtt_high_ms,
#: degraded_above_ms, packet_loss_baseline_percent).
_TOPOLOGY_BASELINES: Dict[TopologyProfile, Dict[str, float]] = {
    TopologyProfile.INTRA_AZ: {
        "low": 0.1,
        "high": 0.6,
        "degraded_above": 1.0,
        "packet_loss_baseline": 0.01,
    },
    TopologyProfile.INTER_AZ: {
        "low": 1.0,
        "high": 2.0,
        # Sync-replication risk starts at 3 ms; the profile is rated POOR
        # only past the 5 ms end of RESEARCH_11's "3-5 ms" degraded band.
        "degraded_above": 5.0,
        "sync_replication_warn_ms": 3.0,
        "packet_loss_baseline": 0.01,
    },
    TopologyProfile.SAME_REGION_PUBLIC: {
        "low": 2.0,
        "high": 10.0,
        "degraded_above": 20.0,
        "packet_loss_baseline": 0.01,
    },
    TopologyProfile.INTERNET_EDGE: {
        "low": 20.0,
        "high": 150.0,
        "degraded_above": 195.0,  # 1.3x declared/expected high, RESEARCH_11
        "packet_loss_baseline": 1.0,
    },
}


class LatencyCalculator:
    """
    Calculator for network latency metrics.

    Analyzes latency samples and calculates percentiles, jitter, etc.

    Example:
        calc = LatencyCalculator()
        result = calc.analyze([10, 15, 12, 20, 18, 25, 11])
        print(f"P99: {result.p99_ms}ms")
    """

    GOOD_THRESHOLD = 50
    ACCEPTABLE_THRESHOLD = 100

    def __init__(self):
        """Initialize the calculator."""
        self._percentile_calc = PercentileCalculator()

    def analyze(
        self,
        latencies_ms: List[float],
        packet_loss_percent: Optional[float] = None,
    ) -> LatencyMetrics:
        """
        Analyze latency samples.

        Args:
            latencies_ms: List of latency samples in milliseconds
            packet_loss_percent: Optional packet loss percentage

        Returns:
            LatencyMetrics with analysis
        """
        if not latencies_ms:
            raise ValueError("Cannot analyze empty latency list")

        percentiles = self._percentile_calc.calculate(latencies_ms)
        jitter = self._calculate_jitter(latencies_ms)

        status = self._determine_status(percentiles.p95, packet_loss_percent)
        recommendations = self._generate_recommendations(
            percentiles.p95, jitter, packet_loss_percent
        )

        return LatencyMetrics(
            sample_count=len(latencies_ms),
            min_ms=round(percentiles.min_value, 2),
            max_ms=round(percentiles.max_value, 2),
            mean_ms=round(percentiles.mean, 2),
            median_ms=round(percentiles.median, 2),
            p90_ms=round(percentiles.p90, 2),
            p95_ms=round(percentiles.p95, 2),
            p99_ms=round(percentiles.p99, 2),
            std_dev_ms=round(percentiles.std_dev, 2),
            jitter_ms=round(jitter, 2),
            packet_loss_percent=packet_loss_percent,
            status=status,
            recommendations=recommendations,
        )

    def _calculate_jitter(self, latencies: List[float]) -> float:
        """Calculate jitter (variation between consecutive samples)."""
        if len(latencies) < 2:
            return 0.0

        variations = []
        for i in range(1, len(latencies)):
            variations.append(abs(latencies[i] - latencies[i - 1]))

        return sum(variations) / len(variations)

    def _determine_status(
        self,
        p95: float,
        packet_loss: Optional[float],
    ) -> str:
        """Determine latency status."""
        if packet_loss and packet_loss > 5:
            return "poor"
        if p95 <= self.GOOD_THRESHOLD:
            return "good"
        if p95 <= self.ACCEPTABLE_THRESHOLD:
            return "acceptable"
        return "poor"

    def _generate_recommendations(
        self,
        p95: float,
        jitter: float,
        packet_loss: Optional[float],
    ) -> List[str]:
        """Generate latency recommendations."""
        recommendations = []

        if p95 > self.ACCEPTABLE_THRESHOLD:
            recommendations.append(
                f"P95 latency ({p95:.1f}ms) is high. "
                "Consider using a CDN or optimizing network path."
            )

        if jitter > 20:
            recommendations.append(
                f"High jitter ({jitter:.1f}ms) detected. "
                "Network may be congested or experiencing issues."
            )

        if packet_loss and packet_loss > 1:
            recommendations.append(
                f"Packet loss ({packet_loss:.1f}%) detected. "
                "Check network infrastructure and connections."
            )

        return recommendations

    def analyze_against_profile(
        self,
        latencies_ms: List[float],
        profile: TopologyProfile,
        packet_loss_percent: Optional[float] = None,
        cross_region_declared_ms: Optional[float] = None,
    ) -> ProfileLatencyResult:
        """
        Rate observed latency against a named topology baseline instead of
        the absolute EXCELLENT/GOOD bands (RESEARCH_11). Named profiles:
        INTRA_AZ, INTER_AZ, SAME_REGION_PUBLIC, CROSS_REGION, INTERNET_EDGE.
        LEGACY_DEFAULT reuses the original absolute bands from `analyze()`.

        Args:
            latencies_ms: RTT samples in milliseconds
            profile: Named topology baseline to rate against
            packet_loss_percent: Optional observed packet loss
            cross_region_declared_ms: Required for CROSS_REGION: the
                distance-based expected RTT the caller declares up front

        Returns:
            ProfileLatencyResult; INSUFFICIENT_DATA when latencies_ms is
            empty or CROSS_REGION is used without a declared baseline.
        """
        if not latencies_ms:
            return ProfileLatencyResult(
                profile=profile,
                rating=TopologyRating.INSUFFICIENT_DATA,
                warnings=["No latency samples provided."],
            )

        if profile == TopologyProfile.CROSS_REGION:
            if not cross_region_declared_ms or cross_region_declared_ms <= 0:
                return ProfileLatencyResult(
                    profile=profile,
                    rating=TopologyRating.INSUFFICIENT_DATA,
                    warnings=[
                        "CROSS_REGION requires cross_region_declared_ms "
                        "(a distance-based expected RTT)."
                    ],
                )
            baseline = {
                "low": cross_region_declared_ms,
                "high": cross_region_declared_ms,
                "degraded_above": cross_region_declared_ms * 1.3,
                "packet_loss_baseline": 0.01,
            }
        elif profile == TopologyProfile.LEGACY_DEFAULT:
            baseline = {
                "low": 0.0,
                "high": self.GOOD_THRESHOLD,
                "degraded_above": self.ACCEPTABLE_THRESHOLD,
                "packet_loss_baseline": 5.0,
            }
        else:
            baseline = _TOPOLOGY_BASELINES[profile]

        percentiles = self._percentile_calc.calculate(latencies_ms)
        p95 = percentiles.p95

        warnings: List[str] = []
        if p95 <= baseline["high"]:
            rating = TopologyRating.GOOD
        elif p95 <= baseline["degraded_above"]:
            rating = TopologyRating.DEGRADED
        else:
            rating = TopologyRating.POOR

        if profile == TopologyProfile.INTER_AZ and p95 > baseline.get(
            "sync_replication_warn_ms", baseline["degraded_above"]
        ):
            warnings.append(
                "Inter-AZ RTT above ~3-5 ms risks synchronous-replication "
                "timeouts; review replication mode or move to same-AZ."
            )

        recommendations: List[str] = []
        if rating == TopologyRating.POOR:
            recommendations.append(
                f"P95 latency ({p95:.2f} ms) exceeds the {profile.value} "
                "degraded threshold. Investigate routing/placement."
            )

        if packet_loss_percent is not None and packet_loss_percent > baseline[
            "packet_loss_baseline"
        ]:
            warnings.append(
                f"Packet loss ({packet_loss_percent:.3f}%) exceeds the "
                f"{profile.value} baseline "
                f"({baseline['packet_loss_baseline']:.2f}%)."
            )
            if rating == TopologyRating.GOOD:
                rating = TopologyRating.DEGRADED

        return ProfileLatencyResult(
            profile=profile,
            rating=rating,
            sample_count=len(latencies_ms),
            p50_ms=round(percentiles.median, 3),
            p95_ms=round(p95, 3),
            p99_ms=round(percentiles.p99, 3),
            expected_rtt_low_ms=baseline["low"],
            expected_rtt_high_ms=baseline["high"],
            degraded_above_ms=baseline["degraded_above"],
            packet_loss_percent=packet_loss_percent,
            packet_loss_baseline_percent=baseline["packet_loss_baseline"],
            warnings=warnings,
            recommendations=recommendations,
        )
