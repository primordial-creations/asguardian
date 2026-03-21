"""
Avro Schema Compatibility Checker Service.

Checks compatibility between Apache Avro schema versions.
Supports backward, forward, and full compatibility modes.
"""

import json
import time
from pathlib import Path
from typing import Any, Optional

from Asgard.Forseti.Avro.models.avro_models import (
    AvroCompatibilityResult,
    AvroConfig,
    BreakingChange,
    BreakingChangeType,
    CompatibilityLevel,
    CompatibilityMode,
)
from Asgard.Forseti.Avro.services.avro_validator_service import AvroValidatorService
from Asgard.Forseti.Avro.services._avro_compatibility_service_helpers import (
    check_compatibility,
)
from Asgard.Forseti.Avro.services._avro_compatibility_report_helpers import (
    generate_markdown_report,
    generate_text_report,
)


class AvroCompatibilityService:
    """
    Service for checking Avro schema compatibility.

    Checks backward, forward, or full compatibility between schema versions
    and reports breaking changes.

    Compatibility Modes:
    - BACKWARD: New schema can read data written with old schema
    - FORWARD: Old schema can read data written with new schema
    - FULL: Both backward and forward compatible

    Usage:
        service = AvroCompatibilityService()
        result = service.check("old.avsc", "new.avsc")
        if not result.is_compatible:
            for change in result.breaking_changes:
                print(f"Breaking: {change.message}")
    """

    def __init__(self, config: Optional[AvroConfig] = None):
        self.config = config or AvroConfig()
        self.validator = AvroValidatorService(self.config)

    def check(
        self,
        old_schema_path: str | Path,
        new_schema_path: str | Path,
        mode: Optional[CompatibilityMode] = None,
    ) -> AvroCompatibilityResult:
        start_time = time.time()
        mode = mode or self.config.compatibility_mode
        breaking_changes: list[BreakingChange] = []
        warnings: list[BreakingChange] = []
        added_fields: list[str] = []
        removed_fields: list[str] = []
        modified_fields: list[str] = []
        old_result = self.validator.validate_file(old_schema_path)
        new_result = self.validator.validate_file(new_schema_path)
        if not old_result.parsed_schema or not old_result.parsed_schema.raw_schema:
            return AvroCompatibilityResult(
                is_compatible=False,
                compatibility_level=CompatibilityLevel.NONE,
                compatibility_mode=mode,
                source_file=str(old_schema_path),
                target_file=str(new_schema_path),
                breaking_changes=[BreakingChange(
                    change_type=BreakingChangeType.REMOVED_TYPE,
                    path="/",
                    message=f"Failed to parse old schema: {old_result.errors[0].message if old_result.errors else 'Unknown error'}",
                )],
                check_time_ms=(time.time() - start_time) * 1000,
            )
        if not new_result.parsed_schema or not new_result.parsed_schema.raw_schema:
            return AvroCompatibilityResult(
                is_compatible=False,
                compatibility_level=CompatibilityLevel.NONE,
                compatibility_mode=mode,
                source_file=str(old_schema_path),
                target_file=str(new_schema_path),
                breaking_changes=[BreakingChange(
                    change_type=BreakingChangeType.REMOVED_TYPE,
                    path="/",
                    message=f"Failed to parse new schema: {new_result.errors[0].message if new_result.errors else 'Unknown error'}",
                )],
                check_time_ms=(time.time() - start_time) * 1000,
            )
        old_schema = old_result.parsed_schema.raw_schema
        new_schema = new_result.parsed_schema.raw_schema
        changes = self._run_compatibility_check(old_schema, new_schema, mode)
        for change in changes:
            if change.severity == "error":
                breaking_changes.append(change)
            else:
                warnings.append(change)
        if old_result.parsed_schema.fields and new_result.parsed_schema.fields:
            old_field_names = {f.name for f in old_result.parsed_schema.fields}
            new_field_names = {f.name for f in new_result.parsed_schema.fields}
            added_fields = list(new_field_names - old_field_names)
            removed_fields = list(old_field_names - new_field_names)
            for name in old_field_names & new_field_names:
                old_field = next(f for f in old_result.parsed_schema.fields if f.name == name)
                new_field = next(f for f in new_result.parsed_schema.fields if f.name == name)
                if str(old_field.type) != str(new_field.type):
                    modified_fields.append(name)
        if not breaking_changes:
            compatibility_level = CompatibilityLevel.FULL
        elif mode == CompatibilityMode.BACKWARD and not any(
            c.change_type in [BreakingChangeType.REMOVED_FIELD, BreakingChangeType.CHANGED_FIELD_TYPE]
            for c in breaking_changes
        ):
            compatibility_level = CompatibilityLevel.FORWARD
        else:
            compatibility_level = CompatibilityLevel.NONE
        return AvroCompatibilityResult(
            is_compatible=len(breaking_changes) == 0,
            compatibility_level=compatibility_level,
            compatibility_mode=mode,
            source_file=str(old_schema_path),
            target_file=str(new_schema_path),
            breaking_changes=breaking_changes,
            warnings=warnings,
            added_fields=added_fields,
            removed_fields=removed_fields,
            modified_fields=modified_fields,
            check_time_ms=(time.time() - start_time) * 1000,
        )

    def check_schemas(
        self,
        old_schema: dict[str, Any],
        new_schema: dict[str, Any],
        mode: Optional[CompatibilityMode] = None,
    ) -> AvroCompatibilityResult:
        start_time = time.time()
        mode = mode or self.config.compatibility_mode
        changes = self._run_compatibility_check(old_schema, new_schema, mode)
        breaking_changes = [c for c in changes if c.severity == "error"]
        warnings = [c for c in changes if c.severity != "error"]
        compatibility_level = CompatibilityLevel.FULL if not breaking_changes else CompatibilityLevel.NONE
        return AvroCompatibilityResult(
            is_compatible=len(breaking_changes) == 0,
            compatibility_level=compatibility_level,
            compatibility_mode=mode,
            breaking_changes=breaking_changes,
            warnings=warnings,
            check_time_ms=(time.time() - start_time) * 1000,
        )

    def _run_compatibility_check(
        self,
        old_schema: dict[str, Any],
        new_schema: dict[str, Any],
        mode: CompatibilityMode,
    ) -> list[BreakingChange]:
        if mode == CompatibilityMode.BACKWARD:
            return check_compatibility("/", old_schema, new_schema, is_backward=True)
        elif mode == CompatibilityMode.FORWARD:
            return check_compatibility("/", new_schema, old_schema, is_backward=False)
        elif mode == CompatibilityMode.FULL:
            backward = check_compatibility("/", old_schema, new_schema, is_backward=True)
            forward = check_compatibility("/", new_schema, old_schema, is_backward=False)
            return backward + forward
        return []

    def generate_report(self, result: AvroCompatibilityResult, format: str = "text") -> str:
        if format == "json":
            return json.dumps(result.model_dump(), indent=2, default=str)
        elif format == "markdown":
            return generate_markdown_report(result)
        else:
            return generate_text_report(result)
