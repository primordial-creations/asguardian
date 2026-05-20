"""
Heimdall Quality Profile Models

A Quality Profile is a named collection of rules with configured severity thresholds.
Profiles can be assigned to projects and can inherit rules from parent profiles,
allowing teams to define organisation-wide standards with project-specific overrides.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class RuleCategory(str, Enum):
    """Broad category that a rule belongs to."""
    QUALITY = "quality"
    SECURITY = "security"
    PERFORMANCE = "performance"
    RELIABILITY = "reliability"
    ARCHITECTURE = "architecture"


class RuleConfig(BaseModel):
    """
    Configuration for a single rule within a quality profile.

    Each rule may be enabled or disabled, assigned a severity level, given a
    numeric threshold override, and provided with rule-specific extra configuration.
    """
    rule_id: str = Field(..., description="Unique rule identifier (e.g. 'quality.cyclomatic_complexity')")
    enabled: bool = Field(True, description="Whether this rule is active in the profile")
    severity: str = Field("warning", description="Severity level: error, warning, or info")
    threshold: Optional[float] = Field(
        None,
        description="Numeric threshold override for the rule (uses rule default if None)",
    )
    extra_config: Dict[str, Any] = Field(
        default_factory=dict,
        description="Rule-specific extra configuration key-value pairs",
    )

    class Config:
        use_enum_values = True


class QualityProfile(BaseModel):
    """
    A named collection of rule configurations that can be assigned to projects.

    Profiles support single-level inheritance: a profile may declare a parent_profile
    by name, and the effective profile merges parent rules with any overrides defined
    in the child profile. Built-in profiles cannot be overwritten.
    """
    name: str = Field(..., description="Unique profile name")
    language: str = Field("python", description="Target programming language")
    description: str = Field("", description="Human-readable profile description")
    parent_profile: Optional[str] = Field(
        None,
        description="Name of the parent profile to inherit rules from",
    )
    rules: List[RuleConfig] = Field(
        default_factory=list,
        description="Rule configurations defined in this profile",
    )
    created_at: datetime = Field(
        default_factory=datetime.now,
        description="When this profile was created",
    )
    is_builtin: bool = Field(
        False,
        description="Whether this is a built-in profile that cannot be overwritten",
    )

    class Config:
        use_enum_values = True

    def get_rule(self, rule_id: str) -> Optional[RuleConfig]:
        """Return the RuleConfig for the given rule_id, or None if not configured."""
        for rule in self.rules:
            if rule.rule_id == rule_id:
                return rule
        return None


class ProfileAssignment(BaseModel):
    """
    Records that a quality profile has been assigned to a specific project.

    Assignments are stored in ~/.asgard/profile_assignments.json and are
    looked up when analysing a project to determine which profile to apply.
    """
    project_path: str = Field(..., description="Absolute path to the project root")
    profile_name: str = Field(..., description="Name of the assigned quality profile")
    assigned_at: datetime = Field(
        default_factory=datetime.now,
        description="When the assignment was made",
    )

    class Config:
        use_enum_values = True
