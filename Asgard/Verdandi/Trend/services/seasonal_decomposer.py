"""
Robust STL-lite Seasonal Decomposition

Additive: value[i] = trend[i] + seasonal[i] + residual[i]
Multiplicative: value[i] = trend[i] * seasonal[i] * residual[i] (via log-transform)

Algorithm (Plan 03F / RESEARCH_15):
    1. trend = centered moving average over one period.
    2. detrend = value - trend.
    3. seasonal = per-phase medians of the detrended series.
    4. residual = detrend - seasonal.
    5. robust pass: recompute with biweight weights
       w = (1 - (r / (6*MAD))^2)^2, zeroing gross outliers (|r| >= 6*MAD)
       out of the per-phase seasonal estimate.

Requires >= 3 full periods; below that the caller gets a typed
INSUFFICIENT_DATA outcome rather than a decomposition built on noise
(DEEPTHINK_01 / DEEPTHINK_02's seasonal-modeling switching threshold).
"""

import math
from typing import List, Optional, Sequence, Tuple

from Asgard.Verdandi.Trend.models.trend_models import (
    DecompositionMode,
    DecompositionOutcome,
    SeasonalDecomposition,
)

_MIN_CYCLES = 3.0


def _median(values: Sequence[float]) -> float:
    s = sorted(values)
    n = len(s)
    if n == 0:
        return 0.0
    mid = n // 2
    if n % 2:
        return float(s[mid])
    return (s[mid - 1] + s[mid]) / 2.0


