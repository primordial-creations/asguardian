"""
OpenAPI Static Security Rules - OWASP API Security Top 10 (2023) mapping
(plan 03 Phase 3, RESEARCH_16).

All rules are statically decidable from the spec. Heuristic rules
(pagination, sequential ids, verbose errors) are never ERROR.
"""

import re
from typing import Any, Iterator

from Asgard.Forseti.OpenAPI.rules._rule_helpers import (
    escape_pointer,
    iter_operations,
    iter_request_schemas,
    iter_schemas,
    iter_security_schemes,
    openapi_rule,
)
from Asgard.Forseti.OpenAPI.utilities._openapi_spec_utils import deref_node
from Asgard.Forseti.Rules.models._rule_base_models import (
    Confidence,
    RuleCategory,
    Severity,
)

_SEC = RuleCategory.SECURITY
_H = Confidence.HEURISTIC


@openapi_rule(
    "sec.auth.scheme-defined", Severity.WARNING, category=_SEC,
    description="A security scheme must be defined and applied (OWASP API2)",
    rationale="Without declared security schemes, consumers cannot know the "
              "API is authenticated at all — the classic broken-auth setup.",
)
def check_scheme_defined(document: dict[str, Any]) -> Iterator[tuple[str, str]]:
    schemes = list(iter_security_schemes(document))
    if not schemes:
        yield ("/components/securitySchemes",
               "No security schemes defined (components.securitySchemes is empty)")
        return
    global_security = document.get("security")
    for path, method, operation, json_path in iter_operations(document):
        security = operation.get("security", global_security)
        if not security:  # None, [] — no requirement covers this operation
            yield (json_path,
                   f"Operation {method.upper()} {path} is not covered by any "
                   "security requirement")


@openapi_rule(
    "sec.auth.no-http-basic", Severity.WARNING, category=_SEC,
    description="HTTP Basic authentication must not be used (OWASP API2)",
    rationale="Basic auth transmits static credentials on every request and "
              "has no revocation or scoping story.",
)
def check_no_http_basic(document: dict[str, Any]) -> Iterator[tuple[str, str]]:
    for name, scheme, json_path in iter_security_schemes(document):
        if str(scheme.get("type", "")).lower() in ("http", "basic") and \
                (str(scheme.get("scheme", "")).lower() == "basic"
                 or str(scheme.get("type", "")).lower() == "basic"):
            yield json_path, f"Security scheme '{name}' uses HTTP Basic authentication"


@openapi_rule(
    "sec.auth.no-apikey-in-query", Severity.WARNING, category=_SEC,
    description="API keys must not be passed in the query string (OWASP API2)",
    rationale="Query strings leak into server logs, browser history, "
              "referrers and proxies.",
)
def check_no_apikey_in_query(document: dict[str, Any]) -> Iterator[tuple[str, str]]:
    for name, scheme, json_path in iter_security_schemes(document):
        if str(scheme.get("type", "")).lower() == "apikey" \
                and str(scheme.get("in", "")).lower() == "query":
            yield json_path, f"API key scheme '{name}' is transmitted in the query string"


_LOCALHOST_RE = re.compile(r"^(https?://)?(localhost|127\.0\.0\.1|\[::1\]|0\.0\.0\.0)([:/]|$)")


@openapi_rule(
    "sec.transport.https-only", Severity.WARNING, category=_SEC,
    description="Server URLs must use https (OWASP API8; localhost exempt)",
    rationale="Plain-http servers expose credentials and payloads to "
              "on-path attackers.",
)
def check_https_only(document: dict[str, Any]) -> Iterator[tuple[str, str]]:
    for index, server in enumerate(document.get("servers") or []):
        if not isinstance(server, dict):
            continue
        url = str(server.get("url", ""))
        if url.startswith("http://") and not _LOCALHOST_RE.match(url):
            yield f"/servers/{index}/url", f"Server URL is not HTTPS: {url}"
    for scheme in document.get("schemes") or []:  # Swagger 2.0
        if scheme == "http":
            yield "/schemes", "Swagger 2.0 schemes allow plain http"


@openapi_rule(
    "sec.bopla.additional-properties", Severity.WARNING, category=_SEC,
    description="Request-body objects should set additionalProperties: false "
                "(OWASP API3)",
    rationale="Mass-assignment / BOPLA: unless extra properties are rejected, "
              "clients can smuggle fields the handler never expected. "
              "Suppressible for intentionally open payloads (webhooks).",
)
def check_bopla(document: dict[str, Any]) -> Iterator[tuple[str, str]]:
    reported: set[str] = set()
    for node, node_path, prop, label in iter_request_schemas(document):
        if node.get("type") == "object" or "properties" in node:
            if node.get("additionalProperties") is None \
                    and not (node.get("allOf") or node.get("oneOf")
                             or node.get("anyOf")) \
                    and node_path not in reported:
                reported.add(node_path)
                yield (node_path,
                       f"Request object in {label} does not set "
                       "additionalProperties: false")


@openapi_rule(
    "sec.dos.bounded-strings", Severity.WARNING, category=_SEC,
    description="Request strings should declare maxLength (OWASP API4)",
    rationale="Unbounded strings invite memory-exhaustion and storage abuse.",
)
def check_bounded_strings(document: dict[str, Any]) -> Iterator[tuple[str, str]]:
    for node, node_path, prop, label in iter_request_schemas(document):
        if node.get("type") == "string" and not node.get("enum") \
                and node.get("maxLength") is None and not node.get("format") \
                and not node.get("pattern"):
            yield (node_path,
                   f"Request string {('field ' + repr(prop) + ' ') if prop else ''}"
                   f"in {label} has no maxLength")


