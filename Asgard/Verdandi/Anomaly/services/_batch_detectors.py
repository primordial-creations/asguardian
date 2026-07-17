"""
Small-batch detector primitives (DEEPTHINK_02).

Pure-stdlib implementations of the 50-500-point-regime detectors:
split-window MAD, CUSUM, global OLS drift, and the bimodality guard.
These are annotation primitives — they never produce alert severities
(anomalies are not alerts; only SLO-burn integration alerts).
"""

import math
from typing import List, Optional, Sequence, Tuple

from Asgard.Verdandi.Anomaly.models.anomaly_models import (
    BimodalityResult,
    DetectionOutcome,
    DriftResult,
    MethodRecommendation,
    ModeStats,
    StepChangeResult,
)
from Asgard.Verdandi.Anomaly.services._regression_statistics import (
    t_distribution_p_value,
)


def _median(values: Sequence[float]) -> float:
    s = sorted(values)
    n = len(s)
    if n == 0:
        return 0.0
    mid = n // 2
    if n % 2:
        return float(s[mid])
    return (s[mid - 1] + s[mid]) / 2.0


def _mad(values: Sequence[float], center: Optional[float] = None) -> float:
    if not values:
        return 0.0
    med = _median(values) if center is None else center
    return _median([abs(v - med) for v in values])


def split_window_mad(
    values: Sequence[float],
    k: float = 3.0,
    min_segment: int = 5,
) -> StepChangeResult:
    """
    Detect a step change by comparing segment medians in MAD units.

    Scans candidate split points, picks the one maximizing the median shift,
    and flags a step when the shift exceeds k x MAD of the left segment.
    """
    n = len(values)
    if n < 2 * min_segment:
        return StepChangeResult(
            outcome=DetectionOutcome.INSUFFICIENT_DATA,
            notes=[f"Need >= {2 * min_segment} points for split-window MAD; got {n}."],
        )

    # Locate the split with the cumulative-sum change-point estimator
    # (argmax_i |sum_{j<=i}(x_j - mean)|), which is exact for mean shifts,
    # then gate the shift in MAD units of the left segment.
    mean = sum(values) / n
    cum = 0.0
    best_index = None
    best_stat = -1.0
    for i in range(n - 1):
        cum += values[i] - mean
        if min_segment <= i + 1 <= n - min_segment:
            stat = abs(cum)
            if stat > best_stat:
                best_stat = stat
                best_index = i + 1

    if best_index is None:
        return StepChangeResult(detected=False, method="split_window_mad")

    left = values[:best_index]
    right = values[best_index:]
    left_mad = _mad(left)
    magnitude = _median(right) - _median(left)
    scale = left_mad if left_mad > 0 else 1e-12
    mad_units = abs(magnitude) / scale

    detected = mad_units > k if left_mad > 0 else abs(magnitude) > 0
    return StepChangeResult(
        detected=detected,
        method="split_window_mad",
        change_index=best_index if detected else None,
        magnitude=round(magnitude, 6),
        mad_units=round(mad_units, 3) if left_mad > 0 else None,
        notes=[] if left_mad > 0 else ["Baseline MAD is zero; any shift is flagged."],
    )


def cusum(
    values: Sequence[float],
    kappa_sigmas: float = 0.5,
    h_sigmas: float = 5.0,
    reference_fraction: float = 0.5,
    min_reference: int = 10,
) -> StepChangeResult:
    """
    Two-sided CUSUM: S_i = max(0, S_{i-1} + (x_i - mu0 -/+ kappa)); alarm at h.

    mu0/sigma estimated from the leading reference window.
    """
    n = len(values)
    ref_len = max(min_reference, int(n * reference_fraction))
    if n < min_reference + 5 or ref_len >= n:
        return StepChangeResult(
            outcome=DetectionOutcome.INSUFFICIENT_DATA,
            notes=[f"Need >= {min_reference + 5} points for CUSUM; got {n}."],
        )

    reference = values[:ref_len]
    mu0 = sum(reference) / ref_len
    var = sum((x - mu0) ** 2 for x in reference) / max(ref_len - 1, 1)
    sigma = math.sqrt(var)
    if sigma == 0:
        sigma = 1e-12

    kappa = kappa_sigmas * sigma
    h = h_sigmas * sigma

    s_hi = 0.0
    s_lo = 0.0
    alarm_index = None
    for i, x in enumerate(values):
        s_hi = max(0.0, s_hi + (x - mu0 - kappa))
        s_lo = max(0.0, s_lo + (mu0 - x - kappa))
        if s_hi > h or s_lo > h:
            alarm_index = i
            break

    detected = alarm_index is not None
    magnitude = None
    if detected and alarm_index is not None:
        after = values[alarm_index:]
        magnitude = _median(after) - _median(reference)

    return StepChangeResult(
        detected=detected,
        method="cusum",
        change_index=alarm_index,
        cusum_alarm_index=alarm_index,
        magnitude=round(magnitude, 6) if magnitude is not None else None,
    )


