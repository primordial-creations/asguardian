"""
Rule Models - RuleMeta, Profile, SuppressionEntry, BaselineEntry, WaiverEntry.

The rule contract of plan 02: every rule carries metadata on the
Target / Cost / Confidence axes plus a fixed severity, and governance
artifacts (suppressions, baselines, waivers) are first-class models.
"""

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field, model_validator

from Asgard.Forseti.Rules.models._rule_base_models import (
    Confidence,
    Cost,
    RuleCategory,
    SchemaFormat,
    Severity,
    Target,
)


class RuleMeta(BaseModel):
    """Metadata describing a single registered rule."""

    rule_id: str = Field(description="Stable namespaced id, e.g. 'oas.paths.path-format'")
    formats: set[SchemaFormat] = Field(description="Formats the rule applies to")
    target: Target = Field(default=Target.SCHEMA, description="Schema vs payload rule")
    cost: Cost = Field(default=Cost.ON, description="Execution cost class")
    confidence: Confidence = Field(
        default=Confidence.DETERMINISTIC,
        description="Deterministic vs heuristic",
    )
    severity: Severity = Field(description="Fixed objective severity")
    category: RuleCategory = Field(default=RuleCategory.STRUCTURE, description="Rule category")
    description: str = Field(default="", description="One-line description")
    rationale: str = Field(default="", description="Why this matters (educational payload)")
    core: bool = Field(
        default=False,
        description="Inviolable core rule: can never be disabled or downgraded",
    )
    legacy_ids: set[str] = Field(
        default_factory=set,
        description="Pre-registry rule strings this rule id supersedes",
    )

    @model_validator(mode="after")
    def _enforce_severity_discipline(self) -> "RuleMeta":
        """Heuristic rules may never be ERROR; core rules must be deterministic."""
        if self.confidence == Confidence.HEURISTIC and self.severity == Severity.ERROR:
            raise ValueError(
                f"Rule '{self.rule_id}': heuristic rules may never carry ERROR severity"
            )
        if self.core and self.confidence == Confidence.HEURISTIC:
            raise ValueError(f"Rule '{self.rule_id}': core rules must be deterministic")
        return self


class PathOverride(BaseModel):
    """Per-path-glob rule overrides from a config file."""

    path: str = Field(description="Glob pattern relative to repo root")
    rules: dict[str, str] = Field(
        default_factory=dict,
        description="rule-id pattern -> 'off' | severity name",
    )


class Profile(BaseModel):
    """A validation profile: rule selection + execution contract."""

    name: str = Field(description="Profile name (ide, pre-commit, ci, audit, custom)")
    max_cost: Cost = Field(default=Cost.NETWORK, description="Highest allowed rule cost")
    deterministic_only: bool = Field(
        default=False,
        description="Select only deterministic rules",
    )
    budget_ms: Optional[int] = Field(default=None, description="Time budget, None = unbounded")
    fail_open: bool = Field(
        default=False,
        description="On budget exhaustion / internal error, pass instead of fail",
    )
    blocking: str = Field(
        default="hard",
        description="'never' | 'soft' | 'hard' | 'report'",
    )
    rule_overrides: dict[str, str] = Field(
        default_factory=dict,
        description="rule-id pattern -> 'off' | severity name (non-core only)",
    )
    path_overrides: list[PathOverride] = Field(default_factory=list)


class ForsetiConfig(BaseModel):
    """Parsed `.forseti.yaml` repository configuration."""

    version: int = Field(default=1)
    ruleset_version: Optional[str] = Field(
        default=None,
        description="Pinned ruleset version (DEEPTHINK_11 determinism)",
    )
    profile: str = Field(default="ci", description="Selected profile name")
    rules: dict[str, str] = Field(default_factory=dict)
    overrides: list[PathOverride] = Field(default_factory=list)


class SuppressionEntry(BaseModel):
    """An inline suppression (x-forseti-ignore / forseti:ignore comment)."""

    rule: str = Field(description="Rule id or glob pattern being suppressed")
    reason: Optional[str] = Field(default=None, description="Mandatory human reason")
    scope: str = Field(default="", description="JSON-path prefix (or 'line:<n>') scoped to")

    @property
    def has_reason(self) -> bool:
        """True when a non-empty reason string was provided."""
        return bool(self.reason and self.reason.strip())


class BaselineEntry(BaseModel):
    """One accepted pre-existing finding in `.forseti-baseline.json`."""

    fingerprint: str = Field(description="sha1(rule_id + location + message kind)")
    rule_id: str = Field(default="")
    location: str = Field(default="")
    content_hash: str = Field(
        default="",
        description="Hash of the offending node; edits revoke the exemption (Boy-Scout rule)",
    )


class WaiverEntry(BaseModel):
    """Point-in-time compatibility waiver ('epoch severance', DEEPTHINK_02)."""

    rule: str = Field(description="Compatibility rule / change-type being waived")
    location: str = Field(description="Affected location, e.g. 'User.address' or a path")
    from_version: str = Field(alias="from", description="Old version identifier")
    to_version: str = Field(alias="to", description="New version identifier")
    reason: str = Field(description="Mandatory reason")
    expires: Optional[date] = Field(default=None, description="Expiry date")

    model_config = {"populate_by_name": True}

    def is_expired(self, today: date) -> bool:
        """Whether the waiver has expired as of `today`."""
        return self.expires is not None and today > self.expires
