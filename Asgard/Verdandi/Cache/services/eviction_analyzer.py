"""
Eviction Analyzer

Analyzes cache eviction patterns and metrics.
"""

from typing import Dict, List, Optional, Sequence

from Asgard.Verdandi.Cache.models.cache_models import EvictionMetrics, TTLAnalysis


class EvictionAnalyzer:
    """
    Analyzer for cache eviction metrics.

    Tracks eviction rates, reasons, and patterns.

    Example:
        analyzer = EvictionAnalyzer()
        result = analyzer.analyze(
            evictions=100,
            duration_seconds=3600,
            total_operations=10000
        )
        print(f"Eviction Rate: {result.eviction_rate_per_sec}/sec")
    """

    def analyze(
        self,
        evictions: int,
        duration_seconds: float,
        total_operations: int,
        by_reason: Optional[Dict[str, int]] = None,
        avg_entry_age_seconds: Optional[float] = None,
        premature_evictions: int = 0,
    ) -> EvictionMetrics:
        """
        Analyze eviction metrics.

        Args:
            evictions: Total evictions
            duration_seconds: Duration of measurement
            total_operations: Total cache operations
            by_reason: Breakdown by eviction reason
            avg_entry_age_seconds: Average age of evicted entries
            premature_evictions: Entries evicted before natural expiry

        Returns:
            EvictionMetrics with analysis
        """
        eviction_rate = evictions / duration_seconds if duration_seconds > 0 else 0
        eviction_percent = (evictions / total_operations) * 100 if total_operations > 0 else 0

        if by_reason is None:
            by_reason = {}

        status = self._determine_status(eviction_percent, premature_evictions, evictions)
        recommendations = self._generate_recommendations(
            eviction_percent, premature_evictions, avg_entry_age_seconds, by_reason
        )

        return EvictionMetrics(
            total_evictions=evictions,
            eviction_rate_per_sec=round(eviction_rate, 2),
            eviction_percent=round(eviction_percent, 2),
            by_reason=by_reason,
            avg_entry_age_seconds=avg_entry_age_seconds,
            premature_evictions=premature_evictions,
            status=status,
            recommendations=recommendations,
        )

    def calculate_eviction_rate(
        self,
        evictions: int,
        duration_seconds: float,
    ) -> float:
        """
        Calculate evictions per second.

        Args:
            evictions: Number of evictions
            duration_seconds: Duration in seconds

        Returns:
            Evictions per second
        """
        if duration_seconds <= 0:
            return 0.0
        return round(evictions / duration_seconds, 2)

    def analyze_ttl_patterns(
        self,
        evictions: Sequence[Dict],
        near_ttl_fraction: float = 0.9,
        ttl_short_share: float = 0.6,
        lru_undersized_share: float = 0.4,
        lru_bytes_per_sec: Optional[float] = None,
        target_headroom: float = 0.9,
    ) -> TTLAnalysis:
        """
        TTL-distribution and eviction-economics analysis.

        Heuristics (Plan 04 SD):
        - TTL too short: >= 60% of EXPIRED evictions die at age >= 0.9 x TTL
          *and* were re-fetched shortly after -> suggest p75(refetch_interval).
        - Cache undersized: LRU share > 40% with average LRU age
          < 0.25 x median TTL; working set ~= lru_bytes_per_sec x avg_age,
          recommended size = working_set / 0.9 headroom.

        Args:
            evictions: Items of {"key", "reason", "age_seconds",
                "ttl_seconds"?, "refetch_interval_seconds"?, "size_bytes"?}
            near_ttl_fraction: Age/TTL ratio counting as "died of old age"
            ttl_short_share: Share of near-TTL expiries that flags TTL-too-short
            lru_undersized_share: LRU share flagging an undersized cache
            lru_bytes_per_sec: Optional observed LRU eviction throughput for
                working-set estimation
            target_headroom: Sizing headroom target (default 0.9)

        Returns:
            TTLAnalysis
        """
        total = len(evictions)
        if total == 0:
            return TTLAnalysis(
                total_evictions=0,
                notes=["No eviction events supplied — INSUFFICIENT_DATA."],
            )

        def reason(e: Dict) -> str:
            return str(e.get("reason", "")).upper()

        expired = [e for e in evictions if reason(e) == "EXPIRED"]
        lru = [e for e in evictions if reason(e) == "LRU"]

        recommendations: List[str] = []
        notes: List[str] = []

        # --- TTL-too-short heuristic -----------------------------------
        expired_near_ttl = None
        ttl_too_short = False
        suggested_ttl = None
        with_ttl = [
            e for e in expired
            if e.get("ttl_seconds") and e["ttl_seconds"] > 0
        ]
        if with_ttl:
            near = [
                e for e in with_ttl
                if e.get("age_seconds", 0) >= near_ttl_fraction * e["ttl_seconds"]
            ]
            expired_near_ttl = len(near) / len(with_ttl)
            refetches = [
                e["refetch_interval_seconds"]
                for e in near
                if e.get("refetch_interval_seconds") is not None
            ]
            if expired_near_ttl >= ttl_short_share and refetches:
                ttl_too_short = True
                suggested_ttl = self._percentile(sorted(refetches), 75)
                recommendations.append(
                    f"{expired_near_ttl * 100:.0f}% of EXPIRED evictions die at "
                    f">= {near_ttl_fraction * 100:.0f}% of TTL and are re-fetched "
                    f"soon after: TTL is too short. Suggested TTL ~= p75 of the "
                    f"refetch interval: {suggested_ttl:.0f}s."
                )
        else:
            notes.append("No ttl_seconds on EXPIRED events; TTL analysis skipped.")

        # --- LRU pressure / working set ---------------------------------
        lru_share = len(lru) / total if total else None
        cache_undersized = False
        working_set = None
        recommended_size = None
        if lru:
            lru_ages = [e.get("age_seconds", 0.0) for e in lru]
            avg_lru_age = sum(lru_ages) / len(lru_ages)
            ttls = sorted(
                e["ttl_seconds"] for e in evictions
                if e.get("ttl_seconds") and e["ttl_seconds"] > 0
            )
            median_ttl = self._percentile(ttls, 50) if ttls else None
            young = median_ttl is None or avg_lru_age < 0.25 * median_ttl
            if lru_share > lru_undersized_share and young:
                cache_undersized = True
                recommendations.append(
                    f"LRU evictions are {lru_share * 100:.0f}% of the total with "
                    f"average age {avg_lru_age:.0f}s — entries are evicted long "
                    "before natural expiry: the cache is undersized for its "
                    "working set."
                )
                if lru_bytes_per_sec:
                    working_set = lru_bytes_per_sec * avg_lru_age
                    recommended_size = working_set / target_headroom
                    recommendations.append(
                        f"Estimated working set ~= {working_set:,.0f} bytes; "
                        f"size the cache to ~{recommended_size:,.0f} bytes "
                        f"({target_headroom:.0%} target fill)."
                    )

        return TTLAnalysis(
            total_evictions=total,
            expired_share=round(len(expired) / total, 4),
            expired_near_ttl_fraction=(
                round(expired_near_ttl, 4) if expired_near_ttl is not None else None
            ),
            ttl_too_short=ttl_too_short,
            suggested_ttl_seconds=(
                round(suggested_ttl, 2) if suggested_ttl is not None else None
            ),
            lru_share=round(lru_share, 4) if lru_share is not None else None,
            cache_undersized=cache_undersized,
            working_set_bytes=round(working_set, 2) if working_set else None,
            recommended_size_bytes=(
                round(recommended_size, 2) if recommended_size else None
            ),
            recommendations=recommendations,
            notes=notes,
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

    def _determine_status(
        self,
        eviction_percent: float,
        premature: int,
        total: int,
    ) -> str:
        """Determine eviction status."""
        premature_rate = (premature / total) * 100 if total > 0 else 0

        if premature_rate > 30:
            return "critical"
        if eviction_percent > 20:
            return "high"
        if eviction_percent > 10:
            return "moderate"
        return "normal"

    def _generate_recommendations(
        self,
        eviction_percent: float,
        premature: int,
        avg_age: Optional[float],
        by_reason: Dict[str, int],
    ) -> List[str]:
        """Generate eviction recommendations."""
        recommendations = []

        if eviction_percent > 20:
            recommendations.append(
                f"High eviction rate ({eviction_percent:.1f}%). "
                "Consider increasing cache size."
            )

        if premature > 0:
            recommendations.append(
                f"{premature} premature evictions detected. "
                "Cache may be undersized for workload."
            )

        if avg_age and avg_age < 60:
            recommendations.append(
                f"Average entry age is low ({avg_age:.1f}s). "
                "Entries are being evicted quickly."
            )

        if by_reason:
            total_evictions = sum(by_reason.values())
            if "lru" in by_reason and total_evictions > 0:
                lru_percent = (by_reason["lru"] / total_evictions) * 100
                if lru_percent > 70:
                    recommendations.append(
                        f"Most evictions ({lru_percent:.0f}%) are LRU-based. "
                        "Cache is at capacity frequently."
                    )

        return recommendations
