"""
Cache Metrics Calculator

Calculates cache performance metrics.
"""

from typing import Dict, List, Optional, Sequence

from Asgard.Verdandi.Cache.models.cache_models import (
    CacheEfficiency,
    CacheMetrics,
    KeyAnalysisResult,
    KeyStats,
    WarmupTrajectory,
)


class CacheMetricsCalculator:
    """
    Calculator for cache performance metrics.

    Analyzes cache hit rates, latency savings, and efficiency.

    Example:
        calc = CacheMetricsCalculator()
        result = calc.analyze(hits=950, misses=50)
        print(f"Hit Rate: {result.hit_rate_percent}%")
    """

    EXCELLENT_THRESHOLD = 95.0
    GOOD_THRESHOLD = 85.0
    FAIR_THRESHOLD = 70.0

    def analyze(
        self,
        hits: int,
        misses: int,
        avg_hit_latency_ms: Optional[float] = None,
        avg_miss_latency_ms: Optional[float] = None,
        size_bytes: Optional[int] = None,
        max_size_bytes: Optional[int] = None,
    ) -> CacheMetrics:
        """
        Analyze cache metrics.

        Args:
            hits: Number of cache hits
            misses: Number of cache misses
            avg_hit_latency_ms: Average latency for cache hits
            avg_miss_latency_ms: Average latency for cache misses
            size_bytes: Current cache size in bytes
            max_size_bytes: Maximum cache size in bytes

        Returns:
            CacheMetrics with analysis
        """
        total = hits + misses
        hit_rate = (hits / total) * 100 if total > 0 else 0
        miss_rate = (misses / total) * 100 if total > 0 else 0

        latency_savings = None
        if avg_hit_latency_ms is not None and avg_miss_latency_ms is not None:
            savings_per_hit = avg_miss_latency_ms - avg_hit_latency_ms
            latency_savings = savings_per_hit * hits

        fill_percent = None
        if size_bytes is not None and max_size_bytes and max_size_bytes > 0:
            fill_percent = (size_bytes / max_size_bytes) * 100

        status = self._determine_status(hit_rate)
        recommendations = self._generate_recommendations(
            hit_rate, fill_percent, avg_hit_latency_ms, avg_miss_latency_ms
        )

        return CacheMetrics(
            total_requests=total,
            hits=hits,
            misses=misses,
            hit_rate_percent=round(hit_rate, 2),
            miss_rate_percent=round(miss_rate, 2),
            avg_hit_latency_ms=avg_hit_latency_ms,
            avg_miss_latency_ms=avg_miss_latency_ms,
            latency_savings_ms=round(latency_savings, 2) if latency_savings else None,
            size_bytes=size_bytes,
            max_size_bytes=max_size_bytes,
            fill_percent=round(fill_percent, 2) if fill_percent else None,
            status=status,
            recommendations=recommendations,
        )

    def calculate_hit_rate(self, hits: int, total: int) -> float:
        """
        Calculate cache hit rate.

        Args:
            hits: Number of hits
            total: Total requests

        Returns:
            Hit rate as percentage
        """
        if total <= 0:
            return 0.0
        return round((hits / total) * 100, 2)

    def calculate_efficiency(
        self,
        metrics: CacheMetrics,
        memory_overhead_percent: float = 10.0,
    ) -> CacheEfficiency:
        """
        Calculate overall cache efficiency.

        Args:
            metrics: Cache metrics to analyze
            memory_overhead_percent: Estimated memory overhead

        Returns:
            CacheEfficiency assessment
        """
        hit_rate = metrics.hit_rate_percent

        memory_efficiency = 100.0
        if metrics.fill_percent:
            if metrics.fill_percent < 50:
                memory_efficiency = metrics.fill_percent * 2
            elif metrics.fill_percent > 95:
                memory_efficiency = 90 + (100 - metrics.fill_percent)
            else:
                memory_efficiency = 90 + (metrics.fill_percent - 50) * 0.2

        latency_factor = None
        if metrics.avg_hit_latency_ms and metrics.avg_miss_latency_ms:
            if metrics.avg_hit_latency_ms > 0:
                latency_factor = metrics.avg_miss_latency_ms / metrics.avg_hit_latency_ms

        efficiency_score = (hit_rate * 0.7) + (memory_efficiency * 0.3)

        status = self._determine_status(efficiency_score)
        recommendations = self._generate_efficiency_recommendations(
            hit_rate, memory_efficiency, latency_factor, metrics.fill_percent
        )

        return CacheEfficiency(
            efficiency_score=round(efficiency_score, 2),
            hit_rate_percent=hit_rate,
            memory_efficiency_percent=round(memory_efficiency, 2),
            latency_improvement_factor=round(latency_factor, 2) if latency_factor else None,
            cost_savings_percent=round(hit_rate * 0.8, 2),
            optimal_size_bytes=None,
            status=status,
            recommendations=recommendations,
        )

    def analyze_trend(
        self,
        history: Sequence[Dict],
        db_load_series: Optional[Sequence[float]] = None,
    ) -> WarmupTrajectory:
        """
        Analyze a hit-rate time series with trajectory-aware classification.

        Delegates to WarmupAnalyzer (DEEPTHINK_08): post-deploy dips with a
        positive recovery slope are WARMING (suppressed); plunge-and-flatline
        is FLATLINED (critical, bypasses suppression); < 5% is COLLAPSED.

        Args:
            history: Buckets of {"hits": int, "misses": int} in time order
                (extra keys such as "timestamp" are ignored)
            db_load_series: Optional aligned downstream DB load series

        Returns:
            WarmupTrajectory
        """
        from Asgard.Verdandi.Cache.services.warmup_analyzer import WarmupAnalyzer

        return WarmupAnalyzer().analyze(history, db_load_series)

    def analyze_keys(
        self,
        key_stats: Sequence[Dict],
        low_hit_rate_threshold: float = 0.5,
        churn_threshold: int = 20,
    ) -> KeyAnalysisResult:
        """
        Per-key hit-rate analysis.

        Identifies low-hit keys and low-hit high-churn "do-not-cache"
        candidates (keys that cost cache memory and eviction pressure while
        rarely serving a hit — negative caching value).

        Args:
            key_stats: Items of {"key": str, "hits": int, "misses": int}
            low_hit_rate_threshold: Hit fraction below which a key is low-hit
            churn_threshold: Minimum misses for a low-hit key to be a
                do-not-cache candidate

        Returns:
            KeyAnalysisResult
        """
        keys: List[KeyStats] = []
        total_hits = 0
        total_all = 0
        for item in key_stats:
            hits = int(item.get("hits", 0))
            misses = int(item.get("misses", 0))
            total = hits + misses
            keys.append(
                KeyStats(
                    key=str(item.get("key", "")),
                    hits=hits,
                    misses=misses,
                    total=total,
                    hit_rate=round(hits / total, 4) if total > 0 else 0.0,
                )
            )
            total_hits += hits
            total_all += total

        low_hit = [k for k in keys if k.total > 0 and k.hit_rate < low_hit_rate_threshold]
        do_not_cache = [k for k in low_hit if k.misses >= churn_threshold]

        recommendations = []
        if do_not_cache:
            worst = sorted(do_not_cache, key=lambda k: k.hit_rate)[:5]
            names = ", ".join(k.key for k in worst)
            recommendations.append(
                f"{len(do_not_cache)} key(s) have low hit rates with high churn "
                f"(e.g. {names}): caching them has negative value — consider "
                "excluding them or reworking their TTL/keying."
            )

        return KeyAnalysisResult(
            keys=keys,
            low_hit_rate_keys=low_hit,
            do_not_cache_candidates=do_not_cache,
            overall_hit_rate=round(total_hits / total_all, 4) if total_all else 0.0,
            recommendations=recommendations,
        )

    def _determine_status(self, rate: float) -> str:
        """Determine cache status based on hit rate."""
        if rate >= self.EXCELLENT_THRESHOLD:
            return "excellent"
        if rate >= self.GOOD_THRESHOLD:
            return "good"
        if rate >= self.FAIR_THRESHOLD:
            return "fair"
        return "poor"

    def _generate_recommendations(
        self,
        hit_rate: float,
        fill_percent: Optional[float],
        hit_latency: Optional[float],
        miss_latency: Optional[float],
    ) -> List[str]:
        """Generate cache recommendations."""
        recommendations = []

        if hit_rate < self.FAIR_THRESHOLD:
            recommendations.append(
                f"Cache hit rate ({hit_rate:.1f}%) is low. "
                "Consider increasing cache size or adjusting TTL."
            )

        if fill_percent and fill_percent > 95:
            recommendations.append(
                "Cache is nearly full. Consider increasing size to reduce evictions."
            )

        if fill_percent and fill_percent < 30:
            recommendations.append(
                f"Cache utilization is low ({fill_percent:.1f}%). "
                "Consider caching more data types."
            )

        if hit_latency and miss_latency:
            if hit_latency > miss_latency * 0.5:
                recommendations.append(
                    "Cache hit latency is relatively high. "
                    "Consider optimizing cache access patterns."
                )

        return recommendations

    def _generate_efficiency_recommendations(
        self,
        hit_rate: float,
        memory_efficiency: float,
        latency_factor: Optional[float],
        fill_percent: Optional[float],
    ) -> List[str]:
        """Generate efficiency recommendations."""
        recommendations = []

        if hit_rate < 80:
            recommendations.append(
                "Improve hit rate by increasing cache size or optimizing eviction policy."
            )

        if memory_efficiency < 70:
            recommendations.append(
                "Memory efficiency is suboptimal. Review cache sizing strategy."
            )

        if latency_factor and latency_factor < 5:
            recommendations.append(
                "Latency improvement from caching is modest. "
                "Ensure high-latency operations are being cached."
            )

        return recommendations
