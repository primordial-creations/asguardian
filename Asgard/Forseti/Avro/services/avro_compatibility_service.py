"""
Avro Schema Compatibility Checker Service.

Checks compatibility between Apache Avro schema versions.
Supports backward, forward, and full compatibility modes.
"""

import json
import time
from pathlib import Path
from typing import Any, Optional, cast

from Asgard.Forseti.Avro.models.avro_models import (
    AvroCompatibilityResult,
    AvroConfig,
    AvroSchema,
    BreakingChange,
    BreakingChangeType,
    CompatibilityLevel,
    CompatibilityMode,
)
from Asgard.Forseti.Avro.services.avro_validator_service import (
    AvroValidatorService,
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
        """
        Initialize the compatibility checker service.

        Args:
            config: Optional configuration for checking behavior.
        """
        self.config = config or AvroConfig()
        self.validator = AvroValidatorService(self.config)

    def check(
        self,
        old_schema_path: str | Path,
        new_schema_path: str | Path,
        mode: Optional[CompatibilityMode] = None
    ) -> AvroCompatibilityResult:
        """
        Check compatibility between two Avro schema versions.

        Args:
            old_schema_path: Path to the old schema file.
            new_schema_path: Path to the new schema file.
            mode: Compatibility mode to check (default from config).

        Returns:
            AvroCompatibilityResult with compatibility details.
        """
        start_time = time.time()
        mode = mode or self.config.compatibility_mode

        breaking_changes: list[BreakingChange] = []
        warnings: list[BreakingChange] = []
        added_fields: list[str] = []
        removed_fields: list[str] = []
        modified_fields: list[str] = []

        # Load and validate both schemas
        old_result = self.validator.validate_file(old_schema_path)
        new_result = self.validator.validate_file(new_schema_path)

        # Check if parsing succeeded
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

        # Perform compatibility check based on mode
        if mode == CompatibilityMode.BACKWARD:
            changes = self._check_backward_compatibility(old_schema, new_schema)
        elif mode == CompatibilityMode.FORWARD:
            changes = self._check_forward_compatibility(old_schema, new_schema)
        elif mode == CompatibilityMode.FULL:
            backward_changes = self._check_backward_compatibility(old_schema, new_schema)
            forward_changes = self._check_forward_compatibility(old_schema, new_schema)
            changes = backward_changes + forward_changes
        else:
            changes = []

        # Categorize changes
        for change in changes:
            if change.severity == "error":
                breaking_changes.append(change)
            else:
                warnings.append(change)

        # Collect field-level changes
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

        # Determine compatibility level
        if not breaking_changes:
            compatibility_level = CompatibilityLevel.FULL
        elif mode == CompatibilityMode.BACKWARD and not any(
            c.change_type in [BreakingChangeType.REMOVED_FIELD, BreakingChangeType.CHANGED_FIELD_TYPE]
            for c in breaking_changes
        ):
            compatibility_level = CompatibilityLevel.FORWARD
        else:
            compatibility_level = CompatibilityLevel.NONE

        check_time_ms = (time.time() - start_time) * 1000

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
            check_time_ms=check_time_ms,
        )

    def check_schemas(
        self,
        old_schema: dict[str, Any],
        new_schema: dict[str, Any],
        mode: Optional[CompatibilityMode] = None
    ) -> AvroCompatibilityResult:
        """
        Check compatibility between two parsed schemas.

        Args:
            old_schema: The old schema as a dictionary.
            new_schema: The new schema as a dictionary.
            mode: Compatibility mode to check (default from config).

        Returns:
            AvroCompatibilityResult with compatibility details.
        """
        start_time = time.time()
        mode = mode or self.config.compatibility_mode

        # Perform compatibility check based on mode
        if mode == CompatibilityMode.BACKWARD:
            changes = self._check_backward_compatibility(old_schema, new_schema)
        elif mode == CompatibilityMode.FORWARD:
            changes = self._check_forward_compatibility(old_schema, new_schema)
        elif mode == CompatibilityMode.FULL:
            backward_changes = self._check_backward_compatibility(old_schema, new_schema)
            forward_changes = self._check_forward_compatibility(old_schema, new_schema)
            changes = backward_changes + forward_changes
        else:
            changes = []

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

    def _check_backward_compatibility(
        self,
        old_schema: dict[str, Any],
        new_schema: dict[str, Any]
    ) -> list[BreakingChange]:
        """
        Check backward compatibility (new reader, old writer).

        New schema must be able to read data written with old schema.
        """
        return self._check_compatibility("/", old_schema, new_schema, is_backward=True)

    def _check_forward_compatibility(
        self,
        old_schema: dict[str, Any],
        new_schema: dict[str, Any]
    ) -> list[BreakingChange]:
        """
        Check forward compatibility (old reader, new writer).

        Old schema must be able to read data written with new schema.
        """
        return self._check_compatibility("/", new_schema, old_schema, is_backward=False)

    def _check_compatibility(
        self,
        path: str,
        writer_schema: dict[str, Any],
        reader_schema: dict[str, Any],
        is_backward: bool
    ) -> list[BreakingChange]:
        """Check compatibility between writer and reader schemas."""
        changes: list[BreakingChange] = []

        writer_type = self._get_schema_type(writer_schema)
        reader_type = self._get_schema_type(reader_schema)

        # Check type compatibility
        if not self._types_compatible(writer_type, reader_type):
            change_type = BreakingChangeType.CHANGED_FIELD_TYPE
            direction = "backward" if is_backward else "forward"
            changes.append(BreakingChange(
                change_type=change_type,
                path=path,
                message=f"Incompatible types for {direction} compatibility: writer='{writer_type}', reader='{reader_type}'",
                old_value=writer_type,
                new_value=reader_type,
                severity="error",
            ))
            return changes

        # Check specific type compatibility rules
        if writer_type == "record":
            changes.extend(self._check_record_compatibility(
                path, writer_schema, reader_schema, is_backward
            ))
        elif writer_type == "enum":
            changes.extend(self._check_enum_compatibility(
                path, writer_schema, reader_schema, is_backward
            ))
        elif writer_type == "array":
            changes.extend(self._check_array_compatibility(
                path, writer_schema, reader_schema, is_backward
            ))
        elif writer_type == "map":
            changes.extend(self._check_map_compatibility(
                path, writer_schema, reader_schema, is_backward
            ))
        elif writer_type == "fixed":
            changes.extend(self._check_fixed_compatibility(
                path, writer_schema, reader_schema, is_backward
            ))
        elif writer_type == "union":
            changes.extend(self._check_union_compatibility(
                path, writer_schema, reader_schema, is_backward
            ))

        return changes

    def _get_schema_type(self, schema: Any) -> str:
        """Get the type of a schema."""
        if isinstance(schema, str):
            return schema
        if isinstance(schema, list):
            return "union"
        if isinstance(schema, dict):
            return cast(str, schema.get("type", "unknown"))
        return "unknown"

    def _types_compatible(self, writer_type: str, reader_type: str) -> bool:
        """Check if two types are compatible for reading."""
        if writer_type == reader_type:
            return True

        # Promotion rules
        promotions = {
            "int": {"long", "float", "double"},
            "long": {"float", "double"},
            "float": {"double"},
            "string": {"bytes"},
            "bytes": {"string"},
        }

        if writer_type in promotions:
            if reader_type in promotions[writer_type]:
                return True

        return False

    def _check_record_compatibility(
        self,
        path: str,
        writer_schema: dict[str, Any],
        reader_schema: dict[str, Any],
        is_backward: bool
    ) -> list[BreakingChange]:
        """Check compatibility for record types."""
        changes: list[BreakingChange] = []

        # Check name and namespace
        writer_name = writer_schema.get("name", "")
        reader_name = reader_schema.get("name", "")
        writer_ns = writer_schema.get("namespace", "")
        reader_ns = reader_schema.get("namespace", "")

        writer_full = f"{writer_ns}.{writer_name}" if writer_ns else writer_name
        reader_full = f"{reader_ns}.{reader_name}" if reader_ns else reader_name

        # Check aliases
        reader_aliases = set(reader_schema.get("aliases", []))
        if writer_full != reader_full and writer_full not in reader_aliases:
            changes.append(BreakingChange(
                change_type=BreakingChangeType.CHANGED_NAME,
                path=path,
                message=f"Record name changed from '{writer_full}' to '{reader_full}' without alias",
                old_value=writer_full,
                new_value=reader_full,
                severity="error",
                mitigation="Add an alias for the old name",
            ))

        writer_fields = {f["name"]: f for f in writer_schema.get("fields", [])}
        reader_fields = {f["name"]: f for f in reader_schema.get("fields", [])}

        # Also consider field aliases
        reader_field_by_alias: dict[str, dict] = {}
        for field in reader_schema.get("fields", []):
            for alias in field.get("aliases", []):
                reader_field_by_alias[alias] = field

        # Check writer fields (must be readable by reader)
        for field_name, writer_field in writer_fields.items():
            reader_field = reader_fields.get(field_name) or reader_field_by_alias.get(field_name)

            if reader_field is None:
                # Field not in reader - reader will get default or error
                changes.append(BreakingChange(
                    change_type=BreakingChangeType.REMOVED_FIELD,
                    path=f"{path}/fields/{field_name}",
                    message=f"Field '{field_name}' exists in writer but not in reader (will be ignored)",
                    old_value=field_name,
                    severity="warning",
                ))
            else:
                # Check field type compatibility
                field_path = f"{path}/fields/{field_name}"
                field_changes = self._check_compatibility(
                    field_path,
                    writer_field["type"],
                    reader_field["type"],
                    is_backward
                )
                changes.extend(field_changes)

        # Check reader fields (must have default or be in writer)
        for field_name, reader_field in reader_fields.items():
            if field_name not in writer_fields:
                # Check if any alias matches
                has_alias_match = False
                for alias in reader_field.get("aliases", []):
                    if alias in writer_fields:
                        has_alias_match = True
                        break

                if not has_alias_match:
                    # New field - must have default
                    if "default" not in reader_field:
                        changes.append(BreakingChange(
                            change_type=BreakingChangeType.ADDED_REQUIRED_FIELD,
                            path=f"{path}/fields/{field_name}",
                            message=f"New field '{field_name}' without default value",
                            new_value=field_name,
                            severity="error",
                            mitigation="Add a default value for the new field",
                        ))
                    else:
                        changes.append(BreakingChange(
                            change_type=BreakingChangeType.ADDED_REQUIRED_FIELD,
                            path=f"{path}/fields/{field_name}",
                            message=f"New field '{field_name}' added with default value",
                            new_value=field_name,
                            severity="warning",
                        ))

        return changes

    def _check_enum_compatibility(
        self,
        path: str,
        writer_schema: dict[str, Any],
        reader_schema: dict[str, Any],
        is_backward: bool
    ) -> list[BreakingChange]:
        """Check compatibility for enum types."""
        changes: list[BreakingChange] = []

        writer_symbols = set(writer_schema.get("symbols", []))
        reader_symbols = set(reader_schema.get("symbols", []))

        # Symbols in writer but not in reader
        removed_symbols = writer_symbols - reader_symbols
        if removed_symbols:
            # Check if reader has a default
            if "default" not in reader_schema:
                for symbol in removed_symbols:
                    changes.append(BreakingChange(
                        change_type=BreakingChangeType.REMOVED_ENUM_SYMBOL,
                        path=f"{path}/symbols/{symbol}",
                        message=f"Enum symbol '{symbol}' was removed from reader without default",
                        old_value=symbol,
                        severity="error",
                        mitigation="Add a default value to the enum",
                    ))
            else:
                for symbol in removed_symbols:
                    changes.append(BreakingChange(
                        change_type=BreakingChangeType.REMOVED_ENUM_SYMBOL,
                        path=f"{path}/symbols/{symbol}",
                        message=f"Enum symbol '{symbol}' was removed (will use default)",
                        old_value=symbol,
                        severity="warning",
                    ))

        # Check symbol order (matters for sorting)
        writer_order = writer_schema.get("symbols", [])
        reader_order = reader_schema.get("symbols", [])

        common_symbols = [s for s in writer_order if s in reader_symbols]
        reader_common = [s for s in reader_order if s in writer_symbols]

        if common_symbols != reader_common:
            changes.append(BreakingChange(
                change_type=BreakingChangeType.CHANGED_ENUM_ORDER,
                path=path,
                message="Enum symbol order changed (may affect sort order)",
                severity="warning",
            ))

        return changes

    def _check_array_compatibility(
        self,
        path: str,
        writer_schema: dict[str, Any],
        reader_schema: dict[str, Any],
        is_backward: bool
    ) -> list[BreakingChange]:
        """Check compatibility for array types."""
        writer_items = writer_schema.get("items", "null")
        reader_items = reader_schema.get("items", "null")

        return self._check_compatibility(
            f"{path}/items",
            writer_items,
            reader_items,
            is_backward
        )

    def _check_map_compatibility(
        self,
        path: str,
        writer_schema: dict[str, Any],
        reader_schema: dict[str, Any],
        is_backward: bool
    ) -> list[BreakingChange]:
        """Check compatibility for map types."""
        writer_values = writer_schema.get("values", "null")
        reader_values = reader_schema.get("values", "null")

        return self._check_compatibility(
            f"{path}/values",
            writer_values,
            reader_values,
            is_backward
        )

    def _check_fixed_compatibility(
        self,
        path: str,
        writer_schema: dict[str, Any],
        reader_schema: dict[str, Any],
        is_backward: bool
    ) -> list[BreakingChange]:
        """Check compatibility for fixed types."""
        changes: list[BreakingChange] = []

        writer_size = writer_schema.get("size", 0)
        reader_size = reader_schema.get("size", 0)

        if writer_size != reader_size:
            changes.append(BreakingChange(
                change_type=BreakingChangeType.CHANGED_SIZE,
                path=path,
                message=f"Fixed size changed from {writer_size} to {reader_size}",
                old_value=str(writer_size),
                new_value=str(reader_size),
                severity="error",
            ))

        return changes

    def _check_union_compatibility(
        self,
        path: str,
        writer_schema: Any,
        reader_schema: Any,
        is_backward: bool
    ) -> list[BreakingChange]:
        """Check compatibility for union types."""
        changes: list[BreakingChange] = []

        # Get union types as lists
        writer_types = writer_schema if isinstance(writer_schema, list) else [writer_schema]
        reader_types = reader_schema if isinstance(reader_schema, list) else [reader_schema]

        # For each writer type, there must be a compatible reader type
        for i, wtype in enumerate(writer_types):
            writer_type_name = self._get_schema_type(wtype)
            found_compatible = False

            for rtype in reader_types:
                reader_type_name = self._get_schema_type(rtype)
                if self._types_compatible(writer_type_name, reader_type_name):
                    # Check deeper compatibility
                    sub_changes = self._check_compatibility(
                        f"{path}[{i}]", wtype, rtype, is_backward
                    )
                    if not any(c.severity == "error" for c in sub_changes):
                        found_compatible = True
                        changes.extend(sub_changes)
                        break

            if not found_compatible:
                changes.append(BreakingChange(
                    change_type=BreakingChangeType.INCOMPATIBLE_UNION,
                    path=f"{path}[{i}]",
                    message=f"Writer union type '{writer_type_name}' has no compatible reader type",
                    old_value=writer_type_name,
                    severity="error",
                ))

        return changes

    def generate_report(
        self,
        result: AvroCompatibilityResult,
        format: str = "text"
    ) -> str:
        """
        Generate a compatibility report.

        Args:
            result: Compatibility result to report.
            format: Output format (text, json, markdown).

        Returns:
            Formatted report string.
        """
        if format == "json":
            return json.dumps(result.model_dump(), indent=2, default=str)
        elif format == "markdown":
            return self._generate_markdown_report(result)
        else:
            return self._generate_text_report(result)

    def _generate_text_report(self, result: AvroCompatibilityResult) -> str:
        """Generate a text format report."""
        lines = []
        lines.append("=" * 60)
        lines.append("Avro Schema Compatibility Report")
        lines.append("=" * 60)
        lines.append(f"Old Schema: {result.source_file or 'N/A'}")
        lines.append(f"New Schema: {result.target_file or 'N/A'}")
        lines.append(f"Mode: {result.compatibility_mode}")
        lines.append(f"Compatible: {'Yes' if result.is_compatible else 'No'}")
        lines.append(f"Compatibility Level: {result.compatibility_level}")
        lines.append(f"Breaking Changes: {result.breaking_change_count}")
        lines.append(f"Time: {result.check_time_ms:.2f}ms")
        lines.append("-" * 60)

        if result.added_fields:
            lines.append(f"\nAdded Fields: {', '.join(result.added_fields)}")
        if result.removed_fields:
            lines.append(f"Removed Fields: {', '.join(result.removed_fields)}")
        if result.modified_fields:
            lines.append(f"Modified Fields: {', '.join(result.modified_fields)}")

        if result.breaking_changes:
            lines.append("\nBreaking Changes:")
            for change in result.breaking_changes:
                lines.append(f"  [{change.change_type}] {change.path}")
                lines.append(f"    {change.message}")
                if change.mitigation:
                    lines.append(f"    Mitigation: {change.mitigation}")

        if result.warnings:
            lines.append("\nWarnings:")
            for warning in result.warnings:
                lines.append(f"  [{warning.change_type}] {warning.message}")

        lines.append("=" * 60)
        return "\n".join(lines)

    def _generate_markdown_report(self, result: AvroCompatibilityResult) -> str:
        """Generate a markdown format report."""
        lines = []
        lines.append("# Avro Schema Compatibility Report\n")
        lines.append(f"- **Old Schema**: {result.source_file or 'N/A'}")
        lines.append(f"- **New Schema**: {result.target_file or 'N/A'}")
        lines.append(f"- **Mode**: {result.compatibility_mode}")
        lines.append(f"- **Compatible**: {'Yes' if result.is_compatible else 'No'}")
        lines.append(f"- **Compatibility Level**: {result.compatibility_level}")
        lines.append(f"- **Breaking Changes**: {result.breaking_change_count}\n")

        if result.breaking_changes:
            lines.append("## Breaking Changes\n")
            lines.append("| Type | Path | Message | Mitigation |")
            lines.append("|------|------|---------|------------|")
            for change in result.breaking_changes:
                mitigation = change.mitigation or "-"
                lines.append(f"| {change.change_type} | `{change.path}` | {change.message} | {mitigation} |")

        if result.added_fields:
            lines.append("\n## Added Fields\n")
            for field in result.added_fields:
                lines.append(f"- `{field}`")

        if result.removed_fields:
            lines.append("\n## Removed Fields\n")
            for field in result.removed_fields:
                lines.append(f"- `{field}`")

        if result.modified_fields:
            lines.append("\n## Modified Fields\n")
            for field in result.modified_fields:
                lines.append(f"- `{field}`")

        if result.warnings:
            lines.append("\n## Warnings\n")
            for warning in result.warnings:
                lines.append(f"- [{warning.change_type}] {warning.message}")

        return "\n".join(lines)
