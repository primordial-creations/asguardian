"""
Completeness Helpers - leaf-walk counters, signal extraction and tier
gates for the completeness service (plan 03, DEEPTHINK_08).
"""

from typing import Any

from Asgard.Forseti.OpenAPI.models.completeness_models import (
    CompletenessSignals,
    CompletenessVector,
    GateResult,
    MaturityTier,
)
from Asgard.Forseti.OpenAPI.rules._rule_helpers import (
    description_quality,
    get_success_codes,
    iter_component_schemas,
    iter_operations,
    iter_parameters,
    iter_request_schemas,
    iter_schemas,
)
from Asgard.Forseti.OpenAPI.rules.examples_rules import _validate_example
from Asgard.Forseti.OpenAPI.rules.security_rules import _PAGINATION_PARAMS
from Asgard.Forseti.OpenAPI.utilities._openapi_spec_utils import (
    deref_node,
    find_broken_refs,
)

_RFC7807_MEDIA = "application/problem+json"
_RFC7807_FIELDS = {"type", "title", "status", "detail"}
_RATE_LIMIT_HEADERS = {"x-ratelimit-limit", "x-ratelimit-remaining",
                       "x-rate-limit-limit", "ratelimit-limit", "retry-after"}


def _ratio(numerator: int, denominator: int, default: float = 1.0) -> float:
    """Safe ratio; `default` when the denominator is zero (vacuous truth)."""
    return numerator / denominator if denominator else default


def collect_signals(document: dict[str, Any]) -> CompletenessSignals:
    """Extract all raw completeness signals from a parsed spec."""
    signals = CompletenessSignals()

    # --- experiential: descriptions over ops, params, leaf properties ---
    described = total = 0
    for path, method, operation, _jp in iter_operations(document):
        signals.operation_count += 1
        total += 1
        name = operation.get("operationId") or f"{method} {path}"
        if description_quality(name, operation.get("description")
                               or operation.get("summary"))[0]:
            described += 1
    for param, _jp, _ctx in iter_parameters(document):
        total += 1
        if description_quality(str(param.get("name", "")),
                               param.get("description"))[0]:
            described += 1
    for schema_name, schema, json_path in iter_component_schemas(document):
        for node, _np, prop in iter_schemas(document, schema, json_path):
            if prop is None or node.get("properties") or node.get("$ref"):
                continue  # only leaf properties
            total += 1
            if description_quality(prop, node.get("description"))[0]:
                described += 1
    signals.described_units = described
    signals.total_units = total

    # --- examples ---
    for schema_name, schema, _jp in iter_component_schemas(document):
        example = schema.get("example")
        if example is None and isinstance(schema.get("examples"), list) \
                and schema["examples"]:
            example = schema["examples"][0]
        if example is None:
            continue
        signals.schemas_with_examples += 1
        if not _validate_example(document, schema, example):
            signals.schemas_with_valid_examples += 1
        else:
            signals.all_examples_valid = False
    signals.total_component_schemas = sum(
        1 for _ in iter_component_schemas(document)
    )

    # --- operational ---
    ops_with_errors = 0
    list_gets = 0
    paginated_gets = 0
    for path, method, operation, _jp in iter_operations(document):
        responses = operation.get("responses") or {}
        codes = {str(c) for c in responses}
        has_4xx = any(c.startswith("4") for c in codes)
        has_5xx = any(c.startswith("5") for c in codes) or "default" in codes
        if has_4xx and has_5xx:
            ops_with_errors += 1
        for status, response in responses.items():
            resolved = deref_node(document, response)
            if not isinstance(resolved, dict):
                continue
            if str(status)[:1] in ("4", "5") or str(status) == "default":
                content = resolved.get("content") or {}
                if _RFC7807_MEDIA in content:
                    signals.unified_error_schema = True
                for media_obj in content.values():
                    schema = deref_node(
                        document,
                        media_obj.get("schema") if isinstance(media_obj, dict)
                        else None,
                    )
                    if isinstance(schema, dict):
                        props = {p.lower() for p in (schema.get("properties") or {})}
                        if len(props & _RFC7807_FIELDS) >= 3:
                            signals.unified_error_schema = True
            headers = {str(h).lower() for h in (resolved.get("headers") or {})}
            if headers & _RATE_LIMIT_HEADERS:
                signals.rate_limits_documented = True
        if "429" in codes:
            signals.rate_limits_documented = True
        if method == "get":
            returns_array = False
            for status, response in responses.items():
                if str(status)[:1] != "2":
                    continue
                resolved = deref_node(document, response)
                if not isinstance(resolved, dict):
                    continue
                for media_obj in (resolved.get("content") or {}).values():
                    schema = deref_node(
                        document,
                        media_obj.get("schema") if isinstance(media_obj, dict)
                        else None,
                    )
                    if isinstance(schema, dict) and schema.get("type") == "array":
                        returns_array = True
            if returns_array:
                list_gets += 1
                names = set()
                for param in operation.get("parameters") or []:
                    resolved = deref_node(document, param)
                    if isinstance(resolved, dict):
                        names.add(str(resolved.get("name", "")).lower())
                if names & _PAGINATION_PARAMS:
                    paginated_gets += 1
    signals.error_coverage = _ratio(ops_with_errors, signals.operation_count, 0.0)
    signals.pagination_coverage = _ratio(paginated_gets, list_gets, 1.0)

    schemes = (document.get("components") or {}).get("securitySchemes") \
        or document.get("securityDefinitions") or {}
    applied = bool(document.get("security")) or any(
        op.get("security") for _p, _m, op, _j in iter_operations(document)
    )
    signals.auth_documented = bool(schemes) and (applied or not signals.operation_count)

    # --- structural ---
    signals.broken_refs = len(find_broken_refs(document))
    required_ok = ("openapi" in document or "swagger" in document) \
        and isinstance(document.get("info"), dict) \
        and bool(document["info"].get("title")) \
        and bool(document["info"].get("version")) \
        and ("paths" in document or "webhooks" in document
             or "components" in document)
    signals.structural_errors = (0 if required_ok else 1) + signals.broken_refs
    return signals


