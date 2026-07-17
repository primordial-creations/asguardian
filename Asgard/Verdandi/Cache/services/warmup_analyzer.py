"""
Warm-up Trajectory Analyzer

Derivative-based analysis of post-deploy cache hit-rate trajectories
(DEEPTHINK_08 s3). Post-deploy hit-rate drops are mechanical certainties,
but a static suppression window is dangerous: a broken cache connection
string melts the database while alerts sleep. The correct approach is to
expect the drop and monitor the recovery slope — a plunge-and-flatline or
correlation with downstream DB load bypasses suppression.
"""

import math
from typing import Dict, List, Optional, Sequence

from Asgard.Verdandi.Cache.models.cache_models import WarmupState, WarmupTrajectory


class WarmupAnalyzer:
    """
    Trajectory-aware warm-up classifier for hit-rate time series.

    Classification after a drop of >= drop_threshold points:
    - WARMING: positive recovery slope within the grace window; alert
      suppressed, recovery ETA estimated from an exponential fit.
    - FLATLINED: |h'| < flatline_slope for the grace window at a depressed
      level; CRITICAL, bypasses suppression (broken-connection case).
    - COLLAPSED: hit rate < collapse_threshold at any point; immediate
      CRITICAL regardless of grace.

    Example:
        analyzer = WarmupAnalyzer()
        result = analyzer.analyze([
            {"hits": 900, "misses": 100},
            {"hits": 500, "misses": 500},
            {"hits": 650, "misses": 350},
            {"hits": 780, "misses": 220},
        ])
        print(result.state)
    """

    def __init__(
        self,
        drop_threshold: float = 15.0,
        grace_buckets: int = 3,
        flatline_slope: float = 0.5,
        collapse_threshold: float = 5.0,
        min_buckets: int = 3,
    ):
        """
        Args:
            drop_threshold: Hit-rate points lost that count as a drop
            grace_buckets: Buckets of recovery observation after a drop
            flatline_slope: |derivative| (pts/bucket) below which the
                trajectory is flat
            collapse_threshold: Hit rate (percent) treated as collapse
            min_buckets: Minimum buckets required for any verdict
        """
        self.drop_threshold = drop_threshold
        self.grace_buckets = grace_buckets
        self.flatline_slope = flatline_slope
        self.collapse_threshold = collapse_threshold
        self.min_buckets = min_buckets

    def analyze(
        self,
        series: Sequence[Dict],
        db_load_series: Optional[Sequence[float]] = None,
    ) -> WarmupTrajectory:
        """
        Classify a hit-rate trajectory.

        Args:
            series: Buckets of {"hits": int, "misses": int} in time order
                (optional extra keys such as "timestamp" are ignored)
            db_load_series: Optional aligned downstream DB load series;
                Pearson r(miss_rate, db_load) > 0.8 strengthens severity

        Returns:
            WarmupTrajectory (INSUFFICIENT_DATA when starved — never an alert)
        """
        rates = [self._hit_rate(b) for b in series]
        rates = [r for r in rates if r is not None]
        if len(rates) < self.min_buckets:
            return WarmupTrajectory(
                state=WarmupState.INSUFFICIENT_DATA,
                severity="info",
                notes=[
                    f"Need >= {self.min_buckets} buckets with traffic; got {len(rates)}."
                ],
            )

        db_correlation = self._db_correlation(series, db_load_series)

        # COLLAPSED: total loss at any point — no grace applies.
        if min(rates) < self.collapse_threshold:
            return WarmupTrajectory(
                state=WarmupState.COLLAPSED,
                severity="critical",
                suppress_alert=False,
                baseline_hit_rate=round(rates[0], 2),
                drop_pct=round(rates[0] - min(rates), 2),
                drop_index=rates.index(min(rates)),
                db_correlation=db_correlation,
                notes=[
                    f"Hit rate fell below {self.collapse_threshold:.0f}% — this is "
                    "not warm-up; treat as a cache outage (broken connection, "
                    "flushed keyspace, or serialization mismatch)."
                ],
            )

        baseline, drop_index, trough = self._find_drop(rates)
        if drop_index is None:
            return WarmupTrajectory(
                state=WarmupState.STABLE,
                severity="info",
                baseline_hit_rate=round(baseline, 2),
                db_correlation=db_correlation,
            )

        post = rates[drop_index:]
        derivatives = [post[i + 1] - post[i] for i in range(len(post) - 1)]
        window = derivatives[: self.grace_buckets] if derivatives else []
        slope = sum(window) / len(window) if window else 0.0
        drop_pct = baseline - trough

        notes: List[str] = []
        if db_correlation is not None and db_correlation > 0.8:
            notes.append(
                f"Miss rate correlates with downstream DB load (r={db_correlation:.2f}): "
                "the misses are landing on the database."
            )

        if slope > self.flatline_slope:
            tau, eta = self._fit_recovery(post, baseline)
            return WarmupTrajectory(
                state=WarmupState.WARMING,
                severity="warning" if db_correlation and db_correlation > 0.8 else "info",
                suppress_alert=not (db_correlation and db_correlation > 0.8),
                baseline_hit_rate=round(baseline, 2),
                drop_pct=round(drop_pct, 2),
                drop_index=drop_index,
                recovery_slope=round(slope, 3),
                tau_buckets=round(tau, 2) if tau is not None else None,
                eta_buckets=round(eta, 2) if eta is not None else None,
                db_correlation=db_correlation,
                notes=notes
                + [
                    "Hit rate is recovering — expected post-deploy warm-up; "
                    "alert suppressed while the slope stays positive."
                ],
            )

        # Dropped and not recovering (mean slope at or below the flatline
        # threshold): plunge-and-flatline — the broken-connection signature.
        return WarmupTrajectory(
            state=WarmupState.FLATLINED,
            severity="critical",
            suppress_alert=False,
            baseline_hit_rate=round(baseline, 2),
            drop_pct=round(drop_pct, 2),
            drop_index=drop_index,
            recovery_slope=round(slope, 3),
            db_correlation=db_correlation,
            notes=notes
            + [
                "Hit rate dropped and is NOT recovering (plunge-and-flatline). "
                "This is the broken-connection signature, not warm-up — "
                "suppression bypassed."
            ],
        )

    @staticmethod
    def _hit_rate(bucket: Dict) -> Optional[float]:
        hits = bucket.get("hits", 0)
        misses = bucket.get("misses", 0)
        total = hits + misses
        if total <= 0:
            return None
        return hits / total * 100.0

    def _find_drop(self, rates: List[float]):
        """Return (baseline, drop_index, trough). drop_index None when stable."""
        baseline = rates[0]
        best_index = None
        trough = rates[0]
        running_baseline = rates[0]
        for i in range(1, len(rates)):
            if rates[i] < running_baseline - self.drop_threshold:
                if best_index is None or rates[i] < trough:
                    best_index = i
                    trough = rates[i]
                    baseline = running_baseline
            else:
                running_baseline = max(running_baseline, rates[i])
        if best_index is None:
            return running_baseline, None, None
        # Walk back to the first bucket of the fall.
        i = best_index
        while i > 1 and rates[i - 1] < baseline - self.drop_threshold:
            i -= 1
        return baseline, i, trough

    def _fit_recovery(self, post: List[float], baseline: float):
        """
        Fit h(t) = baseline - a*exp(-t/tau) via log-linear regression on the
        deficit; return (tau, eta) where eta = tau * ln(a / 1pt).
        """
        deficits = [(i, baseline - r) for i, r in enumerate(post) if baseline - r > 0.5]
        if len(deficits) < 3:
            return None, None
        xs = [d[0] for d in deficits]
        ys = [math.log(d[1]) for d in deficits]
        n = len(xs)
        x_mean = sum(xs) / n
        y_mean = sum(ys) / n
        sxx = sum((x - x_mean) ** 2 for x in xs)
        if sxx == 0:
            return None, None
        slope = sum((xs[i] - x_mean) * (ys[i] - y_mean) for i in range(n)) / sxx
        if slope >= 0:
            return None, None  # deficit not shrinking exponentially
        tau = -1.0 / slope
        a = math.exp(y_mean - slope * x_mean)
        eta = tau * math.log(max(a, 1.0001))  # buckets until deficit < 1 pt
        return tau, max(eta, 0.0)

    @staticmethod
    def _db_correlation(
        series: Sequence[Dict],
        db_load_series: Optional[Sequence[float]],
    ) -> Optional[float]:
        """Pearson r between per-bucket miss rate and DB load."""
        if not db_load_series:
            return None
        miss_rates = []
        loads = []
        for bucket, load in zip(series, db_load_series):
            hits = bucket.get("hits", 0)
            misses = bucket.get("misses", 0)
            total = hits + misses
            if total > 0:
                miss_rates.append(misses / total)
                loads.append(load)
        n = len(miss_rates)
        if n < 3:
            return None
        mx = sum(miss_rates) / n
        my = sum(loads) / n
        sxy = sum((miss_rates[i] - mx) * (loads[i] - my) for i in range(n))
        sxx = sum((x - mx) ** 2 for x in miss_rates)
        syy = sum((y - my) ** 2 for y in loads)
        if sxx == 0 or syy == 0:
            return None
        return round(sxy / math.sqrt(sxx * syy), 4)
