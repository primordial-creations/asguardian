"""
Avro Compatibility Service Helpers.

Compatibility checking helper functions for AvroCompatibilityService.
"""

from typing import Any, cast

from Asgard.Forseti.Avro.models.avro_models import (
    BreakingChange,
    BreakingChangeType,
)


def get_schema_type(schema: Any) -> str:
    """Get the type of a schema."""
    if isinstance(schema, str):
        return schema
    if isinstance(schema, list):
        return "union"
    if isinstance(schema, dict):
        return cast(str, schema.get("type", "unknown"))
    return "unknown"


def types_compatible(writer_type: str, reader_type: str) -> bool:
    """Check if two types are compatible for reading."""
    if writer_type == reader_type:
        return True
    promotions = {
        "int": {"long", "float", "double"},
        "long": {"float", "double"},
        "float": {"double"},
        "string": {"bytes"},
        "bytes": {"string"},
    }
    return writer_type in promotions and reader_type in promotions[writer_type]


def check_fixed_compatibility(path: str, writer_schema: dict[str, Any], reader_schema: dict[str, Any], is_backward: bool) -> list[BreakingChange]:
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


def check_enum_compatibility(path: str, writer_schema: dict[str, Any], reader_schema: dict[str, Any], is_backward: bool) -> list[BreakingChange]:
    """Check compatibility for enum types."""
    changes: list[BreakingChange] = []
    writer_symbols = set(writer_schema.get("symbols", []))
    reader_symbols = set(reader_schema.get("symbols", []))
    removed_symbols = writer_symbols - reader_symbols
    if removed_symbols:
        if "default" not in reader_schema:
            for symbol in removed_symbols:
                changes.append(BreakingChange(change_type=BreakingChangeType.REMOVED_ENUM_SYMBOL, path=f"{path}/symbols/{symbol}", message=f"Enum symbol '{symbol}' was removed from reader without default", old_value=symbol, severity="error", mitigation="Add a default value to the enum"))
        else:
            for symbol in removed_symbols:
                changes.append(BreakingChange(change_type=BreakingChangeType.REMOVED_ENUM_SYMBOL, path=f"{path}/symbols/{symbol}", message=f"Enum symbol '{symbol}' was removed (will use default)", old_value=symbol, severity="warning"))
    writer_order = writer_schema.get("symbols", [])
    reader_order = reader_schema.get("symbols", [])
    common_symbols = [s for s in writer_order if s in reader_symbols]
    reader_common = [s for s in reader_order if s in writer_symbols]
    if common_symbols != reader_common:
        changes.append(BreakingChange(change_type=BreakingChangeType.CHANGED_ENUM_ORDER, path=path, message="Enum symbol order changed (may affect sort order)", severity="warning"))
    return changes


def check_compatibility(path: str, writer_schema: Any, reader_schema: Any, is_backward: bool) -> list[BreakingChange]:
    """Check compatibility between writer and reader schemas."""
    changes: list[BreakingChange] = []
    writer_type = get_schema_type(writer_schema)
    reader_type = get_schema_type(reader_schema)
    if not types_compatible(writer_type, reader_type):
        direction = "backward" if is_backward else "forward"
        changes.append(BreakingChange(change_type=BreakingChangeType.CHANGED_FIELD_TYPE, path=path, message=f"Incompatible types for {direction} compatibility: writer='{writer_type}', reader='{reader_type}'", old_value=writer_type, new_value=reader_type, severity="error"))
        return changes
    if writer_type == "record":
        changes.extend(check_record_compatibility(path, writer_schema, reader_schema, is_backward))
    elif writer_type == "enum":
        changes.extend(check_enum_compatibility(path, writer_schema, reader_schema, is_backward))
    elif writer_type == "array":
        changes.extend(check_compatibility(f"{path}/items", writer_schema.get("items", "null"), reader_schema.get("items", "null"), is_backward))
    elif writer_type == "map":
        changes.extend(check_compatibility(f"{path}/values", writer_schema.get("values", "null"), reader_schema.get("values", "null"), is_backward))
    elif writer_type == "fixed":
        changes.extend(check_fixed_compatibility(path, writer_schema, reader_schema, is_backward))
    elif writer_type == "union":
        changes.extend(check_union_compatibility(path, writer_schema, reader_schema, is_backward))
    return changes


