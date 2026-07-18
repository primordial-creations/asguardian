"""
Apdex Calculator Service

Calculates Application Performance Index (Apdex) scores.
"""

from typing import Dict, List, Optional, Sequence, Union

from Asgard.Verdandi.Analysis.models.analysis_models import (
    ApdexConfig,
    ApdexRecalibrationRecord,
    ApdexResult,
    MultiEndpointApdexResult,
)
from Asgard.Verdandi.Anomaly.services._batch_detectors import bimodality_guard
from Asgard.Verdandi.Anomaly.models.anomaly_models import DetectionOutcome

#: Minimum shadow (parallel-run) period, in days, before a recalibration
#: cutover is considered safe (DEEPTHINK_03).
MIN_SHADOW_PERIOD_DAYS = 30

BIMODAL_WARNING = (
    "BIMODAL — Apdex masks mode structure; use segmented SLOs (Plan 04/02)"
)


def _distribution_warning(response_times_ms: Sequence[Union[int, float]]) -> Optional[str]:
    """Run the bimodality guard on raw response times; None when not bimodal
    or when there is insufficient data to judge (annotation only, never an
    alert)."""
    guard = bimodality_guard(list(response_times_ms))
    if guard.outcome == DetectionOutcome.BIMODAL_DISTRIBUTION and guard.is_bimodal:
        return BIMODAL_WARNING
    return None


