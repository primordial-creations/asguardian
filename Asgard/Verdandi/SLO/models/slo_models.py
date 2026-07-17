"""
SLO Models

Pydantic models for Service Level Objectives, including SLO definitions,
SLI metrics, error budgets, and burn rate analysis.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SLOType(str, Enum):
    """Type of SLO measurement."""

    AVAILABILITY = "availability"
    LATENCY = "latency"
    THROUGHPUT = "throughput"
    ERROR_RATE = "error_rate"
    QUALITY = "quality"
    FRESHNESS = "freshness"


class SLOComplianceStatus(str, Enum):
    """Status of SLO compliance."""

    COMPLIANT = "compliant"
    AT_RISK = "at_risk"
    BREACHED = "breached"
    UNKNOWN = "unknown"


class SLODefinition(BaseModel):
    """
    Definition of a Service Level Objective.

    An SLO defines the target level of reliability for a service
    based on one or more SLIs.
    """

    name: str = Field(..., description="Name of the SLO")
    description: Optional[str] = Field(
        default=None, description="Human-readable description"
    )
    slo_type: SLOType = Field(..., description="Type of SLO")
    target: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Target percentage (e.g., 99.9 for 99.9% availability)",
    )
    window_days: int = Field(
        default=30, description="Rolling window in days for SLO calculation"
    )
    service_name: str = Field(..., description="Name of the service")
    labels: Dict[str, str] = Field(
        default_factory=dict, description="Additional labels/tags"
    )
    threshold_ms: Optional[float] = Field(
        default=None, description="Latency threshold for latency SLOs"
    )
    percentile: Optional[float] = Field(
        default=None, description="Target percentile for latency SLOs (e.g., 99)"
    )
    external_sla_target: Optional[float] = Field(
        default=None,
        description=(
            "Contractual external SLA target percentage. Meta-SLO buffer "
            "policy (RESEARCH_13) requires this internal target to be "
            "strictly tighter than the external SLA so budget is exhausted "
            "internally before the SLA is breached."
        ),
    )

    @property
    def error_budget_percent(self) -> float:
        """Calculate error budget as percentage."""
        return 100.0 - self.target


class SLIMetric(BaseModel):
    """
    A single SLI measurement.

    An SLI (Service Level Indicator) is a quantitative measure of
    some aspect of the service level.
    """

    timestamp: datetime = Field(..., description="Timestamp of the measurement")
    service_name: str = Field(..., description="Name of the service")
    slo_type: SLOType = Field(..., description="Type of SLI")
    good_events: int = Field(
        default=0, description="Number of good events (meeting SLO)"
    )
    total_events: int = Field(default=0, description="Total number of events")
    value: float = Field(
        default=0.0, description="Direct value (for non-event-based SLIs)"
    )
    rejected_events: int = Field(
        default=0,
        description=(
            "Valid rejections (e.g. typed INSUFFICIENT_DATA outcomes) within "
            "total_events. Rejections are not failures: they never consume "
            "error budget (DEEPTHINK_01)."
        ),
    )
    labels: Dict[str, str] = Field(
        default_factory=dict, description="Additional labels/tags"
    )

    @property
    def success_rate(self) -> float:
        """Calculate success rate from good/total events."""
        if self.total_events == 0:
            return 1.0
        return self.good_events / self.total_events

    @property
    def failure_rate(self) -> float:
        """Calculate failure rate."""
        return 1.0 - self.success_rate

    @property
    def bad_events(self) -> int:
        """Events that are neither good nor validly rejected (budget-consuming)."""
        return max(0, self.total_events - self.good_events - self.rejected_events)


class ErrorBudget(BaseModel):
    """
    Error budget calculation result.

    Error budget represents the acceptable amount of downtime or errors
    within the SLO window.
    """

    slo_name: str = Field(..., description="Name of the associated SLO")
    slo_target: float = Field(..., description="SLO target percentage")
    window_days: int = Field(..., description="SLO window in days")
    calculated_at: datetime = Field(
        default_factory=datetime.now, description="Calculation timestamp"
    )
    total_events: int = Field(default=0, description="Total events in window")
    good_events: int = Field(default=0, description="Good events in window")
    bad_events: int = Field(default=0, description="Bad events in window")
    current_sli: float = Field(
        default=0.0, ge=0.0, le=100.0, description="Current SLI percentage"
    )
    allowed_failures: float = Field(
        default=0.0, description="Total allowed failures in window"
    )
    consumed_failures: int = Field(
        default=0, description="Failures consumed so far"
    )
    remaining_budget: float = Field(
        default=0.0, description="Remaining error budget (can be negative)"
    )
    budget_consumed_percent: float = Field(
        default=0.0, description="Percentage of error budget consumed"
    )
    status: SLOComplianceStatus = Field(
        default=SLOComplianceStatus.UNKNOWN, description="Compliance status"
    )
    time_remaining_days: float = Field(
        default=0.0, description="Days remaining in window"
    )
    projected_budget_at_window_end: Optional[float] = Field(
        default=None, description="Projected remaining budget at window end"
    )

    @property
    def is_budget_exhausted(self) -> bool:
        """Check if error budget is exhausted."""
        return self.remaining_budget <= 0

    @property
    def budget_remaining_percent(self) -> float:
        """Get remaining budget as percentage."""
        return max(0.0, 100.0 - self.budget_consumed_percent)


class BurnRate(BaseModel):
    """
    Burn rate analysis for error budget.

    Burn rate measures how fast the error budget is being consumed.
    A burn rate of 1.0 means budget is being consumed at exactly the
    expected rate to hit 0 at the end of the window.
    """

    calculated_at: datetime = Field(
        default_factory=datetime.now, description="Calculation timestamp"
    )
    slo_name: str = Field(..., description="Name of the associated SLO")
    window_hours: float = Field(..., description="Analysis window in hours")
    burn_rate: float = Field(
        ..., description="Current burn rate (1.0 = sustainable rate)"
    )
    burn_rate_short: Optional[float] = Field(
        default=None, description="Short-window burn rate (e.g., 1 hour)"
    )
    burn_rate_long: Optional[float] = Field(
        default=None, description="Long-window burn rate (e.g., 6 hours)"
    )
    budget_consumed_in_window: float = Field(
        default=0.0, description="Budget consumed in the analysis window"
    )
    alert_severity: str = Field(
        default="none", description="Severity of any triggered alerts"
    )
    time_to_exhaustion_hours: Optional[float] = Field(
        default=None, description="Hours until budget exhaustion at current rate"
    )
    is_critical: bool = Field(
        default=False, description="Whether burn rate is critically high"
    )
    is_warning: bool = Field(
        default=False, description="Whether burn rate is warning level"
    )
    recommendations: List[str] = Field(
        default_factory=list, description="Recommended actions"
    )


class BurnRateAlert(BaseModel):
    """
    One tier of the multi-window multi-burn-rate alert policy.

    Each tier pairs a LONG alert window (smooths noise) with a SHORT guard
    window at 1/12 of the long window (resets quickly once the burn stops).
    The tier fires only when BOTH windows exceed the tier threshold.
    """

    tier: str = Field(
        ..., description="Policy tier: page_fast, page_slow, or ticket"
    )
    severity: str = Field(
        ...,
        description="page / warning / ticket / none / insufficient_traffic",
    )
    long_window_hours: float = Field(..., description="Long (alert) window")
    short_window_hours: float = Field(..., description="Short (guard) window")
    threshold: float = Field(..., description="Burn-rate threshold for this tier")
    long_burn_rate: float = Field(..., description="Burn rate over the long window")
    short_burn_rate: float = Field(..., description="Burn rate over the short window")
    fired: bool = Field(default=False, description="Whether this tier fired")
    budget_consumed_pct: float = Field(
        default=0.0,
        description="Percent of total error budget consumed in the long window",
    )
    total_events_long_window: int = Field(
        default=0, description="Total events observed in the long window"
    )
    min_events_required: int = Field(
        default=0,
        description="Minimum events for statistical validity: 10 / (1 - target)",
    )
    insufficient_traffic: bool = Field(
        default=False,
        description=(
            "True when the long window had too few events for the alert to be "
            "statistically valid; the tier never fires in this state"
        ),
    )
    min_detectable_outage_seconds: Optional[float] = Field(
        default=None,
        description=(
            "Detection limit: shortest full outage that can trip the long "
            "window at this threshold"
        ),
    )
    min_detectable_outage_seconds_short: Optional[float] = Field(
        default=None,
        description="Detection limit for the short (guard) window",
    )
    recommendations: List[str] = Field(
        default_factory=list, description="Recommended actions"
    )


class ThresholdDerivation(BaseModel):
    """
    Window-scaled burn-rate threshold derivation (DEEPTHINK_05).

    BR_threshold = budget_fraction / (alert_window / slo_window). The 14.4x
    default is exact only for 30-day windows; rescaling for shorter windows
    destroys the absolute noise floor, so the default recommendation stays
    14.4 with the trade-off surfaced in `recommendations`.
    """

    slo_window_days: float = Field(..., description="SLO window in days")
    alert_window_hours: float = Field(..., description="Alert window in hours")
    budget_fraction: float = Field(
        ..., description="Fraction of total budget consumed to trigger (e.g. 0.02)"
    )
    derived_threshold: float = Field(
        ..., description="Window-rescaled burn-rate threshold"
    )
    default_threshold: float = Field(
        default=14.4, description="Reference 30-day default threshold"
    )
    recommended_threshold: float = Field(
        ..., description="Recommended threshold to actually configure"
    )
    recommendations: List[str] = Field(
        default_factory=list,
        description="Caveats, including the absolute-noise-floor trade-off",
    )


class SLOReport(BaseModel):
    """Comprehensive SLO compliance report."""

    generated_at: datetime = Field(
        default_factory=datetime.now, description="Report generation timestamp"
    )
    report_period_start: datetime = Field(..., description="Start of report period")
    report_period_end: datetime = Field(..., description="End of report period")
    service_name: str = Field(..., description="Name of the service")
    slo_definitions: List[SLODefinition] = Field(
        default_factory=list, description="SLO definitions evaluated"
    )
    error_budgets: List[ErrorBudget] = Field(
        default_factory=list, description="Error budget calculations"
    )
    burn_rates: List[BurnRate] = Field(
        default_factory=list, description="Burn rate analyses"
    )
    overall_compliance: SLOComplianceStatus = Field(
        default=SLOComplianceStatus.UNKNOWN, description="Overall compliance status"
    )
    slos_compliant: int = Field(default=0, description="Number of compliant SLOs")
    slos_at_risk: int = Field(default=0, description="Number of at-risk SLOs")
    slos_breached: int = Field(default=0, description="Number of breached SLOs")
    total_slos: int = Field(default=0, description="Total number of SLOs")
    critical_alerts: List[str] = Field(
        default_factory=list, description="Critical alert messages"
    )
    warnings: List[str] = Field(default_factory=list, description="Warning messages")
    recommendations: List[str] = Field(
        default_factory=list, description="Improvement recommendations"
    )

    @property
    def compliance_percentage(self) -> float:
        """Calculate percentage of SLOs in compliance."""
        if self.total_slos == 0:
            return 100.0
        return (self.slos_compliant / self.total_slos) * 100.0
