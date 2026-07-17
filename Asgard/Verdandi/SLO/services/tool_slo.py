"""
Verdandi Self-SLOs ("the tool eats its own SLO machinery")

Verdandi is itself a batch analysis tool and ships with its own SLO
framework (DEEPTHINK_01):

    Analytical Yield      >= 99.5% / 28d  -- (scored + valid_rejections) / submitted
    Freshness/Time-to-Insight  95% / 28d @ 15 min default -- report_ready - data_closed <= threshold
    Retrospective Incident Recall  85% / 90d lagged 14d -- overlap of Sev1/2 incidents with findings
    Actionability Rate     > 30% / 28d -- acknowledged_high_sev / total_high_sev

INSUFFICIENT_DATA outcomes are successes here too: a valid rejection is not
a failure and burns nothing (DEEPTHINK_01).
"""

from datetime import datetime, timedelta
from enum import Enum
from typing import List, Optional, Sequence

from pydantic import BaseModel, Field

from Asgard.Verdandi.SLO.models.slo_models import SLIMetric, SLOType


class RunOutcome(str, Enum):
    """Typed outcome accounting for a single submitted entity in a run."""

    SCORED = "scored"
    VALID_REJECTION = "valid_rejection"
    FAILED = "failed"


class Finding(BaseModel):
    """A single finding emitted by a Verdandi run, for actionability/recall SLIs."""

    id: str = Field(...)
    severity: str = Field(..., description="e.g. 'sev1', 'sev2', 'high', 'medium', 'low'")
    acknowledged: bool = Field(default=False)
    timestamp: Optional[datetime] = Field(default=None)


class Incident(BaseModel):
    """An external, known incident used for retrospective recall evaluation."""

    id: str = Field(...)
    severity: str = Field(..., description="e.g. 'sev1', 'sev2'")
    started_at: datetime = Field(...)
    ended_at: Optional[datetime] = Field(default=None)


class RunRecord(BaseModel):
    """
    Run-report shaped input: every Verdandi CLI/batch invocation can emit
    one of these.
    """

    entities_submitted: int = Field(..., description="Entities offered to this run")
    entities_scored: int = Field(default=0, description="Entities that produced a real result")
    valid_rejections: int = Field(
        default=0,
        description="Entities honestly rejected as INSUFFICIENT_DATA (a success, not a failure)",
    )
    entities_failed: int = Field(
        default=0,
        description="Entities that errored/crashed (accounted infrastructure failures)",
    )
    run_started: datetime = Field(...)
    data_closed_at: datetime = Field(..., description="When the underlying telemetry window closed")
    report_ready_at: datetime = Field(..., description="When the run's report was produced")
    findings: List[Finding] = Field(default_factory=list)

    @property
    def accounted(self) -> int:
        """Entities with a known disposition (scored + rejected + failed)."""
        return self.entities_scored + self.valid_rejections + self.entities_failed

    @property
    def silent_drop(self) -> int:
        """Entities submitted but with no accounted disposition -- an integrity error."""
        return max(0, self.entities_submitted - self.accounted)

    @property
    def has_integrity_error(self) -> bool:
        """True when some submitted entities silently vanished (unaccounted)."""
        return self.silent_drop > 0


class SelfSLOResult(BaseModel):
    """Result of evaluating one Verdandi self-SLI."""

    sli_name: str = Field(...)
    value: Optional[float] = Field(default=None, description="Fraction in [0, 1]; None if INSUFFICIENT_DATA")
    target: float = Field(..., description="Target fraction for this SLI")
    meets_target: Optional[bool] = Field(default=None)
    insufficient_data: bool = Field(default=False)
    governance: str = Field(
        default="normal",
        description="'normal' (feeds error budgets) or 'data_science_freeze' (annotation only)",
    )
    integrity_errors: List[str] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)


