"""
Protobuf Compatibility Service Helpers.

Compatibility checking helper functions for ProtobufCompatibilityService.
"""

from typing import Any

from Asgard.Forseti.Protobuf.models.protobuf_models import (
    BreakingChange,
    BreakingChangeType,
    ProtobufEnum,
    ProtobufMessage,
)


def check_message_compatibility(old_msg: ProtobufMessage, new_msg: ProtobufMessage) -> list[BreakingChange]:
    """Check compatibility for a single message."""
    changes: list[BreakingChange] = []
    base_path = f"message {old_msg.name}"
    old_fields_by_number = {f.number: f for f in old_msg.fields}
    new_fields_by_number = {f.number: f for f in new_msg.fields}
    old_fields_by_name = {f.name: f for f in old_msg.fields}
    new_fields_by_name = {f.name: f for f in new_msg.fields}
    for field_number, old_field in old_fields_by_number.items():
        if field_number not in new_fields_by_number:
            is_reserved = (
                field_number in new_msg.reserved_numbers or
                any(start <= field_number <= end for start, end in new_msg.reserved_ranges)
            )
            if not is_reserved:
                changes.append(BreakingChange(
                    change_type=BreakingChangeType.REMOVED_FIELD,
                    path=f"{base_path}.{old_field.name}",
                    message=f"Field '{old_field.name}' (number {field_number}) was removed without being reserved",
                    old_value=f"{old_field.name} = {field_number}",
                    severity="error",
                    mitigation="Add field number to reserved list to prevent reuse",
                ))
            else:
                changes.append(BreakingChange(
                    change_type=BreakingChangeType.REMOVED_FIELD,
                    path=f"{base_path}.{old_field.name}",
                    message=f"Field '{old_field.name}' (number {field_number}) was removed (properly reserved)",
                    old_value=f"{old_field.name} = {field_number}",
                    severity="warning",
                ))
    for field_number in old_fields_by_number.keys() & new_fields_by_number.keys():
        old_field = old_fields_by_number[field_number]
        new_field = new_fields_by_number[field_number]
        if old_field.type != new_field.type:
            changes.append(BreakingChange(
                change_type=BreakingChangeType.CHANGED_FIELD_TYPE,
                path=f"{base_path}.{old_field.name}",
                message=f"Field type changed from '{old_field.type}' to '{new_field.type}'",
                old_value=old_field.type,
                new_value=new_field.type,
                severity="error",
                mitigation="Create a new field with the new type instead",
            ))
        if old_field.label != new_field.label:
            severity = "error"
            if old_field.label != "repeated" and new_field.label != "repeated":
                severity = "warning"
            changes.append(BreakingChange(
                change_type=BreakingChangeType.CHANGED_FIELD_LABEL,
                path=f"{base_path}.{old_field.name}",
                message=f"Field label changed from '{old_field.label or 'singular'}' to '{new_field.label or 'singular'}'",
                old_value=old_field.label or "singular",
                new_value=new_field.label or "singular",
                severity=severity,
            ))
    for field_name in old_fields_by_name.keys() & new_fields_by_name.keys():
        old_field = old_fields_by_name[field_name]
        new_field = new_fields_by_name[field_name]
        if old_field.number != new_field.number:
            changes.append(BreakingChange(
                change_type=BreakingChangeType.CHANGED_FIELD_NUMBER,
                path=f"{base_path}.{field_name}",
                message=f"Field number changed from {old_field.number} to {new_field.number}",
                old_value=str(old_field.number),
                new_value=str(new_field.number),
                severity="error",
                mitigation="Field numbers must remain stable",
            ))
    for field_number in new_fields_by_number.keys():
        if field_number in old_msg.reserved_numbers:
            changes.append(BreakingChange(
                change_type=BreakingChangeType.RESERVED_NUMBER_REUSED,
                path=f"{base_path}",
                message=f"Reserved field number {field_number} is now being used",
                new_value=str(field_number),
                severity="error",
                mitigation="Reserved field numbers must never be reused",
            ))
        for start, end in old_msg.reserved_ranges:
            if start <= field_number <= end and field_number not in old_fields_by_number:
                changes.append(BreakingChange(
                    change_type=BreakingChangeType.RESERVED_NUMBER_REUSED,
                    path=f"{base_path}",
                    message=f"Field number {field_number} from reserved range {start}-{end} is now being used",
                    new_value=str(field_number),
                    severity="error",
                ))
    for new_field in new_msg.fields:
        if new_field.name in old_msg.reserved_names:
            changes.append(BreakingChange(
                change_type=BreakingChangeType.RESERVED_FIELD_REUSED,
                path=f"{base_path}.{new_field.name}",
                message=f"Reserved field name '{new_field.name}' is now being used",
                new_value=new_field.name,
                severity="error",
                mitigation="Reserved field names must never be reused",
            ))
    old_nested_map = {m.name: m for m in old_msg.nested_messages}
    new_nested_map = {m.name: m for m in new_msg.nested_messages}
    for nested_name in old_nested_map.keys() - new_nested_map.keys():
        changes.append(BreakingChange(
            change_type=BreakingChangeType.REMOVED_MESSAGE,
            path=f"{base_path}.{nested_name}",
            message=f"Nested message '{nested_name}' was removed",
            old_value=nested_name,
            severity="error",
        ))
    for nested_name in old_nested_map.keys() & new_nested_map.keys():
        changes.extend(check_message_compatibility(old_nested_map[nested_name], new_nested_map[nested_name]))
    old_enum_map = {e.name: e for e in old_msg.nested_enums}
    new_enum_map = {e.name: e for e in new_msg.nested_enums}
    for enum_name in old_enum_map.keys() - new_enum_map.keys():
        changes.append(BreakingChange(
            change_type=BreakingChangeType.REMOVED_ENUM,
            path=f"{base_path}.{enum_name}",
            message=f"Nested enum '{enum_name}' was removed",
            old_value=enum_name,
            severity="error",
        ))
    for enum_name in old_enum_map.keys() & new_enum_map.keys():
        changes.extend(check_enum_compatibility(old_enum_map[enum_name], new_enum_map[enum_name], f"{base_path}.{enum_name}"))
    return changes