def check_record_compatibility(path: str, writer_schema: dict[str, Any], reader_schema: dict[str, Any], is_backward: bool) -> list[BreakingChange]:
    """Check compatibility for record types."""
    changes: list[BreakingChange] = []
    writer_name = writer_schema.get("name", "")
    reader_name = reader_schema.get("name", "")
    writer_ns = writer_schema.get("namespace", "")
    reader_ns = reader_schema.get("namespace", "")
    writer_full = f"{writer_ns}.{writer_name}" if writer_ns else writer_name
    reader_full = f"{reader_ns}.{reader_name}" if reader_ns else reader_name
    reader_aliases = set(reader_schema.get("aliases", []))
    if writer_full != reader_full and writer_full not in reader_aliases:
        changes.append(BreakingChange(change_type=BreakingChangeType.CHANGED_NAME, path=path, message=f"Record name changed from '{writer_full}' to '{reader_full}' without alias", old_value=writer_full, new_value=reader_full, severity="error", mitigation="Add an alias for the old name"))
    writer_fields = {f["name"]: f for f in writer_schema.get("fields", [])}
    reader_fields = {f["name"]: f for f in reader_schema.get("fields", [])}
    reader_field_by_alias: dict[str, dict] = {}
    for field in reader_schema.get("fields", []):
        for alias in field.get("aliases", []):
            reader_field_by_alias[alias] = field
    for field_name, writer_field in writer_fields.items():
        reader_field = reader_fields.get(field_name) or reader_field_by_alias.get(field_name)
        if reader_field is None:
            changes.append(BreakingChange(change_type=BreakingChangeType.REMOVED_FIELD, path=f"{path}/fields/{field_name}", message=f"Field '{field_name}' exists in writer but not in reader (will be ignored)", old_value=field_name, severity="warning"))
        else:
            changes.extend(check_compatibility(f"{path}/fields/{field_name}", writer_field["type"], reader_field["type"], is_backward))
    for field_name, reader_field in reader_fields.items():
        if field_name not in writer_fields:
            has_alias_match = any(alias in writer_fields for alias in reader_field.get("aliases", []))
            if not has_alias_match:
                if "default" not in reader_field:
                    changes.append(BreakingChange(change_type=BreakingChangeType.ADDED_REQUIRED_FIELD, path=f"{path}/fields/{field_name}", message=f"New field '{field_name}' without default value", new_value=field_name, severity="error", mitigation="Add a default value for the new field"))
                else:
                    changes.append(BreakingChange(change_type=BreakingChangeType.ADDED_REQUIRED_FIELD, path=f"{path}/fields/{field_name}", message=f"New field '{field_name}' added with default value", new_value=field_name, severity="warning"))
    return changes


def check_union_compatibility(path: str, writer_schema: Any, reader_schema: Any, is_backward: bool) -> list[BreakingChange]:
    """Check compatibility for union types."""
    changes: list[BreakingChange] = []
    writer_types = writer_schema if isinstance(writer_schema, list) else [writer_schema]
    reader_types = reader_schema if isinstance(reader_schema, list) else [reader_schema]
    for i, wtype in enumerate(writer_types):
        writer_type_name = get_schema_type(wtype)
        found_compatible = False
        for rtype in reader_types:
            reader_type_name = get_schema_type(rtype)
            if types_compatible(writer_type_name, reader_type_name):
                sub_changes = check_compatibility(f"{path}[{i}]", wtype, rtype, is_backward)
                if not any(c.severity == "error" for c in sub_changes):
                    found_compatible = True
                    changes.extend(sub_changes)
                    break
        if not found_compatible:
            changes.append(BreakingChange(change_type=BreakingChangeType.INCOMPATIBLE_UNION, path=f"{path}[{i}]", message=f"Writer union type '{writer_type_name}' has no compatible reader type", old_value=writer_type_name, severity="error"))
    return changes