class ApdexCalculator:
    """
    Calculator for Application Performance Index (Apdex) scores.

    Apdex measures user satisfaction based on response time:
    - Satisfied: response time <= T
    - Tolerating: T < response time <= 4T
    - Frustrated: response time > 4T

    Formula: Apdex = (Satisfied + Tolerating * 0.5) / Total

    Example:
        calc = ApdexCalculator(threshold_ms=500)
        result = calc.calculate([100, 200, 300, 600, 800, 2500])
        print(f"Apdex Score: {result.score}")
    """

    def __init__(
        self,
        threshold_ms: float = 500.0,
        frustration_multiplier: float = 4.0,
    ):
        """
        Initialize the Apdex calculator.

        Args:
            threshold_ms: Satisfied threshold T in milliseconds
            frustration_multiplier: Multiplier for frustration threshold (default 4T)
        """
        self.config = ApdexConfig(
            threshold_ms=threshold_ms,
            frustration_multiplier=frustration_multiplier,
        )

    def calculate(
        self,
        response_times_ms: Sequence[Union[int, float]],
        config: Optional[ApdexConfig] = None,
    ) -> ApdexResult:
        """
        Calculate Apdex score for a set of response times.

        Args:
            response_times_ms: Sequence of response times in milliseconds
            config: Optional config override

        Returns:
            ApdexResult with score and breakdown

        Raises:
            ValueError: If response_times_ms is empty
        """
        if not response_times_ms:
            raise ValueError("Cannot calculate Apdex for empty dataset")

        cfg = config or self.config
        threshold = cfg.threshold_ms
        frustration_threshold = cfg.frustration_threshold_ms

        satisfied = 0
        tolerating = 0
        frustrated = 0

        for time_ms in response_times_ms:
            if time_ms <= threshold:
                satisfied += 1
            elif time_ms <= frustration_threshold:
                tolerating += 1
            else:
                frustrated += 1

        total = satisfied + tolerating + frustrated
        score = (satisfied + tolerating * 0.5) / total

        return ApdexResult(
            score=round(score, 4),
            satisfied_count=satisfied,
            tolerating_count=tolerating,
            frustrated_count=frustrated,
            total_count=total,
            threshold_ms=threshold,
            rating=ApdexResult.get_rating(score),
            version=cfg.version,
            endpoint=cfg.endpoint,
            distribution_warning=_distribution_warning(response_times_ms),
        )

    def calculate_with_weights(
        self,
        response_times_ms: Sequence[Union[int, float]],
        weights: Sequence[Union[int, float]],
        config: Optional[ApdexConfig] = None,
    ) -> ApdexResult:
        """
        Calculate weighted Apdex score.

        Useful when different transactions have different importance.

        Args:
            response_times_ms: Sequence of response times in milliseconds
            weights: Weights for each response time (must match length)
            config: Optional config override

        Returns:
            ApdexResult with weighted score

        Raises:
            ValueError: If lengths don't match or inputs are empty
        """
        if not response_times_ms:
            raise ValueError("Cannot calculate Apdex for empty dataset")
        if len(response_times_ms) != len(weights):
            raise ValueError("Response times and weights must have same length")

        cfg = config or self.config
        threshold = cfg.threshold_ms
        frustration_threshold = cfg.frustration_threshold_ms

        satisfied_weight = 0.0
        tolerating_weight = 0.0
        frustrated_weight = 0.0
        total_weight = sum(weights)

        satisfied_count = 0
        tolerating_count = 0
        frustrated_count = 0

        for time_ms, weight in zip(response_times_ms, weights):
            if time_ms <= threshold:
                satisfied_weight += weight
                satisfied_count += 1
            elif time_ms <= frustration_threshold:
                tolerating_weight += weight
                tolerating_count += 1
            else:
                frustrated_weight += weight
                frustrated_count += 1

        score = (satisfied_weight + tolerating_weight * 0.5) / total_weight

        return ApdexResult(
            score=round(score, 4),
            satisfied_count=satisfied_count,
            tolerating_count=tolerating_count,
            frustrated_count=frustrated_count,
            total_count=len(response_times_ms),
            threshold_ms=threshold,
            rating=ApdexResult.get_rating(score),
        )

    @staticmethod
    def get_recommended_threshold(
        response_times_ms: Sequence[Union[int, float]],
        target_score: float = 0.85,
    ) -> float:
        """
        Calculate recommended threshold to achieve target Apdex score.

        Args:
            response_times_ms: Historical response times
            target_score: Desired Apdex score (default 0.85 = Good)

        Returns:
            Recommended threshold T in milliseconds
        """
        if not response_times_ms:
            return 500.0

        sorted_times = sorted(response_times_ms)
        n = len(sorted_times)

        target_satisfied = target_score * n

        if target_satisfied >= n:
            return sorted_times[-1]

        index = int(target_satisfied)
        if index >= n:
            index = n - 1

        return sorted_times[index]

    def calculate_with_errors(
        self,
        response_times_ms: Sequence[Union[int, float]],
        error_flags: Sequence[bool],
        config: Optional[ApdexConfig] = None,
        is_human: Optional[Sequence[bool]] = None,
    ) -> ApdexResult:
        """
        Error-unified Apdex: any errored request is Frustrated regardless of
        how fast it returned (DEEPTHINK_03 section 4.3 — unified SLI).

        Args:
            response_times_ms: Sequence of response times in milliseconds
            error_flags: Parallel sequence; True means the request errored
            config: Optional config override
            is_human: Optional parallel sequence; False marks machine/bot
                traffic, which is excluded from the score and reported
                separately via `machine_traffic_excluded`

        Returns:
            ApdexResult with errored requests counted as Frustrated

        Raises:
            ValueError: If inputs are empty or lengths mismatch
        """
        if not response_times_ms:
            raise ValueError("Cannot calculate Apdex for empty dataset")
        if len(response_times_ms) != len(error_flags):
            raise ValueError("response_times_ms and error_flags must have same length")
        if is_human is not None and len(is_human) != len(response_times_ms):
            raise ValueError("is_human must have same length as response_times_ms")

        cfg = config or self.config
        threshold = cfg.threshold_ms
        frustration_threshold = cfg.frustration_threshold_ms

        satisfied = 0
        tolerating = 0
        frustrated = 0
        excluded = 0
        human_times: List[Union[int, float]] = []

        for i, (time_ms, errored) in enumerate(zip(response_times_ms, error_flags)):
            if is_human is not None and not is_human[i]:
                excluded += 1
                continue
            human_times.append(time_ms)
            if errored:
                frustrated += 1
            elif time_ms <= threshold:
                satisfied += 1
            elif time_ms <= frustration_threshold:
                tolerating += 1
            else:
                frustrated += 1

        total = satisfied + tolerating + frustrated
        if total == 0:
            raise ValueError("No human traffic remaining after excluding machine traffic")
        score = (satisfied + tolerating * 0.5) / total

        return ApdexResult(
            score=round(score, 4),
            satisfied_count=satisfied,
            tolerating_count=tolerating,
            frustrated_count=frustrated,
            total_count=total,
            threshold_ms=threshold,
            rating=ApdexResult.get_rating(score),
            version=cfg.version,
            endpoint=cfg.endpoint,
            distribution_warning=_distribution_warning(human_times),
            machine_traffic_excluded=excluded,
        )

    @staticmethod
    def rollup(
        endpoint_results: Dict[str, ApdexResult],
        target_score: float = 0.85,
    ) -> MultiEndpointApdexResult:
        """
        Aggregate per-endpoint Apdex results as "% of endpoints meeting
        target" (DEEPTHINK_03 Simpson's-paradox guard). This is the correct
        replacement for volume-weighted pooling: a single huge, fast
        endpoint cannot mask a slow one behind a blended score.

        Args:
            endpoint_results: Mapping of endpoint name -> ApdexResult
            target_score: Apdex score an endpoint must meet/exceed to comply

        Returns:
            MultiEndpointApdexResult with compliance percentage and the
            names of failing endpoints

        Raises:
            ValueError: If endpoint_results is empty
        """
        if not endpoint_results:
            raise ValueError("Cannot roll up an empty set of endpoint results")

        failing = [
            name
            for name, result in endpoint_results.items()
            if result.score < target_score
        ]
        total = len(endpoint_results)
        meeting = total - len(failing)

        return MultiEndpointApdexResult(
            endpoint_results=dict(endpoint_results),
            target_score=target_score,
            total_endpoints=total,
            endpoints_meeting_target=meeting,
            pct_endpoints_meeting_target=round(100.0 * meeting / total, 4),
            failing_endpoints=sorted(failing),
        )

    def calculate_pooled(
        self,
        endpoint_response_times: Dict[str, Sequence[Union[int, float]]],
        config: Optional[ApdexConfig] = None,
        force: bool = False,
    ) -> ApdexResult:
        """
        Compute a single Apdex score pooled across multiple endpoints.

        Refused by default: pooling volume-weights every endpoint into one
        number, which is exactly the Simpson's-paradox failure mode
        DEEPTHINK_03 warns about (a high-volume fast endpoint can hide a
        low-volume slow one). Use `rollup()` instead. Pass `force=True` only
        when a single pooled number is genuinely required and the caller
        understands the risk.

        Raises:
            ValueError: If not force, or if endpoint_response_times is empty
        """
        if not force:
            raise ValueError(
                "calculate_pooled() blends endpoints into one score, which can "
                "mask a slow endpoint behind fast ones (Simpson's paradox). "
                "Use rollup() for '% of endpoints meeting target' instead, or "
                "pass force=True if a single pooled number is truly required."
            )
        if not endpoint_response_times:
            raise ValueError("Cannot calculate pooled Apdex for empty input")

        all_times: List[Union[int, float]] = []
        for times in endpoint_response_times.values():
            all_times.extend(times)

        return self.calculate(all_times, config=config)

    @staticmethod
    def recalibrate(
        old_version: str,
        new_version: str,
        old_threshold_ms: float,
        new_threshold_ms: float,
        shadow_period_days: int = MIN_SHADOW_PERIOD_DAYS,
        endpoint: Optional[str] = None,
    ) -> ApdexRecalibrationRecord:
        """
        Record a versioned Apdex threshold recalibration with its audit
        trail (DEEPTHINK_03): old and new configs should run in parallel
        ("shadow") for >= 30 days, annotated in dashboards/reports, and cut
        over at a quarter boundary.

        Returns:
            ApdexRecalibrationRecord documenting the change and checklist
        """
        shadow_sufficient = shadow_period_days >= MIN_SHADOW_PERIOD_DAYS

        checklist = [
            f"Run Apdex_{old_version}_T{old_threshold_ms:g} and "
            f"Apdex_{new_version}_T{new_threshold_ms:g} in parallel for "
            f"{shadow_period_days} days.",
            "Annotate dashboards/reports during the shadow period so viewers "
            "know two epochs are being compared.",
            "Cut over at a quarter boundary to avoid splitting a reporting "
            "period across two Apdex definitions.",
        ]
        if not shadow_sufficient:
            checklist.append(
                f"WARNING: requested shadow period ({shadow_period_days}d) is "
                f"below the recommended minimum of {MIN_SHADOW_PERIOD_DAYS}d."
            )

        return ApdexRecalibrationRecord(
            old_version=old_version,
            new_version=new_version,
            old_threshold_ms=old_threshold_ms,
            new_threshold_ms=new_threshold_ms,
            endpoint=endpoint,
            shadow_period_days=shadow_period_days,
            shadow_sufficient=shadow_sufficient,
            checklist=checklist,
        )