def check_enum_compatibility(old_enum: ProtobufEnum, new_enum: ProtobufEnum, base_path: str) -> list[BreakingChange]:
    """Check compatibility for a single enum."""
    changes: list[BreakingChange] = []
    for value_name, value_number in old_enum.values.items():
        if value_name not in new_enum.values:
            is_reserved = (value_name in new_enum.reserved_names or value_number in new_enum.reserved_numbers)
            if not is_reserved:
                changes.append(BreakingChange(
                    change_type=BreakingChangeType.REMOVED_ENUM_VALUE,
                    path=f"{base_path}.{value_name}",
                    message=f"Enum value '{value_name}' (= {value_number}) was removed without being reserved",
                    old_value=f"{value_name} = {value_number}",
                    severity="error",
                    mitigation="Add value name/number to reserved list",
                ))
            else:
                changes.append(BreakingChange(
                    change_type=BreakingChangeType.REMOVED_ENUM_VALUE,
                    path=f"{base_path}.{value_name}",
                    message=f"Enum value '{value_name}' was removed (properly reserved)",
                    old_value=f"{value_name} = {value_number}",
                    severity="warning",
                ))
    for value_name in old_enum.values.keys() & new_enum.values.keys():
        old_number = old_enum.values[value_name]
        new_number = new_enum.values[value_name]
        if old_number != new_number:
            changes.append(BreakingChange(
                change_type=BreakingChangeType.CHANGED_ENUM_VALUE_NUMBER,
                path=f"{base_path}.{value_name}",
                message=f"Enum value number changed from {old_number} to {new_number}",
                old_value=str(old_number),
                new_value=str(new_number),
                severity="error",
                mitigation="Enum value numbers must remain stable",
            ))
    return changes


def check_enums_compatibility(old_enums: list[ProtobufEnum], new_enums: list[ProtobufEnum]) -> list[BreakingChange]:
    """Check compatibility for top-level enums."""
    changes: list[BreakingChange] = []
    old_enum_map = {e.name: e for e in old_enums}
    new_enum_map = {e.name: e for e in new_enums}
    for enum_name in old_enum_map.keys() - new_enum_map.keys():
        changes.append(BreakingChange(
            change_type=BreakingChangeType.REMOVED_ENUM,
            path=f"enum {enum_name}",
            message=f"Enum '{enum_name}' was removed",
            old_value=enum_name,
            severity="error",
            mitigation="Keep the enum or deprecate it first",
        ))
    for enum_name in old_enum_map.keys() & new_enum_map.keys():
        changes.extend(check_enum_compatibility(old_enum_map[enum_name], new_enum_map[enum_name], f"enum {enum_name}"))
    return changes


def check_services_compatibility(old_services: list[Any], new_services: list[Any]) -> list[BreakingChange]:
    """Check compatibility for services."""
    changes: list[BreakingChange] = []
    old_service_map = {s.name: s for s in old_services}
    new_service_map = {s.name: s for s in new_services}
    for service_name in old_service_map.keys() - new_service_map.keys():
        changes.append(BreakingChange(
            change_type=BreakingChangeType.REMOVED_SERVICE,
            path=f"service {service_name}",
            message=f"Service '{service_name}' was removed",
            old_value=service_name,
            severity="error",
            mitigation="Keep the service or deprecate it first",
        ))
    for service_name in old_service_map.keys() & new_service_map.keys():
        old_service = old_service_map[service_name]
        new_service = new_service_map[service_name]
        old_rpcs = set(old_service.rpcs.keys())
        new_rpcs = set(new_service.rpcs.keys())
        for rpc_name in old_rpcs - new_rpcs:
            changes.append(BreakingChange(
                change_type=BreakingChangeType.REMOVED_RPC,
                path=f"service {service_name}.{rpc_name}",
                message=f"RPC '{rpc_name}' was removed from service '{service_name}'",
                old_value=rpc_name,
                severity="error",
            ))
        for rpc_name in old_rpcs & new_rpcs:
            old_rpc = old_service.rpcs[rpc_name]
            new_rpc = new_service.rpcs[rpc_name]
            if old_rpc.get("input") != new_rpc.get("input"):
                changes.append(BreakingChange(
                    change_type=BreakingChangeType.CHANGED_FIELD_TYPE,
                    path=f"service {service_name}.{rpc_name}",
                    message=f"RPC input type changed from '{old_rpc.get('input')}' to '{new_rpc.get('input')}'",
                    old_value=old_rpc.get("input"),
                    new_value=new_rpc.get("input"),
                    severity="error",
                ))
            if old_rpc.get("output") != new_rpc.get("output"):
                changes.append(BreakingChange(
                    change_type=BreakingChangeType.CHANGED_FIELD_TYPE,
                    path=f"service {service_name}.{rpc_name}",
                    message=f"RPC output type changed from '{old_rpc.get('output')}' to '{new_rpc.get('output')}'",
                    old_value=old_rpc.get("output"),
                    new_value=new_rpc.get("output"),
                    severity="error",
                ))
    return changes
