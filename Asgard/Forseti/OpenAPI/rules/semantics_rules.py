"""
OpenAPI Semantics Rules - protocol semantics and lexical-inference
heuristics (plan 03 Phase 4, DEEPTHINK_06).

Layering: protocol facts are deterministic WARNINGs; lexical guesses about
developer intent are HINTs and never harder — the tool must not force the
developer to lie about their API.
"""

import re

from typing import Any, Iterator, Optional

from Asgard.Forseti.OpenAPI.rules._rule_helpers import (
    escape_pointer,
    get_success_codes,
    iter_component_schemas,
    iter_operations,
    iter_schemas,
    openapi_rule,
)
from Asgard.Forseti.Rules.models._rule_base_models import (
    Confidence,
    RuleCategory,
    Severity,
)

_SEM = RuleCategory.SEMANTICS
_H = Confidence.HEURISTIC

_MONEY_WORDS = {"price", "amount", "cost", "balance", "total", "fee",
                "salary", "tax", "subtotal", "discount"}


@openapi_rule(
    "oas.semantics.success-response-required", Severity.WARNING, category=_SEM,
    description="Every operation should declare at least one success response",
    rationale="An operation with only error responses cannot describe its "
              "happy path.",
)
def check_success_response(document: dict[str, Any]) -> Iterator[tuple[str, str]]:
    for path, method, operation, json_path in iter_operations(document):
        responses = operation.get("responses") or {}
        if responses and not get_success_codes(operation) \
                and "default" not in responses:
            yield (f"{json_path}/responses",
                   f"Operation {method.upper()} {path} declares no 2xx/3xx/"
                   "default response")


@openapi_rule(
    "oas.semantics.get-no-request-body", Severity.WARNING, category=_SEM,
    description="GET operations should not declare a request body",
    rationale="RFC 9110: a GET body has no defined semantics; intermediaries "
              "may drop it.",
)
def check_get_no_body(document: dict[str, Any]) -> Iterator[tuple[str, str]]:
    for path, method, operation, json_path in iter_operations(document):
        if method in ("get", "head") and operation.get("requestBody"):
            yield (f"{json_path}/requestBody",
                   f"{method.upper()} {path} declares a request body")


@openapi_rule(
    "oas.semantics.delete-no-request-body", Severity.HINT, category=_SEM,
    confidence=_H,
    description="DELETE operations usually should not need a request body",
    rationale="DELETE bodies are legal but widely unsupported by proxies and "
              "client libraries.",
)
def check_delete_no_body(document: dict[str, Any]) -> Iterator[tuple[str, str]]:
    for path, method, operation, json_path in iter_operations(document):
        if method == "delete" and operation.get("requestBody"):
            yield (f"{json_path}/requestBody",
                   f"DELETE {path} declares a request body")


@openapi_rule(
    "oas.semantics.204-no-content-body", Severity.WARNING, category=_SEM,
    description="204 responses must not define content",
    rationale="RFC 9110: 204 No Content forbids a message body.",
)
def check_204_no_content(document: dict[str, Any]) -> Iterator[tuple[str, str]]:
    for path, method, operation, json_path in iter_operations(document):
        for status in ("204", "304"):
            response = (operation.get("responses") or {}).get(status)
            if isinstance(response, dict) and response.get("content"):
                yield (f"{json_path}/responses/{status}",
                       f"{status} response of {method.upper()} {path} "
                       "defines content")


@openapi_rule(
    "oas.semantics.post-created-201", Severity.HINT, category=_SEM, confidence=_H,
    description="Collection POST operations conventionally return 201",
    rationale="Creating a resource usually answers 201 Created with a "
              "Location header; 200 hides the creation semantics.",
)
def check_post_201(document: dict[str, Any]) -> Iterator[tuple[str, str]]:
    for path, method, operation, json_path in iter_operations(document):
        if method != "post" or str(path).rstrip("/").endswith("}"):
            continue
        responses = operation.get("responses") or {}
        codes = {str(c) for c in responses}
        if "200" in codes and not codes & {"201", "202", "204"}:
            yield (f"{json_path}/responses",
                   f"POST {path} returns 200; consider 201 Created for "
                   "resource creation")


