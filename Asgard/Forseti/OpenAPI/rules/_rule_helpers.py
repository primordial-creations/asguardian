"""
OpenAPI Rule Helpers - shared walkers and registration glue (plan 03).

Rules yield (json_path, message) tuples; the `openapi_rule` decorator
turns them into canonical Findings carrying the rule's fixed metadata
and registers the rule in the default registry.
"""

import difflib
import re
from typing import Any, Callable, Iterable, Iterator, Optional

from Asgard.Forseti.OpenAPI.utilities._openapi_spec_utils import deref_node
from Asgard.Forseti.Reporting.models.finding_models import Coordinates, Finding
from Asgard.Forseti.Rules.models._rule_base_models import (
    Confidence,
    Cost,
    RuleCategory,
    SchemaFormat,
    Severity,
)
from Asgard.Forseti.Rules.models.rule_models import RuleMeta
from Asgard.Forseti.Rules.services.rule_registry_service import default_registry

HTTP_METHODS = ["get", "put", "post", "delete", "options", "head", "patch", "trace"]

RawFinding = tuple[str, str]
RuleFunction = Callable[[dict[str, Any]], Iterable[RawFinding]]


def openapi_rule(
    rule_id: str,
    severity: Severity,
    *,
    category: RuleCategory,
    confidence: Confidence = Confidence.DETERMINISTIC,
    core: bool = False,
    cost: Cost = Cost.ON,
    description: str = "",
    rationale: str = "",
):
    """Register an OpenAPI rule yielding (json_path, message) tuples."""
    meta = RuleMeta(
        rule_id=rule_id,
        formats={SchemaFormat.OPENAPI},
        cost=cost,
        confidence=confidence,
        severity=severity,
        category=category,
        core=core,
        description=description,
        rationale=rationale,
    )

    def decorator(fn: RuleFunction) -> RuleFunction:
        def check(document: dict[str, Any]) -> Iterator[Finding]:
            for json_path, message in fn(document):
                yield Finding(
                    rule_id=rule_id,
                    severity=severity,
                    message=message,
                    coordinates=Coordinates(json_path=json_path),
                    rationale=rationale or None,
                    category=category,
                    format=SchemaFormat.OPENAPI,
                )

        default_registry.register(meta, check)
        return fn

    return decorator


def escape_pointer(segment: str) -> str:
    """Escape a key for use in a JSON pointer path."""
    return str(segment).replace("~", "~0").replace("/", "~1")


def iter_operations(document: dict[str, Any]) -> Iterator[tuple[str, str, dict[str, Any], str]]:
    """Yield (path, method, operation, json_path) for every operation."""
    for path, path_item in (document.get("paths") or {}).items():
        if not isinstance(path_item, dict):
            continue
        for method in HTTP_METHODS:
            operation = path_item.get(method)
            if isinstance(operation, dict):
                yield path, method, operation, f"/paths/{escape_pointer(path)}/{method}"


def iter_parameters(
    document: dict[str, Any],
) -> Iterator[tuple[dict[str, Any], str, str]]:
    """
    Yield (parameter, json_path, context) for path-item and operation
    parameters, with local $refs resolved (context = 'PATH /x' style label).
    """
    for path, path_item in (document.get("paths") or {}).items():
        if not isinstance(path_item, dict):
            continue
        base = f"/paths/{escape_pointer(path)}"
        for index, param in enumerate(path_item.get("parameters") or []):
            resolved = deref_node(document, param)
            if isinstance(resolved, dict):
                yield resolved, f"{base}/parameters/{index}", path
        for method in HTTP_METHODS:
            operation = path_item.get(method)
            if not isinstance(operation, dict):
                continue
            for index, param in enumerate(operation.get("parameters") or []):
                resolved = deref_node(document, param)
                if isinstance(resolved, dict):
                    yield (resolved, f"{base}/{method}/parameters/{index}",
                           f"{method.upper()} {path}")


_SCHEMA_CHILD_KEYS = ("properties", "items", "additionalProperties",
                      "allOf", "anyOf", "oneOf", "not")


def iter_schemas(
    document: dict[str, Any],
    root_schema: dict[str, Any],
    json_path: str,
    *,
    follow_refs: bool = False,
    _seen_refs: Optional[set[str]] = None,
) -> Iterator[tuple[dict[str, Any], str, Optional[str]]]:
    """
    Walk a schema tree yielding (schema, json_path, property_name).

    property_name is set for schemas that are object properties. Cycle-safe:
    $refs are followed at most once each when follow_refs is True.
    """
    seen = _seen_refs if _seen_refs is not None else set()

    def walk(schema: Any, path: str, prop: Optional[str]) -> Iterator:
        if not isinstance(schema, dict):
            return
        ref = schema.get("$ref")
        if isinstance(ref, str):
            if not follow_refs or ref in seen:
                return
            seen.add(ref)
            resolved = deref_node(document, schema, set(seen))
            if isinstance(resolved, dict) and resolved is not schema:
                yield from walk(resolved, path, prop)
            return
        yield schema, path, prop
        for name, sub in (schema.get("properties") or {}).items():
            yield from walk(sub, f"{path}/properties/{escape_pointer(name)}", name)
        items = schema.get("items")
        if isinstance(items, dict):
            yield from walk(items, f"{path}/items", prop)
        extra = schema.get("additionalProperties")
        if isinstance(extra, dict):
            yield from walk(extra, f"{path}/additionalProperties", None)
        for combiner in ("allOf", "anyOf", "oneOf"):
            for index, sub in enumerate(schema.get(combiner) or []):
                yield from walk(sub, f"{path}/{combiner}/{index}", prop)
        if isinstance(schema.get("not"), dict):
            yield from walk(schema["not"], f"{path}/not", prop)

    yield from walk(root_schema, json_path, None)


