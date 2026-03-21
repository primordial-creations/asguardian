"""
Breaking Change Detector Service.

Detects breaking changes between API versions with detailed analysis,
semantic versioning suggestions, impact analysis, and migration paths.
"""

import re
from pathlib import Path
from typing import Any, List, Optional, cast

from Asgard.Forseti.Contracts.models.contract_models import (
    ContractConfig,
    BreakingChange,
    BreakingChangeType,
)
from Asgard.Forseti.Contracts.services.compatibility_checker_service import CompatibilityCheckerService
from Asgard.Forseti.Contracts.services._breaking_change_detector_service_helpers import (
    CompatibilityScore,
    MigrationPath,
    MigrationStep,
    SemanticVersionSuggestion,
    calculate_client_impact,
    estimate_migration_effort,
    generate_migration_steps,
    get_recommendation,
    suggest_deprecation_period,
)


class BreakingChangeDetectorService:
    """
    Service for detecting breaking changes between API versions.

    Usage:
        service = BreakingChangeDetectorService()
        changes = service.detect("v1.yaml", "v2.yaml")
        for change in changes:
            print(f"Breaking: {change.message}")
    """

    def __init__(self, config: Optional[ContractConfig] = None):
        self.config = config or ContractConfig()
        self.compatibility_checker = CompatibilityCheckerService(config)

    def detect(self, old_version_path: str | Path, new_version_path: str | Path) -> list[BreakingChange]:
        result = self.compatibility_checker.check(old_version_path, new_version_path)
        return cast(List[Any], result.breaking_changes)

    def categorize_changes(self, changes: list[BreakingChange]) -> dict[str, list[BreakingChange]]:
        categorized: dict[str, list[BreakingChange]] = {}
        for change in changes:
            change_type = change.change_type
            if change_type not in categorized:
                categorized[change_type] = []
            categorized[change_type].append(change)
        return categorized

    def get_severity_summary(self, changes: list[BreakingChange]) -> dict[str, int]:
        summary: dict[str, int] = {"error": 0, "warning": 0, "info": 0}
        for change in changes:
            severity = change.severity
            if severity in summary:
                summary[severity] += 1
        return summary

    def suggest_mitigations(self, changes: list[BreakingChange]) -> dict[str, str]:
        mitigations: dict[str, str] = {}
        mitigation_templates = {
            BreakingChangeType.REMOVED_ENDPOINT: "Consider keeping the endpoint with a deprecation warning, or version the API to maintain backward compatibility.",
            BreakingChangeType.REMOVED_FIELD: "Keep the field in responses with a null or default value, and mark it as deprecated in documentation.",
            BreakingChangeType.CHANGED_TYPE: "Maintain both type formats during a transition period, or provide a type coercion layer.",
            BreakingChangeType.CHANGED_REQUIRED: "Keep the field optional with a default value, or provide a migration guide for clients.",
            BreakingChangeType.ADDED_REQUIRED_PARAMETER: "Make the new parameter optional with a sensible default, or version the endpoint.",
            BreakingChangeType.REMOVED_PARAMETER: "Keep accepting the parameter (ignore it if unused), and document the deprecation.",
        }
        for change in changes:
            location = change.location
            if change.mitigation:
                mitigations[location] = change.mitigation
            elif change.change_type in mitigation_templates:
                mitigations[location] = mitigation_templates[change.change_type]
            else:
                mitigations[location] = "Review the change impact and consider backward compatibility options."
        return mitigations

    def estimate_impact(self, changes: list[BreakingChange]) -> dict[str, Any]:
        high_impact_types = {BreakingChangeType.REMOVED_ENDPOINT, BreakingChangeType.CHANGED_TYPE, BreakingChangeType.REMOVED_FIELD}
        medium_impact_types = {BreakingChangeType.CHANGED_REQUIRED, BreakingChangeType.ADDED_REQUIRED_PARAMETER, BreakingChangeType.CHANGED_RESPONSE_TYPE}
        high_impact = [c for c in changes if c.change_type in high_impact_types]
        medium_impact = [c for c in changes if c.change_type in medium_impact_types]
        low_impact = [c for c in changes if c.change_type not in high_impact_types and c.change_type not in medium_impact_types]
        overall = "HIGH" if high_impact else ("MEDIUM" if medium_impact else ("LOW" if low_impact else "NONE"))
        return {
            "overall_impact": overall, "high_impact_count": len(high_impact),
            "medium_impact_count": len(medium_impact), "low_impact_count": len(low_impact),
            "high_impact_changes": high_impact, "medium_impact_changes": medium_impact,
            "low_impact_changes": low_impact, "recommendation": get_recommendation(overall, len(changes)),
        }

    def generate_changelog(self, changes: list[BreakingChange], version: str = "unknown") -> str:
        lines = [f"## Breaking Changes in {version}\n"]
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

    def suggest_semantic_version(self, changes: list[BreakingChange], current_version: str = "1.0.0") -> SemanticVersionSuggestion:
        version_match = re.match(r"(\d+)\.(\d+)\.(\d+)", current_version)
        if version_match:
            major, minor, patch = map(int, version_match.groups())
        else:
            major, minor, patch = 1, 0, 0
        if not changes:
            return SemanticVersionSuggestion(current_version=current_version, suggested_version=f"{major}.{minor}.{patch + 1}", version_bump="patch", reasoning="No breaking changes detected. Safe to release as a patch version.", confidence=0.95)
        impact = self.estimate_impact(changes)
        overall_impact = impact["overall_impact"]
        high_impact_types = {BreakingChangeType.REMOVED_ENDPOINT, BreakingChangeType.CHANGED_TYPE, BreakingChangeType.REMOVED_FIELD, BreakingChangeType.CHANGED_PATH, BreakingChangeType.CHANGED_METHOD}
        has_high_impact = any(c.change_type in high_impact_types for c in changes)
        if has_high_impact or overall_impact == "HIGH":
            reasoning = f"Detected {len(changes)} breaking change(s) including high-impact changes (removed endpoints, type changes, or removed fields). Recommend major version bump per semantic versioning."
            confidence = 0.90
        elif overall_impact == "MEDIUM":
            reasoning = f"Detected {len(changes)} breaking change(s) with medium impact. Breaking changes typically require a major version bump per semantic versioning, though some may consider these acceptable in a minor release with proper deprecation."
            confidence = 0.75
        else:
            reasoning = f"Detected {len(changes)} low-impact breaking change(s). Even minor breaking changes should trigger a major version bump per strict semantic versioning, but these may be acceptable in a minor release with advance notice."
            confidence = 0.60
        return SemanticVersionSuggestion(current_version=current_version, suggested_version=f"{major + 1}.0.0", version_bump="major", reasoning=reasoning, confidence=confidence)

    def analyze_detailed_impact(self, changes: list[BreakingChange]) -> dict[str, Any]:
        basic_impact = self.estimate_impact(changes)
        endpoints_affected: dict[str, list[BreakingChange]] = {}
        for change in changes:
            endpoint = change.path
            if endpoint not in endpoints_affected:
                endpoints_affected[endpoint] = []
            endpoints_affected[endpoint].append(change)
        type_distribution: dict[str, int] = {}
        for change in changes:
            change_type = str(change.change_type)
            type_distribution[change_type] = type_distribution.get(change_type, 0) + 1
        client_impact = calculate_client_impact(changes)
        impact_summary = []
        if basic_impact["high_impact_count"] > 0:
            impact_summary.append(f"{basic_impact['high_impact_count']} high-impact change(s) will likely break all clients")
        if basic_impact["medium_impact_count"] > 0:
            impact_summary.append(f"{basic_impact['medium_impact_count']} medium-impact change(s) may affect some client functionality")
        if basic_impact["low_impact_count"] > 0:
            impact_summary.append(f"{basic_impact['low_impact_count']} low-impact change(s) may require minor client updates")
        return {
            **basic_impact,
            "endpoints_affected": len(endpoints_affected), "endpoints_detail": endpoints_affected,
            "type_distribution": type_distribution, "client_impact": client_impact,
            "impact_summary": impact_summary, "total_changes": len(changes),
            "requires_migration_guide": basic_impact["overall_impact"] in ["HIGH", "MEDIUM"],
            "suggested_deprecation_period_days": suggest_deprecation_period(basic_impact["overall_impact"]),
        }

    def generate_migration_paths(self, changes: list[BreakingChange]) -> list[MigrationPath]:
        migration_paths = []
        for change in changes:
            steps = generate_migration_steps(change)
            effort, risk = estimate_migration_effort(change)
            migration_paths.append(MigrationPath(change_location=change.location, change_type=str(change.change_type), steps=steps, estimated_effort=effort, risk_level=risk))
        return migration_paths

    def calculate_compatibility_score(self, changes: list[BreakingChange], total_endpoints: int = 0, total_schemas: int = 0) -> CompatibilityScore:
        if not changes:
            return CompatibilityScore(overall_score=100.0, api_stability_score=100.0, schema_stability_score=100.0, parameter_stability_score=100.0, response_stability_score=100.0, grade="A", details={"message": "No breaking changes detected. Full backward compatibility maintained.", "changes_detected": 0})
        api_changes = []
        schema_changes = []
        parameter_changes = []
        response_changes = []
        for change in changes:
            ct = change.change_type
            if ct in {BreakingChangeType.REMOVED_ENDPOINT, BreakingChangeType.CHANGED_PATH, BreakingChangeType.CHANGED_METHOD}:
                api_changes.append(change)
            elif ct in {BreakingChangeType.REMOVED_FIELD, BreakingChangeType.CHANGED_TYPE, BreakingChangeType.REMOVED_ENUM_VALUE, BreakingChangeType.NARROWED_TYPE}:
                schema_changes.append(change)
            elif ct in {BreakingChangeType.REMOVED_PARAMETER, BreakingChangeType.ADDED_REQUIRED_PARAMETER, BreakingChangeType.CHANGED_REQUIRED}:
                parameter_changes.append(change)
            elif ct in {BreakingChangeType.REMOVED_RESPONSE, BreakingChangeType.CHANGED_RESPONSE_TYPE}:
                response_changes.append(change)
            else:
                schema_changes.append(change)
        high_penalty, medium_penalty, low_penalty = 15, 10, 5
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
        weights = {"api": 0.35, "schema": 0.25, "parameter": 0.20, "response": 0.20}
        overall = api_score * weights["api"] + schema_score * weights["schema"] + param_score * weights["parameter"] + response_score * weights["response"]
        grade = "A" if overall >= 90 else ("B" if overall >= 80 else ("C" if overall >= 70 else ("D" if overall >= 60 else "F")))
        details: dict[str, Any] = {
            "total_changes": len(changes), "api_changes": len(api_changes),
            "schema_changes": len(schema_changes), "parameter_changes": len(parameter_changes),
            "response_changes": len(response_changes), "weights_used": weights,
            "scoring_explanation": f"Score starts at 100 and is reduced based on breaking changes. High-severity changes reduce score by {high_penalty}, medium by {medium_penalty}, low by {low_penalty}.",
        }
        if total_endpoints > 0:
            details["endpoints_affected_percentage"] = round(len(api_changes) / total_endpoints * 100, 2)
        return CompatibilityScore(overall_score=round(overall, 2), api_stability_score=round(api_score, 2), schema_stability_score=round(schema_score, 2), parameter_stability_score=round(param_score, 2), response_stability_score=round(response_score, 2), grade=grade, details=details)

    def generate_comprehensive_report(self, old_version_path: str | Path, new_version_path: str | Path, current_version: str = "1.0.0") -> dict[str, Any]:
        changes = self.detect(old_version_path, new_version_path)
        version_suggestion = self.suggest_semantic_version(changes, current_version)
        detailed_impact = self.analyze_detailed_impact(changes)
        migration_paths = self.generate_migration_paths(changes)
        compatibility_score = self.calculate_compatibility_score(changes)
        mitigations = self.suggest_mitigations(changes)
        changelog = self.generate_changelog(changes, version_suggestion.suggested_version)
        return {
            "summary": {"total_breaking_changes": len(changes), "overall_impact": detailed_impact["overall_impact"], "compatibility_grade": compatibility_score.grade, "compatibility_score": compatibility_score.overall_score, "suggested_version": version_suggestion.suggested_version, "version_bump": version_suggestion.version_bump},
            "version_suggestion": {"current": version_suggestion.current_version, "suggested": version_suggestion.suggested_version, "bump_type": version_suggestion.version_bump, "reasoning": version_suggestion.reasoning, "confidence": version_suggestion.confidence},
            "impact_analysis": detailed_impact,
            "compatibility_score": {"overall": compatibility_score.overall_score, "grade": compatibility_score.grade, "api_stability": compatibility_score.api_stability_score, "schema_stability": compatibility_score.schema_stability_score, "parameter_stability": compatibility_score.parameter_stability_score, "response_stability": compatibility_score.response_stability_score, "details": compatibility_score.details},
            "migration_paths": [{"location": mp.change_location, "type": mp.change_type, "effort": mp.estimated_effort, "risk": mp.risk_level, "steps": [{"order": s.order, "action": s.action, "description": s.description, "code_example": s.code_example} for s in mp.steps]} for mp in migration_paths],
            "mitigations": mitigations, "changelog": changelog,
            "breaking_changes": [{"type": str(c.change_type), "path": c.path, "location": c.location, "message": c.message, "severity": c.severity, "old_value": c.old_value, "new_value": c.new_value} for c in changes],
        }
