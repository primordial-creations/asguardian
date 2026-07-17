"""
Finding Adapter Service - convert legacy validator error models to Findings.

Every pre-registry validator error (OpenAPIValidationError,
GraphQLValidationError, AvroValidationError, ProtobufValidationError,
AsyncAPIValidationError, JSONSchemaValidationError, BreakingChange...)
is duck-typed on `path` / `message` / `severity` / `rule`. Rule ids and
fixed severities come from the registry when the legacy rule string is
known; otherwise a namespaced id is synthesized so ids stay stable.
"""

from typing import Any, Optional, Sequence

from Asgard.Forseti.Reporting.models.finding_models import Coordinates, Finding
from Asgard.Forseti.Rules.models._rule_base_models import (
    RuleCategory,
    SchemaFormat,
    Severity,
)

_FORMAT_PREFIXES = {
    SchemaFormat.OPENAPI: "oas",
    SchemaFormat.ASYNCAPI: "asyncapi",
    SchemaFormat.GRAPHQL: "gql",
    SchemaFormat.JSONSCHEMA: "jsonschema",
    SchemaFormat.AVRO: "avro",
    SchemaFormat.PROTOBUF: "proto",
    SchemaFormat.SQL: "sql",
    SchemaFormat.CONTRACT: "contract",
}


def _coerce_severity(raw: Any) -> Severity:
    value = str(getattr(raw, "value", raw) or "error").lower()
    try:
        return Severity(value)
    except ValueError:
        return Severity.ERROR


def legacy_error_to_finding(
    error: Any,
    fmt: SchemaFormat,
    file: Optional[str] = None,
) -> Finding:
    """Convert one legacy error object to a canonical Finding."""
    from Asgard.Forseti.Rules.services.rule_registry_service import get_default_registry

    legacy_rule = getattr(error, "rule", None) or getattr(error, "constraint", None)
    severity = _coerce_severity(getattr(error, "severity", "error"))
    category = RuleCategory.STRUCTURE
    rationale = None
    registered = get_default_registry().resolve_legacy(fmt, legacy_rule) if legacy_rule else None
    if registered is not None:
        rule_id = registered.meta.rule_id
        severity = registered.meta.severity
        category = registered.meta.category
        rationale = registered.meta.rationale or None
    else:
        prefix = _FORMAT_PREFIXES[fmt]
        rule_id = f"{prefix}.{legacy_rule}" if legacy_rule else f"{prefix}.generic"
    path = getattr(error, "path", None) or getattr(error, "location", None) or "/"
    return Finding(
        rule_id=rule_id,
        severity=severity,
        message=getattr(error, "message", str(error)),
        coordinates=Coordinates(file=file, json_path=str(path)),
        rationale=rationale,
        category=category,
        format=fmt,
    )


def legacy_errors_to_findings(
    errors: Sequence[Any],
    fmt: SchemaFormat,
    file: Optional[str] = None,
) -> list[Finding]:
    """Convert a sequence of legacy error objects to Findings."""
    return [legacy_error_to_finding(error, fmt, file) for error in errors]


def result_to_findings(
    result: Any,
    fmt: SchemaFormat,
    file: Optional[str] = None,
) -> list[Finding]:
    """
    Convert a legacy result model (errors/warnings/info_messages lists)
    into a unified Finding list.
    """
    findings: list[Finding] = []
    for attr in ("errors", "warnings", "info_messages", "breaking_changes"):
        findings.extend(
            legacy_errors_to_findings(getattr(result, attr, None) or [], fmt, file)
        )
    return findings
