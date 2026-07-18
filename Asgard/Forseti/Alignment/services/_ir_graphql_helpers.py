"""
GraphQL -> IR adapter.

Reuses `parse_sdl` (GraphQL/utilities/_graphql_parse_utils.py) rather than
re-implementing SDL parsing. GraphQL nullability is *inverted* relative to
most formats: a bare `String` is nullable, `String!` is non-null - the
adapter normalizes the trailing `!` into IR's `nullable=False`.
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

_GRAPHQL_SCALAR_MAP: dict[str, TypeClass] = {
    "Int": TypeClass.INT32,
    "Float": TypeClass.FLOAT64,
    "String": TypeClass.STRING,
    "Boolean": TypeClass.BOOL,
    "ID": TypeClass.STRING,
}


def _parse_field_type(raw_type: str) -> tuple[str, bool, bool]:
    """Return (bare_type_name, nullable, is_list) from a raw SDL type string."""
    raw_type = raw_type.strip()
    non_null = raw_type.endswith("!")
    if non_null:
        raw_type = raw_type[:-1].strip()
    is_list = raw_type.startswith("[") and raw_type.endswith("]")
    if is_list:
        raw_type = raw_type[1:-1].strip()
        if raw_type.endswith("!"):
            raw_type = raw_type[:-1].strip()
    return raw_type, not non_null, is_list


def _graphql_type_to_ir(bare_name: str, enums: dict[str, list[str]], known_types: set[str]) -> IRType:
    if bare_name in _GRAPHQL_SCALAR_MAP:
        return IRType(type_class=_GRAPHQL_SCALAR_MAP[bare_name])
    if bare_name in enums:
        return IRType(type_class=TypeClass.ENUM, enum_symbols=enums[bare_name])
    if bare_name in known_types:
        return IRType(type_class=TypeClass.RECORD, record_name=bare_name)
    return IRType(type_class=TypeClass.ANY)


def graphql_sdl_to_ir_record(parsed: dict[str, Any], type_name: str, file: str = "", path: str = "/") -> IRRecord:
    """Build an IRRecord for `type_name` from `parse_sdl(...)` output."""
    type_def = parsed.get("types", {}).get(type_name)
    if type_def is None:
        raise ValueError(f"GraphQL type {type_name!r} not found in schema (file={file!r})")

    enums: dict[str, list[str]] = dict(parsed.get("enums", {}))
    known_types = set(parsed.get("types", {}).keys())

    fields: list[IRField] = []
    for field_name, field_def in (type_def.get("fields") or {}).items():
        raw_type = field_def.get("type", "") if isinstance(field_def, dict) else str(field_def)
        bare_name, nullable, is_list = _parse_field_type(str(raw_type))
        base_type = _graphql_type_to_ir(bare_name, enums, known_types)
        ir_type = IRType(type_class=TypeClass.LIST, item_type=base_type) if is_list else base_type
        fields.append(
            IRField(
                raw_name=field_name,
                lexical_tokens=tokenize(field_name),
                type=ir_type,
                nullable=nullable,
                required=not nullable,
                source=SourceRef(file=file, format="graphql", path=f"{path}/{field_name}"),
            )
        )
    return IRRecord(name=type_name, fields=fields, source=SourceRef(file=file, format="graphql", path=path))
