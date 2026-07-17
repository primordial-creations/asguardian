"""
Compat Utilities - format detection, $ref resolution and the shared
direction-aware JSON-schema pair walker used by the OpenAPI, AsyncAPI
and JSON Schema adapters.
"""

import json
from pathlib import Path
from typing import Any, Callable, Optional

import yaml

from Asgard.Forseti.Compatibility.models._compat_base_models import Direction
from Asgard.Forseti.Compatibility.models.compat_models import UnifiedChange
from Asgard.Forseti.Compatibility.services._classification_helpers import make_change
from Asgard.Forseti.Rules.models._rule_base_models import SchemaFormat

Resolver = Callable[[str], Optional[dict[str, Any]]]

# Per-format rule ids for the shared schema walker.
SCHEMA_RULES: dict[SchemaFormat, dict[str, str]] = {
    SchemaFormat.OPENAPI: {
        "field_removed_out": "OAS-RES-FIELD-REMOVED",
        "field_removed_in": "OAS-REQ-FIELD-REMOVED",
        "required_added_in": "OAS-REQ-FIELD-REQUIRED-ADDED",
        "required_removed_out": "OAS-RES-FIELD-REQUIRED-REMOVED",
        "type_changed_in": "OAS-REQ-TYPE-CHANGED",
        "type_changed_out": "OAS-RES-TYPE-CHANGED",
        "enum_narrowed_in": "OAS-REQ-ENUM-NARROWED",
        "enum_extended_out": "OAS-RES-ENUM-EXTENDED",
    },
    SchemaFormat.ASYNCAPI: {
        "field_removed_out": "ASYNC-MSG-FIELD-REMOVED",
        "field_removed_in": "ASYNC-MSG-FIELD-REMOVED",
        "required_added_in": "ASYNC-MSG-FIELD-REQUIRED-ADDED",
        "required_removed_out": "ASYNC-MSG-FIELD-REQUIRED-ADDED",
        "type_changed_in": "ASYNC-MSG-TYPE-CHANGED",
        "type_changed_out": "ASYNC-MSG-TYPE-CHANGED",
        "enum_narrowed_in": "ASYNC-MSG-TYPE-CHANGED",
        "enum_extended_out": "ASYNC-MSG-TYPE-CHANGED",
    },
    SchemaFormat.JSONSCHEMA: {
        "field_removed_out": "JSON-FIELD-REMOVED",
        "field_removed_in": "JSON-FIELD-REMOVED",
        "required_added_in": "JSON-FIELD-REQUIRED-ADDED",
        "required_removed_out": "JSON-FIELD-REQUIRED-ADDED",
        "type_changed_in": "JSON-TYPE-CHANGED",
        "type_changed_out": "JSON-TYPE-CHANGED",
        "enum_narrowed_in": "JSON-TYPE-CHANGED",
        "enum_extended_out": "JSON-TYPE-CHANGED",
    },
}


def load_document(path: str | Path) -> Any:
    """Load a YAML/JSON document from disk."""
    text = Path(path).read_text(encoding="utf-8")
    if str(path).endswith(".json"):
        return json.loads(text)
    return yaml.safe_load(text)


def detect_format(path: str | Path) -> Optional[SchemaFormat]:
    """Best-effort schema-format detection from extension and content."""
    p = str(path)
    if p.endswith(".proto"):
        return SchemaFormat.PROTOBUF
    if p.endswith((".graphql", ".gql", ".graphqls")):
        return SchemaFormat.GRAPHQL
    if p.endswith(".avsc"):
        return SchemaFormat.AVRO
    try:
        doc = load_document(p)
    except Exception:
        return None
    if not isinstance(doc, dict):
        return None
    if "openapi" in doc or "swagger" in doc:
        return SchemaFormat.OPENAPI
    if "asyncapi" in doc:
        return SchemaFormat.ASYNCAPI
    if doc.get("type") in ("record", "enum", "fixed") and "name" in doc:
        return SchemaFormat.AVRO
    if "$schema" in doc or "properties" in doc:
        return SchemaFormat.JSONSCHEMA
    return None


def make_ref_resolver(document: dict[str, Any]) -> Resolver:
    """Build a $ref resolver over local JSON-pointer references."""

    def resolve(ref: str) -> Optional[dict[str, Any]]:
        if not ref.startswith("#/"):
            return None
        node: Any = document
        for part in ref[2:].split("/"):
            part = part.replace("~1", "/").replace("~0", "~")
            if not isinstance(node, dict) or part not in node:
                return None
            node = node[part]
        return node if isinstance(node, dict) else None

    return resolve


def collect_refs(node: Any, acc: set[str]) -> None:
    """Collect every local $ref string reachable from `node`."""
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str):
            acc.add(ref)
        for value in node.values():
            collect_refs(value, acc)
    elif isinstance(node, list):
        for item in node:
            collect_refs(item, acc)


