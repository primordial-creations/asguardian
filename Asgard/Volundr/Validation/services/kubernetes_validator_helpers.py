import hashlib
import time
from typing import Any, Dict, List

from Asgard.Volundr.Validation.models.validation_models import (
    FileValidationSummary,
    ValidationCategory,
    ValidationContext,
    ValidationReport,
    ValidationResult,
    ValidationSeverity,
)


def validate_workload(
    manifest: Dict[str, Any], file_path: str
) -> List[ValidationResult]:
    results: List[ValidationResult] = []
    kind = manifest.get("kind", "")
    name = manifest.get("metadata", {}).get("name", "unknown")
    spec = manifest.get("spec", {})
    template_spec = spec.get("template", {}).get("spec", {})
    containers = template_spec.get("containers", [])

    if not spec.get("selector"):
        results.append(ValidationResult(
            rule_id="missing-selector",
            message="Missing spec.selector",
            severity=ValidationSeverity.ERROR,
            category=ValidationCategory.SCHEMA,
            file_path=file_path,
            resource_kind=kind,
            resource_name=name,
        ))

    if not containers:
        results.append(ValidationResult(
            rule_id="no-containers",
            message="No containers defined in pod template",
            severity=ValidationSeverity.ERROR,
            category=ValidationCategory.SCHEMA,
            file_path=file_path,
            resource_kind=kind,
            resource_name=name,
        ))

    for container in containers:
        container_name = container.get("name", "unknown")

        image = container.get("image", "")
        if not image:
            results.append(ValidationResult(
                rule_id="missing-image",
                message=f"Container '{container_name}' missing image",
                severity=ValidationSeverity.ERROR,
                category=ValidationCategory.SCHEMA,
                file_path=file_path,
                resource_kind=kind,
                resource_name=name,
            ))
        elif ":latest" in image or ":" not in image:
            results.append(ValidationResult(
                rule_id="unpinned-image",
                message=f"Container '{container_name}' uses unpinned image: {image}",
                severity=ValidationSeverity.WARNING,
                category=ValidationCategory.BEST_PRACTICE,
                file_path=file_path,
                resource_kind=kind,
                resource_name=name,
                suggestion="Pin image to specific version",
            ))

        resources = container.get("resources", {})
        if not resources.get("limits"):
            results.append(ValidationResult(
                rule_id="missing-resource-limits",
                message=f"Container '{container_name}' missing resource limits",
                severity=ValidationSeverity.WARNING,
                category=ValidationCategory.RELIABILITY,
                file_path=file_path,
                resource_kind=kind,
                resource_name=name,
                suggestion="Add resources.limits for cpu and memory",
            ))
        if not resources.get("requests"):
            results.append(ValidationResult(
                rule_id="missing-resource-requests",
                message=f"Container '{container_name}' missing resource requests",
                severity=ValidationSeverity.WARNING,
                category=ValidationCategory.RELIABILITY,
                file_path=file_path,
                resource_kind=kind,
                resource_name=name,
                suggestion="Add resources.requests for cpu and memory",
            ))

        security_context = container.get("securityContext", {})
        if not security_context:
            results.append(ValidationResult(
                rule_id="missing-security-context",
                message=f"Container '{container_name}' missing securityContext",
                severity=ValidationSeverity.WARNING,
                category=ValidationCategory.SECURITY,
                file_path=file_path,
                resource_kind=kind,
                resource_name=name,
                suggestion="Add securityContext with runAsNonRoot, readOnlyRootFilesystem",
            ))
        else:
            if not security_context.get("runAsNonRoot"):
                results.append(ValidationResult(
                    rule_id="not-running-as-non-root",
                    message=f"Container '{container_name}' not configured to run as non-root",
                    severity=ValidationSeverity.WARNING,
                    category=ValidationCategory.SECURITY,
                    file_path=file_path,
                    resource_kind=kind,
                    resource_name=name,
                ))
            if security_context.get("privileged"):
                results.append(ValidationResult(
                    rule_id="privileged-container",
                    message=f"Container '{container_name}' runs in privileged mode",
                    severity=ValidationSeverity.ERROR,
                    category=ValidationCategory.SECURITY,
                    file_path=file_path,
                    resource_kind=kind,
                    resource_name=name,
                ))
            if security_context.get("allowPrivilegeEscalation", True):
                results.append(ValidationResult(
                    rule_id="privilege-escalation-allowed",
                    message=f"Container '{container_name}' allows privilege escalation",
                    severity=ValidationSeverity.WARNING,
                    category=ValidationCategory.SECURITY,
                    file_path=file_path,
                    resource_kind=kind,
                    resource_name=name,
                ))

        if not container.get("livenessProbe"):
            results.append(ValidationResult(
                rule_id="missing-liveness-probe",
                message=f"Container '{container_name}' missing livenessProbe",
                severity=ValidationSeverity.WARNING,
                category=ValidationCategory.RELIABILITY,
                file_path=file_path,
                resource_kind=kind,
                resource_name=name,
            ))
        if not container.get("readinessProbe"):
            results.append(ValidationResult(
                rule_id="missing-readiness-probe",
                message=f"Container '{container_name}' missing readinessProbe",
                severity=ValidationSeverity.WARNING,
                category=ValidationCategory.RELIABILITY,
                file_path=file_path,
                resource_kind=kind,
                resource_name=name,
            ))

    return results