@openapi_rule(
    "sec.dos.bounded-arrays", Severity.WARNING, category=_SEC,
    description="Request arrays should declare maxItems (OWASP API4)",
    rationale="Unbounded arrays allow a single request to exhaust the worker.",
)
def check_bounded_arrays(document: dict[str, Any]) -> Iterator[tuple[str, str]]:
    for node, node_path, prop, label in iter_request_schemas(document):
        if node.get("type") == "array" and node.get("maxItems") is None:
            yield (node_path,
                   f"Request array {('field ' + repr(prop) + ' ') if prop else ''}"
                   f"in {label} has no maxItems")


@openapi_rule(
    "sec.dos.bounded-integers", Severity.INFO, category=_SEC,
    description="Request integers should declare minimum/maximum (OWASP API4)",
    rationale="Bounds stop pathological values (page_size=10**9) at the edge.",
)
def check_bounded_integers(document: dict[str, Any]) -> Iterator[tuple[str, str]]:
    for node, node_path, prop, label in iter_request_schemas(document):
        if node.get("type") in ("integer", "number") and not node.get("enum") \
                and node.get("maximum") is None and node.get("minimum") is None \
                and node.get("exclusiveMaximum") is None:
            yield (node_path,
                   f"Request number {('field ' + repr(prop) + ' ') if prop else ''}"
                   f"in {label} declares no bounds")


_PAGINATION_PARAMS = {"limit", "page", "pagesize", "page_size", "per_page",
                      "perpage", "cursor", "offset", "after", "before",
                      "next", "top", "skip", "maxresults", "max_results",
                      "pagetoken", "page_token"}


@openapi_rule(
    "sec.dos.pagination-required", Severity.WARNING, category=_SEC, confidence=_H,
    description="Array-returning GET operations should support pagination "
                "(OWASP API4)",
    rationale="Unpaginated collection endpoints degrade linearly with data "
              "growth until they time out or OOM.",
)
def check_pagination(document: dict[str, Any]) -> Iterator[tuple[str, str]]:
    for path, method, operation, json_path in iter_operations(document):
        if method != "get":
            continue
        returns_array = False
        for status, response in (operation.get("responses") or {}).items():
            if str(status)[:1] != "2":
                continue
            resolved = deref_node(document, response)
            if not isinstance(resolved, dict):
                continue
            for media_obj in (resolved.get("content") or {}).values():
                if not isinstance(media_obj, dict):
                    continue
                schema = deref_node(document, media_obj.get("schema"))
                if isinstance(schema, dict) and schema.get("type") == "array":
                    returns_array = True
        if not returns_array:
            continue
        param_names = set()
        for param in operation.get("parameters") or []:
            resolved = deref_node(document, param)
            if isinstance(resolved, dict):
                param_names.add(str(resolved.get("name", "")).lower())
        if not param_names & _PAGINATION_PARAMS:
            yield (json_path,
                   f"GET {path} returns an array but defines no pagination "
                   "parameters (limit/cursor/offset)")


@openapi_rule(
    "sec.bola.uuid-ids", Severity.WARNING, category=_SEC, confidence=_H,
    description="Integer path ids invite enumeration; prefer UUIDs (OWASP API1)",
    rationale="Sequential integer object ids make BOLA scanning trivial; "
              "opaque UUIDs raise the cost of enumeration. Heuristic — never "
              "blocking.",
)
def check_uuid_ids(document: dict[str, Any]) -> Iterator[tuple[str, str]]:
    for path, method, operation, json_path in iter_operations(document):
        for index, param in enumerate(operation.get("parameters") or []):
            resolved = deref_node(document, param)
            if not isinstance(resolved, dict) or resolved.get("in") != "path":
                continue
            name = str(resolved.get("name", ""))
            schema = resolved.get("schema") or {}
            declared = schema.get("type") or resolved.get("type")
            if name.lower().endswith("id") and declared == "integer":
                yield (f"{json_path}/parameters/{index}",
                       f"Path parameter '{name}' on {method.upper()} {path} "
                       "is a sequential integer id; consider UUIDs")


_VERBOSE_FIELDS = {"stack", "stacktrace", "stack_trace", "trace",
                   "traceback", "exception", "debug"}


@openapi_rule(
    "sec.info.no-verbose-errors", Severity.WARNING, category=_SEC, confidence=_H,
    description="5xx response schemas should not expose stack traces "
                "(OWASP API8)",
    rationale="Stack traces in error payloads leak framework versions, "
              "paths and query text to attackers.",
)
def check_verbose_errors(document: dict[str, Any]) -> Iterator[tuple[str, str]]:
    for path, method, operation, json_path in iter_operations(document):
        for status, response in (operation.get("responses") or {}).items():
            if str(status)[:1] != "5" and str(status) != "default":
                continue
            resolved = deref_node(document, response)
            if not isinstance(resolved, dict):
                continue
            for media, media_obj in (resolved.get("content") or {}).items():
                if not isinstance(media_obj, dict):
                    continue
                schema = media_obj.get("schema")
                if not isinstance(schema, dict):
                    continue
                base = (f"{json_path}/responses/{escape_pointer(str(status))}"
                        f"/content/{escape_pointer(media)}/schema")
                for node, node_path, prop in iter_schemas(
                    document, schema, base, follow_refs=True
                ):
                    if prop and prop.lower().replace("-", "_") in _VERBOSE_FIELDS:
                        yield (node_path,
                               f"Error schema of {method.upper()} {path} "
                               f"({status}) exposes '{prop}'")