@openapi_rule(
    "oas.semantics.financial-float", Severity.HINT, category=_SEM, confidence=_H,
    description="Money-like fields should not use binary floating point",
    rationale="IEEE-754 floats cannot represent 0.1 exactly; monetary values "
              "belong in integers of minor units or decimal strings.",
)
def check_financial_float(document: dict[str, Any]) -> Iterator[tuple[str, str]]:
    for name, schema, json_path in iter_component_schemas(document):
        for node, node_path, prop in iter_schemas(document, schema, json_path):
            if not prop:
                continue
            tokens = {t.lower() for t in
                      re.split(r"(?<=[a-z])(?=[A-Z])|[_\-]", prop)}
            if tokens & _MONEY_WORDS and node.get("type") == "number" \
                    and node.get("format") in (None, "float", "double"):
                yield (node_path,
                       f"Money-like field '{prop}' uses floating point; "
                       "consider integer minor units or a decimal string")


_DATE_SUFFIXES = ("at", "date", "time", "timestamp")


@openapi_rule(
    "oas.semantics.lexical-date-format", Severity.HINT, category=_SEM, confidence=_H,
    description="Date-like field names suggest format: date-time",
    rationale="'createdAt' as a bare string invites inconsistent formats; "
              "declare date-time if that is the intent.",
)
def check_lexical_dates(document: dict[str, Any]) -> Iterator[tuple[str, str]]:
    for name, schema, json_path in iter_component_schemas(document):
        for node, node_path, prop in iter_schemas(document, schema, json_path):
            if not prop:
                continue
            tokens = [t.lower() for t in
                      re.split(r"(?<=[a-z0-9])(?=[A-Z])|[_\-]", prop) if t]
            if tokens and tokens[-1] in _DATE_SUFFIXES \
                    and node.get("type") == "string" and not node.get("format") \
                    and not node.get("enum") and not node.get("pattern"):
                yield (node_path,
                       f"Field '{prop}' looks like a date/time but declares "
                       "no format (consider format: date-time)")


@openapi_rule(
    "oas.semantics.lexical-boolean-prefix", Severity.HINT, category=_SEM,
    confidence=_H,
    description="is*/has* field names suggest type: boolean",
    rationale="Boolean-named fields with non-boolean types confuse consumers.",
)
def check_lexical_booleans(document: dict[str, Any]) -> Iterator[tuple[str, str]]:
    for name, schema, json_path in iter_component_schemas(document):
        for node, node_path, prop in iter_schemas(document, schema, json_path):
            if not prop:
                continue
            if re.match(r"^(is|has|can|should)[A-Z_]", prop) \
                    and node.get("type") not in (None, "boolean") \
                    and not node.get("enum"):
                yield (node_path,
                       f"Field '{prop}' is named like a boolean but typed "
                       f"'{node.get('type')}'")


@openapi_rule(
    "oas.semantics.lexical-email-format", Severity.HINT, category=_SEM,
    confidence=_H,
    description="email-named string fields suggest format: email",
    rationale="Declaring format: email unlocks validation for free.",
)
def check_lexical_email(document: dict[str, Any]) -> Iterator[tuple[str, str]]:
    for name, schema, json_path in iter_component_schemas(document):
        for node, node_path, prop in iter_schemas(document, schema, json_path):
            if prop and "email" in prop.lower() and node.get("type") == "string" \
                    and not node.get("format") and not node.get("pattern") \
                    and not node.get("enum"):
                yield (node_path,
                       f"Field '{prop}' looks like an email but declares no "
                       "format (consider format: email)")


