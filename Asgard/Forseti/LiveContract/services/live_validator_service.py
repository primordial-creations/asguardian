"""
Live Validator Service - executes a ProbePlan against a live base URL.

Cost: NETWORK. This is the ONLY code path in Forseti that opens a socket
to probe a live implementation, and it is only reached when a caller
explicitly constructs a `ProbeConfig` with a `base_url` and calls `run()`
(CLI: `forseti contract test <spec> --base-url ...`, never on by default).
Uses stdlib `urllib` only - no new dependency.
"""

import json
import ssl
import urllib.error
import urllib.request
from typing import Any, Optional

from Asgard.Forseti.LiveContract.models.live_contract_models import (
    DriftReport,
    ProbeConfig,
    ProbeOperation,
    ProbePlan,
    ProbeResult,
)
from Asgard.Forseti.LiveContract.services._response_check_helpers import (
    check_negative_expectation,
    check_response,
)
from Asgard.Forseti.MockServer.services.mock_data_generator import MockDataGeneratorService


class LiveValidatorService:
    """Executes a `ProbePlan` against `ProbeConfig.base_url` and reports drift."""

    def __init__(self, config: ProbeConfig, generator: Optional[MockDataGeneratorService] = None):
        self.config = config
        self._generator = generator or MockDataGeneratorService()
        self._values: dict[str, Any] = {}

    def run(self, plan: ProbePlan) -> DriftReport:
        """Execute the plan's operations in order; returns the aggregate DriftReport."""
        report = DriftReport(base_url=self.config.base_url)
        for operation in plan.operations[: self.config.max_requests]:
            result = self._execute(operation, negative=False)
            report.results.append(result)
            report.findings.extend(result.findings)
            report.operations_attempted += 1
            if result.error is None:
                report.operations_succeeded += 1
                self._record_produced_values(operation, result.body)

            if self.config.negative:
                neg_result = self._execute(operation, negative=True)
                report.results.append(neg_result)
                report.findings.extend(neg_result.findings)
        return report

    def _execute(self, operation: ProbeOperation, negative: bool) -> ProbeResult:
        path = self._resolve_path(operation)
        url = self.config.base_url.rstrip("/") + path
        body = self._build_body(operation, negative=negative)

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
            return ProbeResult(
                operation_id=operation.operation_id,
                method=operation.method,
                path=path,
                request_url=url,
                error=str(exc),
            )

        parsed_body: Any = None
        if raw:
            try:
                parsed_body = json.loads(raw)
            except (json.JSONDecodeError, UnicodeDecodeError):
                parsed_body = None

        if negative:
            findings = check_negative_expectation(operation, status)
        else:
            findings = check_response(operation, status, parsed_body)

        return ProbeResult(
            operation_id=operation.operation_id,
            method=operation.method,
            path=path,
            request_url=url,
            status_code=status,
            body=parsed_body,
            findings=findings,
        )

    def _resolve_path(self, operation: ProbeOperation) -> str:
        path = operation.path
        for param in operation.path_params:
            key = self._value_key(param)
            value = self._values.get(key)
            if value is None:
                value = self._generator.generate_value(_guess_data_type(param))
            path = path.replace("{" + param + "}", str(value))
        return path

    def _build_body(self, operation: ProbeOperation, negative: bool) -> Optional[dict[str, Any]]:
        if not operation.request_body_schema:
            return None
        result = self._generator.generate_from_schema(operation.request_body_schema)
        body = result.data
        if negative and isinstance(body, dict) and operation.required_body_fields:
            # CATS-style single mutation: drop one required field.
            mutated = dict(body)
            mutated.pop(operation.required_body_fields[0], None)
            return mutated
        return body if isinstance(body, dict) else None

    def _record_produced_values(self, operation: ProbeOperation, body: Any) -> None:
        if not isinstance(body, dict):
            return
        for field in operation.produced_fields:
            if field in body:
                self._values[self._value_key(field)] = body[field]

    @staticmethod
    def _value_key(name: str) -> str:
        lowered = name.lower()
        return "id" if lowered.endswith("id") and lowered != "id" or lowered == "id" else lowered


def _guess_data_type(param_name: str):
    from Asgard.Forseti.MockServer.models.mock_models import DataType

    lowered = param_name.lower()
    if lowered.endswith("id") or lowered == "id":
        return DataType.STRING
    return DataType.STRING
