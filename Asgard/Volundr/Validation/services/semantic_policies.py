"""
Tier 4 — default-deny semantic policy packs over the canonical model.

Policy style (enforced):
- Assert the PRESENCE of safety (``runAsNonRoot is True``), never the
  absence of danger — unknown/new values fail closed.
- Every rule yields gracefully on ``<computed>``/``<tainted>`` values per
  its declared UnknownValueBehavior: never a hard failure it cannot
  justify, never a silent pass (default-deny).
"""

from typing import Any, List, Optional

from Asgard.Volundr.Validation.models.canonical_models import (
    CanonicalComposeService,
    CanonicalPipelineJob,
    CanonicalWorkload,
    is_unknown,
)
from Asgard.Volundr.Validation.models.rule_registry import (
    RuleRegistry,
    UnknownValueBehavior,
    default_registry,
)
from Asgard.Volundr.Validation.models.validation_models import (
    ValidationResult,
    ValidationSeverity,
)


class PolicyEngine:
    """Runs the default-deny policy packs against canonical models."""

    def __init__(self, registry: Optional[RuleRegistry] = None):
        self.registry = registry or default_registry()

    # -- shared result construction ------------------------------------

    def _finding(
        self,
        rule_id: str,
        message: str,
        target: str,
        value: Any = None,
        tainted: bool = False,
        file_path: Optional[str] = None,
        resource_kind: Optional[str] = None,
        resource_name: Optional[str] = None,
        line_number: Optional[int] = None,
        suggestion: Optional[str] = None,
    ) -> Optional[ValidationResult]:
        rule = self.registry.get(rule_id)
        if rule is None or not rule.enabled:
            return None
        severity = rule.severity.to_validation_severity()
        unknown = is_unknown(value) or tainted
        if unknown:
            behavior = rule.on_tainted if tainted else rule.on_computed
            if behavior == UnknownValueBehavior.SKIP:
                return None
            # WARN / CONDITIONAL_ASSERT: soften to warning, never fail-open.
            severity = ValidationSeverity.WARNING
            message += " (value unknown at validation time — verify manually)"
        return ValidationResult(
            rule_id=rule_id,
            message=message,
            severity=severity,
            category=rule.category,
            file_path=file_path,
            line_number=line_number,
            resource_kind=resource_kind,
            resource_name=resource_name,
            suggestion=suggestion or rule.remediation or None,
            context={"target": target, "tainted": tainted},
        )

    # -- Kubernetes ------------------------------------------------------

    def check_workload(self, workload: CanonicalWorkload) -> List[ValidationResult]:
        results: List[ValidationResult] = []
        common = {
            "file_path": workload.file_path,
            "resource_kind": workload.kind,
            "resource_name": workload.name,
        }

        def add(finding: Optional[ValidationResult]) -> None:
            if finding is not None:
                results.append(finding)

        # Pod-level: host namespaces must be provably absent/false.
        for field, label in (
            (workload.host_network, "hostNetwork"),
            (workload.host_pid, "hostPID"),
            (workload.host_ipc, "hostIPC"),
        ):
            if field is True or is_unknown(field):
                add(self._finding(
                    "VOL-K8S-0010",
                    f"{workload.kind} '{workload.name}' shares a host namespace ({label})",
                    target=workload.name, value=field,
                    tainted=workload.tainted and is_unknown(field), **common,
                ))

        if workload.automount_service_account_token is not False:
            add(self._finding(
                "VOL-K8S-0008",
                f"{workload.kind} '{workload.name}' does not set "
                "automountServiceAccountToken: false",
                target=workload.name,
                value=workload.automount_service_account_token,
                tainted=workload.tainted
                and is_unknown(workload.automount_service_account_token),
                **common,
            ))

        for container in workload.containers:
            target = container.name
            line = container.line_number

            def cadd(rule_id: str, message: str, value: Any) -> None:
                add(self._finding(
                    rule_id, message, target=target, value=value,
                    tainted=container.tainted and is_unknown(value),
                    line_number=line, **common,
                ))

            if container.run_as_non_root is not True:
                cadd("VOL-K8S-0001",
                     f"Container '{target}' does not assert runAsNonRoot: true",
                     container.run_as_non_root)
            if container.privileged is True or is_unknown(container.privileged):
                cadd("VOL-K8S-0009",
                     f"Container '{target}' runs privileged",
                     container.privileged)
            if container.allow_privilege_escalation is not False:
                cadd("VOL-K8S-0002",
                     f"Container '{target}' does not assert "
                     "allowPrivilegeEscalation: false",
                     container.allow_privilege_escalation)
            if container.read_only_root_filesystem is not True:
                cadd("VOL-K8S-0004",
                     f"Container '{target}' does not assert "
                     "readOnlyRootFilesystem: true",
                     container.read_only_root_filesystem)

            drops = container.capabilities_drop
            has_drop_all = (
                isinstance(drops, list)
                and any(str(d).upper() == "ALL" for d in drops)
            )
            if not has_drop_all:
                cadd("VOL-K8S-0003",
                     f"Container '{target}' does not drop ALL capabilities",
                     drops)

            seccomp = container.seccomp_profile_type
            if seccomp not in ("RuntimeDefault", "Localhost"):
                cadd("VOL-K8S-0007",
                     f"Container '{target}' has no RuntimeDefault seccompProfile",
                     seccomp)

            image = container.image
            if isinstance(image, str):
                pinned = "@sha256:" in image or (
                    ":" in image.rsplit("/", 1)[-1]
                    and not image.endswith(":latest")
                )
                if not pinned:
                    cadd("VOL-K8S-0005",
                         f"Container '{target}' image is not pinned: {image}",
                         image)
            elif image is None or is_unknown(image):
                cadd("VOL-K8S-0005",
                     f"Container '{target}' image is not pinned", image)

            if not (container.has_resource_limits and container.has_resource_requests):
                cadd("VOL-K8S-0006",
                     f"Container '{target}' is missing resource limits and/or requests",
                     container.has_resource_limits)

        return results

    # -- Compose ---------------------------------------------------------

    def check_compose_service(
        self, service: CanonicalComposeService, file_path: Optional[str] = None
    ) -> List[ValidationResult]:
        results: List[ValidationResult] = []
        target = service.name

        def add(finding: Optional[ValidationResult]) -> None:
            if finding is not None:
                results.append(finding)

        if service.privileged is True or is_unknown(service.privileged):
            add(self._finding(
                "VOL-COMPOSE-0002",
                f"Service '{target}' sets privileged",
                target=target, value=service.privileged, file_path=file_path,
                resource_name=target,
            ))
        if service.network_mode == "host" or is_unknown(service.network_mode):
            add(self._finding(
                "VOL-COMPOSE-0003",
                f"Service '{target}' uses host networking",
                target=target, value=service.network_mode, file_path=file_path,
                resource_name=target,
            ))
        image = service.image
        if isinstance(image, str):
            pinned = "@sha256:" in image or (
                ":" in image.rsplit("/", 1)[-1] and not image.endswith(":latest")
            )
            if not pinned:
                add(self._finding(
                    "VOL-COMPOSE-0004",
                    f"Service '{target}' image is not pinned: {image}",
                    target=target, value=image, file_path=file_path,
                    resource_name=target,
                ))
        for port in service.ports:
            if port.host_port and port.host_interface not in ("127.0.0.1", "::1"):
                add(self._finding(
                    "VOL-COMPOSE-0005",
                    f"Service '{target}' publishes port "
                    f"{port.host_port} on all interfaces",
                    target=target, value=port.host_interface, file_path=file_path,
                    resource_name=target,
                ))
        return results

    # -- Pipelines ---------------------------------------------------------

    def check_pipeline_job(
        self, job: CanonicalPipelineJob, file_path: Optional[str] = None
    ) -> List[ValidationResult]:
        results: List[ValidationResult] = []
        target = job.name

        def add(finding: Optional[ValidationResult]) -> None:
            if finding is not None:
                results.append(finding)

        if job.permissions is None and job.workflow_permissions is None:
            add(self._finding(
                "VOL-CICD-0001",
                f"Job '{target}' has no explicit permissions block "
                "(inherits the platform's permissive default token)",
                target=target, file_path=file_path, resource_name=target,
            ))
        if job.timeout_minutes is None:
            add(self._finding(
                "VOL-CICD-0003",
                f"Job '{target}' does not declare timeout-minutes",
                target=target, file_path=file_path, resource_name=target,
            ))
        for step in job.steps:
            uses = step.uses
            if isinstance(uses, str) and not uses.startswith("./"):
                ref = uses.split("@", 1)[1] if "@" in uses else ""
                is_sha = len(ref) == 40 and all(
                    c in "0123456789abcdef" for c in ref.lower()
                )
                if not is_sha:
                    add(self._finding(
                        "VOL-CICD-0002",
                        f"Step in job '{target}' uses non-SHA-pinned action: {uses}",
                        target=target, value=uses, file_path=file_path,
                        resource_name=target,
                    ))
        return results
