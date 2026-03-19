"""
Breaking Change Detector Service.

Detects breaking changes between API versions with detailed analysis,
semantic versioning suggestions, impact analysis, and migration paths.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional, cast

from Asgard.Forseti.Contracts.models.contract_models import (
    ContractConfig,
    BreakingChange,
    BreakingChangeType,
)
from Asgard.Forseti.Contracts.services.compatibility_checker_service import CompatibilityCheckerService


@dataclass
class SemanticVersionSuggestion:
    """Semantic versioning suggestion based on changes."""
    current_version: str
    suggested_version: str
    version_bump: str  # "major", "minor", "patch"
    reasoning: str
    confidence: float  # 0.0 to 1.0


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
    estimated_effort: str  # "low", "medium", "high"
    risk_level: str  # "low", "medium", "high"


@dataclass
class CompatibilityScore:
    """Backwards compatibility scoring."""
    overall_score: float  # 0.0 (fully incompatible) to 100.0 (fully compatible)
    api_stability_score: float
    schema_stability_score: float
    parameter_stability_score: float
    response_stability_score: float
    grade: str  # "A", "B", "C", "D", "F"
    details: dict[str, Any]


class BreakingChangeDetectorService:
    """
    Service for detecting breaking changes between API versions.

    Provides detailed analysis of breaking changes with mitigations.

    Usage:
        service = BreakingChangeDetectorService()
        changes = service.detect("v1.yaml", "v2.yaml")
        for change in changes:
            print(f"Breaking: {change.message}")
            print(f"Mitigation: {change.mitigation}")
    """

    def __init__(self, config: Optional[ContractConfig] = None):
        """
        Initialize the breaking change detector service.

        Args:
            config: Optional configuration for detection behavior.
        """
        self.config = config or ContractConfig()
        self.compatibility_checker = CompatibilityCheckerService(config)

    def detect(
        self,
        old_version_path: str | Path,
        new_version_path: str | Path
    ) -> list[BreakingChange]:
        """
        Detect breaking changes between two API versions.

        Args:
            old_version_path: Path to the old version specification.
            new_version_path: Path to the new version specification.

        Returns:
            List of breaking changes.
        """
        result = self.compatibility_checker.check(old_version_path, new_version_path)
        return cast(List[Any], result.breaking_changes)

    def categorize_changes(
        self,
        changes: list[BreakingChange]
    ) -> dict[str, list[BreakingChange]]:
        """
        Categorize breaking changes by type.

        Args:
            changes: List of breaking changes.

        Returns:
            Dictionary mapping change type to list of changes.
        """
        categorized: dict[str, list[BreakingChange]] = {}

        for change in changes:
            change_type = change.change_type
            if change_type not in categorized:
                categorized[change_type] = []
            categorized[change_type].append(change)

        return categorized

    def get_severity_summary(
        self,
        changes: list[BreakingChange]
    ) -> dict[str, int]:
        """
        Get summary of changes by severity.

        Args:
            changes: List of breaking changes.

        Returns:
            Dictionary mapping severity to count.
        """
        summary: dict[str, int] = {
            "error": 0,
            "warning": 0,
            "info": 0,
        }

        for change in changes:
            severity = change.severity
            if severity in summary:
                summary[severity] += 1

        return summary

    def suggest_mitigations(
        self,
        changes: list[BreakingChange]
    ) -> dict[str, str]:
        """
        Suggest mitigations for breaking changes.

        Args:
            changes: List of breaking changes.

        Returns:
            Dictionary mapping change location to mitigation.
        """
        mitigations: dict[str, str] = {}

        mitigation_templates = {
            BreakingChangeType.REMOVED_ENDPOINT: (
                "Consider keeping the endpoint with a deprecation warning, "
                "or version the API to maintain backward compatibility."
            ),
            BreakingChangeType.REMOVED_FIELD: (
                "Keep the field in responses with a null or default value, "
                "and mark it as deprecated in documentation."
            ),
            BreakingChangeType.CHANGED_TYPE: (
                "Maintain both type formats during a transition period, "
                "or provide a type coercion layer."
            ),
            BreakingChangeType.CHANGED_REQUIRED: (
                "Keep the field optional with a default value, "
                "or provide a migration guide for clients."
            ),
            BreakingChangeType.ADDED_REQUIRED_PARAMETER: (
                "Make the new parameter optional with a sensible default, "
                "or version the endpoint."
            ),
            BreakingChangeType.REMOVED_PARAMETER: (
                "Keep accepting the parameter (ignore it if unused), "
                "and document the deprecation."
            ),
        }

        for change in changes:
            location = change.location
            if change.mitigation:
                mitigations[location] = change.mitigation
            elif change.change_type in mitigation_templates:
                mitigations[location] = mitigation_templates[change.change_type]
            else:
                mitigations[location] = (
                    "Review the change impact and consider backward compatibility options."
                )

        return mitigations

    def estimate_impact(
        self,
        changes: list[BreakingChange]
    ) -> dict[str, Any]:
        """
        Estimate the impact of breaking changes.

        Args:
            changes: List of breaking changes.

        Returns:
            Impact assessment dictionary.
        """
        high_impact_types = {
            BreakingChangeType.REMOVED_ENDPOINT,
            BreakingChangeType.CHANGED_TYPE,
            BreakingChangeType.REMOVED_FIELD,
        }

        medium_impact_types = {
            BreakingChangeType.CHANGED_REQUIRED,
            BreakingChangeType.ADDED_REQUIRED_PARAMETER,
            BreakingChangeType.CHANGED_RESPONSE_TYPE,
        }

        high_impact = [c for c in changes if c.change_type in high_impact_types]
        medium_impact = [c for c in changes if c.change_type in medium_impact_types]
        low_impact = [
            c for c in changes
            if c.change_type not in high_impact_types and c.change_type not in medium_impact_types
        ]

        # Estimate overall impact
        if high_impact:
            overall = "HIGH"
        elif medium_impact:
            overall = "MEDIUM"
        elif low_impact:
            overall = "LOW"
        else:
            overall = "NONE"

        return {
            "overall_impact": overall,
            "high_impact_count": len(high_impact),
            "medium_impact_count": len(medium_impact),
            "low_impact_count": len(low_impact),
            "high_impact_changes": high_impact,
            "medium_impact_changes": medium_impact,
            "low_impact_changes": low_impact,
            "recommendation": self._get_recommendation(overall, len(changes)),
        }

    def _get_recommendation(self, impact: str, total_changes: int) -> str:
        """Get a recommendation based on impact level."""
        if impact == "HIGH":
            return (
                "This update contains high-impact breaking changes. "
                "Consider releasing as a major version with migration documentation."
            )
        elif impact == "MEDIUM":
            return (
                "This update contains some breaking changes. "
                "Provide deprecation notices and transition period for clients."
            )
        elif impact == "LOW":
            return (
                "Minor breaking changes detected. "
                "Document the changes and notify consumers."
            )
        else:
            return "No breaking changes detected. Safe to deploy."

    def generate_changelog(
        self,
        changes: list[BreakingChange],
        version: str = "unknown"
    ) -> str:
        """
        Generate a changelog entry for breaking changes.

        Args:
            changes: List of breaking changes.
            version: Version string for the changelog.

        Returns:
            Changelog markdown string.
        """
        lines = []
        lines.append(f"## Breaking Changes in {version}\n")

        if not changes:
            lines.append("No breaking changes in this release.\n")
            return "\n".join(lines)

        categorized = self.categorize_changes(changes)

        for change_type, type_changes in categorized.items():
            lines.append(f"### {change_type.replace('_', ' ').title()}\n")
            for change in type_changes:
                lines.append(f"- **{change.location}**: {change.message}")
                if change.mitigation:
                    lines.append(f"  - *Mitigation*: {change.mitigation}")
            lines.append("")

        return "\n".join(lines)

    def suggest_semantic_version(
        self,
        changes: list[BreakingChange],
        current_version: str = "1.0.0"
    ) -> SemanticVersionSuggestion:
        """
        Suggest a semantic version based on the breaking changes detected.

        Args:
            changes: List of breaking changes.
            current_version: Current version string (e.g., "1.2.3").

        Returns:
            SemanticVersionSuggestion with recommended version bump.
        """
        # Parse current version
        version_match = re.match(r"(\d+)\.(\d+)\.(\d+)", current_version)
        if version_match:
            major, minor, patch = map(int, version_match.groups())
        else:
            major, minor, patch = 1, 0, 0

        if not changes:
            # No breaking changes - could be patch or minor
            suggested = f"{major}.{minor}.{patch + 1}"
            return SemanticVersionSuggestion(
                current_version=current_version,
                suggested_version=suggested,
                version_bump="patch",
                reasoning="No breaking changes detected. Safe to release as a patch version.",
                confidence=0.95,
            )

        # Analyze changes for version bump decision
        impact = self.estimate_impact(changes)
        overall_impact = impact["overall_impact"]

        high_impact_types = {
            BreakingChangeType.REMOVED_ENDPOINT,
            BreakingChangeType.CHANGED_TYPE,
            BreakingChangeType.REMOVED_FIELD,
            BreakingChangeType.CHANGED_PATH,
            BreakingChangeType.CHANGED_METHOD,
        }

        has_high_impact = any(
            c.change_type in high_impact_types for c in changes
        )

        if has_high_impact or overall_impact == "HIGH":
            # Major version bump
            suggested = f"{major + 1}.0.0"
            reasoning = (
                f"Detected {len(changes)} breaking change(s) including high-impact changes "
                f"(removed endpoints, type changes, or removed fields). "
                "Recommend major version bump per semantic versioning."
            )
            confidence = 0.90
            bump = "major"
        elif overall_impact == "MEDIUM":
            # Could be major or minor depending on severity
            suggested = f"{major + 1}.0.0"
            reasoning = (
                f"Detected {len(changes)} breaking change(s) with medium impact. "
                "Breaking changes typically require a major version bump per semantic versioning, "
                "though some may consider these acceptable in a minor release with proper deprecation."
            )
            confidence = 0.75
            bump = "major"
        else:
            # Low impact breaking changes
            suggested = f"{major + 1}.0.0"
            reasoning = (
                f"Detected {len(changes)} low-impact breaking change(s). "
                "Even minor breaking changes should trigger a major version bump per strict semantic versioning, "
                "but these may be acceptable in a minor release with advance notice."
            )
            confidence = 0.60
            bump = "major"

        return SemanticVersionSuggestion(
            current_version=current_version,
            suggested_version=suggested,
            version_bump=bump,
            reasoning=reasoning,
            confidence=confidence,
        )

    def analyze_detailed_impact(
        self,
        changes: list[BreakingChange]
    ) -> dict[str, Any]:
        """
        Perform detailed impact analysis of breaking changes.

        Args:
            changes: List of breaking changes.

        Returns:
            Detailed impact analysis dictionary.
        """
        # Start with basic impact estimation
        basic_impact = self.estimate_impact(changes)

        # Analyze by endpoint
        endpoints_affected: dict[str, list[BreakingChange]] = {}
        for change in changes:
            endpoint = change.path
            if endpoint not in endpoints_affected:
                endpoints_affected[endpoint] = []
            endpoints_affected[endpoint].append(change)

        # Analyze by change type distribution
        type_distribution: dict[str, int] = {}
        for change in changes:
            change_type = str(change.change_type)
            type_distribution[change_type] = type_distribution.get(change_type, 0) + 1

        # Calculate client impact
        client_impact = self._calculate_client_impact(changes)

        # Generate impact summary
        impact_summary = []
        if basic_impact["high_impact_count"] > 0:
            impact_summary.append(
                f"{basic_impact['high_impact_count']} high-impact change(s) will likely break all clients"
            )
        if basic_impact["medium_impact_count"] > 0:
            impact_summary.append(
                f"{basic_impact['medium_impact_count']} medium-impact change(s) may affect some client functionality"
            )
        if basic_impact["low_impact_count"] > 0:
            impact_summary.append(
                f"{basic_impact['low_impact_count']} low-impact change(s) may require minor client updates"
            )

        return {
            **basic_impact,
            "endpoints_affected": len(endpoints_affected),
            "endpoints_detail": endpoints_affected,
            "type_distribution": type_distribution,
            "client_impact": client_impact,
            "impact_summary": impact_summary,
            "total_changes": len(changes),
            "requires_migration_guide": basic_impact["overall_impact"] in ["HIGH", "MEDIUM"],
            "suggested_deprecation_period_days": self._suggest_deprecation_period(basic_impact["overall_impact"]),
        }

    def _calculate_client_impact(self, changes: list[BreakingChange]) -> dict[str, Any]:
        """Calculate the impact on API clients."""
        request_breaking = 0
        response_breaking = 0
        auth_breaking = 0

        for change in changes:
            location = change.location.lower()
            if "request" in location or "parameter" in location:
                request_breaking += 1
            elif "response" in location:
                response_breaking += 1
            elif "security" in location or "auth" in location:
                auth_breaking += 1
            else:
                # Default to request if unclear
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

    def _suggest_deprecation_period(self, impact: str) -> int:
        """Suggest deprecation period in days based on impact."""
        if impact == "HIGH":
            return 90  # 3 months
        elif impact == "MEDIUM":
            return 60  # 2 months
        elif impact == "LOW":
            return 30  # 1 month
        return 0

    def generate_migration_paths(
        self,
        changes: list[BreakingChange]
    ) -> list[MigrationPath]:
        """
        Generate migration paths for each breaking change.

        Args:
            changes: List of breaking changes.

        Returns:
            List of MigrationPath objects with step-by-step guidance.
        """
        migration_paths = []

        for change in changes:
            steps = self._generate_migration_steps(change)
            effort, risk = self._estimate_migration_effort(change)

            migration_path = MigrationPath(
                change_location=change.location,
                change_type=str(change.change_type),
                steps=steps,
                estimated_effort=effort,
                risk_level=risk,
            )
            migration_paths.append(migration_path)

        return migration_paths

    def _generate_migration_steps(self, change: BreakingChange) -> list[MigrationStep]:
        """Generate migration steps for a single breaking change."""
        steps = []
        change_type = change.change_type

        if change_type == BreakingChangeType.REMOVED_ENDPOINT:
            steps = [
                MigrationStep(
                    order=1,
                    action="Identify all client usages",
                    description=f"Search codebase for references to {change.path}",
                    affected_endpoints=[change.path],
                ),
                MigrationStep(
                    order=2,
                    action="Find replacement endpoint",
                    description="Check API documentation for alternative endpoints that provide similar functionality",
                ),
                MigrationStep(
                    order=3,
                    action="Update client code",
                    description="Replace calls to the removed endpoint with the new endpoint",
                    code_example=f"// Before: fetch('{change.path}')\n// After: fetch('/new-endpoint')",
                ),
                MigrationStep(
                    order=4,
                    action="Test thoroughly",
                    description="Run integration tests to verify the replacement works correctly",
                ),
            ]

        elif change_type == BreakingChangeType.REMOVED_FIELD:
            steps = [
                MigrationStep(
                    order=1,
                    action="Identify field usage",
                    description=f"Find all code that references the removed field at {change.location}",
                ),
                MigrationStep(
                    order=2,
                    action="Check for alternatives",
                    description="Review API docs for alternative fields or computed values",
                ),
                MigrationStep(
                    order=3,
                    action="Update data models",
                    description="Remove the field from client-side data models/interfaces",
                    code_example="// Remove field from interface\ninterface Response {\n  // removedField: string; // Removed\n  newField: string;\n}",
                ),
                MigrationStep(
                    order=4,
                    action="Handle missing data gracefully",
                    description="Add fallback logic for clients that may receive responses with or without the field during transition",
                ),
            ]

        elif change_type == BreakingChangeType.CHANGED_TYPE:
            old_type = change.old_value or "unknown"
            new_type = change.new_value or "unknown"
            steps = [
                MigrationStep(
                    order=1,
                    action="Identify type usage",
                    description=f"Find all code that handles the field at {change.location}",
                ),
                MigrationStep(
                    order=2,
                    action="Update type definitions",
                    description=f"Change type from {old_type} to {new_type} in data models",
                    code_example=f"// Before: {change.location}: {old_type}\n// After: {change.location}: {new_type}",
                ),
                MigrationStep(
                    order=3,
                    action="Add type conversion",
                    description="Implement conversion logic if data format changes (e.g., string to number)",
                ),
                MigrationStep(
                    order=4,
                    action="Update validation",
                    description="Modify any validation logic to handle the new type",
                ),
            ]

        elif change_type == BreakingChangeType.ADDED_REQUIRED_PARAMETER:
            steps = [
                MigrationStep(
                    order=1,
                    action="Identify affected calls",
                    description=f"Find all API calls to endpoints affected by {change.location}",
                ),
                MigrationStep(
                    order=2,
                    action="Determine parameter value",
                    description="Review documentation to understand what value the new required parameter should have",
                ),
                MigrationStep(
                    order=3,
                    action="Update API calls",
                    description="Add the new required parameter to all affected API calls",
                    code_example=f"// Add new parameter to request\nfetch(url, {{\n  body: JSON.stringify({{\n    newParam: 'value'  // Required now\n  }})\n}})",
                ),
            ]

        elif change_type == BreakingChangeType.CHANGED_REQUIRED:
            steps = [
                MigrationStep(
                    order=1,
                    action="Review change",
                    description=f"Understand whether field at {change.location} became required or optional",
                ),
                MigrationStep(
                    order=2,
                    action="Update requests",
                    description="If field became required, ensure all requests include it",
                ),
                MigrationStep(
                    order=3,
                    action="Handle optionality",
                    description="If field became optional, update response handling to handle missing values",
                ),
            ]

        else:
            # Generic migration steps
            steps = [
                MigrationStep(
                    order=1,
                    action="Review change",
                    description=f"Understand the breaking change at {change.location}: {change.message}",
                ),
                MigrationStep(
                    order=2,
                    action="Update client code",
                    description="Modify affected code to accommodate the change",
                ),
                MigrationStep(
                    order=3,
                    action="Test changes",
                    description="Verify the updated code works with the new API version",
                ),
            ]

        return steps

    def _estimate_migration_effort(self, change: BreakingChange) -> tuple[str, str]:
        """Estimate migration effort and risk for a change."""
        change_type = change.change_type

        high_effort_types = {
            BreakingChangeType.REMOVED_ENDPOINT,
            BreakingChangeType.CHANGED_PATH,
            BreakingChangeType.CHANGED_METHOD,
        }

        high_risk_types = {
            BreakingChangeType.REMOVED_ENDPOINT,
            BreakingChangeType.CHANGED_TYPE,
            BreakingChangeType.REMOVED_FIELD,
        }

        medium_effort_types = {
            BreakingChangeType.CHANGED_TYPE,
            BreakingChangeType.REMOVED_FIELD,
            BreakingChangeType.CHANGED_RESPONSE_TYPE,
        }

        medium_risk_types = {
            BreakingChangeType.CHANGED_REQUIRED,
            BreakingChangeType.ADDED_REQUIRED_PARAMETER,
        }

        # Determine effort
        if change_type in high_effort_types:
            effort = "high"
        elif change_type in medium_effort_types:
            effort = "medium"
        else:
            effort = "low"

        # Determine risk
        if change_type in high_risk_types:
            risk = "high"
        elif change_type in medium_risk_types:
            risk = "medium"
        else:
            risk = "low"

        return effort, risk

    def calculate_compatibility_score(
        self,
        changes: list[BreakingChange],
        total_endpoints: int = 0,
        total_schemas: int = 0
    ) -> CompatibilityScore:
        """
        Calculate a backwards compatibility score.

        Args:
            changes: List of breaking changes.
            total_endpoints: Total number of endpoints in the API.
            total_schemas: Total number of schemas in the API.

        Returns:
            CompatibilityScore with detailed scoring.
        """
        if not changes:
            return CompatibilityScore(
                overall_score=100.0,
                api_stability_score=100.0,
                schema_stability_score=100.0,
                parameter_stability_score=100.0,
                response_stability_score=100.0,
                grade="A",
                details={
                    "message": "No breaking changes detected. Full backward compatibility maintained.",
                    "changes_detected": 0,
                },
            )

        # Categorize changes for scoring
        api_changes = []
        schema_changes = []
        parameter_changes = []
        response_changes = []

        for change in changes:
            change_type = change.change_type

            if change_type in {BreakingChangeType.REMOVED_ENDPOINT, BreakingChangeType.CHANGED_PATH, BreakingChangeType.CHANGED_METHOD}:
                api_changes.append(change)
            elif change_type in {BreakingChangeType.REMOVED_FIELD, BreakingChangeType.CHANGED_TYPE, BreakingChangeType.REMOVED_ENUM_VALUE, BreakingChangeType.NARROWED_TYPE}:
                schema_changes.append(change)
            elif change_type in {BreakingChangeType.REMOVED_PARAMETER, BreakingChangeType.ADDED_REQUIRED_PARAMETER, BreakingChangeType.CHANGED_REQUIRED}:
                parameter_changes.append(change)
            elif change_type in {BreakingChangeType.REMOVED_RESPONSE, BreakingChangeType.CHANGED_RESPONSE_TYPE}:
                response_changes.append(change)
            else:
                # Default to schema changes
                schema_changes.append(change)

        # Calculate component scores (each change reduces score)
        # Penalty weights by severity
        high_penalty = 15
        medium_penalty = 10
        low_penalty = 5

        def calculate_score(changes_list: list[BreakingChange], base: int = 100) -> float:
            penalty = 0
            for change in changes_list:
                if change.severity == "error":
                    penalty += high_penalty
                elif change.severity == "warning":
                    penalty += medium_penalty
                else:
                    penalty += low_penalty
            return max(0.0, base - penalty)

        api_score = calculate_score(api_changes)
        schema_score = calculate_score(schema_changes)
        param_score = calculate_score(parameter_changes)
        response_score = calculate_score(response_changes)

        # Calculate overall score (weighted average)
        weights = {
            "api": 0.35,
            "schema": 0.25,
            "parameter": 0.20,
            "response": 0.20,
        }

        overall = (
            api_score * weights["api"] +
            schema_score * weights["schema"] +
            param_score * weights["parameter"] +
            response_score * weights["response"]
        )

        # Determine grade
        if overall >= 90:
            grade = "A"
        elif overall >= 80:
            grade = "B"
        elif overall >= 70:
            grade = "C"
        elif overall >= 60:
            grade = "D"
        else:
            grade = "F"

        # Build details
        details = {
            "total_changes": len(changes),
            "api_changes": len(api_changes),
            "schema_changes": len(schema_changes),
            "parameter_changes": len(parameter_changes),
            "response_changes": len(response_changes),
            "weights_used": weights,
            "scoring_explanation": (
                "Score starts at 100 and is reduced based on breaking changes. "
                f"High-severity changes reduce score by {high_penalty}, "
                f"medium by {medium_penalty}, low by {low_penalty}."
            ),
        }

        if total_endpoints > 0:
            details["endpoints_affected_percentage"] = round(
                len(api_changes) / total_endpoints * 100, 2
            )

        return CompatibilityScore(
            overall_score=round(overall, 2),
            api_stability_score=round(api_score, 2),
            schema_stability_score=round(schema_score, 2),
            parameter_stability_score=round(param_score, 2),
            response_stability_score=round(response_score, 2),
            grade=grade,
            details=details,
        )

    def generate_comprehensive_report(
        self,
        old_version_path: str | Path,
        new_version_path: str | Path,
        current_version: str = "1.0.0"
    ) -> dict[str, Any]:
        """
        Generate a comprehensive breaking change report with all analyses.

        Args:
            old_version_path: Path to the old version specification.
            new_version_path: Path to the new version specification.
            current_version: Current version string for versioning suggestions.

        Returns:
            Comprehensive report dictionary.
        """
        # Detect changes
        changes = self.detect(old_version_path, new_version_path)

        # Perform all analyses
        version_suggestion = self.suggest_semantic_version(changes, current_version)
        detailed_impact = self.analyze_detailed_impact(changes)
        migration_paths = self.generate_migration_paths(changes)
        compatibility_score = self.calculate_compatibility_score(changes)
        mitigations = self.suggest_mitigations(changes)
        changelog = self.generate_changelog(changes, version_suggestion.suggested_version)

        return {
            "summary": {
                "total_breaking_changes": len(changes),
                "overall_impact": detailed_impact["overall_impact"],
                "compatibility_grade": compatibility_score.grade,
                "compatibility_score": compatibility_score.overall_score,
                "suggested_version": version_suggestion.suggested_version,
                "version_bump": version_suggestion.version_bump,
            },
            "version_suggestion": {
                "current": version_suggestion.current_version,
                "suggested": version_suggestion.suggested_version,
                "bump_type": version_suggestion.version_bump,
                "reasoning": version_suggestion.reasoning,
                "confidence": version_suggestion.confidence,
            },
            "impact_analysis": detailed_impact,
            "compatibility_score": {
                "overall": compatibility_score.overall_score,
                "grade": compatibility_score.grade,
                "api_stability": compatibility_score.api_stability_score,
                "schema_stability": compatibility_score.schema_stability_score,
                "parameter_stability": compatibility_score.parameter_stability_score,
                "response_stability": compatibility_score.response_stability_score,
                "details": compatibility_score.details,
            },
            "migration_paths": [
                {
                    "location": mp.change_location,
                    "type": mp.change_type,
                    "effort": mp.estimated_effort,
                    "risk": mp.risk_level,
                    "steps": [
                        {
                            "order": s.order,
                            "action": s.action,
                            "description": s.description,
                            "code_example": s.code_example,
                        }
                        for s in mp.steps
                    ],
                }
                for mp in migration_paths
            ],
            "mitigations": mitigations,
            "changelog": changelog,
            "breaking_changes": [
                {
                    "type": str(c.change_type),
                    "path": c.path,
                    "location": c.location,
                    "message": c.message,
                    "severity": c.severity,
                    "old_value": c.old_value,
                    "new_value": c.new_value,
                }
                for c in changes
            ],
        }
