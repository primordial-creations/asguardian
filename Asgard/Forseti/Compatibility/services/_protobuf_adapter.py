"""
Protobuf Adapter - projects the existing message/enum/service checks onto
UnifiedChange, adding wire-type equivalence groups (RESEARCH_08 1.1),
field-rename detection (wire PASS / source HAZARD) and RPC streaming-mode
routing breaks (RESEARCH_14).
"""

from typing import Optional

from Asgard.Forseti.Compatibility.models._compat_base_models import Direction
from Asgard.Forseti.Compatibility.models.compat_models import UnifiedChange
from Asgard.Forseti.Compatibility.services._classification_helpers import make_change
from Asgard.Forseti.Compatibility.utilities.compat_utils import dedup_changes
from Asgard.Forseti.Protobuf.models.protobuf_models import (
    BreakingChange as ProtoBreakingChange,
    ProtobufMessage,
    ProtobufSchema,
)
from Asgard.Forseti.Protobuf.services._protobuf_compatibility_service_helpers import (
    check_enums_compatibility,
    check_message_compatibility,
    check_services_compatibility,
)
from Asgard.Forseti.Rules.models._rule_base_models import SchemaFormat

FMT = SchemaFormat.PROTOBUF

# Wire-type equivalence groups (RESEARCH_08 1.1): changes within a group
# are safe on the wire but hazardous for source/JSON compatibility.
WIRE_GROUPS: list[set[str]] = [
    {"int32", "int64", "uint32", "uint64", "bool"},   # varint
    {"sint32", "sint64"},                              # zigzag varint
    {"string", "bytes"},                               # length-delimited
    {"fixed32", "sfixed32"},                           # 32-bit
    {"fixed64", "sfixed64"},                           # 64-bit
]


def wire_compatible(old_type: Optional[str], new_type: Optional[str]) -> bool:
    """Whether two scalar types share a wire-type equivalence group."""
    if not old_type or not new_type:
        return False
    return any(old_type in group and new_type in group for group in WIRE_GROUPS)


_RULE_MAP: dict[tuple[str, str], str] = {
    ("removed_message", "error"): "PROTO-MESSAGE-REMOVED",
    ("removed_field", "error"): "PROTO-FIELD-REMOVED-UNRESERVED",
    ("removed_field", "warning"): "PROTO-FIELD-REMOVED-RESERVED",
    ("changed_field_type", "error"): "PROTO-FIELD-TYPE-CHANGED",
    ("changed_field_label", "error"): "PROTO-FIELD-LABEL-CHANGED",
    ("changed_field_label", "warning"): "PROTO-FIELD-LABEL-MODIFIED",
    ("changed_field_number", "error"): "PROTO-FIELD-NUMBER-CHANGED",
    ("reserved_number_reused", "error"): "PROTO-RESERVED-REUSED",
    ("reserved_field_reused", "error"): "PROTO-RESERVED-REUSED",
    ("removed_enum", "error"): "PROTO-ENUM-REMOVED",
    ("removed_enum_value", "error"): "PROTO-ENUM-VALUE-REMOVED",
    ("removed_enum_value", "warning"): "PROTO-ENUM-VALUE-REMOVED-RESERVED",
    ("changed_enum_value_number", "error"): "PROTO-ENUM-VALUE-NUMBER-CHANGED",
    ("removed_service", "error"): "PROTO-SERVICE-REMOVED",
    ("removed_rpc", "error"): "PROTO-RPC-REMOVED",
}


def _to_unified(change: ProtoBreakingChange) -> UnifiedChange:
    key = (str(change.change_type), change.severity)
    rule_id = _RULE_MAP.get(key)
    if rule_id is None:
        rule_id = "PROTO-FIELD-TYPE-CHANGED"
    # RPC input/output type changes come through as changed_field_type on a
    # 'service X.rpc' path.
    if str(change.change_type) == "changed_field_type" and change.path.startswith("service "):
        rule_id = "PROTO-RPC-TYPE-CHANGED"
    # Wire-type group downgrade: type changes within a group are wire-safe.
    if rule_id == "PROTO-FIELD-TYPE-CHANGED" and wire_compatible(
            change.old_value, change.new_value):
        rule_id = "PROTO-FIELD-TYPE-WIRE-COMPATIBLE"
    direction = Direction.INPUT if change.path.startswith("service ") else Direction.OUTPUT
    return make_change(
        rule_id, FMT, direction, change.path, change.message,
        old_value=change.old_value, new_value=change.new_value,
        mitigation=change.mitigation,
    )


