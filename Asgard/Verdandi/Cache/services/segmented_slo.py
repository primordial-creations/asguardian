"""
Segmented Cache SLOs

Independent hit-path and miss-path threshold-fraction SLIs (DEEPTHINK_04).

Cache-heavy services are the canonical bimodal distribution: hit rate
collapsing 85% -> 0% can keep a loose blended latency SLO green while the
median user experience degrades 80x. The remedy is separate budgets —
"99% of hits < 20 ms" and "95% of misses < 1000 ms" — plus the hit ratio
as its own SLI, and a mode-shift alarm for fast-path regressions that
blended percentiles (and Apdex) mask.
"""

from typing import List, Optional, Sequence

from Asgard.Verdandi.Cache.models.cache_models import SegmentedCacheSLO


class SegmentedSloAnalyzer:
    """
    Computes hit/miss threshold-fraction SLIs from labeled latency samples,
    with an unlabeled fallback that splits modes via the Anomaly bimodality
    guard.

    Example:
        analyzer = SegmentedSloAnalyzer()
        result = analyzer.analyze(hit_latencies_ms=[8, 12], miss_latencies_ms=[700])
        print(result.hit_sli, result.miss_sli)
    """

    def __init__(
        self,
        hit_threshold_ms: float = 20.0,
        miss_threshold_ms: float = 1000.0,
        mode_shift_mads: float = 3.0,
    ):
        """
        Args:
            hit_threshold_ms: Hit-path latency budget (default 20 ms)
            miss_threshold_ms: Miss-path latency budget (default 1000 ms)
            mode_shift_mads: Baseline MADs the hit-mode median may migrate
                before a fast-path regression is flagged
        """
        self.hit_threshold_ms = hit_threshold_ms
        self.miss_threshold_ms = miss_threshold_ms
        self.mode_shift_mads = mode_shift_mads

    def analyze(
        self,
        hit_latencies_ms: Sequence[float],
        miss_latencies_ms: Sequence[float],
        baseline_hit_median_ms: Optional[float] = None,
        baseline_hit_mad_ms: Optional[float] = None,
    ) -> SegmentedCacheSLO:
        """
        Compute segmented SLIs from labeled samples.

        Args:
            hit_latencies_ms: Latencies of cache hits
            miss_latencies_ms: Latencies of cache misses
            baseline_hit_median_ms: Healthy-period hit-mode median
            baseline_hit_mad_ms: Healthy-period hit-mode MAD

        Returns:
            SegmentedCacheSLO with per-path good/total counts consumable by
            the SLO module's SLITracker
        """
        hit_good = sum(1 for v in hit_latencies_ms if v <= self.hit_threshold_ms)
        miss_good = sum(1 for v in miss_latencies_ms if v <= self.miss_threshold_ms)
        hit_total = len(hit_latencies_ms)
        miss_total = len(miss_latencies_ms)

        hit_median = self._median(hit_latencies_ms) if hit_total else None

        mode_shift_alert = False
        mode_shift_details = None
        notes: List[str] = []
        if (
            hit_median is not None
            and baseline_hit_median_ms is not None
            and baseline_hit_mad_ms is not None
            and baseline_hit_mad_ms > 0
        ):
            shift = abs(hit_median - baseline_hit_median_ms)
            if shift > self.mode_shift_mads * baseline_hit_mad_ms:
                mode_shift_alert = True
                mode_shift_details = (
                    f"Hit-mode median moved {baseline_hit_median_ms:.1f}ms -> "
                    f"{hit_median:.1f}ms ({shift / baseline_hit_mad_ms:.1f} baseline "
                    "MADs): fast-path regression. Blended percentiles and Apdex "
                    "mask this while the miss path dominates the tail."
                )
                notes.append(mode_shift_details)

        total = hit_total + miss_total
        return SegmentedCacheSLO(
            hit_sli=round(hit_good / hit_total, 6) if hit_total else None,
            miss_sli=round(miss_good / miss_total, 6) if miss_total else None,
            hit_threshold_ms=self.hit_threshold_ms,
            miss_threshold_ms=self.miss_threshold_ms,
            hit_good=hit_good,
            hit_total=hit_total,
            miss_good=miss_good,
            miss_total=miss_total,
            hit_ratio=round(hit_total / total, 6) if total else None,
            hit_median_ms=round(hit_median, 3) if hit_median is not None else None,
            mode_shift_alert=mode_shift_alert,
            mode_shift_details=mode_shift_details,
            labeled=True,
            notes=notes,
        )

    def analyze_unlabeled(
        self,
        latencies_ms: Sequence[float],
        baseline_hit_median_ms: Optional[float] = None,
        baseline_hit_mad_ms: Optional[float] = None,
    ) -> SegmentedCacheSLO:
        """
        Fallback for unlabeled samples: split hit/miss modes with the
        Anomaly bimodality guard, then compute segmented SLIs.

        When the distribution is not bimodal the samples are treated as a
        single (hit) mode and a note records the reduced confidence.

        Args:
            latencies_ms: Unlabeled latency samples
            baseline_hit_median_ms: Healthy-period hit-mode median
            baseline_hit_mad_ms: Healthy-period hit-mode MAD

        Returns:
            SegmentedCacheSLO with labeled=False
        """
        from Asgard.Verdandi.Anomaly.services._batch_detectors import bimodality_guard

        guard = bimodality_guard(latencies_ms)
        if guard.is_bimodal and guard.split_value is not None:
            hits = [v for v in latencies_ms if v <= guard.split_value]
            misses = [v for v in latencies_ms if v > guard.split_value]
            note = (
                f"Hit/miss split inferred from bimodality at {guard.split_value:.1f}ms "
                "(unlabeled data): treat SLIs as approximate."
            )
        else:
            hits = list(latencies_ms)
            misses = []
            note = (
                "Distribution not bimodal; all samples treated as one mode. "
                "Provide labeled hit/miss samples for real segmented SLOs."
            )

        result = self.analyze(
            hits, misses, baseline_hit_median_ms, baseline_hit_mad_ms
        )
        result.labeled = False
        result.notes.append(note)
        return result

    @staticmethod
    def _median(values: Sequence[float]) -> float:
        s = sorted(values)
        n = len(s)
        mid = n // 2
        if n % 2:
            return float(s[mid])
        return (s[mid - 1] + s[mid]) / 2.0
