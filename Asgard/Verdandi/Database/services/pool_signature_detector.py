"""
Pool-Exhaustion Signature Detector

Classifies bimodal latency distributions (RESEARCH_11): connection-pool
exhaustion produces two near-equal-variance peaks whose separation IS the
mean queue wait; cache-aside bimodality shows a narrow fast peak and a wide
slow peak. Blended mean/median are statistically meaningless during
exhaustion — this detector says which regime you are in.
"""

from typing import List, Optional, Sequence

from Asgard.Verdandi.Anomaly.services._batch_detectors import bimodality_guard
from Asgard.Verdandi.Database.models.database_models import (
    PoolModeStats,
    PoolSignature,
    PoolSignatureClass,
)


class PoolSignatureDetector:
    """
    Detects the pool-exhaustion bimodal signature in blended query latencies.

    Classification of a bimodal fit (modes m1 < m2 with MADs s1, s2):
    - POOL_EXHAUSTION: |s1 - s2| / max(s1, s2) < 0.35 (near-equal variance)
      -> mean_queue_wait_ms ~= m2 - m1. Every affected request waits about
      the same time for a connection, so the slow peak is a shifted copy of
      the fast one.
    - CACHE_ASIDE_PATTERN: s2 > 2 x s1 (wide slow mode) -> route to the
      Cache module's segmented SLO analysis.

    Optional acquisition-wait samples corroborate: p50(wait) within +/- 25%
    of (m2 - m1) raises confidence to HIGH.

    Example:
        detector = PoolSignatureDetector()
        signature = detector.detect(latencies_ms)
        if signature.classification == PoolSignatureClass.POOL_EXHAUSTION:
            print(signature.mean_queue_wait_ms)
    """

    EQUAL_VARIANCE_DISPARITY = 0.35
    CACHE_ASIDE_MAD_RATIO = 2.0
    CORROBORATION_TOLERANCE = 0.25

    def detect(
        self,
        latencies_ms: Sequence[float],
        acquisition_wait_samples: Optional[Sequence[float]] = None,
    ) -> PoolSignature:
        """
        Classify a blended latency distribution.

        Args:
            latencies_ms: Raw (blended) query latencies in ms
            acquisition_wait_samples: Optional connection acquisition waits
                used to corroborate the queue-wait estimate

        Returns:
            PoolSignature (INSUFFICIENT_DATA when the bimodality guard is starved)
        """
        guard = bimodality_guard(latencies_ms)

        if guard.outcome.value == "insufficient_data":
            return PoolSignature(
                classification=PoolSignatureClass.INSUFFICIENT_DATA,
                confidence="low",
                warnings=list(guard.notes),
            )

        if not guard.is_bimodal:
            return PoolSignature(
                classification=PoolSignatureClass.UNIMODAL,
                confidence="medium",
                warnings=[
                    "Distribution is unimodal: no pool-exhaustion or cache-aside "
                    "signature present."
                ],
            )

        low, high = guard.modes[0], guard.modes[1]
        m1, m2 = low.median, high.median
        s1, s2 = low.mad, high.mad
        modes = [
            PoolModeStats(median_ms=m1, mad_ms=s1, count=low.count, weight=low.weight),
            PoolModeStats(median_ms=m2, mad_ms=s2, count=high.count, weight=high.weight),
        ]

        s_max = max(s1, s2)
        disparity = abs(s1 - s2) / s_max if s_max > 0 else 0.0
        queue_wait = m2 - m1

        blended_warning = (
            "Blended mean/median are invalid during pool exhaustion: the "
            "distribution is a mixture, and averages land between the modes "
            "where no requests actually live (RESEARCH_11)."
        )

        if disparity < self.EQUAL_VARIANCE_DISPARITY:
            corroborated, confidence, corr_notes = self._corroborate(
                queue_wait, acquisition_wait_samples
            )
            return PoolSignature(
                classification=PoolSignatureClass.POOL_EXHAUSTION,
                mean_queue_wait_ms=round(queue_wait, 3),
                modes=modes,
                mad_disparity=round(disparity, 4),
                confidence=confidence,
                corroborated_by_wait_samples=corroborated,
                warnings=[blended_warning] + corr_notes,
                recommendations=[
                    f"Two near-equal-variance latency peaks {queue_wait:.0f}ms "
                    "apart: the slow mode is the fast mode plus a constant "
                    f"connection-queue wait of ~{queue_wait:.0f}ms. Increase the "
                    "pool (Little's law: qps x avg query seconds / 0.7) or reduce "
                    "connection hold time.",
                ],
            )

        if s2 > self.CACHE_ASIDE_MAD_RATIO * s1:
            return PoolSignature(
                classification=PoolSignatureClass.CACHE_ASIDE_PATTERN,
                modes=modes,
                mad_disparity=round(disparity, 4),
                confidence="medium",
                warnings=[
                    "Narrow fast mode with a wide slow mode: cache-aside "
                    "bimodality (hits vs misses), not pool exhaustion."
                ],
                recommendations=[
                    "Route to cache analysis: segment hit/miss latency SLOs "
                    "(Verdandi.Cache.SegmentedSloAnalyzer) instead of pool sizing."
                ],
            )

        return PoolSignature(
            classification=PoolSignatureClass.AMBIGUOUS_BIMODAL,
            modes=modes,
            mad_disparity=round(disparity, 4),
            confidence="low",
            warnings=[
                blended_warning,
                "Bimodal but matches neither the equal-variance (pool) nor the "
                "wide-slow-mode (cache-aside) template; investigate per-mode "
                "membership manually.",
            ],
        )

    def _corroborate(
        self,
        queue_wait: float,
        acquisition_wait_samples: Optional[Sequence[float]],
    ):
        """Check p50(wait) ~= m2 - m1 within tolerance; returns (bool, confidence, notes)."""
        if not acquisition_wait_samples:
            return False, "medium", []
        s = sorted(acquisition_wait_samples)
        n = len(s)
        mid = n // 2
        p50 = float(s[mid]) if n % 2 else (s[mid - 1] + s[mid]) / 2.0
        if queue_wait > 0 and abs(p50 - queue_wait) / queue_wait <= self.CORROBORATION_TOLERANCE:
            return True, "high", [
                f"Acquisition-wait p50 ({p50:.0f}ms) matches the inter-peak "
                f"distance ({queue_wait:.0f}ms): pool exhaustion confirmed."
            ]
        return False, "medium", [
            f"Acquisition-wait p50 ({p50:.0f}ms) does not match the inter-peak "
            f"distance ({queue_wait:.0f}ms); classification kept at MEDIUM confidence."
        ]
