"""
Compatibility Checker Service.

Checks backward compatibility between API versions.
"""

import json
import time
from pathlib import Path
from typing import Any, Optional

from Asgard.Forseti.Contracts.models.contract_models import (
    ContractConfig,
    CompatibilityResult,
    BreakingChange,
    BreakingChangeType,
    CompatibilityLevel,
)
from Asgard.Forseti.Contracts.utilities.contract_utils import load_contract_file


class CompatibilityCheckerService:
    """
    Service for checking API compatibility.

    Checks backward compatibility between API versions and reports
    breaking changes.

    Usage:
        service = CompatibilityCheckerService()
        result = service.check("v1.yaml", "v2.yaml")
        if not result.is_compatible:
            for change in result.breaking_changes:
                print(f"Breaking: {change.message}")
    """

    def __init__(self, config: Optional[ContractConfig] = None):
        """
        Initialize the compatibility checker service.

        Args:
            config: Optional configuration for checking behavior.
        """
        self.config = config or ContractConfig()

    def check(
        self,
        old_version_path: str | Path,
        new_version_path: str | Path
    ) -> CompatibilityResult:
        """
        Check compatibility between two API versions.

        Args:
            old_version_path: Path to the old version specification.
            new_version_path: Path to the new version specification.

        Returns:
            CompatibilityResult with compatibility details.
        """
        start_time = time.time()

        breaking_changes: list[BreakingChange] = []
        warnings: list[BreakingChange] = []
        added_endpoints: list[str] = []
        removed_endpoints: list[str] = []
        modified_endpoints: list[str] = []

        # Load specifications
        try:
            old_spec = load_contract_file(Path(old_version_path))
            new_spec = load_contract_file(Path(new_version_path))
        except Exception as e:
            return CompatibilityResult(
                is_compatible=False,
                compatibility_level=CompatibilityLevel.NONE,
                source_version=str(old_version_path),
                target_version=str(new_version_path),
                breaking_changes=[BreakingChange(
                    change_type=BreakingChangeType.REMOVED_ENDPOINT,
                    path="/",
                    location="/",
                    message=f"Failed to load specifications: {str(e)}",
                )],
                check_time_ms=(time.time() - start_time) * 1000,
            )

        old_paths = set(old_spec.get("paths", {}).keys())
        new_paths = set(new_spec.get("paths", {}).keys())

        # Find removed endpoints (breaking)
        for path in old_paths - new_paths:
            removed_endpoints.append(path)
            breaking_changes.append(BreakingChange(
                change_type=BreakingChangeType.REMOVED_ENDPOINT,
                path=path,
                location=path,
                message=f"Endpoint removed: {path}",
                old_value=path,
                severity="error",
                mitigation="Keep the endpoint for backward compatibility or version the API",
            ))

        # Find added endpoints (non-breaking)
        for path in new_paths - old_paths:
            added_endpoints.append(path)

        # Check modified endpoints
        for path in old_paths & new_paths:
            old_item = old_spec.get("paths", {}).get(path, {})
            new_item = new_spec.get("paths", {}).get(path, {})

            path_changes = self._check_path_compatibility(path, old_item, new_item)
            if path_changes:
                modified_endpoints.append(path)
                for change in path_changes:
                    if change.severity == "error":
                        breaking_changes.append(change)
                    else:
                        warnings.append(change)

        # Check schema changes
        schema_changes = self._check_schema_compatibility(
            old_spec.get("components", {}).get("schemas", {}),
            new_spec.get("components", {}).get("schemas", {})
        )
        for change in schema_changes:
            if change.severity == "error":
                breaking_changes.append(change)
            else:
                warnings.append(change)

        # Determine compatibility level
        if not breaking_changes:
            compatibility_level = CompatibilityLevel.FULL
        elif not removed_endpoints:
            compatibility_level = CompatibilityLevel.BACKWARD
        else:
            compatibility_level = CompatibilityLevel.NONE

        check_time_ms = (time.time() - start_time) * 1000

        return CompatibilityResult(
            is_compatible=len(breaking_changes) == 0,
            compatibility_level=compatibility_level,
            source_version=str(old_version_path),
            target_version=str(new_version_path),
            breaking_changes=breaking_changes,
            warnings=warnings,
            added_endpoints=added_endpoints,
            removed_endpoints=removed_endpoints,
            modified_endpoints=modified_endpoints,
            check_time_ms=check_time_ms,
        )

    def _check_path_compatibility(
        self,
        path: str,
        old_item: dict[str, Any],
        new_item: dict[str, Any]
    ) -> list[BreakingChange]:
        """Check compatibility for a single path."""
        changes: list[BreakingChange] = []
        methods = ["get", "post", "put", "delete", "patch", "options", "head"]

        for method in methods:
            if method in old_item and method not in new_item:
                changes.append(BreakingChange(
                    change_type=BreakingChangeType.REMOVED_ENDPOINT,
                    path=path,
                    location=f"{path}/{method}",
                    message=f"Method {method.upper()} removed from {path}",
                    old_value=method.upper(),
                    severity="error",
                ))
            elif method in old_item and method in new_item:
                op_changes = self._check_operation_compatibility(
                    path, method, old_item[method], new_item[method]
                )
                changes.extend(op_changes)

        return changes

    def _check_operation_compatibility(
        self,
        path: str,
        method: str,
        old_op: dict[str, Any],
        new_op: dict[str, Any]
    ) -> list[BreakingChange]:
        """Check compatibility for a single operation."""
        changes: list[BreakingChange] = []
        base_path = f"{path}/{method}"

        # Check parameters
        if self.config.check_parameters:
            param_changes = self._check_parameters_compatibility(
                base_path,
                old_op.get("parameters", []),
                new_op.get("parameters", [])
            )
            changes.extend(param_changes)

        # Check request body
        if self.config.check_request_body:
            body_changes = self._check_request_body_compatibility(
                base_path,
                old_op.get("requestBody"),
                new_op.get("requestBody")
            )
            changes.extend(body_changes)

        # Check responses
        if self.config.check_response_body:
            resp_changes = self._check_responses_compatibility(
                base_path,
                old_op.get("responses", {}),
                new_op.get("responses", {})
            )
            changes.extend(resp_changes)

        return changes

    def _check_parameters_compatibility(
        self,
        base_path: str,
        old_params: list[dict[str, Any]],
        new_params: list[dict[str, Any]]
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

        # Check for removed parameters
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

        # Check for added required parameters
        if not self.config.allow_added_required:
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

    def _check_request_body_compatibility(
        self,
        base_path: str,
        old_body: Optional[dict[str, Any]],
        new_body: Optional[dict[str, Any]]
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
            if not self.config.allow_added_required:
                changes.append(BreakingChange(
                    change_type=BreakingChangeType.CHANGED_REQUIRED,
                    path=base_path,
                    location="requestBody",
                    message="Required request body added",
                    severity="error",
                    mitigation="Make the request body optional",
                ))

        return changes

    def _check_responses_compatibility(
        self,
        base_path: str,
        old_responses: dict[str, Any],
        new_responses: dict[str, Any]
    ) -> list[BreakingChange]:
        """Check response compatibility."""
        changes: list[BreakingChange] = []

        # Check for removed responses
        for status_code in old_responses:
            if status_code not in new_responses:
                changes.append(BreakingChange(
                    change_type=BreakingChangeType.REMOVED_RESPONSE,
                    path=base_path,
                    location=f"responses/{status_code}",
                    message=f"Response {status_code} removed",
                    old_value=status_code,
                    severity="warning",  # Removing responses is less critical
                ))

        return changes

    def _check_schema_compatibility(
        self,
        old_schemas: dict[str, Any],
        new_schemas: dict[str, Any]
    ) -> list[BreakingChange]:
        """Check schema compatibility."""
        changes: list[BreakingChange] = []

        for name, old_schema in old_schemas.items():
            if name not in new_schemas:
                changes.append(BreakingChange(
                    change_type=BreakingChangeType.REMOVED_FIELD,
                    path=f"#/components/schemas/{name}",
                    location=name,
                    message=f"Schema '{name}' removed",
                    old_value=name,
                    severity="error",
                ))
            else:
                new_schema = new_schemas[name]
                schema_changes = self._check_schema_properties(
                    f"#/components/schemas/{name}",
                    old_schema,
                    new_schema
                )
                changes.extend(schema_changes)

        return changes

    def _check_schema_properties(
        self,
        base_path: str,
        old_schema: dict[str, Any],
        new_schema: dict[str, Any]
    ) -> list[BreakingChange]:
        """Check schema property compatibility."""
        changes: list[BreakingChange] = []

        old_props = old_schema.get("properties", {})
        new_props = new_schema.get("properties", {})
        old_required = set(old_schema.get("required", []))
        new_required = set(new_schema.get("required", []))

        # Check for removed properties
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

        # Check for newly required properties
        if not self.config.allow_added_required:
            for prop_name in new_required - old_required:
                if prop_name in old_props:  # Only if it existed before
                    changes.append(BreakingChange(
                        change_type=BreakingChangeType.CHANGED_REQUIRED,
                        path=base_path,
                        location=f"properties/{prop_name}",
                        message=f"Property '{prop_name}' changed to required",
                        new_value="required=true",
                        severity="error",
                        mitigation="Keep the property optional",
                    ))

        # Check type changes
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

    def generate_report(
        self,
        result: CompatibilityResult,
        format: str = "text"
    ) -> str:
        """Generate a compatibility report."""
        if format == "json":
            return json.dumps(result.model_dump(), indent=2, default=str)
        elif format == "markdown":
            return self._generate_markdown_report(result)
        else:
            return self._generate_text_report(result)

    def _generate_text_report(self, result: CompatibilityResult) -> str:
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

    def _generate_markdown_report(self, result: CompatibilityResult) -> str:
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