@openapi_rule(
    "oas.semantics.cross-schema-type-consistency", Severity.WARNING,
    category=_SEM, confidence=_H,
    description="The same property name should not have divergent types "
                "across schemas",
    rationale="Internal inconsistency is the low-false-positive proxy for a "
              "modelling mistake (DEEPTHINK_06).",
)
def check_cross_schema_consistency(document: dict[str, Any]) -> Iterator[tuple[str, str]]:
    seen: dict[str, tuple[str, str]] = {}
    reported: set[str] = set()
    for name, schema, json_path in iter_component_schemas(document):
        for prop, prop_schema in (schema.get("properties") or {}).items():
            if not isinstance(prop_schema, dict):
                continue
            prop_type = prop_schema.get("type")
            if not isinstance(prop_type, str):
                continue
            key = str(prop)
            if key in seen and seen[key][0] != prop_type and key not in reported:
                reported.add(key)
                yield (f"{json_path}/properties/{escape_pointer(key)}",
                       f"Property '{key}' is '{prop_type}' here but "
                       f"'{seen[key][0]}' in schema '{seen[key][1]}'")
            else:
                seen.setdefault(key, (prop_type, str(name)))


@openapi_rule(
    "oas.semantics.enum-values-match-type", Severity.ERROR, category=_SEM,
    description="Enum values must conform to the declared type",
    rationale="An integer-typed enum containing strings can never validate.",
)
def check_enum_types(document: dict[str, Any]) -> Iterator[tuple[str, str]]:
    type_checks = {
        "string": lambda v: isinstance(v, str),
        "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
        "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
        "boolean": lambda v: isinstance(v, bool),
    }
    for name, schema, json_path in iter_component_schemas(document):
        for node, node_path, prop in iter_schemas(document, schema, json_path):
            declared = node.get("type")
            check = type_checks.get(declared) if isinstance(declared, str) else None
            if not check:
                continue
            for value in node.get("enum") or []:
                if value is not None and not check(value):
                    yield (f"{node_path}/enum",
                           f"Enum value {value!r} does not match declared "
                           f"type '{declared}'")


@openapi_rule(
    "oas.semantics.required-property-defined", Severity.WARNING, category=_SEM,
    description="required entries should exist in properties",
    rationale="A required property that is never defined usually indicates a "
              "typo or an incomplete refactor.",
)
def check_required_defined(document: dict[str, Any]) -> Iterator[tuple[str, str]]:
    for name, schema, json_path in iter_component_schemas(document):
        if schema.get("allOf") or schema.get("anyOf") or schema.get("oneOf"):
            continue  # composition may supply the property elsewhere
        extra = schema.get("additionalProperties")
        if extra not in (False, None):
            continue
        properties = schema.get("properties")
        if not isinstance(properties, dict):
            continue
        for required in schema.get("required") or []:
            if required not in properties:
                yield (f"{json_path}/required",
                       f"Schema '{name}' requires '{required}' but never "
                       "defines it")


@openapi_rule(
    "oas.semantics.default-matches-type", Severity.WARNING, category=_SEM,
    description="Schema defaults must conform to the declared type",
    rationale="A default the schema itself rejects will fail on first use.",
)
def check_default_types(document: dict[str, Any]) -> Iterator[tuple[str, str]]:
    type_checks = {
        "string": lambda v: isinstance(v, str),
        "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
        "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
        "boolean": lambda v: isinstance(v, bool),
        "array": lambda v: isinstance(v, list),
        "object": lambda v: isinstance(v, dict),
    }
    for name, schema, json_path in iter_component_schemas(document):
        for node, node_path, prop in iter_schemas(document, schema, json_path):
            declared = node.get("type")
            check = type_checks.get(declared) if isinstance(declared, str) else None
            if not check or "default" not in node:
                continue
            default: Optional[Any] = node.get("default")
            if default is not None and not check(default) \
                    and not (node.get("nullable") and default is None):
                yield (node_path,
                       f"Default {default!r} does not match declared type "
                       f"'{declared}'")
