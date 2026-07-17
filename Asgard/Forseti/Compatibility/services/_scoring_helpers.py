"""
Scoring Helpers - the Unified Compatibility Score (DEEPTHINK_04).

score = max(0, 100 - sum(base_severity x temporal_penalty x blast_radius
x usage_probability)), explained line-by-line by the Blast Radius Receipt.
"""

from typing import Optional

from Asgard.Forseti.Compatibility.models._compat_base_models import (
    CompatStatus,
    EmpiricalVerdict,
    TierVerdict,
)
from Asgard.Forseti.Compatibility.models.compat_models import (
    TelemetrySource,
    UnifiedChange,
)
from Asgard.Forseti.Rules.models._rule_base_models import SchemaFormat

# Per-paradigm temporal penalty: immutable event logs are poison pills.
TEMPORAL_PENALTIES: dict[SchemaFormat, float] = {
    SchemaFormat.OPENAPI: 1.0,
    SchemaFormat.GRAPHQL: 1.0,
    SchemaFormat.JSONSCHEMA: 1.0,
    SchemaFormat.CONTRACT: 1.0,
    SchemaFormat.SQL: 1.0,
    SchemaFormat.PROTOBUF: 1.5,
    SchemaFormat.AVRO: 5.0,
    SchemaFormat.ASYNCAPI: 5.0,
}


def temporal_penalty(fmt: SchemaFormat) -> float:
    """Temporal penalty multiplier for a schema format."""
    return TEMPORAL_PENALTIES.get(fmt, 1.0)


def usage_probability(change: UnifiedChange) -> float:
    """Usage probability: 1.0 unless telemetry proved the element unused."""
    if change.impact.empirical == EmpiricalVerdict.SAFE_UNUSED:
        return 0.0
    return 1.0


def deduction(change: UnifiedChange) -> float:
    """One change's score deduction."""
    if change.waived:
        return 0.0
    return (
        change.base_severity
        * temporal_penalty(change.format)
        * change.blast_radius
        * usage_probability(change)
    )


def compute_score(changes: list[UnifiedChange]) -> tuple[int, list[str]]:
    """Compute the 0-100 score plus the Blast Radius Receipt lines."""
    total = 0.0
    receipt: list[str] = []
    for change in changes:
        d = deduction(change)
        total += d
        note = ""
        if change.waived:
            note = " [WAIVED]"
        elif change.impact.empirical == EmpiricalVerdict.SAFE_UNUSED:
            note = " [UNUSED - telemetry]"
        receipt.append(
            f"-{d:g} {change.rule_id} @ {change.location} "
            f"(base {change.base_severity} x temporal "
            f"{temporal_penalty(change.format):g} x blast {change.blast_radius})"
            f"{note}"
        )
    score = max(0, round(100 - total))
    return score, receipt


def compute_status(changes: list[UnifiedChange]) -> CompatStatus:
    """FAILED on any active structural FAIL; CONDITIONAL on hazards only."""
    active = [c for c in changes if not c.waived]
    failing = [
        c for c in active
        if c.impact.structural == TierVerdict.FAIL
        and c.impact.empirical != EmpiricalVerdict.SAFE_UNUSED
    ]
    if failing:
        return CompatStatus.FAILED
    hazardous = [
        c for c in active
        if c.impact.structural in (TierVerdict.FAIL, TierVerdict.HAZARD)
        or c.impact.semantic in (TierVerdict.FAIL, TierVerdict.HAZARD)
    ]
    if hazardous:
        return CompatStatus.CONDITIONALLY_PASSED
    return CompatStatus.PASSED


def apply_telemetry(
    changes: list[UnifiedChange],
    telemetry: Optional[TelemetrySource],
) -> str:
    """Annotate changes with empirical verdicts. Returns confidence level."""
    if telemetry is None:
        return "high"
    low_confidence = False
    for change in changes:
        stats = telemetry.get_usage(change.location)
        if stats is None:
            change.impact.empirical = EmpiricalVerdict.UNKNOWN
            continue
        if stats.low_confidence:
            low_confidence = True
        change.impact.empirical = (
            EmpiricalVerdict.SAFE_UNUSED if stats.call_count == 0
            else EmpiricalVerdict.ACTIVE
        )
    return "low" if low_confidence else "high"