class ToolSelfSLOCalculator:
    """
    Calculators for Verdandi's own self-measurement SLOs. These reuse
    SLIMetric/SLOType so results can be fed straight into SLITracker /
    ErrorBudgetCalculator -- the tool eats its own SLO machinery.
    """

    ANALYTICAL_YIELD_TARGET = 0.995
    FRESHNESS_TARGET = 0.95
    FRESHNESS_DEFAULT_MINUTES = 15.0
    INCIDENT_RECALL_TARGET = 0.85
    INCIDENT_RECALL_LAG_DAYS = 14
    ACTIONABILITY_TARGET = 0.30

    def analytical_yield(self, run: RunRecord) -> SelfSLOResult:
        """
        (scored + valid_rejections) / submitted; target 99.5%/28d.

        A silent drop (submitted > scored + rejections + failed) is an
        integrity error and is surfaced, not silently absorbed into the
        yield fraction.
        """
        integrity_errors = []
        if run.has_integrity_error:
            integrity_errors.append(
                f"{run.silent_drop} of {run.entities_submitted} submitted entities have "
                "no accounted disposition (not scored, rejected, or failed) -- possible "
                "silent drop / pipeline integrity error."
            )

        if run.entities_submitted <= 0:
            return SelfSLOResult(
                sli_name="analytical_yield",
                target=self.ANALYTICAL_YIELD_TARGET,
                insufficient_data=True,
                notes=["No entities submitted."],
                integrity_errors=integrity_errors,
            )

        yield_fraction = (run.entities_scored + run.valid_rejections) / run.entities_submitted

        return SelfSLOResult(
            sli_name="analytical_yield",
            value=round(yield_fraction, 6),
            target=self.ANALYTICAL_YIELD_TARGET,
            meets_target=yield_fraction >= self.ANALYTICAL_YIELD_TARGET,
            integrity_errors=integrity_errors,
        )

    def analytical_yield_sli_metric(
        self, run: RunRecord, service_name: str = "verdandi"
    ) -> SLIMetric:
        """Package analytical yield as an SLIMetric for SLITracker.record()."""
        return SLIMetric(
            timestamp=run.report_ready_at,
            service_name=service_name,
            slo_type=SLOType.QUALITY,
            good_events=run.entities_scored,
            rejected_events=run.valid_rejections,
            total_events=run.entities_submitted,
        )

    def freshness(
        self,
        runs: Sequence[RunRecord],
        threshold_minutes: float = FRESHNESS_DEFAULT_MINUTES,
    ) -> SelfSLOResult:
        """
        Fraction of runs where report_ready_at - data_closed_at <=
        threshold; target 95% @ 15 min default.
        """
        if not runs:
            return SelfSLOResult(
                sli_name="freshness",
                target=self.FRESHNESS_TARGET,
                insufficient_data=True,
                notes=["No runs supplied."],
            )

        fresh = sum(
            1
            for r in runs
            if (r.report_ready_at - r.data_closed_at) <= timedelta(minutes=threshold_minutes)
        )
        fraction = fresh / len(runs)

        return SelfSLOResult(
            sli_name="freshness",
            value=round(fraction, 6),
            target=self.FRESHNESS_TARGET,
            meets_target=fraction >= self.FRESHNESS_TARGET,
            notes=[f"{fresh}/{len(runs)} runs within {threshold_minutes:g} min of data close."],
        )

    def incident_recall(
        self,
        incidents: Sequence[Incident],
        findings: Sequence[Finding],
        overlap_window: timedelta = timedelta(hours=1),
        high_severities: Sequence[str] = ("sev1", "sev2"),
    ) -> SelfSLOResult:
        """
        Fraction of Sev1/2 incidents with an overlapping high-severity
        finding within `overlap_window` of the incident start. Evaluated
        over a 90-day window, lagged 14 days (incidents need time to be
        confirmed/classified before recall can be judged fairly).

        Explicitly `governance="data_science_freeze"`: this is a slow,
        offline quality metric for Verdandi's detectors, not a paging
        signal (DEEPTHINK_01 section 2).
        """
        relevant = [i for i in incidents if i.severity.lower() in high_severities]

        if not relevant:
            return SelfSLOResult(
                sli_name="incident_recall",
                target=self.INCIDENT_RECALL_TARGET,
                insufficient_data=True,
                governance="data_science_freeze",
                notes=["No Sev1/Sev2 incidents in the evaluation window."],
            )

        high_sev_findings = [f for f in findings if f.timestamp is not None]

        recalled = 0
        for incident in relevant:
            window_start = incident.started_at - overlap_window
            window_end = (incident.ended_at or incident.started_at) + overlap_window
            if any(window_start <= f.timestamp <= window_end for f in high_sev_findings):
                recalled += 1

        fraction = recalled / len(relevant)

        return SelfSLOResult(
            sli_name="incident_recall",
            value=round(fraction, 6),
            target=self.INCIDENT_RECALL_TARGET,
            meets_target=fraction >= self.INCIDENT_RECALL_TARGET,
            governance="data_science_freeze",
            notes=[f"{recalled}/{len(relevant)} Sev1/Sev2 incidents had an overlapping finding."],
        )

    def actionability(
        self,
        findings: Sequence[Finding],
        high_severities: Sequence[str] = ("high", "sev1", "sev2"),
    ) -> SelfSLOResult:
        """
        acknowledged_high_sev / total_high_sev; target > 30%/28d. Measures
        whether Verdandi's high-severity findings actually get acted on
        (vs. ignored / drowned in noise).
        """
        high_sev = [f for f in findings if f.severity.lower() in high_severities]

        if not high_sev:
            return SelfSLOResult(
                sli_name="actionability",
                target=self.ACTIONABILITY_TARGET,
                insufficient_data=True,
                notes=["No high-severity findings in the evaluation window."],
            )

        acknowledged = sum(1 for f in high_sev if f.acknowledged)
        fraction = acknowledged / len(high_sev)

        return SelfSLOResult(
            sli_name="actionability",
            value=round(fraction, 6),
            target=self.ACTIONABILITY_TARGET,
            meets_target=fraction > self.ACTIONABILITY_TARGET,
            notes=[f"{acknowledged}/{len(high_sev)} high-severity findings acknowledged."],
        )
