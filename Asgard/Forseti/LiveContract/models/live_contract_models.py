"""
LiveContract Models - ProbeConfig, ProbePlan, ProbeResult, DriftReport.

Pure data models; no I/O. `ProbeOperation` captures the RESTler-style
producer/consumer facts (RESEARCH_15) that `_dependency_helpers` uses to
topologically order requests: which fields a 2xx response *produces*
(usually `*id`) and which path/body fields a request *consumes*.
"""

from typing import Any, Optional

from pydantic import BaseModel, Field

from Asgard.Forseti.Reporting.models.finding_models import Finding


class ProbeConfig(BaseModel):
    """Configuration for a live probe run. Never constructed implicitly."""

    base_url: str = Field(description="Base URL of the live implementation under test")
    auth_header: Optional[str] = Field(default=None, description="Raw 'Header: value' string")
    max_requests: int = Field(default=50, description="Hard cap on requests issued")
    negative: bool = Field(default=False, description="Enable CATS-style negative pass")
    timeout_s: float = Field(default=5.0, description="Per-request socket timeout")
    verify_tls: bool = Field(default=True, description="Verify TLS certificates")


class ProbeOperation(BaseModel):
    """One spec operation with its dependency-relevant facts."""

    operation_id: str
    method: str
    path: str
    path_params: list[str] = Field(default_factory=list)
    required_body_fields: list[str] = Field(default_factory=list)
    produced_fields: list[str] = Field(
        default_factory=list,
        description="Field names present in a 2xx response body (candidate producers)",
    )
    request_body_schema: Optional[dict[str, Any]] = Field(default=None)
    responses: dict[str, dict[str, Any]] = Field(
        default_factory=dict,
        description="status code (as string, may be 'default') -> response schema",
    )


class ProbePlan(BaseModel):
    """Topologically ordered operations plus the edges that drove the order."""

    operations: list[ProbeOperation] = Field(default_factory=list)
    ignored_cycle_edges: list[tuple[str, str]] = Field(
        default_factory=list,
        description="(producer_op_id, consumer_op_id) edges dropped to break a cycle",
    )


class ProbeResult(BaseModel):
    """Outcome of executing one operation against the live base URL."""

    operation_id: str
    method: str
    path: str
    request_url: str
    status_code: Optional[int] = None
    error: Optional[str] = Field(default=None, description="Transport-level error, if any")
    body: Any = None
    findings: list[Finding] = Field(default_factory=list)


class WorkflowStep(BaseModel):
    """One Arazzo-lite workflow step (plan 06-C): forward-compatible subset of
    Arazzo step semantics - `operationId` + optional `parameters`/`body`
    overrides, `extract` (name -> minimal JSONPath: `$.status`,
    `$.body.<dotted.path>`), and `expect` (`{status: <int>}`)."""

    operation_id: str = Field(alias="operationId")
    parameters: dict[str, Any] = Field(default_factory=dict)
    body: Optional[dict[str, Any]] = Field(default=None)
    extract: dict[str, str] = Field(default_factory=dict)
    expect: dict[str, Any] = Field(default_factory=dict)

    class Config:
        populate_by_name = True


class Workflow(BaseModel):
    """A minimal Arazzo-lite workflow: an ordered list of steps."""

    steps: list[WorkflowStep] = Field(default_factory=list)


class WorkflowStepResult(BaseModel):
    """Outcome of one executed workflow step."""

    operation_id: str
    status_code: Optional[int] = None
    error: Optional[str] = None
    extracted: dict[str, Any] = Field(default_factory=dict)
    findings: list[Finding] = Field(default_factory=list)


class WorkflowReport(BaseModel):
    """Aggregate result of running a workflow end-to-end."""

    base_url: str
    steps: list[WorkflowStepResult] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        from Asgard.Forseti.Rules.models._rule_base_models import Severity

        return any(f.severity == Severity.ERROR for f in self.findings)


class DriftReport(BaseModel):
    """Aggregate drift report across a probe run."""

    base_url: str
    results: list[ProbeResult] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    operations_attempted: int = 0
    operations_succeeded: int = 0

    @property
    def has_errors(self) -> bool:
        """Whether any finding is ERROR severity (drives exit code 1)."""
        from Asgard.Forseti.Rules.models._rule_base_models import Severity

        return any(f.severity == Severity.ERROR for f in self.findings)