def compute_precision(document: dict[str, Any]) -> float:
    """Schema-precision vector: bounded/typed leaf constraints."""
    satisfied = total = 0

    def account(node: dict[str, Any]) -> None:
        nonlocal satisfied, total
        declared = node.get("type")
        if declared == "string" and not node.get("enum"):
            total += 1
            if node.get("format") or node.get("pattern") \
                    or node.get("maxLength") is not None:
                satisfied += 1
        elif declared in ("integer", "number") and not node.get("enum"):
            total += 1
            if node.get("minimum") is not None or node.get("maximum") is not None \
                    or node.get("exclusiveMinimum") is not None \
                    or node.get("exclusiveMaximum") is not None:
                satisfied += 1
        elif declared == "array":
            total += 1
            if node.get("maxItems") is not None:
                satisfied += 1
        elif declared == "object" or "properties" in node:
            total += 1
            if node.get("additionalProperties") is not None:
                satisfied += 1

    seen_paths: set[str] = set()
    for _name, schema, json_path in iter_component_schemas(document):
        for node, node_path, _prop in iter_schemas(document, schema, json_path):
            if node_path not in seen_paths:
                seen_paths.add(node_path)
                account(node)
    for node, node_path, _prop, _label in iter_request_schemas(document):
        if node_path not in seen_paths:
            seen_paths.add(node_path)
            account(node)
    return _ratio(satisfied, total, 0.0)


def compute_vector(
    document: dict[str, Any],
    signals: CompletenessSignals,
) -> CompletenessVector:
    """Fold signals into the 4-vector."""
    desc = _ratio(signals.described_units, signals.total_units, 0.0)
    if signals.total_component_schemas:
        example_share = _ratio(
            signals.schemas_with_valid_examples,
            signals.total_component_schemas, 0.0,
        )
        experiential = 0.7 * desc + 0.3 * example_share
    else:
        experiential = desc
    operational = (
        0.4 * signals.error_coverage
        + 0.2 * (1.0 if signals.unified_error_schema else 0.0)
        + 0.2 * (1.0 if signals.auth_documented else 0.0)
        + 0.2 * signals.pagination_coverage
    )
    structural = 1.0 if signals.structural_errors == 0 else max(
        0.0, 1.0 - 0.25 * signals.structural_errors
    )
    return CompletenessVector(
        experiential=round(min(1.0, experiential), 4),
        precision=round(compute_precision(document), 4),
        operational=round(min(1.0, operational), 4),
        structural=round(structural, 4),
    )


def evaluate_gates(
    vector: CompletenessVector,
    signals: CompletenessSignals,
    profile: str = "dx",
) -> list[GateResult]:
    """Evaluate all tier gates (DEEPTHINK_08 §3). secops ignores experiential."""
    secops = profile == "secops"

    def gate(tier: MaturityTier, name: str, passed: bool, detail: str) -> GateResult:
        return GateResult(tier=tier, name=name, passed=passed, detail=detail)

    gates = [
        gate(MaturityTier.BASIC, "structural complete",
             vector.structural >= 1.0, f"structural={vector.structural:.2f}"),
        gate(MaturityTier.BASIC, "auth documented",
             signals.auth_documented, f"auth_documented={signals.auth_documented}"),
    ]
    if not secops:
        gates.append(gate(MaturityTier.BASIC, "experiential > 60%",
                          vector.experiential > 0.60,
                          f"experiential={vector.experiential:.2f}"))
        gates.append(gate(MaturityTier.STANDARD, "experiential > 85%",
                          vector.experiential > 0.85,
                          f"experiential={vector.experiential:.2f}"))
        gates.append(gate(MaturityTier.STANDARD, "all examples validate",
                          signals.all_examples_valid,
                          f"all_examples_valid={signals.all_examples_valid}"))
    gates.append(gate(MaturityTier.STANDARD, "error coverage > 80%",
                      signals.error_coverage > 0.80,
                      f"error_coverage={signals.error_coverage:.2f}"))
    gates.extend([
        gate(MaturityTier.COMPREHENSIVE, "precision > 90%",
             vector.precision > 0.90, f"precision={vector.precision:.2f}"),
        gate(MaturityTier.COMPREHENSIVE, "unified error schema",
             signals.unified_error_schema,
             f"unified_error_schema={signals.unified_error_schema}"),
        gate(MaturityTier.COMPREHENSIVE, "rate limits documented",
             signals.rate_limits_documented,
             f"rate_limits_documented={signals.rate_limits_documented}"),
    ])
    return gates


def assign_tier(gates: list[GateResult]) -> tuple[MaturityTier, list[str]]:
    """
    Lowest-common-denominator tier assignment.

    Returns (tier, failed gate names of the next tier up).
    """
    order = [MaturityTier.BASIC, MaturityTier.STANDARD, MaturityTier.COMPREHENSIVE]
    achieved = MaturityTier.NONE
    for tier in order:
        tier_gates = [g for g in gates if g.tier == tier]
        if all(g.passed for g in tier_gates):
            achieved = tier
        else:
            break
    missing: list[str] = []
    if achieved != MaturityTier.COMPREHENSIVE:
        next_index = 0 if achieved == MaturityTier.NONE else order.index(achieved) + 1
        next_tier = order[next_index]
        missing = [f"{g.name} ({g.detail})" for g in gates
                   if g.tier == next_tier and not g.passed]
    return achieved, missing
