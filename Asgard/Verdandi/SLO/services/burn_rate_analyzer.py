"""Burn Rate Analyzer Service - analyzes error budget burn rate for alerting and forecasting."""

from datetime import datetime, timedelta
from typing import List, Optional, Sequence, Tuple, cast

from Asgard.Verdandi.SLO.models.slo_models import (
    BurnRate,
    BurnRateAlert,
    ErrorBudget,
    SLIMetric,
    SLODefinition,
    ThresholdDerivation,
)
from Asgard.Verdandi.SLO.services._burn_rate_helpers import (
    calculate_time_to_exhaustion,
    determine_burn_rate_severity,
    full_outage_burn_rate,
    generate_burn_rate_recommendations,
    generate_multi_window_recommendations,
    min_detectable_outage_seconds,
    minimum_traffic_for_target,
)


class BurnRateAnalyzer:
    """
    Analyzer for error budget burn rate.

    Burn rate measures how quickly error budget is being consumed relative
    to the sustainable rate. Used for multi-window alerting strategies.

    A burn rate of 1.0 means budget is being consumed at exactly the rate
    that would exhaust it at the end of the SLO window.

    Example:
        analyzer = BurnRateAnalyzer()

        # Analyze current burn rate
        burn_rate = analyzer.analyze(slo, metrics)
        if burn_rate.is_critical:
            trigger_alert(burn_rate)

        # Multi-window analysis for reliable alerting
        alerts = analyzer.multi_window_alert(slo, metrics)
    """

    CRITICAL_BURN_RATE = 14.4
    WARNING_BURN_RATE = 6.0
    ELEVATED_BURN_RATE = 1.0

    def __init__(
        self,
        critical_threshold: float = 14.4,
        warning_threshold: float = 6.0,
    ):
        """Initialize the burn rate analyzer."""
        self.critical_threshold = critical_threshold
        self.warning_threshold = warning_threshold

    def analyze(
        self,
        slo: SLODefinition,
        metrics: Sequence[SLIMetric],
        window_hours: float = 1.0,
        current_time: Optional[datetime] = None,
    ) -> BurnRate:
        """Analyze burn rate for a single time window."""
        current_time = current_time or datetime.now()
        window_start = current_time - timedelta(hours=window_hours)

        window_metrics = [
            m
            for m in metrics
            if m.timestamp >= window_start and m.timestamp <= current_time
        ]

        total_events = sum(m.total_events for m in window_metrics)
        good_events = sum(m.good_events for m in window_metrics)
        bad_events = total_events - good_events

        error_budget_fraction = (100.0 - slo.target) / 100.0
        slo_window_hours = slo.window_days * 24

        # Burn rate = observed failure rate / allowed failure rate.
        # 1.0 means the budget is being consumed at exactly the sustainable
        # rate; a 100% outage on a 99.9% SLO burns at 1000x regardless of
        # the observation window (DEEPTHINK_05).
        actual_failure_rate = bad_events / total_events if total_events > 0 else 0.0
        burn_rate = (
            actual_failure_rate / error_budget_fraction
            if error_budget_fraction > 0
            else 0.0
        )

        # Fraction of the TOTAL error budget consumed within this window.
        actual_budget_consumed = (
            burn_rate * window_hours / slo_window_hours
            if slo_window_hours > 0
            else 0.0
        )

        time_to_exhaustion = calculate_time_to_exhaustion(
            burn_rate, slo.window_days * 24
        )

        is_critical = burn_rate >= self.critical_threshold
        is_warning = not is_critical and burn_rate >= self.warning_threshold
        alert_severity = determine_burn_rate_severity(
            burn_rate, self.critical_threshold, self.warning_threshold,
            self.ELEVATED_BURN_RATE,
        )

        recommendations = generate_burn_rate_recommendations(
            burn_rate, is_critical, is_warning, time_to_exhaustion,
            self.ELEVATED_BURN_RATE,
        )

        return BurnRate(
            calculated_at=current_time,
            slo_name=slo.name,
            window_hours=window_hours,
            burn_rate=burn_rate,
            budget_consumed_in_window=actual_budget_consumed * 100,
            alert_severity=alert_severity,
            time_to_exhaustion_hours=time_to_exhaustion,
            is_critical=is_critical,
            is_warning=is_warning,
            recommendations=recommendations,
        )

    def multi_window_analyze(
        self,
        slo: SLODefinition,
        metrics: Sequence[SLIMetric],
        short_window_hours: float = 5.0 / 60.0,
        long_window_hours: float = 1.0,
        current_time: Optional[datetime] = None,
    ) -> BurnRate:
        """
        Perform multi-window burn rate analysis to reduce false positive alerts.

        The default pair follows the reference design (Google SRE Workbook /
        DEEPTHINK_05): a 1-hour LONG alert window that smooths noise, guarded
        by a 5-minute SHORT window (long/12, the "1/12 rule") that lets the
        alert reset quickly once the burn stops. The previous 1h+6h pairing
        was mis-paired (it used the long window as the guard); callers that
        need it can still pass short_window_hours=1.0, long_window_hours=6.0
        explicitly, but that legacy pairing is deprecated and will be removed.

        For the full tiered policy (page/warn/ticket) use
        evaluate_alert_policy().
        """
        current_time = current_time or datetime.now()

        short_result = self.analyze(slo, metrics, short_window_hours, current_time)
        long_result = self.analyze(slo, metrics, long_window_hours, current_time)

        is_critical = (
            short_result.burn_rate >= self.critical_threshold
            and long_result.burn_rate >= self.critical_threshold
        )
        is_warning = not is_critical and (
            short_result.burn_rate >= self.warning_threshold
            and long_result.burn_rate >= self.warning_threshold
        )

        alert_severity = "none"
        if is_critical:
            alert_severity = "critical"
        elif is_warning:
            alert_severity = "warning"

        recommendations = generate_multi_window_recommendations(
            short_result.burn_rate,
            long_result.burn_rate,
            is_critical,
            is_warning,
            self.warning_threshold,
        )

        return BurnRate(
            calculated_at=current_time,
            slo_name=slo.name,
            window_hours=long_window_hours,
            burn_rate=long_result.burn_rate,
            burn_rate_short=short_result.burn_rate,
            burn_rate_long=long_result.burn_rate,
            budget_consumed_in_window=long_result.budget_consumed_in_window,
            alert_severity=alert_severity,
            time_to_exhaustion_hours=long_result.time_to_exhaustion_hours,
            is_critical=is_critical,
            is_warning=is_warning,
            recommendations=recommendations,
        )

    #: Canonical multi-window multi-burn-rate policy (long_h, short_h = long/12,
    #: threshold, severity) per Google SRE Workbook / DEEPTHINK_05 / RESEARCH_13.
    ALERT_POLICY = (
        ("page_fast", 1.0, 5.0 / 60.0, 14.4, "page"),
        ("page_slow", 6.0, 0.5, 6.0, "warning"),
        ("ticket", 72.0, 6.0, 1.0, "ticket"),
    )

    def evaluate_alert_policy(
        self,
        slo: SLODefinition,
        metrics: Sequence[SLIMetric],
        current_time: Optional[datetime] = None,
    ) -> List[BurnRateAlert]:
        """
        Evaluate the canonical three-tier multi-window burn-rate alert policy.

        Tiers (each fires only when BOTH windows exceed the threshold):
            PAGE_FAST: BR(1h)  >= 14.4 AND BR(5m)  >= 14.4  (2% of 30d budget/h)
            PAGE_SLOW: BR(6h)  >= 6.0  AND BR(30m) >= 6.0   (5% of 30d budget/6h)
            TICKET:    BR(72h) >= 1.0  AND BR(6h)  >= 1.0   (sustained overspend)

        Statistical validity gate: a tier whose long window saw fewer than
        10 / (1 - target) events reports severity="insufficient_traffic" and
        never fires — low-traffic noise must not page anyone (DEEPTHINK_04).

        Detection-limit metadata: each alert carries the minimum detectable
        full outage for both windows (99.9% + 14.4x + 1h -> 51.8 s; the 5m
        guard -> 4.3 s). Note the documented blind spot: a sub-critical bleed
        (e.g. 14.0x for 55 minutes) evades PAGE_FAST by design; the TICKET
        tier is the safety net that catches sustained overspend.

        Returns:
            One BurnRateAlert per tier, in policy order.
        """
        current_time = current_time or datetime.now()
        target_fraction = slo.target / 100.0
        min_events = (
            minimum_traffic_for_target(target_fraction)
            if target_fraction < 1.0
            else 0
        )

        alerts: List[BurnRateAlert] = []
        for tier, long_h, short_h, threshold, severity in self.ALERT_POLICY:
            long_result = self.analyze(slo, metrics, long_h, current_time)
            short_result = self.analyze(slo, metrics, short_h, current_time)

            window_start = current_time - timedelta(hours=long_h)
            total_events_long = sum(
                m.total_events
                for m in metrics
                if window_start <= m.timestamp <= current_time
            )

            insufficient = total_events_long < min_events
            over_threshold = (
                long_result.burn_rate >= threshold
                and short_result.burn_rate >= threshold
            )
            fired = over_threshold and not insufficient

            recommendations: List[str] = []
            if insufficient:
                recommendations.append(
                    f"Only {total_events_long} events in the {long_h:g}h window; "
                    f"{min_events} are required for a statistically valid "
                    f"burn-rate alert at a {slo.target}% target. Options: lower "
                    "the SLO target, widen the alert window, or add synthetic "
                    "probe traffic."
                )
            elif fired:
                recommendations.append(
                    f"{tier}: burn rate {long_result.burn_rate:.1f}x over "
                    f"{long_h:g}h and {short_result.burn_rate:.1f}x over "
                    f"{short_h * 60:.0f}m both exceed {threshold}x."
                )
            if tier == "ticket" and total_events_long > 0 and not insufficient:
                recommendations.append(
                    "Note: sustained burn just below the paging thresholds "
                    "(e.g. 14.0x for 55 minutes) never pages; this ticket tier "
                    "is the documented safety net for that blind spot."
                )

            alerts.append(
                BurnRateAlert(
                    tier=tier,
                    severity=(
                        "insufficient_traffic"
                        if insufficient
                        else severity if fired else "none"
                    ),
                    long_window_hours=long_h,
                    short_window_hours=short_h,
                    threshold=threshold,
                    long_burn_rate=long_result.burn_rate,
                    short_burn_rate=short_result.burn_rate,
                    fired=fired,
                    budget_consumed_pct=long_result.budget_consumed_in_window,
                    total_events_long_window=total_events_long,
                    min_events_required=min_events,
                    insufficient_traffic=insufficient,
                    min_detectable_outage_seconds=(
                        min_detectable_outage_seconds(target_fraction, threshold, long_h)
                        if target_fraction < 1.0
                        else None
                    ),
                    min_detectable_outage_seconds_short=(
                        min_detectable_outage_seconds(target_fraction, threshold, short_h)
                        if target_fraction < 1.0
                        else None
                    ),
                    recommendations=recommendations,
                )
            )
        return alerts

    def derive_thresholds(
        self,
        window_days: float,
        budget_fraction: float = 0.02,
        alert_window_hours: float = 1.0,
    ) -> ThresholdDerivation:
        """
        Derive the burn-rate threshold for a non-30-day SLO window.

        BR = budget_fraction / (alert_window / slo_window). "Page when 2% of
        the budget burns in 1 hour" gives 14.4x for 30 days, 13.44x for 28
        days, 6.72x for 14 days, 3.36x for 7 days.

        The recommendation stays at the 30-day default (14.4x) because
        rescaling destroys the absolute noise floor: a rescaled 7-day 99.9%
        SLO would page on ~12 seconds of downtime (DEEPTHINK_05 section 2).
        The trade-off is surfaced in `recommendations` so the caller can
        make an informed choice.
        """
        if window_days <= 0 or alert_window_hours <= 0:
            raise ValueError("window_days and alert_window_hours must be positive")
        if not 0.0 < budget_fraction < 1.0:
            raise ValueError("budget_fraction must be in (0, 1)")

        slo_window_hours = window_days * 24.0
        derived = budget_fraction / (alert_window_hours / slo_window_hours)

        recommendations = [
            (
                f"Rescaled threshold for a {window_days:g}-day window is "
                f"{derived:.2f}x (burn {budget_fraction:.0%} of budget in "
                f"{alert_window_hours:g}h)."
            ),
            (
                "Recommended default remains 14.4x: rescaling to shorter SLO "
                "windows lowers the absolute noise floor (a rescaled 7-day "
                "99.9% SLO pages on ~12s of downtime), trading fewer missed "
                "slow burns for far more noise pages."
            ),
        ]

        return ThresholdDerivation(
            slo_window_days=window_days,
            alert_window_hours=alert_window_hours,
            budget_fraction=budget_fraction,
            derived_threshold=derived,
            default_threshold=self.CRITICAL_BURN_RATE,
            recommended_threshold=self.CRITICAL_BURN_RATE,
            recommendations=recommendations,
        )

    def analyze_history(
        self,
        slo: SLODefinition,
        metrics: Sequence[SLIMetric],
        window_hours: float = 1.0,
        history_hours: int = 24,
        step_hours: float = 1.0,
    ) -> List[BurnRate]:
        """Analyze burn rate over time, returning a BurnRate for each time step."""
        results = []
        current = datetime.now()
        start = current - timedelta(hours=history_hours)

        analysis_time = start
        while analysis_time <= current:
            result = self.analyze(slo, metrics, window_hours, analysis_time)
            results.append(result)
            analysis_time += timedelta(hours=step_hours)

        return results

    def detect_incidents(
        self,
        burn_rate_history: Sequence[BurnRate],
        min_duration_hours: float = 0.5,
    ) -> List[Tuple[datetime, datetime, str]]:
        """Detect incidents (periods where burn rate exceeds thresholds) from history."""
        incidents = []
        current_incident_start: Optional[datetime] = None
        current_severity: Optional[str] = None

        for burn_rate in sorted(burn_rate_history, key=lambda b: b.calculated_at):
            if burn_rate.is_critical or burn_rate.is_warning:
                severity = "critical" if burn_rate.is_critical else "warning"
                if current_incident_start is None:
                    current_incident_start = burn_rate.calculated_at
                    current_severity = severity
                elif severity == "critical" and current_severity == "warning":
                    current_severity = severity
            else:
                if current_incident_start is not None:
                    duration_hours = (
                        burn_rate.calculated_at - current_incident_start
                    ).total_seconds() / 3600
                    if duration_hours >= min_duration_hours:
                        incidents.append(
                            (
                                current_incident_start,
                                burn_rate.calculated_at,
                                current_severity or "warning",
                            )
                        )
                    current_incident_start = None
                    current_severity = None

        return incidents

    def forecast_budget_exhaustion(
        self,
        current_budget: ErrorBudget,
        burn_rate: BurnRate,
    ) -> Optional[datetime]:
        """Forecast when error budget will be exhausted, or None if safe."""
        if burn_rate.burn_rate <= 1.0:
            return None

        if burn_rate.time_to_exhaustion_hours is None:
            return None

        return cast(datetime, burn_rate.calculated_at) + timedelta(
            hours=cast(float, burn_rate.time_to_exhaustion_hours)
        )