def _mad(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    med = _median(values)
    return _median([abs(v - med) for v in values])


def _centered_moving_average(
    values: Sequence[float], period: int
) -> List[Optional[float]]:
    """Centered moving average over one period; None at the un-centerable ends."""
    n = len(values)
    trend: List[Optional[float]] = [None] * n
    half = period // 2

    if period % 2 == 1:
        for i in range(half, n - half):
            window = values[i - half : i + half + 1]
            trend[i] = sum(window) / period
    else:
        # Even period: a 2xN moving average (average of two staggered
        # period-windows) so every point gets an equal-weight centered trend.
        for i in range(half, n - half):
            edge_lo = values[i - half]
            edge_hi = values[i + half]
            middle = values[i - half + 1 : i + half]
            trend[i] = (0.5 * edge_lo + sum(middle) + 0.5 * edge_hi) / period

    return trend


def _fill_ends(values: List[Optional[float]]) -> List[float]:
    """Forward/back-fill None edges with the nearest computed trend value."""
    n = len(values)
    filled: List[Optional[float]] = list(values)
    first_valid = next((i for i, v in enumerate(filled) if v is not None), None)
    if first_valid is None:
        return [0.0] * n
    last_valid = next(
        (i for i in range(n - 1, -1, -1) if filled[i] is not None), None
    )
    for i in range(first_valid):
        filled[i] = filled[first_valid]
    for i in range(last_valid + 1, n):
        filled[i] = filled[last_valid]
    return [float(v) for v in filled]  # type: ignore[misc]


def _seasonal_indices(
    detrend: Sequence[Optional[float]],
    period: int,
    weights: Optional[Sequence[float]] = None,
) -> List[float]:
    """Per-phase median of the detrended series, optionally weight-filtered."""
    buckets: List[List[float]] = [[] for _ in range(period)]
    for i, d in enumerate(detrend):
        if d is None:
            continue
        if weights is not None and weights[i] <= 0.0:
            continue
        buckets[i % period].append(d)

    indices = [
        _median(bucket) if bucket else 0.0 for bucket in buckets
    ]
    return indices


def _decompose_linear(
    values: Sequence[float], period: int
) -> Tuple[List[float], List[float], List[float], List[float], List[float], List[int]]:
    """
    Additive STL-lite decomposition in whatever domain `values` is given
    (raw for additive mode, log-transformed for multiplicative mode).

    Returns (trend, seasonal, residual, seasonal_indices, robust_weights,
    outlier_indices), all length-n except seasonal_indices (length period).
    """
    n = len(values)

    raw_trend = _centered_moving_average(values, period)
    raw_detrend: List[Optional[float]] = [
        (values[i] - raw_trend[i]) if raw_trend[i] is not None else None
        for i in range(n)
    ]

    seasonal_indices = _seasonal_indices(raw_detrend, period)
    mean_index = sum(seasonal_indices) / period
    seasonal_indices = [s - mean_index for s in seasonal_indices]  # sum to 0

    filled_trend = _fill_ends(raw_trend)
    seasonal = [seasonal_indices[i % period] for i in range(n)]
    residual = [values[i] - filled_trend[i] - seasonal[i] for i in range(n)]

    # Robust pass: biweight weights zero out gross outliers before the
    # seasonal component is finalized (Plan 03F).
    mad = _mad(residual)
    outlier_indices: List[int] = []
    if mad > 0:
        weights = []
        for i, r in enumerate(residual):
            u = r / (6.0 * mad)
            if abs(u) >= 1.0:
                weights.append(0.0)
                outlier_indices.append(i)
            else:
                weights.append((1.0 - u * u) ** 2)
    else:
        weights = [1.0] * n

    robust_seasonal_indices = _seasonal_indices(raw_detrend, period, weights=weights)
    mean_robust = sum(robust_seasonal_indices) / period
    robust_seasonal_indices = [s - mean_robust for s in robust_seasonal_indices]

    robust_seasonal = [robust_seasonal_indices[i % period] for i in range(n)]
    robust_residual = [
        values[i] - filled_trend[i] - robust_seasonal[i] for i in range(n)
    ]

    return (
        filled_trend,
        robust_seasonal,
        robust_residual,
        robust_seasonal_indices,
        weights,
        outlier_indices,
    )


class SeasonalDecomposer:
    """
    Robust STL-lite additive/multiplicative seasonal decomposition.

    Example:
        decomposer = SeasonalDecomposer()
        result = decomposer.decompose(values, period=24)
        if result.outcome == DecompositionOutcome.OK:
            print(result.trend, result.seasonal, result.residual)
    """

    def decompose(
        self,
        values: Sequence[float],
        period: int,
        mode: DecompositionMode = DecompositionMode.ADDITIVE,
    ) -> SeasonalDecomposition:
        """
        Decompose a time series into trend + seasonal + residual components.

        Args:
            values: Time series values (assumed uniformly sampled)
            period: Length of one seasonal cycle, in points
            mode: ADDITIVE or MULTIPLICATIVE (log-transform internally)

        Returns:
            SeasonalDecomposition; INSUFFICIENT_DATA when fewer than 3 full
            periods are available, or (multiplicative only) when a
            non-positive value makes the log-transform undefined.
        """
        n = len(values)
        if period <= 0:
            return SeasonalDecomposition(
                outcome=DecompositionOutcome.INSUFFICIENT_DATA,
                mode=mode,
                period=period,
                notes=["period must be a positive integer."],
            )

        cycles_available = n / period
        if cycles_available < _MIN_CYCLES:
            return SeasonalDecomposition(
                outcome=DecompositionOutcome.INSUFFICIENT_DATA,
                mode=mode,
                period=period,
                cycles_available=round(cycles_available, 2),
                notes=[
                    f"Need >= {_MIN_CYCLES} full periods "
                    f"(>= {int(_MIN_CYCLES * period)} points); got {n} "
                    f"points ({cycles_available:.2f} cycles)."
                ],
            )

        if mode == DecompositionMode.MULTIPLICATIVE:
            if any(v <= 0 for v in values):
                return SeasonalDecomposition(
                    outcome=DecompositionOutcome.INSUFFICIENT_DATA,
                    mode=mode,
                    period=period,
                    cycles_available=round(cycles_available, 2),
                    notes=[
                        "Multiplicative decomposition requires all values > 0 "
                        "(log-transform is undefined otherwise)."
                    ],
                )
            log_values = [math.log(v) for v in values]
            (
                log_trend,
                log_seasonal,
                _log_residual,
                log_indices,
                weights,
                outliers,
            ) = _decompose_linear(log_values, period)

            trend = [math.exp(t) for t in log_trend]
            seasonal_indices = [math.exp(s) for s in log_indices]
            seasonal = [seasonal_indices[i % period] for i in range(n)]
            residual = [
                values[i] / (trend[i] * seasonal[i]) if trend[i] * seasonal[i] != 0 else 1.0
                for i in range(n)
            ]

            return SeasonalDecomposition(
                outcome=DecompositionOutcome.OK,
                mode=mode,
                period=period,
                cycles_available=round(cycles_available, 2),
                trend=[round(t, 6) for t in trend],
                seasonal=[round(s, 6) for s in seasonal],
                residual=[round(r, 6) for r in residual],
                seasonal_indices=[round(s, 6) for s in seasonal_indices],
                robust_weights=[round(w, 4) for w in weights],
                outlier_indices=outliers,
            )

        trend, seasonal, residual, seasonal_indices, weights, outliers = (
            _decompose_linear(list(values), period)
        )

        return SeasonalDecomposition(
            outcome=DecompositionOutcome.OK,
            mode=mode,
            period=period,
            cycles_available=round(cycles_available, 2),
            trend=[round(t, 6) for t in trend],
            seasonal=[round(s, 6) for s in seasonal],
            residual=[round(r, 6) for r in residual],
            seasonal_indices=[round(s, 6) for s in seasonal_indices],
            robust_weights=[round(w, 4) for w in weights],
            outlier_indices=outliers,
        )
