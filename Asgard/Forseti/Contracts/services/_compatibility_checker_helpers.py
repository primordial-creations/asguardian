"""
Compatibility Checker Helpers.

Helper functions for CompatibilityCheckerService.
"""

from typing import Any, Optional

from Asgard.Forseti.Contracts.models.contract_models import (
    BreakingChange,
    BreakingChangeType,
    CompatibilityResult,
)


def check_parameters_compatibility(
    base_path: str,
    old_params: list[dict[str, Any]],
    new_params: list[dict[str, Any]],
    allow_added_required: bool,
) -> list[BreakingChange]:
    """Check parameter compatibility."""
    changes: list[BreakingChange] = []

    old_param_map = {
        (p.get("name"), p.get("in")): p
        for p in old_params
    }
    new_param_map = {
        (p.get("name"), p.get("in")): p
        for p in new_params
    }

    for (name, loc), param in old_param_map.items():
        if (name, loc) not in new_param_map:
            changes.append(BreakingChange(
                change_type=BreakingChangeType.REMOVED_PARAMETER,
                path=base_path,
                location=f"parameters/{name}",
                message=f"Parameter '{name}' ({loc}) removed",
                old_value=name,
                severity="error",
            ))

    if not allow_added_required:
        for (name, loc), param in new_param_map.items():
            if (name, loc) not in old_param_map:
                if param.get("required", False):
                    changes.append(BreakingChange(
                        change_type=BreakingChangeType.ADDED_REQUIRED_PARAMETER,
                        path=base_path,
                        location=f"parameters/{name}",
                        message=f"Required parameter '{name}' added",
                        new_value=name,
                        severity="error",
                        mitigation="Make the parameter optional with a default value",
                    ))

    return changes


def check_request_body_compatibility(
    base_path: str,
    old_body: Optional[dict[str, Any]],
    new_body: Optional[dict[str, Any]],
    allow_added_required: bool,
) -> list[BreakingChange]:
    """Check request body compatibility."""
    changes: list[BreakingChange] = []

    if old_body and not new_body:
        changes.append(BreakingChange(
            change_type=BreakingChangeType.REMOVED_FIELD,
            path=base_path,
            location="requestBody",
            message="Request body removed",
            severity="error",
        ))
    elif not old_body and new_body and new_body.get("required", False):
        if not allow_added_required:
            changes.append(BreakingChange(
                change_type=BreakingChangeType.CHANGED_REQUIRED,
                path=base_path,
                location="requestBody",
                message="Required request body added",
                severity="error",
                mitigation="Make the request body optional",
            ))

    return changes


def check_responses_compatibility(
    base_path: str,
    old_responses: dict[str, Any],
    new_responses: dict[str, Any],
) -> list[BreakingChange]:
    """Check response compatibility."""
    changes: list[BreakingChange] = []

    for status_code in old_responses:
        if status_code not in new_responses:
            changes.append(BreakingChange(
                change_type=BreakingChangeType.REMOVED_RESPONSE,
                path=base_path,
                location=f"responses/{status_code}",
                message=f"Response {status_code} removed",
                old_value=status_code,
                severity="warning",
            ))

    return changes


def check_schema_properties(
    base_path: str,
    old_schema: dict[str, Any],
    new_schema: dict[str, Any],
    allow_added_required: bool,
) -> list[BreakingChange]:
    """Check schema property compatibility."""
    changes: list[BreakingChange] = []

    old_props = old_schema.get("properties", {})
    new_props = new_schema.get("properties", {})
    old_required = set(old_schema.get("required", []))
    new_required = set(new_schema.get("required", []))

    for prop_name in old_props:
        if prop_name not in new_props:
            changes.append(BreakingChange(
                change_type=BreakingChangeType.REMOVED_FIELD,
                path=base_path,
                location=f"properties/{prop_name}",
                message=f"Property '{prop_name}' removed",
                old_value=prop_name,
                severity="error",
            ))

    if not allow_added_required:
        for prop_name in new_required - old_required:
            if prop_name in old_props:
                changes.append(BreakingChange(
                    change_type=BreakingChangeType.CHANGED_REQUIRED,
                    path=base_path,
                    location=f"properties/{prop_name}",
                    message=f"Property '{prop_name}' changed to required",
                    new_value="required=true",
                    severity="error",
                    mitigation="Keep the property optional",
                ))

    for prop_name in old_props:
        if prop_name in new_props:
            old_type = old_props[prop_name].get("type")
            new_type = new_props[prop_name].get("type")
            if old_type != new_type:
                changes.append(BreakingChange(
                    change_type=BreakingChangeType.CHANGED_TYPE,
                    path=base_path,
                    location=f"properties/{prop_name}",
                    message=f"Property '{prop_name}' type changed from '{old_type}' to '{new_type}'",
                    old_value=str(old_type),
                    new_value=str(new_type),
                    severity="error",
                ))

    return changes


def generate_text_report(result: CompatibilityResult) -> str:
    """Generate a text format report."""
    lines = []
    lines.append("=" * 60)
    lines.append("API Compatibility Report")
    lines.append("=" * 60)
    lines.append(f"Old Version: {result.source_version or 'N/A'}")
    lines.append(f"New Version: {result.target_version or 'N/A'}")
    lines.append(f"Compatible: {'Yes' if result.is_compatible else 'No'}")
    lines.append(f"Compatibility Level: {result.compatibility_level}")
    lines.append(f"Breaking Changes: {result.breaking_change_count}")
    lines.append(f"Time: {result.check_time_ms:.2f}ms")
    lines.append("-" * 60)

    if result.added_endpoints:
        lines.append(f"\nAdded Endpoints: {', '.join(result.added_endpoints)}")
    if result.removed_endpoints:
        lines.append(f"Removed Endpoints: {', '.join(result.removed_endpoints)}")
    if result.modified_endpoints:
        lines.append(f"Modified Endpoints: {', '.join(result.modified_endpoints)}")

    if result.breaking_changes:
        lines.append("\nBreaking Changes:")
        for change in result.breaking_changes:
            lines.append(f"  [{change.change_type}] {change.message}")
            if change.mitigation:
                lines.append(f"    Mitigation: {change.mitigation}")

    lines.append("=" * 60)
    return "\n".join(lines)


def generate_markdown_report(result: CompatibilityResult) -> str:
    """Generate a markdown format report."""
    lines = []
    lines.append("# API Compatibility Report\n")
    lines.append(f"- **Old Version**: {result.source_version or 'N/A'}")
    lines.append(f"- **New Version**: {result.target_version or 'N/A'}")
    lines.append(f"- **Compatible**: {'Yes' if result.is_compatible else 'No'}")
    lines.append(f"- **Compatibility Level**: {result.compatibility_level}")
    lines.append(f"- **Breaking Changes**: {result.breaking_change_count}\n")

    if result.breaking_changes:
        lines.append("## Breaking Changes\n")
        lines.append("| Type | Location | Message |")
        lines.append("|------|----------|---------|")
        for change in result.breaking_changes:
            lines.append(f"| {change.change_type} | `{change.location}` | {change.message} |")

    if result.added_endpoints:
        lines.append("\n## Added Endpoints\n")
        for ep in result.added_endpoints:
            lines.append(f"- `{ep}`")

    if result.removed_endpoints:
        lines.append("\n## Removed Endpoints\n")
        for ep in result.removed_endpoints:
            lines.append(f"- `{ep}`")

    return "\n".join(lines)
