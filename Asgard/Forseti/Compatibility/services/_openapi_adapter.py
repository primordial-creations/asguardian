"""
OpenAPI Adapter - directional (contravariant request / covariant response)
diff of two OpenAPI documents onto UnifiedChange (plan 01, DEEPTHINK_01).

Blast radius: component schemas are weighted by the number of operations
whose subtree references them (reverse-$ref index, DEEPTHINK_04 1A).
"""

from typing import Any

from Asgard.Forseti.Compatibility.models._compat_base_models import Direction
from Asgard.Forseti.Compatibility.models.compat_models import UnifiedChange
from Asgard.Forseti.Compatibility.services._classification_helpers import make_change
from Asgard.Forseti.Compatibility.utilities.compat_utils import (
    collect_refs,
    dedup_changes,
    diff_schema_pair,
    make_ref_resolver,
)
from Asgard.Forseti.Rules.models._rule_base_models import SchemaFormat

_METHODS = ["get", "post", "put", "delete", "patch", "options", "head"]
FMT = SchemaFormat.OPENAPI


def build_reverse_ref_index(spec: dict[str, Any]) -> dict[str, set[str]]:
    """Map component-schema ref -> set of operation ids referencing it."""
    index: dict[str, set[str]] = {}
    resolver = make_ref_resolver(spec)
    for path, item in (spec.get("paths") or {}).items():
        if not isinstance(item, dict):
            continue
        for method in _METHODS:
            if method not in item:
                continue
            op_id = f"{path}/{method}"
            direct: set[str] = set()
            collect_refs(item[method], direct)
            # transitive closure through referenced schemas
            frontier = set(direct)
            seen: set[str] = set()
            while frontier:
                ref = frontier.pop()
                if ref in seen:
                    continue
                seen.add(ref)
                index.setdefault(ref, set()).add(op_id)
                target = resolver(ref)
                if target is not None:
                    nested: set[str] = set()
                    collect_refs(target, nested)
                    frontier |= nested - seen
    return index


def diff_openapi(old_spec: dict[str, Any], new_spec: dict[str, Any]) -> list[UnifiedChange]:
    """Full directional diff of two OpenAPI documents."""
    changes: list[UnifiedChange] = []
    old_resolver = make_ref_resolver(old_spec)
    new_resolver = make_ref_resolver(new_spec)
    ref_index = build_reverse_ref_index(old_spec)

    old_paths = old_spec.get("paths") or {}
    new_paths = new_spec.get("paths") or {}

    for path in sorted(set(old_paths) - set(new_paths)):
        changes.append(make_change(
            "OAS-PATH-REMOVED", FMT, Direction.INPUT, path,
            f"Endpoint removed: {path}", old_value=path,
            mitigation="Keep the endpoint for backward compatibility or version the API",
        ))

    for path in sorted(set(old_paths) & set(new_paths)):
        old_item = old_paths[path] or {}
        new_item = new_paths[path] or {}
        for method in _METHODS:
            if method in old_item and method not in new_item:
                changes.append(make_change(
                    "OAS-METHOD-REMOVED", FMT, Direction.INPUT,
                    f"{path}/{method}",
                    f"Method {method.upper()} removed from {path}",
                    old_value=method.upper(),
                ))
            elif method in old_item and method in new_item:
                changes.extend(_diff_operation(
                    f"{path}/{method}", old_item[method], new_item[method],
                    old_resolver, new_resolver,
                ))

    old_schemas = (old_spec.get("components") or {}).get("schemas") or {}
    new_schemas = (new_spec.get("components") or {}).get("schemas") or {}
    for name in sorted(set(old_schemas) - set(new_schemas)):
        ref = f"#/components/schemas/{name}"
        blast = max(1, len(ref_index.get(ref, set())))
        changes.append(make_change(
            "OAS-SCHEMA-REMOVED", FMT, Direction.OUTPUT, ref,
            f"Schema '{name}' removed", old_value=name, blast_radius=blast,
        ))
    for name in sorted(set(old_schemas) & set(new_schemas)):
        ref = f"#/components/schemas/{name}"
        blast = max(1, len(ref_index.get(ref, set())))
        # Component schemas can be reached from both directions; evaluate
        # covariantly (the stricter default for shared models).
        changes.extend(diff_schema_pair(
            ref, old_schemas[name], new_schemas[name], Direction.OUTPUT, FMT,
            old_resolver=old_resolver, new_resolver=new_resolver,
            blast_radius=blast,
        ))

    return dedup_changes(changes)


