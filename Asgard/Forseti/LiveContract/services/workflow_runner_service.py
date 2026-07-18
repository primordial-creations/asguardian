"""
Workflow Runner Service - Arazzo-lite multi-step execution (plan 06-C).

Executes a minimal workflow YAML (`steps: [{operationId, extract, expect}]`)
against a live base URL, resolving each step's `operationId` against the
OpenAPI spec and threading `extract`-ed values into later steps via a
`{{name}}` template substitution in `parameters`/`body`. Forward-compatible
subset of Arazzo step semantics - not a full Arazzo implementation.

Cost: NETWORK. Only reached via the explicit `forseti contract workflow`
CLI command, mirroring `LiveValidatorService`'s opt-in posture. Stdlib
`urllib` only.
"""

import json
import re
import ssl
import urllib.error
import urllib.request
from typing import Any, Optional

from Asgard.Forseti.LiveContract.models.live_contract_models import (
    ProbeConfig,
    ProbeOperation,
    Workflow,
    WorkflowReport,
    WorkflowStep,
    WorkflowStepResult,
)
from Asgard.Forseti.LiveContract.services._dependency_helpers import extract_operations
from Asgard.Forseti.Reporting.models.finding_models import Coordinates, Finding
from Asgard.Forseti.Rules.models._rule_base_models import RuleCategory, SchemaFormat, Severity

_TEMPLATE_RE = re.compile(r"\{\{\s*([A-Za-z0-9_.]+)\s*\}\}")


def _extract_jsonpath(expr: str, status_code: Optional[int], body: Any) -> Any:
    """Minimal JSONPath subset: `$.status`, `$.body.<dotted.path>`."""
    if expr == "$.status":
        return status_code
    if expr.startswith("$.body."):
        current: Any = body
        for part in expr[len("$.body."):].split("."):
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None
        return current
    return None


def _substitute(value: Any, context: dict[str, Any]) -> Any:
    """Recursively replace `{{name}}` placeholders using `context` values."""
    if isinstance(value, str):
        match = _TEMPLATE_RE.fullmatch(value.strip())
        if match:
            return context.get(match.group(1), value)
        return _TEMPLATE_RE.sub(lambda m: str(context.get(m.group(1), m.group(0))), value)
    if isinstance(value, dict):
        return {k: _substitute(v, context) for k, v in value.items()}
    if isinstance(value, list):
        return [_substitute(v, context) for v in value]
    return value


class WorkflowRunnerService:
    """Executes a `Workflow` against `ProbeConfig.base_url`, step by step."""

    def __init__(self, openapi_doc: dict[str, Any], config: ProbeConfig):
        self.config = config
        self.operations: dict[str, ProbeOperation] = {
            op.operation_id: op for op in extract_operations(openapi_doc)
        }
        self.context: dict[str, Any] = {}

    def run(self, workflow: Workflow) -> WorkflowReport:
        report = WorkflowReport(base_url=self.config.base_url)
        for step in workflow.steps:
            result = self._execute_step(step)
            report.steps.append(result)
            report.findings.extend(result.findings)
            self.context.update(result.extracted)
        return report

    def _execute_step(self, step: WorkflowStep) -> WorkflowStepResult:
        operation = self.operations.get(step.operation_id)
        if operation is None:
            return WorkflowStepResult(
                operation_id=step.operation_id,
                error=f"operationId '{step.operation_id}' not found in spec",
                findings=[
                    Finding(
                        rule_id="workflow.unknown-operation",
                        severity=Severity.ERROR,
                        message=f"Workflow step references unknown operationId '{step.operation_id}'",
                        coordinates=Coordinates(json_path="/steps"),
                        category=RuleCategory.COMPATIBILITY,
                        format=SchemaFormat.OPENAPI,
                    )
                ],
            )

        params = _substitute(step.parameters, self.context)
        path = operation.path
        for name, value in params.items():
            path = path.replace("{" + name + "}", str(value))
        for param in operation.path_params:
            placeholder = "{" + param + "}"
            if placeholder in path:
                path = path.replace(placeholder, str(self.context.get(param, "")))

        url = self.config.base_url.rstrip("/") + path
        body = _substitute(step.body, self.context) if step.body is not None else None

        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.config.auth_header and ":" in self.config.auth_header:
            key, value = self.config.auth_header.split(":", 1)
            headers[key.strip()] = value.strip()

        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(url, data=data, headers=headers, method=operation.method)

        ctx = None
        if not self.config.verify_tls:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout_s, context=ctx) as resp:
                status = resp.getcode()
                raw = resp.read()
        except urllib.error.HTTPError as exc:
            status = exc.code
            raw = exc.read()
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            return WorkflowStepResult(operation_id=step.operation_id, error=str(exc))

        parsed_body: Any = None
        if raw:
            try:
                parsed_body = json.loads(raw)
            except (json.JSONDecodeError, UnicodeDecodeError):
                parsed_body = None

        findings: list[Finding] = []
        expected_status = step.expect.get("status") if step.expect else None
        if expected_status is not None and status != expected_status:
            findings.append(
                Finding(
                    rule_id="workflow.unexpected-status",
                    severity=Severity.ERROR,
                    message=(
                        f"Step '{step.operation_id}' expected status {expected_status}, got {status}"
                    ),
                    coordinates=Coordinates(json_path=f"/steps/{step.operation_id}"),
                    category=RuleCategory.COMPATIBILITY,
                    format=SchemaFormat.OPENAPI,
                )
            )

        extracted = {
            name: _extract_jsonpath(expr, status, parsed_body) for name, expr in step.extract.items()
        }

        return WorkflowStepResult(
            operation_id=step.operation_id,
            status_code=status,
            extracted=extracted,
            findings=findings,
        )