def _detect_renames(old_msg: ProtobufMessage, new_msg: ProtobufMessage,
                    base_path: str) -> list[UnifiedChange]:
    """Same tag number, different name: wire PASS, source/JSON HAZARD."""
    changes: list[UnifiedChange] = []
    old_by_number = {f.number: f for f in old_msg.fields}
    new_by_number = {f.number: f for f in new_msg.fields}
    for number in old_by_number.keys() & new_by_number.keys():
        old_field, new_field = old_by_number[number], new_by_number[number]
        if old_field.name != new_field.name:
            changes.append(make_change(
                "PROTO-FIELD-RENAMED", FMT, Direction.OUTPUT,
                f"{base_path}.{old_field.name}",
                f"Field {number} renamed from '{old_field.name}' to "
                f"'{new_field.name}': wire-compatible, breaks source and JSON mapping",
                old_value=old_field.name, new_value=new_field.name,
                mitigation="Coordinate the rename with all JSON/source consumers",
            ))
    old_nested = {m.name: m for m in old_msg.nested_messages}
    new_nested = {m.name: m for m in new_msg.nested_messages}
    for name in old_nested.keys() & new_nested.keys():
        changes.extend(_detect_renames(old_nested[name], new_nested[name],
                                       f"{base_path}.{name}"))
    return changes


def _diff_streaming(old_schema: ProtobufSchema,
                    new_schema: ProtobufSchema) -> list[UnifiedChange]:
    """Unary <-> streaming mode changes are irrecoverable routing breaks."""
    changes: list[UnifiedChange] = []
    old_services = {s.name: s for s in old_schema.services}
    new_services = {s.name: s for s in new_schema.services}
    for name in old_services.keys() & new_services.keys():
        old_rpcs = old_services[name].rpcs
        new_rpcs = new_services[name].rpcs
        for rpc_name in old_rpcs.keys() & new_rpcs.keys():
            old_rpc, new_rpc = old_rpcs[rpc_name], new_rpcs[rpc_name]
            for side in ("input_stream", "output_stream"):
                old_stream = old_rpc.get(side, "false")
                new_stream = new_rpc.get(side, "false")
                if old_stream != new_stream:
                    which = "client" if side == "input_stream" else "server"
                    changes.append(make_change(
                        "PROTO-RPC-STREAMING-CHANGED", FMT, Direction.INPUT,
                        f"service {name}.{rpc_name}",
                        f"RPC '{rpc_name}' {which}-streaming mode changed "
                        f"from {old_stream} to {new_stream}",
                        old_value=old_stream, new_value=new_stream,
                        mitigation="Add a new RPC instead of changing streaming mode",
                    ))
    return changes


def diff_protobuf(old_schema: ProtobufSchema,
                  new_schema: ProtobufSchema) -> list[UnifiedChange]:
    """Diff two parsed Protobuf schemas onto UnifiedChange."""
    changes: list[UnifiedChange] = []
    old_messages = {m.name: m for m in old_schema.messages}
    new_messages = {m.name: m for m in new_schema.messages}

    for name in sorted(old_messages.keys() - new_messages.keys()):
        changes.append(make_change(
            "PROTO-MESSAGE-REMOVED", FMT, Direction.OUTPUT,
            f"message {name}", f"Message '{name}' was removed",
            old_value=name,
            mitigation="Keep the message or mark it as deprecated first",
        ))
    for name in sorted(old_messages.keys() & new_messages.keys()):
        for change in check_message_compatibility(old_messages[name], new_messages[name]):
            changes.append(_to_unified(change))
        changes.extend(_detect_renames(old_messages[name], new_messages[name],
                                       f"message {name}"))

    for change in check_enums_compatibility(old_schema.enums, new_schema.enums):
        changes.append(_to_unified(change))
    for change in check_services_compatibility(old_schema.services, new_schema.services):
        changes.append(_to_unified(change))
    changes.extend(_diff_streaming(old_schema, new_schema))
    return dedup_changes(changes)
