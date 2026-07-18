"""
Cache Stampede / Thundering-Herd Analyzer

Detects concurrent-recompute stampedes on expiring hot keys and advises
XFetch (Vattani et al.) probabilistic early recomputation:

    fetch_early when: now + Delta * beta * ln(1/rand()) >= expiry

where Delta is the observed recompute cost (p95) and beta ~= 1.0.
"""

import math
from typing import Dict, List, Optional, Sequence

from Asgard.Verdandi.Cache.models.cache_models import StampedeKeyReport, StampedeReport


class StampedeAnalyzer:
    """
    Analyzer for cache-stampede risk and XFetch recommendations.

    Input is a per-key access log: a sequence of records each shaped like
    ``{"key": str, "t": float, "hit": bool, "recompute_ms": float | None,
    "ttl_s": float | None}``. ``t`` is a monotonically increasing timestamp
    in milliseconds.

    Example:
        analyzer = StampedeAnalyzer()
        report = analyzer.analyze(access_log)
        for k in report.flagged_keys:
            print(k.key, k.stampede_factor, k.xfetch_rule)
    """

    STAMPEDE_FACTOR_THRESHOLD = 5.0
    TTL_DELTA_RATIO_THRESHOLD = 0.1
    DEFAULT_BETA = 1.0

    def analyze(
        self,
        access_log: Sequence[Dict],
        beta: float = DEFAULT_BETA,
        factor_threshold: float = STAMPEDE_FACTOR_THRESHOLD,
    ) -> StampedeReport:
        """
        Analyze a per-key access log for stampede signatures.

        Args:
            access_log: Records with key/t/hit/recompute_ms?/ttl_s?
            beta: XFetch beta parameter (default 1.0)
            factor_threshold: stampede_factor above which a key is flagged

        Returns:
            StampedeReport
        """
        by_key: Dict[str, List[Dict]] = {}
        for record in access_log:
            by_key.setdefault(record["key"], []).append(record)

        key_reports: List[StampedeKeyReport] = []
        for key, records in by_key.items():
            key_reports.append(
                self._analyze_key(key, records, beta, factor_threshold)
            )

        flagged = [r for r in key_reports if r.flagged]
        status = "healthy"
        if any(r.flagged and r.stampede_factor >= factor_threshold * 4 for r in flagged):
            status = "critical"
        elif flagged:
            status = "warning"

        recommendations = []
        for r in flagged:
            if r.xfetch_rule:
                recommendations.append(
                    f"Key '{r.key}': stampede_factor={r.stampede_factor:.1f}. "
                    f"Adopt XFetch: {r.xfetch_rule}"
                )
            if r.ttl_too_short_for_delta:
                recommendations.append(
                    f"Key '{r.key}': recompute cost Delta exceeds 10% of TTL — "
                    "increase TTL or use refresh-ahead instead of expire-and-recompute."
                )

        return StampedeReport(
            keys=key_reports,
            flagged_keys=flagged,
            total_keys_analyzed=len(key_reports),
            beta=beta,
            status=status,
            recommendations=recommendations,
        )

    def _analyze_key(
        self,
        key: str,
        records: Sequence[Dict],
        beta: float,
        factor_threshold: float,
    ) -> StampedeKeyReport:
        records_sorted = sorted(records, key=lambda r: r["t"])
        misses = [r for r in records_sorted if not r.get("hit", True)]

        recompute_times = [
            r["recompute_ms"] for r in records_sorted if r.get("recompute_ms") is not None
        ]
        delta_ms = self._percentile(sorted(recompute_times), 95) if recompute_times else None

        ttl_candidates = [r["ttl_s"] for r in records_sorted if r.get("ttl_s") is not None]
        ttl_s = ttl_candidates[-1] if ttl_candidates else None

        window_ms = delta_ms if delta_ms is not None else 0.0

        concurrent_misses = self._max_cluster_size(misses, window_ms)
        stampede_factor = float(concurrent_misses)
        flagged = stampede_factor > factor_threshold

        notes: List[str] = []
        xfetch_rule = None
        expected_reduction = None
        ttl_too_short = False

        if flagged:
            if delta_ms is not None:
                xfetch_rule = (
                    f"fetch_early when now + {delta_ms:.1f}ms * {beta} * ln(1/rand()) "
                    ">= expiry"
                )
                # Heuristic: XFetch spreads recomputation probabilistically over
                # the Delta window before expiry, so the probability that N
                # concurrent requests all still see an expired key (and thus
                # all stampede) collapses roughly as 1/N of the naive case.
                expected_reduction = round(
                    min(99.0, 100.0 * (1.0 - 1.0 / stampede_factor)), 1
                )
            else:
                notes.append(
                    "No recompute_ms samples available for this key; cannot "
                    "compute Delta or an XFetch rule."
                )

            if delta_ms is not None and ttl_s:
                delta_s = delta_ms / 1000.0
                if delta_s > self.TTL_DELTA_RATIO_THRESHOLD * ttl_s:
                    ttl_too_short = True

        return StampedeKeyReport(
            key=key,
            concurrent_misses=concurrent_misses,
            stampede_factor=round(stampede_factor, 2),
            flagged=flagged,
            delta_ms=round(delta_ms, 3) if delta_ms is not None else None,
            ttl_s=ttl_s,
            xfetch_rule=xfetch_rule,
            expected_stampede_reduction_pct=expected_reduction,
            ttl_too_short_for_delta=ttl_too_short,
            notes=notes,
        )

    @staticmethod
    def _max_cluster_size(misses: Sequence[Dict], window_ms: float) -> int:
        """Largest set of misses all within window_ms of the cluster's first miss."""
        if not misses:
            return 0
        times = sorted(r["t"] for r in misses)
        best = 1
        start_idx = 0
        for end_idx in range(len(times)):
            while times[end_idx] - times[start_idx] > window_ms:
                start_idx += 1
            best = max(best, end_idx - start_idx + 1)
        return best

    @staticmethod
    def _percentile(sorted_values: List[float], pct: float) -> Optional[float]:
        if not sorted_values:
            return None
        n = len(sorted_values)
        if n == 1:
            return float(sorted_values[0])
        rank = (pct / 100) * (n - 1)
        lower = int(rank)
        upper = min(lower + 1, n - 1)
        frac = rank - lower
        return sorted_values[lower] + frac * (sorted_values[upper] - sorted_values[lower])