def validate_service(
    manifest: Dict[str, Any], file_path: str
) -> List[ValidationResult]:
    results: List[ValidationResult] = []
    name = manifest.get("metadata", {}).get("name", "unknown")
    spec = manifest.get("spec", {})

    if not spec.get("selector"):
        results.append(ValidationResult(
            rule_id="service-no-selector",
            message="Service missing selector",
            severity=ValidationSeverity.WARNING,
            category=ValidationCategory.BEST_PRACTICE,
            file_path=file_path,
            resource_kind="Service",
            resource_name=name,
        ))

    if not spec.get("ports"):
        results.append(ValidationResult(
            rule_id="service-no-ports",
            message="Service has no ports defined",
            severity=ValidationSeverity.WARNING,
            category=ValidationCategory.SCHEMA,
            file_path=file_path,
            resource_kind="Service",
            resource_name=name,
        ))

    return results


def validate_config_resource(
    manifest: Dict[str, Any], file_path: str
) -> List[ValidationResult]:
    results: List[ValidationResult] = []
    kind = manifest.get("kind", "")
    name = manifest.get("metadata", {}).get("name", "unknown")

    data = manifest.get("data", {})
    string_data = manifest.get("stringData", {})
    if not data and not string_data:
        results.append(ValidationResult(
            rule_id="empty-config-data",
            message=f"{kind} has no data",
            severity=ValidationSeverity.INFO,
            category=ValidationCategory.BEST_PRACTICE,
            file_path=file_path,
            resource_kind=kind,
            resource_name=name,
        ))

    return results


def validate_ingress(
    manifest: Dict[str, Any], file_path: str
) -> List[ValidationResult]:
    results: List[ValidationResult] = []
    name = manifest.get("metadata", {}).get("name", "unknown")
    spec = manifest.get("spec", {})

    if not spec.get("rules"):
        results.append(ValidationResult(
            rule_id="ingress-no-rules",
            message="Ingress has no rules defined",
            severity=ValidationSeverity.WARNING,
            category=ValidationCategory.SCHEMA,
            file_path=file_path,
            resource_kind="Ingress",
            resource_name=name,
        ))

    if not spec.get("tls"):
        results.append(ValidationResult(
            rule_id="ingress-no-tls",
            message="Ingress has no TLS configured",
            severity=ValidationSeverity.WARNING,
            category=ValidationCategory.SECURITY,
            file_path=file_path,
            resource_kind="Ingress",
            resource_name=name,
            suggestion="Add TLS configuration for secure connections",
        ))

    return results


def build_report(
    files: List[str],
    results: List[ValidationResult],
    start_time: float,
    context: ValidationContext,
) -> ValidationReport:
    duration_ms = int((time.time() - start_time) * 1000)

    error_count = sum(1 for r in results if r.severity == ValidationSeverity.ERROR)
    warning_count = sum(1 for r in results if r.severity == ValidationSeverity.WARNING)
    info_count = sum(1 for r in results if r.severity == ValidationSeverity.INFO)

    score = 100.0
    score -= error_count * 10
    score -= warning_count * 3
    score -= info_count * 1
    score = max(0.0, score)

    file_summaries = []
    results_by_file: Dict[str, List[ValidationResult]] = {}
    for result in results:
        fp = result.file_path or "(no file)"
        if fp not in results_by_file:
            results_by_file[fp] = []
        results_by_file[fp].append(result)

    for fp in files:
        file_results = results_by_file.get(fp, [])
        file_errors = sum(1 for r in file_results if r.severity == ValidationSeverity.ERROR)
        file_warnings = sum(1 for r in file_results if r.severity == ValidationSeverity.WARNING)
        file_info = sum(1 for r in file_results if r.severity == ValidationSeverity.INFO)
        file_summaries.append(FileValidationSummary(
            file_path=fp,
            error_count=file_errors,
            warning_count=file_warnings,
            info_count=file_info,
            passed=file_errors == 0,
        ))

    report_id = hashlib.sha256(str(results).encode()).hexdigest()[:16]

    return ValidationReport(
        id=f"k8s-validation-{report_id}",
        title="Kubernetes Manifest Validation",
        validator="KubernetesValidator",
        results=results,
        file_summaries=file_summaries,
        total_files=len(files),
        total_errors=error_count,
        total_warnings=warning_count,
        total_info=info_count,
        passed=error_count == 0,
        score=score,
        duration_ms=duration_ms,
        context=context,
    )