def _diff_operation(
    base: str,
    old_op: dict[str, Any],
    new_op: dict[str, Any],
    old_resolver: Any,
    new_resolver: Any,
) -> list[UnifiedChange]:
    changes: list[UnifiedChange] = []

    # --- parameters: Direction.INPUT (contravariant) ---
    old_params = {(p.get("name"), p.get("in")): p for p in old_op.get("parameters") or []}
    new_params = {(p.get("name"), p.get("in")): p for p in new_op.get("parameters") or []}
    for (name, loc), _param in old_params.items():
        if (name, loc) not in new_params:
            changes.append(make_change(
                "OAS-PARAM-REMOVED", FMT, Direction.INPUT,
                f"{base}/parameters/{name}",
                f"Parameter '{name}' ({loc}) removed", old_value=name,
            ))
    for (name, loc), param in new_params.items():
        if (name, loc) not in old_params and param.get("required", False):
            changes.append(make_change(
                "OAS-PARAM-REQUIRED-ADDED", FMT, Direction.INPUT,
                f"{base}/parameters/{name}",
                f"Required parameter '{name}' added", new_value=name,
                mitigation="Make the parameter optional with a default value",
            ))
    for (name, loc) in set(old_params) & set(new_params):
        old_schema = old_params[(name, loc)].get("schema")
        new_schema = new_params[(name, loc)].get("schema")
        if isinstance(old_schema, dict) and isinstance(new_schema, dict):
            changes.extend(diff_schema_pair(
                f"{base}/parameters/{name}", old_schema, new_schema,
                Direction.INPUT, FMT,
                old_resolver=old_resolver, new_resolver=new_resolver,
            ))

    # --- request body: Direction.INPUT ---
    old_body = old_op.get("requestBody")
    new_body = new_op.get("requestBody")
    if old_body and not new_body:
        changes.append(make_change(
            "OAS-REQBODY-REMOVED", FMT, Direction.INPUT,
            f"{base}/requestBody", "Request body removed",
        ))
    elif not old_body and new_body and new_body.get("required", False):
        changes.append(make_change(
            "OAS-REQBODY-REQUIRED-ADDED", FMT, Direction.INPUT,
            f"{base}/requestBody", "Required request body added",
            mitigation="Make the request body optional",
        ))
    elif old_body and new_body:
        for media, old_media in (old_body.get("content") or {}).items():
            new_media = (new_body.get("content") or {}).get(media)
            if new_media and "schema" in old_media and "schema" in new_media:
                changes.extend(diff_schema_pair(
                    f"{base}/requestBody/{media}",
                    old_media["schema"], new_media["schema"],
                    Direction.INPUT, FMT,
                    old_resolver=old_resolver, new_resolver=new_resolver,
                ))

    # --- responses: Direction.OUTPUT (covariant) ---
    old_responses = old_op.get("responses") or {}
    new_responses = new_op.get("responses") or {}
    for status in old_responses:
        if status not in new_responses:
            changes.append(make_change(
                "OAS-RESPONSE-REMOVED", FMT, Direction.OUTPUT,
                f"{base}/responses/{status}",
                f"Response {status} removed", old_value=status,
            ))
            continue
        old_resp = old_responses[status] or {}
        new_resp = new_responses[status] or {}
        for media, old_media in (old_resp.get("content") or {}).items():
            new_media = (new_resp.get("content") or {}).get(media)
            if new_media and "schema" in old_media and "schema" in new_media:
                changes.extend(diff_schema_pair(
                    f"{base}/responses/{status}/{media}",
                    old_media["schema"], new_media["schema"],
                    Direction.OUTPUT, FMT,
                    old_resolver=old_resolver, new_resolver=new_resolver,
                ))

    return changes
