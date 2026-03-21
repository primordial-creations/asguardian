"""
Breaking Change Detector Service Helpers.

Helper functions for BreakingChangeDetectorService.
"""

from dataclasses import dataclass
from typing import Any, Optional

from Asgard.Forseti.Contracts.models.contract_models import (
    BreakingChange,
    BreakingChangeType,
)


@dataclass
class SemanticVersionSuggestion:
    """Semantic versioning suggestion based on changes."""
    current_version: str
    suggested_version: str
    version_bump: str
    reasoning: str
    confidence: float


@dataclass
class MigrationStep:
    """A single step in a migration path."""
    order: int
    action: str
    description: str
    code_example: Optional[str] = None
    affected_endpoints: Optional[list[str]] = None

    def __post_init__(self):
        if self.affected_endpoints is None:
            self.affected_endpoints = []


@dataclass
class MigrationPath:
    """Complete migration path for a breaking change."""
    change_location: str
    change_type: str
    steps: list[MigrationStep]
    estimated_effort: str
    risk_level: str


@dataclass
class CompatibilityScore:
    """Backwards compatibility scoring."""
    overall_score: float
    api_stability_score: float
    schema_stability_score: float
    parameter_stability_score: float
    response_stability_score: float
    grade: str
    details: dict[str, Any]


def get_recommendation(impact: str, total_changes: int) -> str:
    """Get a recommendation based on impact level."""
    if impact == "HIGH":
        return ("This update contains high-impact breaking changes. Consider releasing as a major version with migration documentation.")
    elif impact == "MEDIUM":
        return ("This update contains some breaking changes. Provide deprecation notices and transition period for clients.")
    elif impact == "LOW":
        return "Minor breaking changes detected. Document the changes and notify consumers."
    else:
        return "No breaking changes detected. Safe to deploy."


def calculate_client_impact(changes: list[BreakingChange]) -> dict[str, Any]:
    """Calculate the impact on API clients."""
    request_breaking = 0
    response_breaking = 0
    auth_breaking = 0
    for change in changes:
        location = change.location.lower()
        if "response" in location:
            response_breaking += 1
        elif "security" in location or "auth" in location:
            auth_breaking += 1
        else:
            request_breaking += 1
    return {
        "request_changes": request_breaking,
        "response_changes": response_breaking,
        "auth_changes": auth_breaking,
        "total_client_changes_required": request_breaking + response_breaking + auth_breaking,
        "affects_request_handling": request_breaking > 0,
        "affects_response_parsing": response_breaking > 0,
        "affects_authentication": auth_breaking > 0,
    }


def suggest_deprecation_period(impact: str) -> int:
    """Suggest deprecation period in days based on impact."""
    if impact == "HIGH":
        return 90
    elif impact == "MEDIUM":
        return 60
    elif impact == "LOW":
        return 30
    return 0


def estimate_migration_effort(change: BreakingChange) -> tuple[str, str]:
    """Estimate migration effort and risk for a change."""
    change_type = change.change_type
    high_effort_types = {BreakingChangeType.REMOVED_ENDPOINT, BreakingChangeType.CHANGED_PATH, BreakingChangeType.CHANGED_METHOD}
    high_risk_types = {BreakingChangeType.REMOVED_ENDPOINT, BreakingChangeType.CHANGED_TYPE, BreakingChangeType.REMOVED_FIELD}
    medium_effort_types = {BreakingChangeType.CHANGED_TYPE, BreakingChangeType.REMOVED_FIELD, BreakingChangeType.CHANGED_RESPONSE_TYPE}
    medium_risk_types = {BreakingChangeType.CHANGED_REQUIRED, BreakingChangeType.ADDED_REQUIRED_PARAMETER}
    effort = "high" if change_type in high_effort_types else ("medium" if change_type in medium_effort_types else "low")
    risk = "high" if change_type in high_risk_types else ("medium" if change_type in medium_risk_types else "low")
    return effort, risk


def generate_migration_steps(change: BreakingChange) -> list[MigrationStep]:
    """Generate migration steps for a single breaking change."""
    change_type = change.change_type
    if change_type == BreakingChangeType.REMOVED_ENDPOINT:
        return [
            MigrationStep(order=1, action="Identify all client usages", description=f"Search codebase for references to {change.path}", affected_endpoints=[change.path]),
            MigrationStep(order=2, action="Find replacement endpoint", description="Check API documentation for alternative endpoints that provide similar functionality"),
            MigrationStep(order=3, action="Update client code", description="Replace calls to the removed endpoint with the new endpoint", code_example=f"// Before: fetch('{change.path}')\n// After: fetch('/new-endpoint')"),
            MigrationStep(order=4, action="Test thoroughly", description="Run integration tests to verify the replacement works correctly"),
        ]
    elif change_type == BreakingChangeType.REMOVED_FIELD:
        return [
            MigrationStep(order=1, action="Identify field usage", description=f"Find all code that references the removed field at {change.location}"),
            MigrationStep(order=2, action="Check for alternatives", description="Review API docs for alternative fields or computed values"),
            MigrationStep(order=3, action="Update data models", description="Remove the field from client-side data models/interfaces", code_example="// Remove field from interface\ninterface Response {\n  // removedField: string; // Removed\n  newField: string;\n}"),
            MigrationStep(order=4, action="Handle missing data gracefully", description="Add fallback logic for clients that may receive responses with or without the field during transition"),
        ]
    elif change_type == BreakingChangeType.CHANGED_TYPE:
        old_type = change.old_value or "unknown"
        new_type = change.new_value or "unknown"
        return [
            MigrationStep(order=1, action="Identify type usage", description=f"Find all code that handles the field at {change.location}"),
            MigrationStep(order=2, action="Update type definitions", description=f"Change type from {old_type} to {new_type} in data models", code_example=f"// Before: {change.location}: {old_type}\n// After: {change.location}: {new_type}"),
            MigrationStep(order=3, action="Add type conversion", description="Implement conversion logic if data format changes (e.g., string to number)"),
            MigrationStep(order=4, action="Update validation", description="Modify any validation logic to handle the new type"),
        ]
    elif change_type == BreakingChangeType.ADDED_REQUIRED_PARAMETER:
        return [
            MigrationStep(order=1, action="Identify affected calls", description=f"Find all API calls to endpoints affected by {change.location}"),
            MigrationStep(order=2, action="Determine parameter value", description="Review documentation to understand what value the new required parameter should have"),
            MigrationStep(order=3, action="Update API calls", description="Add the new required parameter to all affected API calls", code_example=f"// Add new parameter to request\nfetch(url, {{\n  body: JSON.stringify({{\n    newParam: 'value'  // Required now\n  }})\n}})"),
        ]
    elif change_type == BreakingChangeType.CHANGED_REQUIRED:
        return [
            MigrationStep(order=1, action="Review change", description=f"Understand whether field at {change.location} became required or optional"),
            MigrationStep(order=2, action="Update requests", description="If field became required, ensure all requests include it"),
            MigrationStep(order=3, action="Handle optionality", description="If field became optional, update response handling to handle missing values"),
        ]
    else:
        return [
            MigrationStep(order=1, action="Review change", description=f"Understand the breaking change at {change.location}: {change.message}"),
            MigrationStep(order=2, action="Update client code", description="Modify affected code to accommodate the change"),
            MigrationStep(order=3, action="Test changes", description="Verify the updated code works with the new API version"),
        ]