def ols_drift(
    values: Sequence[float],
    alpha: float = 0.05,
    min_points: int = 10,
    min_relative_drift: float = 0.0,
) -> DriftResult:
    """
    Gradual-drift detection via global OLS slope with a t-test on slope != 0.

    Fixes the boiling-frog blindness of rolling z-scores (DEEPTHINK_02 s2):
    a slow ramp never deviates from its own recent window, but the global
    trend line sees it.
    """
    n = len(values)
    if n < min_points:
        return DriftResult(
            outcome=DetectionOutcome.INSUFFICIENT_DATA,
            notes=[f"Need >= {min_points} points for OLS drift; got {n}."],
        )

    x_mean = (n - 1) / 2.0
    y_mean = sum(values) / n
    sxx = sum((i - x_mean) ** 2 for i in range(n))
    sxy = sum((i - x_mean) * (values[i] - y_mean) for i in range(n))
    slope = sxy / sxx if sxx > 0 else 0.0
    intercept = y_mean - slope * x_mean

    ss_res = sum((values[i] - (intercept + slope * i)) ** 2 for i in range(n))
    df = n - 2
    residual_var = ss_res / df if df > 0 else 0.0
    se_slope = math.sqrt(residual_var / sxx) if sxx > 0 and residual_var > 0 else 0.0

    if se_slope == 0:
        t_stat = float("inf") if slope != 0 else 0.0
        p_value = 0.0 if slope != 0 else 1.0
    else:
        t_stat = slope / se_slope
        p_value = t_distribution_p_value(abs(t_stat), df)

    total_drift = slope * (n - 1)
    med = _median(values)
    relative_drift = abs(total_drift) / abs(med) if med != 0 else None

    detected = p_value < alpha and slope != 0.0
    if detected and min_relative_drift > 0 and relative_drift is not None:
        detected = relative_drift >= min_relative_drift

    return DriftResult(
        detected=detected,
        slope=round(slope, 9),
        slope_t_statistic=round(t_stat, 4) if math.isfinite(t_stat) else None,
        slope_p_value=round(p_value, 6),
        total_drift=round(total_drift, 6),
        relative_drift=round(relative_drift, 6) if relative_drift is not None else None,
    )


def _histogram(values: Sequence[float], bins: int) -> Tuple[List[int], float, float]:
    lo = min(values)
    hi = max(values)
    if hi == lo:
        return [len(values)], lo, 1.0
    width = (hi - lo) / bins
    counts = [0] * bins
    for v in values:
        idx = min(int((v - lo) / width), bins - 1)
        counts[idx] += 1
    return counts, lo, width


