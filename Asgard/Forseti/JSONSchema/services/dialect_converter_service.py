"""
Dialect Converter Service.

Deterministic schema-dialect conversion between the OpenAPI 3.0 schema
dialect (draft-04/07-ish, `nullable`, boolean `exclusiveMinimum`) and the
OpenAPI 3.1 / JSON Schema 2020-12 dialect.

Conversions are lossless where possible; every lossy transform is surfaced
explicitly as a LossRecord (silent conversion loss breaks SDK generation
downstream — RESEARCH_17).
"""

from copy import deepcopy
from typing import Any

from Asgard.Forseti.JSONSchema.models.jsonschema_models import (
    DialectConversionResult,
    LossRecord,
)

# Keys whose values are schemas (dict) / maps of schemas / lists of schemas
_SCHEMA_MAP_KEYS = ("properties", "patternProperties", "$defs", "definitions", "dependentSchemas")
_SCHEMA_LIST_KEYS = ("allOf", "anyOf", "oneOf", "prefixItems")
_SCHEMA_VALUE_KEYS = (
    "items", "additionalItems", "additionalProperties", "contains",
    "propertyNames", "not", "if", "then", "else",
    "unevaluatedProperties", "unevaluatedItems",
)


class DialectConverterService:
    """
    Converts embedded schemas between OAS 3.0 and OAS 3.1 (2020-12) dialects.

    Usage:
        service = DialectConverterService()
        result = service.convert_30_to_31(schema)
        for loss in result.lossy_changes:
            print(loss.message)
    """

    def convert_30_to_31(self, schema: dict[str, Any]) -> DialectConversionResult:
        """
        Convert an OAS 3.0 schema to the 3.1 / 2020-12 dialect.

        Transforms: `nullable: true` => `type: [T, "null"]`;
        boolean `exclusiveMinimum/Maximum` + `minimum/maximum` => numeric form;
        `example` => `examples: [example]`.
        """
        converted = deepcopy(schema)
        losses: list[LossRecord] = []
        changed = self._walk(converted, "$", losses, self._up_node)
        return DialectConversionResult(
            converted=converted, source_dialect="oas-3.0", target_dialect="oas-3.1",
            lossy_changes=losses, changed=changed,
        )

    def convert_31_to_30(self, schema: dict[str, Any]) -> DialectConversionResult:
        """
        Convert an OAS 3.1 / 2020-12 schema down to the 3.0 dialect.

        Lossy transforms are reported: `type` arrays => `nullable` (or loss),
        numeric `exclusiveMinimum/Maximum` => boolean form, `prefixItems` =>
        array-form `items`, `unevaluatedProperties` dropped with WARNING,
        `const` => single-value `enum`, `examples` => `example`.
        """
        converted = deepcopy(schema)
        losses: list[LossRecord] = []
        changed = self._walk(converted, "$", losses, self._down_node)
        return DialectConversionResult(
            converted=converted, source_dialect="oas-3.1", target_dialect="oas-3.0",
            lossy_changes=losses, changed=changed,
        )

    # ------------------------------------------------------------------
    # traversal
    # ------------------------------------------------------------------

    def _walk(self, node: Any, path: str, losses: list[LossRecord], transform) -> bool:
        if not isinstance(node, dict):
            return False
        changed = transform(node, path, losses)
        for key in _SCHEMA_MAP_KEYS:
            if isinstance(node.get(key), dict):
                for name, sub in node[key].items():
                    changed |= self._walk(sub, f"{path}.{key}.{name}", losses, transform)
        for key in _SCHEMA_LIST_KEYS:
            if isinstance(node.get(key), list):
                for i, sub in enumerate(node[key]):
                    changed |= self._walk(sub, f"{path}.{key}[{i}]", losses, transform)
        for key in _SCHEMA_VALUE_KEYS:
            if isinstance(node.get(key), dict):
                changed |= self._walk(node[key], f"{path}.{key}", losses, transform)
        if isinstance(node.get("items"), list):
            for i, sub in enumerate(node["items"]):
                changed |= self._walk(sub, f"{path}.items[{i}]", losses, transform)
        return changed

    # ------------------------------------------------------------------
    # 3.0 -> 3.1 (lossless)
    # ------------------------------------------------------------------

    def _up_node(self, node: dict[str, Any], path: str, losses: list[LossRecord]) -> bool:
        changed = False
        if "nullable" in node:
            nullable = node.pop("nullable")
            if nullable is True:
                existing = node.get("type")
                if isinstance(existing, list):
                    if "null" not in existing:
                        existing.append("null")
                elif isinstance(existing, str):
                    node["type"] = [existing, "null"]
                else:
                    losses.append(LossRecord(
                        path=path, keyword="nullable", severity="info", original_value=True,
                        message="'nullable: true' without 'type' dropped (already unconstrained in 3.1)",
                    ))
            changed = True

        if node.get("exclusiveMinimum") is True and "minimum" in node:
            node["exclusiveMinimum"] = node.pop("minimum")
            changed = True
        elif node.get("exclusiveMinimum") is False:
            node.pop("exclusiveMinimum")
            changed = True
        if node.get("exclusiveMaximum") is True and "maximum" in node:
            node["exclusiveMaximum"] = node.pop("maximum")
            changed = True
        elif node.get("exclusiveMaximum") is False:
            node.pop("exclusiveMaximum")
            changed = True

        if "example" in node and "examples" not in node:
            node["examples"] = [node.pop("example")]
            changed = True

        if isinstance(node.get("items"), list):
            node["prefixItems"] = node.pop("items")
            if "additionalItems" in node:
                node["items"] = node.pop("additionalItems")
            changed = True
        return changed

    # ------------------------------------------------------------------
    # 3.1 -> 3.0 (lossy, reported)
    # ------------------------------------------------------------------

    def _down_node(self, node: dict[str, Any], path: str, losses: list[LossRecord]) -> bool:
        changed = False
        type_value = node.get("type")
        if isinstance(type_value, list):
            non_null = [t for t in type_value if t != "null"]
            had_null = len(non_null) != len(type_value)
            if len(non_null) == 1:
                node["type"] = non_null[0]
                if had_null:
                    node["nullable"] = True
            elif len(non_null) == 0:
                node.pop("type")
                node["nullable"] = True
            else:
                node["type"] = non_null[0]
                if had_null:
                    node["nullable"] = True
                losses.append(LossRecord(
                    path=path, keyword="type", severity="warning", original_value=type_value,
                    message=f"Multi-type array {type_value} narrowed to '{non_null[0]}' (OAS 3.0 has no type unions)",
                ))
            changed = True

        for keyword, bound in (("exclusiveMinimum", "minimum"), ("exclusiveMaximum", "maximum")):
            limit = node.get(keyword)
            if isinstance(limit, (int, float)) and not isinstance(limit, bool):
                if bound in node and node[bound] != limit:
                    losses.append(LossRecord(
                        path=path, keyword=keyword, severity="warning", original_value=limit,
                        message=f"Numeric {keyword} {limit} overwrote existing {bound} {node[bound]}",
                    ))
                node[bound] = limit
                node[keyword] = True
                changed = True

        if "prefixItems" in node:
            prefix = node.pop("prefixItems")
            rest = node.pop("items", None)
            node["items"] = prefix
            if rest is not None:
                node["additionalItems"] = rest
            changed = True

        for keyword in ("unevaluatedProperties", "unevaluatedItems"):
            if keyword in node:
                original = node.pop(keyword)
                losses.append(LossRecord(
                    path=path, keyword=keyword, severity="warning", original_value=original,
                    message=f"'{keyword}' dropped: no OAS 3.0 equivalent (constraint is silently weakened)",
                ))
                changed = True

        if "const" in node:
            node["enum"] = [node.pop("const")]
            changed = True

        if "examples" in node and isinstance(node["examples"], list):
            examples = node.pop("examples")
            if examples:
                node["example"] = examples[0]
                if len(examples) > 1:
                    losses.append(LossRecord(
                        path=path, keyword="examples", severity="info", original_value=examples,
                        message=f"Only the first of {len(examples)} examples kept (OAS 3.0 supports a single 'example')",
                    ))
            changed = True
        return changed


__all__ = ["DialectConverterService"]