def _deref(schema: dict[str, Any], resolver: Optional[Resolver]) -> dict[str, Any]:
    ref = schema.get("$ref")
    if isinstance(ref, str) and resolver is not None:
        resolved = resolver(ref)
        if resolved is not None:
            return resolved
    return schema


def diff_schema_pair(
    location: str,
    old_schema: Any,
    new_schema: Any,
    direction: Direction,
    fmt: SchemaFormat,
    *,
    old_resolver: Optional[Resolver] = None,
    new_resolver: Optional[Resolver] = None,
    blast_radius: int = 1,
    _seen: Optional[set] = None,
) -> list[UnifiedChange]:
    """
    Direction-aware structural diff of two JSON-schema nodes.

    INPUT (contravariant): the new schema must accept everything the old
    one accepted. OUTPUT (covariant): the new schema must emit no less
    than the old one guaranteed.
    """
    changes: list[UnifiedChange] = []
    if not isinstance(old_schema, dict) or not isinstance(new_schema, dict):
        return changes
    rules = SCHEMA_RULES[fmt]
    seen = set(_seen or set())
    old_ref = old_schema.get("$ref")
    if isinstance(old_ref, str):
        if ("old", old_ref) in seen:
            return changes
        seen.add(("old", old_ref))
    new_ref = new_schema.get("$ref")
    if isinstance(new_ref, str):
        if ("new", new_ref) in seen:
            return changes
        seen.add(("new", new_ref))
    old_schema = _deref(old_schema, old_resolver)
    new_schema = _deref(new_schema, new_resolver)

    def emit(rule_key: str, loc: str, message: str, **kw: Any) -> None:
        changes.append(make_change(
            rules[rule_key], fmt, direction, loc, message,
            blast_radius=blast_radius, **kw,
        ))

    old_type = old_schema.get("type")
    new_type = new_schema.get("type")
    if old_type is not None and new_type is not None and old_type != new_type:
        key = "type_changed_in" if direction == Direction.INPUT else "type_changed_out"
        emit(key, location,
             f"Type changed from '{old_type}' to '{new_type}'",
             old_value=old_type, new_value=new_type)
        return changes

    old_enum = old_schema.get("enum")
    new_enum = new_schema.get("enum")
    if isinstance(old_enum, list) and isinstance(new_enum, list):
        if direction == Direction.INPUT:
            for value in [v for v in old_enum if v not in new_enum]:
                emit("enum_narrowed_in", f"{location}/enum",
                     f"Accepted enum value '{value}' removed",
                     old_value=value,
                     mitigation="Keep accepting the old value or version the API")
        else:
            for value in [v for v in new_enum if v not in old_enum]:
                emit("enum_extended_out", f"{location}/enum",
                     f"New enum value '{value}' emitted that old consumers never saw",
                     new_value=value,
                     mitigation="Ensure consumers tolerate unknown enum values")

    old_props = old_schema.get("properties", {}) or {}
    new_props = new_schema.get("properties", {}) or {}
    old_required = set(old_schema.get("required", []) or [])
    new_required = set(new_schema.get("required", []) or [])

    for name, old_prop in old_props.items():
        loc = f"{location}/properties/{name}"
        if name not in new_props:
            if direction == Direction.OUTPUT:
                emit("field_removed_out", loc, f"Property '{name}' removed",
                     old_value=name,
                     mitigation="Deprecate the property before removing it")
            else:
                emit("field_removed_in", loc,
                     f"Optional request property '{name}' removed "
                     "(old clients may still send it)",
                     old_value=name)
            continue
        changes.extend(diff_schema_pair(
            loc, old_prop, new_props[name], direction, fmt,
            old_resolver=old_resolver, new_resolver=new_resolver,
            blast_radius=blast_radius, _seen=seen,
        ))

    if direction == Direction.INPUT:
        for name in sorted(new_required - old_required):
            emit("required_added_in", f"{location}/properties/{name}",
                 f"Property '{name}' is now required on input",
                 new_value="required=true",
                 mitigation="Keep the property optional with a default value")
    else:
        for name in sorted(old_required - new_required):
            if name in new_props:
                emit("required_removed_out", f"{location}/properties/{name}",
                     f"Property '{name}' is no longer guaranteed in output",
                     old_value="required=true", new_value="required=false")

    if "items" in old_schema and "items" in new_schema:
        changes.extend(diff_schema_pair(
            f"{location}/items", old_schema["items"], new_schema["items"],
            direction, fmt,
            old_resolver=old_resolver, new_resolver=new_resolver,
            blast_radius=blast_radius, _seen=seen,
        ))

    return changes


def dedup_changes(changes: list[UnifiedChange]) -> list[UnifiedChange]:
    """Drop exact duplicate (rule_id, location, message) changes."""
    seen: set[tuple[str, str, str]] = set()
    out: list[UnifiedChange] = []
    for change in changes:
        key = (change.rule_id, change.location, change.message)
        if key not in seen:
            seen.add(key)
            out.append(change)
    return out