def bimodality_guard(
    values: Sequence[float],
    valley_threshold: float = 0.5,
    min_points: int = 30,
    min_mode_weight: float = 0.1,
) -> BimodalityResult:
    """
    Dip-statistic-lite bimodality guard.

    Flags bimodality when the histogram has two local maxima separated by a
    valley lower than `valley_threshold` x the smaller peak, with both modes
    carrying at least `min_mode_weight` of the samples. Gaussian methods
    (z-score/IQR anchored to a global mean) must be skipped when this fires;
    per-mode stats are reported instead (feeds the Database pool-exhaustion
    signature detector).
    """
    n = len(values)
    if n < min_points:
        return BimodalityResult(
            outcome=DetectionOutcome.INSUFFICIENT_DATA,
            notes=[f"Need >= {min_points} points for bimodality guard; got {n}."],
        )

    bins = max(8, min(40, int(math.sqrt(n))))
    counts, lo, width = _histogram(values, bins)
    if len(counts) == 1:
        return BimodalityResult(is_bimodal=False, notes=["Degenerate distribution."])

    # Light 3-bin smoothing to suppress sampling jitter.
    smoothed = [
        (counts[max(0, i - 1)] + counts[i] + counts[min(len(counts) - 1, i + 1)]) / 3.0
        for i in range(len(counts))
    ]

    peaks = []
    for i in range(len(smoothed)):
        left = smoothed[i - 1] if i > 0 else -1.0
        right = smoothed[i + 1] if i < len(smoothed) - 1 else -1.0
        if smoothed[i] > left and smoothed[i] >= right and smoothed[i] > 0:
            peaks.append(i)

    best = None  # (valley_ratio, p1, p2, valley_idx)
    for a in range(len(peaks)):
        for b in range(a + 1, len(peaks)):
            p1, p2 = peaks[a], peaks[b]
            between = smoothed[p1 + 1 : p2]
            if not between:
                continue
            valley = min(between)
            valley_idx = p1 + 1 + between.index(valley)
            smaller_peak = min(smoothed[p1], smoothed[p2])
            if smaller_peak <= 0:
                continue
            ratio = valley / smaller_peak
            if best is None or ratio < best[0]:
                best = (ratio, p1, p2, valley_idx)

    if best is None:
        return BimodalityResult(is_bimodal=False)

    ratio, p1, p2, valley_idx = best
    split_value = lo + (valley_idx + 0.5) * width
    low_mode = [v for v in values if v <= split_value]
    high_mode = [v for v in values if v > split_value]

    is_bimodal = (
        ratio < valley_threshold
        and len(low_mode) >= max(3, int(min_mode_weight * n))
        and len(high_mode) >= max(3, int(min_mode_weight * n))
    )

    modes = []
    if is_bimodal:
        for mode in (low_mode, high_mode):
            med = _median(mode)
            modes.append(
                ModeStats(
                    median=round(med, 6),
                    mad=round(_mad(mode, med), 6),
                    count=len(mode),
                    weight=round(len(mode) / n, 4),
                )
            )

    return BimodalityResult(
        outcome=DetectionOutcome.BIMODAL_DISTRIBUTION if is_bimodal else DetectionOutcome.OK,
        is_bimodal=is_bimodal,
        modes=modes,
        valley_ratio=round(ratio, 4),
        split_value=round(split_value, 6) if is_bimodal else None,
        notes=(
            [
                "Distribution is bimodal: global-mean methods (z-score/IQR) are "
                "invalid; use per-mode statistics."
            ]
            if is_bimodal
            else []
        ),
    )


def recommend_method(
    n: int,
    cycles_observed: float = 0.0,
    deployment_marker: bool = False,
    suspected_scenario: Optional[str] = None,
) -> MethodRecommendation:
    """
    Scenario-routed method selection (DEEPTHINK_02 switching thresholds).

    - n < 150: statistical methods only (no distributional ML).
    - >= 3-4 seasonal cycles observed: seasonal modelling becomes viable.
    - Deployment marker: suspend long-memory historical baselines.
    - Step change -> split-window MAD / CUSUM; gradual drift -> global OLS.
    """
    recommended: List[str] = []
    avoid: List[str] = []
    reasons: List[str] = []

    if suspected_scenario == "step_change":
        recommended += ["split_window_mad", "cusum"]
        reasons.append("Step changes: split-window MAD and CUSUM localize the shift.")
    elif suspected_scenario == "gradual_drift":
        recommended.append("ols_drift")
        avoid.append("rolling_zscore")
        reasons.append(
            "Gradual drift: rolling statistics absorb the ramp (boiling frog); "
            "use the global OLS trend."
        )
    else:
        recommended += ["split_window_mad", "cusum", "ols_drift"]

    if n < 150:
        avoid.append("distributional_ml")
        reasons.append(
            f"n={n} < 150: distributional/ML methods are starved; use robust statistics."
        )
    else:
        recommended.append("distributional_ml_optional")
        reasons.append(f"n={n} >= 150: distributional methods become viable.")

    if cycles_observed >= 3:
        recommended.append("seasonal_decomposition")
        reasons.append(
            f"{cycles_observed:.1f} seasonal cycles observed (>= 3): seasonal modelling viable."
        )
    elif cycles_observed > 0:
        avoid.append("seasonal_decomposition")
        reasons.append(
            f"Only {cycles_observed:.1f} seasonal cycles observed; need >= 3 full cycles."
        )

    if deployment_marker:
        avoid.append("historical_baseline")
        reasons.append(
            "Deployment marker present: suspend long-memory baselines; the "
            "pre-deploy distribution no longer describes the system."
        )

    recommended.insert(0, "bimodality_guard")
    reasons.append("Always run the bimodality guard before Gaussian methods.")

    return MethodRecommendation(
        recommended_methods=recommended,
        avoid_methods=avoid,
        reasons=reasons,
    )
