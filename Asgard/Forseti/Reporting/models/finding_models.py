"""
Finding Models - the canonical Rich Finding object (plan 08).

Every Forseti validator, checker and compat engine ultimately emits
`Finding` objects; all reporters render from this single model.
"""

from typing import Any, Optional

from pydantic import BaseModel, Field

from Asgard.Forseti.Rules.models._rule_base_models import RuleCategory, SchemaFormat, Severity


class Coordinates(BaseModel):
    """Location of a finding inside a document."""

    file: Optional[str] = Field(default=None, description="File path, if known")
    json_path: str = Field(default="/", description="Canonical pointer within the document")
    line: Optional[int] = Field(default=None, description="1-based line (source-mapped)")
    column: Optional[int] = Field(default=None, description="1-based column (source-mapped)")


class Remediation(BaseModel):
    """Machine-actionable fix guidance."""

    description: str = Field(description="How to fix it")
    json_patch: Optional[list[dict[str, Any]]] = Field(
        default=None,
        description="RFC 6902 operations for deterministic auto-fix",
    )


class Finding(BaseModel):
    """A single analysis finding (the Rich Finding of DEEPTHINK_09)."""

    rule_id: str = Field(description="Stable namespaced rule id")
    severity: Severity = Field(description="Fixed objective severity")
    message: str = Field(description="Terse one-sentence message")
    coordinates: Coordinates = Field(default_factory=Coordinates)
    rationale: Optional[str] = Field(default=None, description="Educational payload")
    remediation: Optional[Remediation] = Field(default=None)
    suppressed: bool = Field(default=False)
    suppression_reason: Optional[str] = Field(default=None)
    category: RuleCategory = Field(default=RuleCategory.STRUCTURE)
    format: SchemaFormat = Field(default=SchemaFormat.OPENAPI)

    model_config = {"use_enum_values": False}


class ReportSummary(BaseModel):
    """Aggregate counts across a finding set (active findings only)."""

    errors: int = 0
    warnings: int = 0
    info: int = 0
    hints: int = 0
    suppressed: int = 0

    @classmethod
    def from_findings(cls, findings: list[Finding]) -> "ReportSummary":
        """Compute a summary from a finding list."""
        summary = cls()
        for finding in findings:
            if finding.suppressed:
                summary.suppressed += 1
                continue
            if finding.severity == Severity.ERROR:
                summary.errors += 1
            elif finding.severity == Severity.WARNING:
                summary.warnings += 1
            elif finding.severity == Severity.INFO:
                summary.info += 1
            else:
                summary.hints += 1
        return summary


class ReportEnvelope(BaseModel):
    """Stable machine-readable envelope for JSON output."""

    tool: str = Field(default="forseti")
    version: str = Field(default="0.1.0")
    ruleset_version: str = Field(default="1.0.0")
    findings: list[Finding] = Field(default_factory=list)
    summary: ReportSummary = Field(default_factory=ReportSummary)
    score: Optional[float] = Field(default=None)
