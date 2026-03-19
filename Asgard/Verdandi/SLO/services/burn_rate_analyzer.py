"""
Burn Rate Analyzer Service

Analyzes error budget burn rate for alerting and forecasting.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Sequence, Tuple, cast

from Asgard.Verdandi.SLO.models.slo_models import (
    BurnRate,
    ErrorBudget,
    SLIMetric,
    SLODefinition,
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

    # Default burn rate thresholds (Google SRE book recommendations)
    CRITICAL_BURN_RATE = 14.4  # Page immediately (2% of budget in 1 hour)
    WARNING_BURN_RATE = 6.0  # Create ticket (5% of budget in 6 hours)
    ELEVATED_BURN_RATE = 1.0  # Above sustainable rate

    def __init__(
        self,
        critical_threshold: float = 14.4,
        warning_threshold: float = 6.0,
    ):
        """
        Initialize the burn rate analyzer.

        Args:
            critical_threshold: Burn rate threshold for critical alerts
            warning_threshold: Burn rate threshold for warning alerts
        """
        self.critical_threshold = critical_threshold
        self.warning_threshold = warning_threshold

    def analyze(
        self,
        slo: SLODefinition,
        metrics: Sequence[SLIMetric],
        window_hours: float = 1.0,
        current_time: Optional[datetime] = None,
    ) -> BurnRate:
        """
        Analyze burn rate for a single time window.

        Args:
            slo: The SLO definition
            metrics: SLI metrics
            window_hours: Analysis window in hours
            current_time: Current time for calculations

        Returns:
            BurnRate analysis result
        """
        current_time = current_time or datetime.now()
        window_start = current_time - timedelta(hours=window_hours)

        # Filter metrics to window
        window_metrics = [
            m
            for m in metrics
            if m.timestamp >= window_start and m.timestamp <= current_time
        ]

        # Calculate events in window
        total_events = sum(m.total_events for m in window_metrics)
        good_events = sum(m.good_events for m in window_metrics)
        bad_events = total_events - good_events

        # Calculate burn rate
        # Burn rate = (actual failure rate) / (allowed failure rate)
        error_budget_fraction = (100.0 - slo.target) / 100.0  # e.g., 0.001 for 99.9%
        slo_window_hours = slo.window_days * 24

        # Expected budget consumption for this window at sustainable rate
        expected_budget_per_hour = 1.0 / slo_window_hours  # Fraction of budget per hour
        expected_budget_in_window = expected_budget_per_hour * window_hours

        # Actual budget consumption
        actual_failure_rate = bad_events / total_events if total_events > 0 else 0.0
        actual_budget_consumed = actual_failure_rate / error_budget_fraction if error_budget_fraction > 0 else 0.0

        # Burn rate
        burn_rate = (
            actual_budget_consumed / expected_budget_in_window
            if expected_budget_in_window > 0
            else 0.0
        )

        # Calculate time to exhaustion
        time_to_exhaustion = self._calculate_time_to_exhaustion(
            burn_rate, slo.window_days * 24
        )

        # Determine alert severity
        is_critical = burn_rate >= self.critical_threshold
        is_warning = not is_critical and burn_rate >= self.warning_threshold
        alert_severity = self._determine_severity(burn_rate)

        # Generate recommendations
        recommendations = self._generate_recommendations(
            burn_rate, is_critical, is_warning, time_to_exhaustion
        )

        return BurnRate(
            calculated_at=current_time,
            slo_name=slo.name,
            window_hours=window_hours,
            burn_rate=burn_rate,
            budget_consumed_in_window=actual_budget_consumed * 100,  # As percentage
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
        short_window_hours: float = 1.0,
        long_window_hours: float = 6.0,
        current_time: Optional[datetime] = None,
    ) -> BurnRate:
        """
        Perform multi-window burn rate analysis.

        Multi-window alerting reduces false positives by requiring both
        short and long window thresholds to be exceeded.

        Args:
            slo: The SLO definition
            metrics: SLI metrics
            short_window_hours: Short analysis window
            long_window_hours: Long analysis window
            current_time: Current time for calculations

        Returns:
            BurnRate with both short and long window rates
        """
        current_time = current_time or datetime.now()

        # Analyze both windows
        short_result = self.analyze(slo, metrics, short_window_hours, current_time)
        long_result = self.analyze(slo, metrics, long_window_hours, current_time)

        # Multi-window alert logic:
        # Critical: short >= 14.4 AND long >= 14.4
        # Warning: short >= 6.0 AND long >= 6.0
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

        recommendations = self._generate_multi_window_recommendations(
            short_result.burn_rate,
            long_result.burn_rate,
            is_critical,
            is_warning,
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

    def analyze_history(
        self,
        slo: SLODefinition,
        metrics: Sequence[SLIMetric],
        window_hours: float = 1.0,
        history_hours: int = 24,
        step_hours: float = 1.0,
    ) -> List[BurnRate]:
        """
        Analyze burn rate over time.

        Args:
            slo: The SLO definition
            metrics: SLI metrics
            window_hours: Size of each analysis window
            history_hours: How far back to analyze
            step_hours: Time step between analyses

        Returns:
            List of BurnRate for each time step
        """
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
        """
        Detect incidents from burn rate history.

        An incident is a period where burn rate exceeds thresholds.

        Args:
            burn_rate_history: Historical burn rate analyses
            min_duration_hours: Minimum incident duration to report

        Returns:
            List of (start_time, end_time, severity) tuples
        """
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
                    # Upgrade severity
                    current_severity = severity
            else:
                if current_incident_start is not None:
                    # End incident
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
        """
        Forecast when error budget will be exhausted.

        Args:
            current_budget: Current error budget status
            burn_rate: Current burn rate

        Returns:
            Datetime when budget will be exhausted, or None if safe
        """
        if burn_rate.burn_rate <= 1.0:
            # Budget is sustainable or being replenished
            return None

        if burn_rate.time_to_exhaustion_hours is None:
            return None

        return cast(datetime, burn_rate.calculated_at) + timedelta(
            hours=cast(float, burn_rate.time_to_exhaustion_hours)
        )

    def _calculate_time_to_exhaustion(
        self,
        burn_rate: float,
        slo_window_hours: float,
    ) -> Optional[float]:
        """Calculate hours until budget exhaustion at current burn rate."""
        if burn_rate <= 0:
            return None  # No consumption

        if burn_rate <= 1.0:
            return None  # Sustainable rate

        # At burn rate X, budget depletes X times faster
        # Time to exhaustion = remaining window / burn_rate
        # Simplified: assume full budget available at start of window
        return slo_window_hours / burn_rate

    def _determine_severity(self, burn_rate: float) -> str:
        """Determine alert severity from burn rate."""
        if burn_rate >= self.critical_threshold:
            return "critical"
        elif burn_rate >= self.warning_threshold:
            return "warning"
        elif burn_rate >= self.ELEVATED_BURN_RATE:
            return "elevated"
        return "none"

    def _generate_recommendations(
        self,
        burn_rate: float,
        is_critical: bool,
        is_warning: bool,
        time_to_exhaustion: Optional[float],
    ) -> List[str]:
        """Generate recommendations based on burn rate analysis."""
        recommendations = []

        if is_critical:
            recommendations.append(
                f"CRITICAL: Error budget burning at {burn_rate:.1f}x sustainable rate. "
                "Immediate action required."
            )
            if time_to_exhaustion:
                recommendations.append(
                    f"Budget will be exhausted in approximately {time_to_exhaustion:.1f} hours "
                    "at current rate."
                )
            recommendations.append(
                "Review recent deployments, rollback if necessary, and investigate error sources."
            )
        elif is_warning:
            recommendations.append(
                f"Warning: Error budget burning at {burn_rate:.1f}x sustainable rate. "
                "Investigation recommended."
            )
            recommendations.append(
                "Create ticket to investigate elevated error rates before budget exhaustion."
            )
        elif burn_rate > 1.0:
            recommendations.append(
                f"Error budget consumption elevated at {burn_rate:.1f}x sustainable rate. "
                "Monitor closely."
            )

        return recommendations

    def _generate_multi_window_recommendations(
        self,
        short_burn_rate: float,
        long_burn_rate: float,
        is_critical: bool,
        is_warning: bool,
    ) -> List[str]:
        """Generate recommendations for multi-window analysis."""
        recommendations = []

        if is_critical:
            recommendations.append(
                f"CRITICAL: Both short ({short_burn_rate:.1f}x) and long ({long_burn_rate:.1f}x) "
                "windows show critical burn rate. Page on-call immediately."
            )
        elif is_warning:
            recommendations.append(
                f"Warning: Both windows show elevated burn rate "
                f"(short: {short_burn_rate:.1f}x, long: {long_burn_rate:.1f}x). "
                "Create ticket for investigation."
            )
        elif short_burn_rate >= self.warning_threshold > long_burn_rate:
            recommendations.append(
                f"Short window burn rate elevated ({short_burn_rate:.1f}x) but long window "
                f"still acceptable ({long_burn_rate:.1f}x). Monitor for persistence."
            )
        elif short_burn_rate < long_burn_rate and long_burn_rate > 1.0:
            recommendations.append(
                "Burn rate improving recently. Continue monitoring recovery."
            )

        return recommendations
