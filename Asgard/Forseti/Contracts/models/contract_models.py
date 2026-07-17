"""
Contract Models - Pydantic models for API contract handling.

These models represent API contracts, compatibility results, and breaking changes.
"""

from datetime import date, datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

from Asgard.Forseti.Compatibility.models.legacy_models import LegacyBreakingChange


class LifecycleMeta(BaseModel):
    """Spec-held lifecycle metadata for one API element (DEEPTHINK_07 §2)."""

    location: str = Field(default="", description="Element location key")
    deprecated: bool = Field(default=False)
    since: Optional[date] = Field(default=None, description="Deprecation date")
    sunset: Optional[date] = Field(
        default=None, description="x-sunset-date (RFC 8594)"
    )
    replaced_by: Optional[str] = Field(
        default=None, description="x-replaced-by JSON pointer / path"
    )
    migration_guide: Optional[str] = Field(
        default=None, description="x-migration-guide URL"
    )

    def sunset_elapsed(self, today: date) -> bool:
        """Whether the declared sunset date has passed."""
        return self.sunset is not None and today >= self.sunset


class Bump(str, Enum):
    """Semantic version bump levels."""

    MAJOR = "major"
    MINOR = "minor"
    PATCH = "patch"


class VersionRecommendation(BaseModel):
    """Algorithmic SemVer bump recommendation (RESEARCH_03 §7)."""

    current: Optional[str] = Field(default=None)
    recommended_bump: Bump = Field(default=Bump.PATCH)
    recommended_version: Optional[str] = Field(default=None)
    reasons: list[str] = Field(
        default_factory=list,
        description="rule ids / change descriptions that forced the bump",
    )
    pre_stability: bool = Field(
        default=False,
        description="0.x version: MAJOR downgraded to MINOR per SemVer item 4",
    )


class BreakingChangeType(str, Enum):
    """Types of breaking changes."""
    REMOVED_ENDPOINT = "removed_endpoint"
    REMOVED_FIELD = "removed_field"
    REMOVED_ENUM_VALUE = "removed_enum_value"
    CHANGED_TYPE = "changed_type"
    CHANGED_REQUIRED = "changed_required"
    NARROWED_TYPE = "narrowed_type"
    REMOVED_PARAMETER = "removed_parameter"
    ADDED_REQUIRED_PARAMETER = "added_required_parameter"
    CHANGED_PATH = "changed_path"
    CHANGED_METHOD = "changed_method"
    REMOVED_RESPONSE = "removed_response"
    CHANGED_RESPONSE_TYPE = "changed_response_type"


class CompatibilityLevel(str, Enum):
    """Compatibility assessment levels."""
    FULL = "full"
    BACKWARD = "backward"
    FORWARD = "forward"
    NONE = "none"


class ContractConfig(BaseModel):
    """Configuration for contract validation."""

    strict_mode: bool = Field(
        default=False,
        description="Enable strict validation mode"
    )
    check_request_body: bool = Field(
        default=True,
        description="Check request body compatibility"
    )
    check_response_body: bool = Field(
        default=True,
        description="Check response body compatibility"
    )
    check_parameters: bool = Field(
        default=True,
        description="Check parameter compatibility"
    )
    check_headers: bool = Field(
        default=True,
        description="Check header compatibility"
    )
    allow_added_required: bool = Field(
        default=False,
        description="Allow adding required fields"
    )
    ignore_descriptions: bool = Field(
        default=True,
        description="Ignore description changes"
    )
    ignore_examples: bool = Field(
        default=True,
        description="Ignore example changes"
    )


class ContractValidationError(BaseModel):
    """Represents a contract validation error."""

    path: str = Field(description="Path to the error location")
    message: str = Field(description="Error message")
    expected: Optional[str] = Field(default=None, description="Expected value")
    actual: Optional[str] = Field(default=None, description="Actual value")
    severity: str = Field(default="error", description="Error severity")


class ContractValidationResult(BaseModel):
    """Result of contract validation."""

    is_valid: bool = Field(description="Whether the contract is valid")
    contract_path: Optional[str] = Field(
        default=None,
        description="Path to the contract file"
    )
    implementation_path: Optional[str] = Field(
        default=None,
        description="Path to the implementation"
    )
    errors: list[ContractValidationError] = Field(
        default_factory=list,
        description="List of validation errors"
    )
    warnings: list[ContractValidationError] = Field(
        default_factory=list,
        description="List of validation warnings"
    )
    validated_at: datetime = Field(
        default_factory=datetime.now,
        description="Validation timestamp"
    )

    @property
    def error_count(self) -> int:
        """Return the number of errors."""
        return len(self.errors)


class BreakingChange(LegacyBreakingChange):
    """Represents a breaking change between API versions.

    Deprecated shape: thin subclass of the shared LegacyBreakingChange
    (plan 01); new code should use Compatibility.UnifiedChange.
    """

    change_type: BreakingChangeType = Field(
        description="Type of breaking change"
    )
    location: str = Field(
        description="Location within the path (e.g., request.body.field)"
    )


class CompatibilityResult(BaseModel):
    """Result of compatibility check between API versions."""

    is_compatible: bool = Field(
        description="Whether versions are compatible"
    )
    compatibility_level: CompatibilityLevel = Field(
        description="Level of compatibility"
    )
    source_version: Optional[str] = Field(
        default=None,
        description="Source (old) version identifier"
    )
    target_version: Optional[str] = Field(
        default=None,
        description="Target (new) version identifier"
    )
    breaking_changes: list[BreakingChange] = Field(
        default_factory=list,
        description="List of breaking changes"
    )
    warnings: list[BreakingChange] = Field(
        default_factory=list,
        description="List of warnings (non-breaking)"
    )
    added_endpoints: list[str] = Field(
        default_factory=list,
        description="Endpoints added in new version"
    )
    removed_endpoints: list[str] = Field(
        default_factory=list,
        description="Endpoints removed in new version"
    )
    modified_endpoints: list[str] = Field(
        default_factory=list,
        description="Endpoints modified in new version"
    )
    checked_at: datetime = Field(
        default_factory=datetime.now,
        description="Check timestamp"
    )
    check_time_ms: float = Field(
        default=0.0,
        description="Time taken to check"
    )

    class Config:
        use_enum_values = True

    @property
    def breaking_change_count(self) -> int:
        """Return the number of breaking changes."""
        return len(self.breaking_changes)

    @property
    def has_breaking_changes(self) -> bool:
        """Check if there are breaking changes."""
        return len(self.breaking_changes) > 0
