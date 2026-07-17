"""
Dependency Helpers - RESTler-style producer/consumer ordering (RESEARCH_15).

Simplified deterministic subset: an operation A "produces" a field name
(e.g. `id`) if that name appears in its 2xx response schema properties.
An operation B "consumes" that field if a path parameter of B matches the
name (after stripping common suffixes like `Id`). We order so producers
run before their consumers; cycles are broken by dropping the
back-edge and logging it (never raising).
"""

from typing import Any

from Asgard.Forseti.LiveContract.models.live_contract_models import ProbeOperation


def extract_operations(openapi_doc: dict[str, Any]) -> list[ProbeOperation]:
    """Walk an OpenAPI document's paths into a flat list of ProbeOperation."""
    operations: list[ProbeOperation] = []
    paths = openapi_doc.get("paths", {}) or {}
    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        for method, op in path_item.items():
            if method.lower() not in ("get", "post", "put", "patch", "delete"):
                continue
            if not isinstance(op, dict):
                continue
            op_id = op.get("operationId") or f"{method.upper()} {path}"
            path_params = [
                p["name"]
                for p in op.get("parameters", [])
                if isinstance(p, dict) and p.get("in") == "path"
            ]
            required_body_fields = _required_body_fields(op)
            produced_fields = _produced_fields(op)
            responses = _response_schemas(op)
            operations.append(
                ProbeOperation(
                    operation_id=op_id,
                    method=method.upper(),
                    path=path,
                    path_params=path_params,
                    required_body_fields=required_body_fields,
                    produced_fields=produced_fields,
                    request_body_schema=_request_body_schema(op),
                    responses=responses,
                )
            )
    return operations


def _request_body_schema(op: dict[str, Any]) -> dict[str, Any] | None:
    body = op.get("requestBody", {})
    content = body.get("content", {}) if isinstance(body, dict) else {}
    json_content = content.get("application/json", {})
    return json_content.get("schema") if isinstance(json_content, dict) else None


def _required_body_fields(op: dict[str, Any]) -> list[str]:
    schema = _request_body_schema(op) or {}
    return list(schema.get("required", []) or [])


def _response_schemas(op: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for status, resp in (op.get("responses", {}) or {}).items():
        if not isinstance(resp, dict):
            continue
        content = resp.get("content", {}) or {}
        json_content = content.get("application/json", {})
        schema = json_content.get("schema") if isinstance(json_content, dict) else None
        if schema:
            out[str(status)] = schema
    return out


def _produced_fields(op: dict[str, Any]) -> list[str]:
    fields: list[str] = []
    for status, schema in _response_schemas(op).items():
        if not status.startswith("2"):
            continue
        props = schema.get("properties", {}) or {}
        fields.extend(props.keys())
    return fields


def _normalize_param(name: str) -> str:
    """Strip common id-suffix decorations so `petId` matches produced `id`."""
    lowered = name.lower()
    for suffix in ("id",):
        if lowered.endswith(suffix) and lowered != suffix:
            return suffix
    return lowered


def build_dependency_edges(
    operations: list[ProbeOperation],
) -> list[tuple[str, str]]:
    """Return (producer_op_id, consumer_op_id) edges: producer must run first."""
    edges: list[tuple[str, str]] = []
    producers_by_field: dict[str, list[str]] = {}
    for op in operations:
        for field in op.produced_fields:
            producers_by_field.setdefault(_normalize_param(field), []).append(op.operation_id)

    for op in operations:
        for param in op.path_params:
            key = _normalize_param(param)
            for producer_id in producers_by_field.get(key, []):
                if producer_id != op.operation_id:
                    edges.append((producer_id, op.operation_id))
    return edges


def topological_order(
    operations: list[ProbeOperation],
) -> tuple[list[ProbeOperation], list[tuple[str, str]]]:
    """Kahn's algorithm; cycle edges are dropped (fallback) and returned separately.

    Ties are broken by declaration order so the result is deterministic.
    """
    by_id = {op.operation_id: op for op in operations}
    edges = build_dependency_edges(operations)

    adjacency: dict[str, list[str]] = {op.operation_id: [] for op in operations}
    indegree: dict[str, int] = {op.operation_id: 0 for op in operations}
    for producer, consumer in edges:
        adjacency[producer].append(consumer)
        indegree[consumer] += 1

    declared_order = [op.operation_id for op in operations]
    ready = [oid for oid in declared_order if indegree[oid] == 0]
    ordered_ids: list[str] = []
    while ready:
        ready.sort(key=declared_order.index)
        current = ready.pop(0)
        ordered_ids.append(current)
        for nxt in adjacency[current]:
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                ready.append(nxt)

    dropped: list[tuple[str, str]] = []
    if len(ordered_ids) < len(operations):
        # Cycle present: append remaining ids in declared order and record
        # the edges that could not be satisfied.
        remaining = [oid for oid in declared_order if oid not in ordered_ids]
        placed = set(ordered_ids)
        for producer, consumer in edges:
            if consumer in remaining and producer not in placed:
                dropped.append((producer, consumer))
        ordered_ids.extend(remaining)

    return [by_id[oid] for oid in ordered_ids], dropped
