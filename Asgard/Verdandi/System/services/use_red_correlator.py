"""
USE <-> RED Correlator

Encodes the USE-to-RED causality chain (RESEARCH_12) as a correlation/
ordering analysis rather than three unrelated health scores:

    Rate up -> Utilization up -> Saturation spike -> p99 Duration degrades
    first -> Errors -> Rate collapses

Cross-correlates a saturation series (run-queue length, PSI, aqu-sz,
throttle ratio, ...) against p99 duration at small lags: the lag with the
strongest correlation identifies whether saturation *leads* the latency
degradation (a capacity problem) or whether p99 rises while saturation
stays flat (a code regression, not a capacity problem).
"""

import statistics
from typing import Dict, List, Optional, Sequence

from Asgard.Verdandi.System.models.system_models import UseRedCorrelation


class UseRedCorrelator:
    """
    Correlator for USE (saturation) series against RED (p99 duration) series.

    Example:
        correlator = UseRedCorrelator()
        result = correlator.correlate(
            saturation=[10, 12, 40, 80, 90, 88],
            p99_duration_ms=[50, 52, 55, 120, 300, 310],
        )
        print(result.best_lag, result.verdict)
    """

    FLAT_SATURATION_CV = 0.15  # coefficient of variation below which saturation is "flat"
    MIN_CORRELATION_FOR_CAPACITY = 0.6

    def correlate(
        self,
        saturation: Sequence[float],
        p99_duration_ms: Sequence[float],
        max_lag: int = 5,
        rate: Optional[Sequence[float]] = None,
        errors: Optional[Sequence[float]] = None,
    ) -> UseRedCorrelation:
        """
        Cross-correlate saturation against p99 duration at lags 0..max_lag.

        Args:
            saturation: USE saturation time series (run-queue, PSI some_avg10,
                aqu-sz, throttle_ratio, ...), aligned bucket-for-bucket
            p99_duration_ms: p99 duration series, same buckets
            max_lag: Maximum lag (in buckets) saturation may lead duration by
            rate: Optional request-rate series for full ordering confirmation
            errors: Optional error-rate series for full ordering confirmation

        Returns:
            UseRedCorrelation
        """
        n = min(len(saturation), len(p99_duration_ms))
        if n < 4:
            return UseRedCorrelation(
                verdict="insufficient_data",
                notes=[f"Need >= 4 aligned buckets, got {n}."],
            )

        sat = list(saturation[:n])
        dur = list(p99_duration_ms[:n])

        correlations: Dict[int, float] = {}
        for lag in range(0, min(max_lag, n - 3) + 1):
            r = self._pearson_lagged(sat, dur, lag)
            if r is not None:
                correlations[lag] = round(r, 4)

        if not correlations:
            return UseRedCorrelation(
                verdict="insufficient_data",
                notes=["Could not compute a valid correlation at any lag."],
            )

        best_lag = max(correlations, key=lambda lag: correlations[lag])
        best_corr = correlations[best_lag]

        sat_mean = statistics.fmean(sat)
        sat_stdev = statistics.pstdev(sat)
        sat_cv = (sat_stdev / sat_mean) if sat_mean else 0.0
        saturation_flat = sat_cv < self.FLAT_SATURATION_CV

        dur_rising = dur[-1] > dur[0]

        notes: List[str] = []
        if saturation_flat and dur_rising:
            verdict = "regression_suspected"
            notes.append(
                "Saturation is flat while p99 duration rises: this is not a "
                "capacity problem. Route to anomaly/regression analysis "
                "(likely a code-level regression, not load)."
            )
        elif best_corr >= self.MIN_CORRELATION_FOR_CAPACITY:
            verdict = "capacity_bound"
            notes.append(
                f"Saturation leads p99 duration by {best_lag} bucket(s) "
                f"(r={best_corr:.2f}): degradation tracks the USE chain "
                "(rate -> utilization -> saturation -> duration)."
            )
        else:
            verdict = "insufficient_data"
            notes.append(
                f"Best correlation r={best_corr:.2f} at lag {best_lag} is too "
                "weak to confidently attribute causality."
            )

        ordering_confirmed = False
        if rate is not None and errors is not None and len(rate) >= n and len(errors) >= n:
            ordering_confirmed = self._check_ordering(rate[:n], sat, dur, errors[:n])
            if ordering_confirmed:
                notes.append(
                    "Full USE->RED ordering confirmed: rate rose, then "
                    "saturation, then p99 duration, then errors."
                )

        return UseRedCorrelation(
            best_lag=best_lag,
            best_correlation=best_corr,
            correlations_by_lag=correlations,
            verdict=verdict,
            ordering_confirmed=ordering_confirmed,
            notes=notes,
        )

    @staticmethod
    def _pearson_lagged(
        saturation: Sequence[float], duration: Sequence[float], lag: int
    ) -> Optional[float]:
        """Pearson r between saturation[i] and duration[i+lag]."""
        n = len(saturation) - lag
        if n < 3:
            return None
        x = saturation[:n]
        y = duration[lag : lag + n]
        return UseRedCorrelator._pearson(x, y)

    @staticmethod
    def _pearson(x: Sequence[float], y: Sequence[float]) -> Optional[float]:
        n = len(x)
        if n < 2:
            return None
        mean_x = statistics.fmean(x)
        mean_y = statistics.fmean(y)
        cov = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
        var_x = sum((xi - mean_x) ** 2 for xi in x)
        var_y = sum((yi - mean_y) ** 2 for yi in y)
        denom = (var_x * var_y) ** 0.5
        if denom == 0:
            return None
        return cov / denom

    @staticmethod
    def _check_ordering(
        rate: Sequence[float],
        saturation: Sequence[float],
        duration: Sequence[float],
        errors: Sequence[float],
    ) -> bool:
        """Check that peak-onset indices occur in order: rate, sat, duration, errors."""

        def onset_index(series: Sequence[float]) -> int:
            baseline = series[0]
            peak = max(series)
            if peak <= baseline:
                return 0
            threshold = baseline + 0.5 * (peak - baseline)
            for i, v in enumerate(series):
                if v >= threshold:
                    return i
            return 0

        idx_rate = onset_index(rate)
        idx_sat = onset_index(saturation)
        idx_dur = onset_index(duration)
        idx_err = onset_index(errors)
        return idx_rate <= idx_sat <= idx_dur <= idx_err
