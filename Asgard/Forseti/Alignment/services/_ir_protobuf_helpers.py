"""
Protobuf -> IR adapter.

Reuses Forseti's Protobuf parser (`ProtobufValidatorService`) rather than
re-parsing `.proto` syntax: we parse the file/content once and project the
named `ProtobufMessage` onto `IRRecord`. Proto3 has no explicit nullability
annotation on scalars (proto3 fields are simply optional-with-default);
`optional` keyword / `label == "optional"` maps to `nullable=True`,
`repeated` maps to a LIST wrapper.
"""

from typing import Any, Optional

from Asgard.Forseti.Alignment.models.ir_models import (
    IRField,
    IRRecord,
    IRType,
    SourceRef,
    TypeClass,
)
from Asgard.Forseti.Alignment.services._lexical_helpers import tokenize

_PROTO_SCALAR_MAP: dict[str, TypeClass] = {
    "bool": TypeClass.BOOL,
    "int32": TypeClass.INT32,
    "sint32": TypeClass.INT32,
    "sfixed32": TypeClass.INT32,
    "uint32": TypeClass.INT32,
    "fixed32": TypeClass.INT32,
    "int64": TypeClass.INT64,
    "sint64": TypeClass.INT64,
    "sfixed64": TypeClass.INT64,
    "uint64": TypeClass.INT64,
    "fixed64": TypeClass.INT64,
    "float": TypeClass.FLOAT32,
    "double": TypeClass.FLOAT64,
    "string": TypeClass.STRING,
    "bytes": TypeClass.BYTES,
}


def _proto_field_type_to_ir(field: Any, enums_by_name: dict[str, list[str]], messages_by_name: set[str]) -> IRType:
    type_name = field.type
    if type_name in _PROTO_SCALAR_MAP:
        return IRType(type_class=_PROTO_SCALAR_MAP[type_name])
    if type_name in enums_by_name:
        return IRType(type_class=TypeClass.ENUM, enum_symbols=enums_by_name[type_name])
    if type_name in messages_by_name:
        return IRType(type_class=TypeClass.RECORD, record_name=type_name)
    if type_name in ("map",):
        return IRType(type_class=TypeClass.MAP)
    return IRType(type_class=TypeClass.ANY)


def protobuf_message_to_ir_record(
    message: Any,
    *,
    enums_by_name: Optional[dict[str, list[str]]] = None,
    messages_by_name: Optional[set[str]] = None,
    file: str = "",
    path: str = "/",
) -> IRRecord:
    """Build an IRRecord from a parsed `ProtobufMessage`."""
    enums_by_name = dict(enums_by_name or {})
    for nested in getattr(message, "nested_enums", []) or []:
        enums_by_name.setdefault(nested.name, list(nested.values.keys()))
    messages_by_name = set(messages_by_name or set())
    for nested in getattr(message, "nested_messages", []) or []:
        messages_by_name.add(nested.name)

    fields: list[IRField] = []
    for field in message.fields:
        base_type = _proto_field_type_to_ir(field, enums_by_name, messages_by_name)
        repeated = (field.label or "") == "repeated"
        ir_type = IRType(type_class=TypeClass.LIST, item_type=base_type) if repeated else base_type
        nullable = (field.label or "") == "optional"
        fields.append(
            IRField(
                raw_name=field.name,
                lexical_tokens=tokenize(field.name),
                type=ir_type,
                nullable=nullable,
                required=not nullable,
                source=SourceRef(file=file, format="protobuf", path=f"{path}/{field.name}"),
            )
        )
    return IRRecord(name=message.name, fields=fields, source=SourceRef(file=file, format="protobuf", path=path))


def protobuf_schema_to_ir_record(schema: Any, message_name: str, file: str = "") -> IRRecord:
    """Locate `message_name` in a parsed `ProtobufSchema` and build its IRRecord."""
    enums_by_name = {e.name: list(e.values.keys()) for e in schema.enums}
    messages_by_name = {m.name for m in schema.messages}
    for message in schema.messages:
        if message.name == message_name:
            return protobuf_message_to_ir_record(
                message, enums_by_name=enums_by_name, messages_by_name=messages_by_name, file=file
            )
    raise ValueError(f"Protobuf message {message_name!r} not found in schema (file={file!r})")
