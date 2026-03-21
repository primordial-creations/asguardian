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
from Asgard.Forseti.Contracts.services._compatibility_checker_helpers import (
    check_parameters_compatibility,
    check_request_body_compatibility,
    check_responses_compatibility,
    check_schema_properties,
    generate_markdown_report,
    generate_text_report,
)


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

        for path in new_paths - old_paths:
            added_endpoints.append(path)

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

        schema_changes = self._check_schema_compatibility(
            old_spec.get("components", {}).get("schemas", {}),
            new_spec.get("components", {}).get("schemas", {})
        )
        for change in schema_changes:
            if change.severity == "error":
                breaking_changes.append(change)
            else:
                warnings.append(change)

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

        if self.config.check_parameters:
            changes.extend(check_parameters_compatibility(
                base_path,
                old_op.get("parameters", []),
                new_op.get("parameters", []),
                self.config.allow_added_required,
            ))

        if self.config.check_request_body:
            changes.extend(check_request_body_compatibility(
                base_path,
                old_op.get("requestBody"),
                new_op.get("requestBody"),
                self.config.allow_added_required,
            ))

        if self.config.check_response_body:
            changes.extend(check_responses_compatibility(
                base_path,
                old_op.get("responses", {}),
                new_op.get("responses", {}),
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
                schema_changes = check_schema_properties(
                    f"#/components/schemas/{name}",
                    old_schema,
                    new_schemas[name],
                    self.config.allow_added_required,
                )
                changes.extend(schema_changes)

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
            return generate_markdown_report(result)
        else:
            return generate_text_report(result)
