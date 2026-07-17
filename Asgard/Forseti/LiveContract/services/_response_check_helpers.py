"""
Response Check Helpers - status/schema conformance checks for drift findings.

Uses the compiled JSON Schema engine (plan 05) for body validation so
drift detection benefits from the same dialect-aware, cached compiler
used everywhere else in Forseti.
"""

from typing import Any, Optional

from Asgard.Forseti.JSONSchema.services.schema_compiler_service import (
    SchemaCompilerService,
)
from Asgard.Forseti.LiveContract.models.live_contract_models import ProbeOperation
from Asgard.Forseti.Reporting.models.finding_models import Coordinates, Finding
from Asgard.Forseti.Rules.models._rule_base_models import RuleCategory, SchemaFormat, Severity

_compiler = SchemaCompilerService()


def check_response(
    operation: ProbeOperation, status_code: Optional[int], body: Any
) -> list[Finding]:
    """Compare an observed (status, body) against the operation's documented responses."""
    findings: list[Finding] = []
    if status_code is None:
        return findings

    status_str = str(status_code)
    documented = operation.responses.get(status_str) or operation.responses.get("default")

    if status_str not in operation.responses and "default" not in operation.responses:
        findings.append(
            Finding(
                rule_id="drift.undocumented-status",
                severity=Severity.ERROR,
                message=(
                    f"{operation.method} {operation.path} returned status {status_code}, "
                    "which is not documented in the spec"
                ),
                coordinates=Coordinates(json_path=f"/paths{operation.path}/{operation.method.lower()}/responses"),
                category=RuleCategory.COMPATIBILITY,
                format=SchemaFormat.OPENAPI,
            )
        )
        return findings

    if documented is None:
        return findings

    result = _compiler.validate(body, documented)
    if not result.is_valid:
        detail = "; ".join(e.message for e in result.errors[:3]) if result.errors else "schema mismatch"
        findings.append(
            Finding(
                rule_id="drift.schema-mismatch",
                severity=Severity.ERROR,
                message=(
                    f"{operation.method} {operation.path} response body does not match "
                    f"the documented {status_code} schema: {detail}"
                ),
                coordinates=Coordinates(json_path=f"/paths{operation.path}/{operation.method.lower()}/responses/{status_str}"),
                category=RuleCategory.COMPATIBILITY,
                format=SchemaFormat.OPENAPI,
            )
        )
    return findings


def check_negative_expectation(
    operation: ProbeOperation, status_code: Optional[int]
) -> list[Finding]:
    """CATS-style negative pass: mutated/invalid input must not be accepted as 2xx."""
    if status_code is None:
        return []
    if 200 <= status_code < 300:
        return [
            Finding(
                rule_id="negative.expected-4xx",
                severity=Severity.ERROR,
                message=(
                    f"{operation.method} {operation.path} accepted an invalid (mutated) "
                    f"request with status {status_code}; expected 4xx"
                ),
                coordinates=Coordinates(json_path=f"/paths{operation.path}/{operation.method.lower()}"),
                category=RuleCategory.SECURITY,
                format=SchemaFormat.OPENAPI,
            )
        ]
    if status_code >= 500:
        return [
            Finding(
                rule_id="negative.server-error",
                severity=Severity.ERROR,
                message=(
                    f"{operation.method} {operation.path} raised a server error "
                    f"({status_code}) on invalid input; expected a handled 4xx"
                ),
                coordinates=Coordinates(json_path=f"/paths{operation.path}/{operation.method.lower()}"),
                category=RuleCategory.SECURITY,
                format=SchemaFormat.OPENAPI,
            )
        ]
    return []
