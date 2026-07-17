"""
OpenAPI / JSON Schema -> IR adapter.

Shared walker: an OpenAPI `components.schemas.<Name>` entry is itself a
JSON Schema object, so this adapter handles both formats. `allOf` is
flattened (properties/required merged); `$ref` is left unresolved here -
callers pass already-dereferenced schemas (Forseti's existing resolvers
handle `$ref`, reused rather than duplicated).
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

_JSONSCHEMA_TYPE_MAP: dict[str, TypeClass] = {
    "string": TypeClass.STRING,
    "integer": TypeClass.INT64,
    "number": TypeClass.FLOAT64,
    "boolean": TypeClass.BOOL,
    "object": TypeClass.RECORD,
    "array": TypeClass.LIST,
}

_FORMAT_TYPE_MAP: dict[str, TypeClass] = {
    "int32": TypeClass.INT32,
    "int64": TypeClass.INT64,
    "float": TypeClass.FLOAT32,
    "double": TypeClass.FLOAT64,
    "date": TypeClass.DATE,
    "date-time": TypeClass.DATETIME,
    "uuid": TypeClass.UUID,
    "byte": TypeClass.BYTES,
    "binary": TypeClass.BYTES,
}


def _flatten_all_of(schema: dict[str, Any]) -> dict[str, Any]:
    if "allOf" not in schema:
        return schema
    merged: dict[str, Any] = {"type": "object", "properties": {}, "required": []}
    for sub in schema["allOf"]:
        if not isinstance(sub, dict):
            continue
        sub = _flatten_all_of(sub)
        merged["properties"].update(sub.get("properties", {}))
        merged["required"].extend(sub.get("required", []))
    return merged


def _scalar_type_class(schema: dict[str, Any]) -> TypeClass:
    fmt = schema.get("format")
    if fmt in _FORMAT_TYPE_MAP:
        return _FORMAT_TYPE_MAP[fmt]
    json_type = schema.get("type", "string")
    if isinstance(json_type, list):
        json_type = next((t for t in json_type if t != "null"), "string")
    return _JSONSCHEMA_TYPE_MAP.get(json_type, TypeClass.ANY)


def json_schema_type_to_ir(schema: dict[str, Any]) -> IRType:
    """Convert a JSON Schema (sub)schema to an IRType (does not recurse into records)."""
    if "enum" in schema:
        return IRType(type_class=TypeClass.ENUM, enum_symbols=[str(v) for v in schema["enum"]])
    json_type = schema.get("type")
    if isinstance(json_type, list):
        json_type = next((t for t in json_type if t != "null"), "string")
    if json_type == "array":
        items = schema.get("items", {}) or {}
        return IRType(type_class=TypeClass.LIST, item_type=json_schema_type_to_ir(items))
    if json_type == "object" or "properties" in schema:
        return IRType(type_class=TypeClass.RECORD, record_name=schema.get("title"))
    return IRType(type_class=_scalar_type_class(schema))


def _is_nullable(schema: dict[str, Any]) -> bool:
    json_type = schema.get("type")
    if isinstance(json_type, list) and "null" in json_type:
        return True
    if schema.get("nullable") is True:
        return True
    return False


def openapi_schema_to_ir_record(
    schema: dict[str, Any], name: str, file: str = "", path: str = "/"
) -> IRRecord:
    """Build an IRRecord from an OpenAPI/JSON Schema object schema."""
    schema = _flatten_all_of(schema)
    required = set(schema.get("required", []) or [])
    fields: list[IRField] = []
    for prop_name, prop_schema in (schema.get("properties", {}) or {}).items():
        if not isinstance(prop_schema, dict):
            continue
        fields.append(
            IRField(
                raw_name=prop_name,
                lexical_tokens=tokenize(prop_name),
                type=json_schema_type_to_ir(prop_schema),
                nullable=_is_nullable(prop_schema),
                required=prop_name in required,
                default=prop_schema.get("default"),
                doc=prop_schema.get("description"),
                source=SourceRef(file=file, format="openapi", path=f"{path}/{prop_name}"),
            )
        )
    return IRRecord(name=name, fields=fields, source=SourceRef(file=file, format="openapi", path=path))
