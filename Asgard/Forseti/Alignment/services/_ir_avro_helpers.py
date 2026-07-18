"""
Avro -> IR adapter.

Operates on the raw Avro schema dict (as loaded from `.avsc` JSON) rather
than duplicating Forseti's Avro parser: a `record` type's `fields` list
maps directly onto `IRField`. Avro nullability is expressed as a union
with `"null"` (`["null", "string"]`), normalized to `IRField.nullable`.
"""

from typing import Any

from Asgard.Forseti.Alignment.models.ir_models import (
    IRField,
    IRRecord,
    IRType,
    SourceRef,
    TypeClass,
)
from Asgard.Forseti.Alignment.services._lexical_helpers import tokenize

_AVRO_PRIMITIVE_MAP: dict[str, TypeClass] = {
    "null": TypeClass.ANY,
    "boolean": TypeClass.BOOL,
    "int": TypeClass.INT32,
    "long": TypeClass.INT64,
    "float": TypeClass.FLOAT32,
    "double": TypeClass.FLOAT64,
    "bytes": TypeClass.BYTES,
    "string": TypeClass.STRING,
}

_LOGICAL_TYPE_MAP: dict[str, TypeClass] = {
    "date": TypeClass.DATE,
    "timestamp-millis": TypeClass.DATETIME,
    "timestamp-micros": TypeClass.DATETIME,
    "uuid": TypeClass.UUID,
    "decimal": TypeClass.DECIMAL,
}


def _avro_scalar_to_ir(avro_type: Any) -> IRType:
    if isinstance(avro_type, dict):
        logical = avro_type.get("logicalType")
        if logical in _LOGICAL_TYPE_MAP:
            return IRType(type_class=_LOGICAL_TYPE_MAP[logical])
        base = avro_type.get("type")
        if base == "array":
            return IRType(type_class=TypeClass.LIST, item_type=_avro_scalar_to_ir(avro_type.get("items", "string")))
        if base == "map":
            return IRType(type_class=TypeClass.MAP)
        if base == "enum":
            return IRType(type_class=TypeClass.ENUM, enum_symbols=list(avro_type.get("symbols", [])))
        if base == "record":
            return IRType(type_class=TypeClass.RECORD, record_name=avro_type.get("name"))
        return _avro_scalar_to_ir(base)
    if isinstance(avro_type, str):
        return IRType(type_class=_AVRO_PRIMITIVE_MAP.get(avro_type, TypeClass.ANY))
    return IRType(type_class=TypeClass.ANY)


def _resolve_field_type(avro_type: Any) -> tuple[IRType, bool]:
    """Return (non-null IRType, nullable) for a possibly-union Avro field type."""
    if isinstance(avro_type, list):
        nullable = "null" in avro_type
        non_null = [t for t in avro_type if t != "null"]
        if len(non_null) == 1:
            return _avro_scalar_to_ir(non_null[0]), nullable
        # True union of >1 non-null branches -> VARIANT.
        return IRType(type_class=TypeClass.VARIANT), nullable
    return _avro_scalar_to_ir(avro_type), False


def avro_schema_to_ir_record(schema: dict[str, Any], file: str = "", path: str = "/") -> IRRecord:
    """Build an IRRecord from an Avro `record` schema dict."""
    name = schema.get("name", "")
    fields: list[IRField] = []
    for field in schema.get("fields", []) or []:
        field_name = field.get("name", "")
        ir_type, nullable = _resolve_field_type(field.get("type"))
        fields.append(
            IRField(
                raw_name=field_name,
                lexical_tokens=tokenize(field_name),
                type=ir_type,
                nullable=nullable,
                required=not nullable,
                default=field.get("default"),
                doc=field.get("doc"),
                source=SourceRef(file=file, format="avro", path=f"{path}/{field_name}"),
            )
        )
    return IRRecord(name=name, fields=fields, source=SourceRef(file=file, format="avro", path=path))