def iter_request_schemas(
    document: dict[str, Any],
) -> Iterator[tuple[dict[str, Any], str, Optional[str], str]]:
    """
    Yield (schema, json_path, property_name, op_label) for every schema node
    reachable from a request body or request parameter (refs followed).
    """
    for path, method, operation, op_path in iter_operations(document):
        label = f"{method.upper()} {path}"
        body = deref_node(document, operation.get("requestBody"))
        if isinstance(body, dict):
            for media, media_obj in (body.get("content") or {}).items():
                if not isinstance(media_obj, dict):
                    continue
                schema = media_obj.get("schema")
                if isinstance(schema, dict):
                    base = (f"{op_path}/requestBody/content/"
                            f"{escape_pointer(media)}/schema")
                    for node, node_path, prop in iter_schemas(
                        document, schema, base, follow_refs=True
                    ):
                        yield node, node_path, prop, label
        for index, param in enumerate(operation.get("parameters") or []):
            resolved = deref_node(document, param)
            if not isinstance(resolved, dict):
                continue
            schema = resolved.get("schema")
            if isinstance(schema, dict):
                base = f"{op_path}/parameters/{index}/schema"
                for node, node_path, prop in iter_schemas(
                    document, schema, base, follow_refs=True
                ):
                    yield node, node_path, prop, label


def iter_component_schemas(
    document: dict[str, Any],
) -> Iterator[tuple[str, dict[str, Any], str]]:
    """Yield (name, schema, json_path) for each component schema."""
    schemas = (document.get("components") or {}).get("schemas") or {}
    for name, schema in schemas.items():
        if isinstance(schema, dict):
            yield name, schema, f"/components/schemas/{escape_pointer(name)}"


def iter_security_schemes(
    document: dict[str, Any],
) -> Iterator[tuple[str, dict[str, Any], str]]:
    """Yield (name, scheme, json_path) for each security scheme (2.0 + 3.x)."""
    schemes = (document.get("components") or {}).get("securitySchemes")
    base = "/components/securitySchemes"
    if schemes is None:
        schemes = document.get("securityDefinitions")
        base = "/securityDefinitions"
    for name, scheme in (schemes or {}).items():
        resolved = deref_node(document, scheme)
        if isinstance(resolved, dict):
            yield name, resolved, f"{base}/{escape_pointer(name)}"


# ---------------------------------------------------------------------------
# Description-quality heuristics (DEEPTHINK_08 §2, deterministic)
# ---------------------------------------------------------------------------

DESCRIPTION_STOP_WORDS = {"todo", "tbd", "fixme", "n/a", "na", "test", "xxx", "..."}
MIN_DESCRIPTION_CHARS = 15
MIN_DESCRIPTION_WORDS = 3
TAUTOLOGY_THRESHOLD = 0.85

_CAMEL_SPLIT = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|[_\-\s./]+")


def tokenize_identifier(name: str) -> list[str]:
    """Split an identifier into normalized lowercase word tokens."""
    return [t.lower() for t in _CAMEL_SPLIT.split(name or "") if t]


def description_quality(name: str, description: Optional[str]) -> tuple[bool, str]:
    """
    Deterministic description-quality check.

    Returns (ok, reason). Zero credit for stop-words, tautologies
    (Levenshtein-style similarity between name tokens and description
    tokens > 0.85), and too-short descriptions.
    """
    text = (description or "").strip()
    if not text:
        return False, "missing"
    lowered = text.lower().strip(".! ")
    if lowered in DESCRIPTION_STOP_WORDS:
        return False, f"placeholder text '{text}'"
    if len(text) < MIN_DESCRIPTION_CHARS or len(text.split()) < MIN_DESCRIPTION_WORDS:
        return False, f"too short ({len(text)} chars)"
    name_tokens = " ".join(tokenize_identifier(name))
    desc_tokens = " ".join(
        t for t in tokenize_identifier(lowered)
        if t not in {"the", "a", "an", "of", "for", "this", "is"}
    )
    if name_tokens and desc_tokens:
        similarity = difflib.SequenceMatcher(None, name_tokens, desc_tokens).ratio()
        if similarity > TAUTOLOGY_THRESHOLD:
            return False, "restates the field name (tautology)"
    return True, "ok"


def get_success_codes(operation: dict[str, Any]) -> list[str]:
    """Status codes in the 2xx/3xx range declared on an operation."""
    return [str(code) for code in (operation.get("responses") or {})
            if str(code)[:1] in ("2", "3")]
