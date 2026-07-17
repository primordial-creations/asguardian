"""
Avro Adapter - projects the existing reader/writer resolution check onto
UnifiedChange, adding named-type resolution and default-value hazards.

Direction semantics: BACKWARD (new reader consumes old writer's data) is
evaluated as OUTPUT (event-log covariance); FORWARD as INPUT.
"""

from typing import Any, Optional

from Asgard.Forseti.Avro.models.avro_models import BreakingChange as AvroBreakingChange
from Asgard.Forseti.Avro.services._avro_compatibility_service_helpers import (
    check_compatibility,
)
from Asgard.Forseti.Compatibility.models._compat_base_models import CompatMode, Direction
from Asgard.Forseti.Compatibility.models.compat_models import UnifiedChange
from Asgard.Forseti.Compatibility.services._classification_helpers import make_change
from Asgard.Forseti.Compatibility.utilities.compat_utils import dedup_changes
from Asgard.Forseti.Rules.models._rule_base_models import SchemaFormat

FMT = SchemaFormat.AVRO

# (change_type value, severity) -> rule id
_RULE_MAP: dict[tuple[str, str], str] = {
    ("changed_field_type", "error"): "AVRO-TYPE-INCOMPATIBLE",
    ("removed_field", "warning"): "AVRO-FIELD-REMOVED",
    ("removed_field", "error"): "AVRO-FIELD-REMOVED",
    ("added_required_field", "error"): "AVRO-FIELD-ADDED-NO-DEFAULT",
    ("added_required_field", "warning"): "AVRO-FIELD-ADDED-DEFAULT",
    ("removed_enum_symbol", "error"): "AVRO-ENUM-SYMBOL-REMOVED",
    ("removed_enum_symbol", "warning"): "AVRO-ENUM-SYMBOL-REMOVED-DEFAULT",
    ("changed_enum_order", "warning"): "AVRO-ENUM-ORDER-CHANGED",
    ("changed_name", "error"): "AVRO-NAME-CHANGED",
    ("changed_size", "error"): "AVRO-FIXED-SIZE-CHANGED",
    ("incompatible_union", "error"): "AVRO-UNION-INCOMPATIBLE",
}


def build_named_type_registry(schema: Any, registry: Optional[dict[str, Any]] = None,
                              namespace: str = "") -> dict[str, Any]:
    """Collect record/enum/fixed definitions by fullname (and short name)."""
    if registry is None:
        registry = {}
    if isinstance(schema, list):
        for branch in schema:
            build_named_type_registry(branch, registry, namespace)
        return registry
    if not isinstance(schema, dict):
        return registry
    stype = schema.get("type")
    ns = schema.get("namespace", namespace)
    if stype in ("record", "enum", "fixed") and "name" in schema:
        name = schema["name"]
        fullname = f"{ns}.{name}" if ns else name
        registry.setdefault(fullname, schema)
        registry.setdefault(name, schema)
    if stype == "record":
        for field in schema.get("fields", []):
            build_named_type_registry(field.get("type"), registry, ns)
    elif stype == "array":
        build_named_type_registry(schema.get("items"), registry, ns)
    elif stype == "map":
        build_named_type_registry(schema.get("values"), registry, ns)
    return registry


_PRIMITIVES = {"null", "boolean", "int", "long", "float", "double", "bytes", "string"}


def resolve_named_types(schema: Any, registry: dict[str, Any],
                        _depth: int = 0) -> Any:
    """Substitute string references to named types with their definitions."""
    if _depth > 20:
        return schema
    if isinstance(schema, str):
        if schema not in _PRIMITIVES and schema in registry:
            return registry[schema]
        return schema
    if isinstance(schema, list):
        return [resolve_named_types(b, registry, _depth + 1) for b in schema]
    if isinstance(schema, dict):
        stype = schema.get("type")
        out = dict(schema)
        if stype == "record":
            out["fields"] = [
                {**f, "type": resolve_named_types(f.get("type"), registry, _depth + 1)}
                for f in schema.get("fields", [])
            ]
        elif stype == "array":
            out["items"] = resolve_named_types(schema.get("items"), registry, _depth + 1)
        elif stype == "map":
            out["values"] = resolve_named_types(schema.get("values"), registry, _depth + 1)
        elif isinstance(stype, (str, list, dict)) and stype not in _PRIMITIVES and \
                stype not in ("record", "enum", "fixed", "array", "map", "union"):
            out["type"] = resolve_named_types(stype, registry, _depth + 1)
        return out
    return schema


def _to_unified(change: AvroBreakingChange, direction: Direction) -> UnifiedChange:
    rule_id = _RULE_MAP.get(
        (str(change.change_type), change.severity),
        "AVRO-TYPE-INCOMPATIBLE",
    )
    unified = make_change(
        rule_id, FMT, direction, change.path, change.message,
        old_value=change.old_value, new_value=change.new_value,
        mitigation=change.mitigation,
    )
    if rule_id == "AVRO-FIELD-ADDED-DEFAULT":
        unified.mitigation = unified.mitigation or (
            "Structural bridge only: readers will observe the default value for "
            "old data; verify downstream logic treats it as 'absent', not as fact."
        )
    return unified


def diff_avro(old_schema: Any, new_schema: Any,
              mode: CompatMode = CompatMode.BACKWARD) -> list[UnifiedChange]:
    """Diff two parsed Avro schemas under a compatibility mode."""
    old_registry = build_named_type_registry(old_schema)
    new_registry = build_named_type_registry(new_schema)
    old_resolved = resolve_named_types(old_schema, old_registry)
    new_resolved = resolve_named_types(new_schema, new_registry)

    changes: list[UnifiedChange] = []
    base = mode.pairwise
    if base in (CompatMode.BACKWARD, CompatMode.FULL):
        for change in check_compatibility("/", old_resolved, new_resolved, is_backward=True):
            changes.append(_to_unified(change, Direction.OUTPUT))
    if base in (CompatMode.FORWARD, CompatMode.FULL):
        for change in check_compatibility("/", new_resolved, old_resolved, is_backward=False):
            changes.append(_to_unified(change, Direction.INPUT))
    return dedup_changes(changes)
