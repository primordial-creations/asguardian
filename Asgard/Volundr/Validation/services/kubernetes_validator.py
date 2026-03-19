"""
Kubernetes Manifest Validator Service

Validates Kubernetes manifests for schema compliance,
best practices, and security configurations.
"""

import hashlib
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml  # type: ignore[import-untyped]

from Asgard.Volundr.Validation.models.validation_models import (
    ValidationReport,
    ValidationResult,
    ValidationSeverity,
    ValidationCategory,
    ValidationContext,
    FileValidationSummary,
)


class KubernetesValidator:
    """Validates Kubernetes manifests."""

    # Known Kubernetes API versions
    KNOWN_API_VERSIONS = {
        "v1",
        "apps/v1",
        "batch/v1",
        "networking.k8s.io/v1",
        "policy/v1",
        "autoscaling/v2",
        "rbac.authorization.k8s.io/v1",
        "storage.k8s.io/v1",
        "admissionregistration.k8s.io/v1",
    }

    # Required fields by kind
    REQUIRED_FIELDS = {
        "Deployment": ["spec.selector", "spec.template"],
        "Service": ["spec.ports", "spec.selector"],
        "ConfigMap": [],
        "Secret": [],
        "Ingress": ["spec.rules"],
        "StatefulSet": ["spec.selector", "spec.serviceName", "spec.template"],
        "DaemonSet": ["spec.selector", "spec.template"],
        "Job": ["spec.template"],
        "CronJob": ["spec.schedule", "spec.jobTemplate"],
    }

    def __init__(self, context: Optional[ValidationContext] = None):
        """
        Initialize the Kubernetes validator.

        Args:
            context: Validation context with settings
        """
        self.context = context or ValidationContext()

    def validate_file(self, file_path: str) -> ValidationReport:
        """
        Validate a Kubernetes manifest file.

        Args:
            file_path: Path to the manifest file

        Returns:
            ValidationReport with results
        """
        start_time = time.time()
        results: List[ValidationResult] = []

        if not os.path.exists(file_path):
            results.append(ValidationResult(
                rule_id="file-not-found",
                message=f"File not found: {file_path}",
                severity=ValidationSeverity.ERROR,
                category=ValidationCategory.SYNTAX,
                file_path=file_path,
            ))
            return self._build_report([file_path], results, start_time)

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            results.append(ValidationResult(
                rule_id="file-read-error",
                message=f"Error reading file: {e}",
                severity=ValidationSeverity.ERROR,
                category=ValidationCategory.SYNTAX,
                file_path=file_path,
            ))
            return self._build_report([file_path], results, start_time)

        results.extend(self._validate_content(content, file_path))
        return self._build_report([file_path], results, start_time)

    def validate_directory(self, directory: str, pattern: str = "*.yaml") -> ValidationReport:
        """
        Validate all Kubernetes manifests in a directory.

        Args:
            directory: Directory path
            pattern: File pattern to match

        Returns:
            ValidationReport with results
        """
        start_time = time.time()
        results: List[ValidationResult] = []
        files_validated: List[str] = []

        path = Path(directory)
        if not path.exists():
            results.append(ValidationResult(
                rule_id="directory-not-found",
                message=f"Directory not found: {directory}",
                severity=ValidationSeverity.ERROR,
                category=ValidationCategory.SYNTAX,
            ))
            return self._build_report([], results, start_time)

        for file_path in path.rglob(pattern):
            files_validated.append(str(file_path))
            file_results = self.validate_file(str(file_path))
            results.extend(file_results.results)

        # Also check for .yml files
        for file_path in path.rglob("*.yml"):
            if str(file_path) not in files_validated:
                files_validated.append(str(file_path))
                file_results = self.validate_file(str(file_path))
                results.extend(file_results.results)

        return self._build_report(files_validated, results, start_time)

    def validate_content(self, content: str, source: str = "manifest") -> ValidationReport:
        """
        Validate Kubernetes manifest content.

        Args:
            content: YAML content to validate
            source: Source identifier for reporting

        Returns:
            ValidationReport with results
        """
        start_time = time.time()
        results = self._validate_content(content, source)
        return self._build_report([source], results, start_time)

    def _validate_content(self, content: str, file_path: str) -> List[ValidationResult]:
        """Validate YAML content."""
        results: List[ValidationResult] = []

        # Parse YAML (handle multi-document)
        try:
            docs = list(yaml.safe_load_all(content))
        except yaml.YAMLError as e:
            results.append(ValidationResult(
                rule_id="yaml-syntax",
                message=f"Invalid YAML syntax: {e}",
                severity=ValidationSeverity.ERROR,
                category=ValidationCategory.SYNTAX,
                file_path=file_path,
            ))
            return results

        for doc in docs:
            if doc is None:
                continue
            results.extend(self._validate_manifest(doc, file_path))

        return results

    def _validate_manifest(
        self, manifest: Dict[str, Any], file_path: str
    ) -> List[ValidationResult]:
        """Validate a single manifest document."""
        results: List[ValidationResult] = []

        # Check required top-level fields
        if "apiVersion" not in manifest:
            results.append(ValidationResult(
                rule_id="missing-api-version",
                message="Missing required field: apiVersion",
                severity=ValidationSeverity.ERROR,
                category=ValidationCategory.SCHEMA,
                file_path=file_path,
            ))

        if "kind" not in manifest:
            results.append(ValidationResult(
                rule_id="missing-kind",
                message="Missing required field: kind",
                severity=ValidationSeverity.ERROR,
                category=ValidationCategory.SCHEMA,
                file_path=file_path,
            ))
            return results  # Can't continue without kind

        kind = manifest.get("kind", "")
        api_version = manifest.get("apiVersion", "")
        metadata = manifest.get("metadata", {})
        name = metadata.get("name", "unknown")

        # Check API version
        if api_version and api_version not in self.KNOWN_API_VERSIONS:
            results.append(ValidationResult(
                rule_id="unknown-api-version",
                message=f"Unknown or deprecated API version: {api_version}",
                severity=ValidationSeverity.WARNING,
                category=ValidationCategory.SCHEMA,
                file_path=file_path,
                resource_kind=kind,
                resource_name=name,
            ))

        # Check metadata
        if not metadata:
            results.append(ValidationResult(
                rule_id="missing-metadata",
                message="Missing metadata section",
                severity=ValidationSeverity.ERROR,
                category=ValidationCategory.SCHEMA,
                file_path=file_path,
                resource_kind=kind,
            ))
        else:
            if not metadata.get("name"):
                results.append(ValidationResult(
                    rule_id="missing-name",
                    message="Missing metadata.name",
                    severity=ValidationSeverity.ERROR,
                    category=ValidationCategory.SCHEMA,
                    file_path=file_path,
                    resource_kind=kind,
                ))

            # Check labels
            if not metadata.get("labels"):
                results.append(ValidationResult(
                    rule_id="missing-labels",
                    message="Missing metadata.labels - recommended for organization",
                    severity=ValidationSeverity.WARNING,
                    category=ValidationCategory.BEST_PRACTICE,
                    file_path=file_path,
                    resource_kind=kind,
                    resource_name=name,
                    suggestion="Add labels for better resource organization",
                ))

        # Kind-specific validation
        if kind in ["Deployment", "StatefulSet", "DaemonSet"]:
            results.extend(self._validate_workload(manifest, file_path))
        elif kind == "Service":
            results.extend(self._validate_service(manifest, file_path))
        elif kind in ["ConfigMap", "Secret"]:
            results.extend(self._validate_config_resource(manifest, file_path))
        elif kind == "Ingress":
            results.extend(self._validate_ingress(manifest, file_path))

        return results

    def _validate_workload(
        self, manifest: Dict[str, Any], file_path: str
    ) -> List[ValidationResult]:
        """Validate workload resources (Deployment, StatefulSet, DaemonSet)."""
        results: List[ValidationResult] = []
        kind = manifest.get("kind", "")
        name = manifest.get("metadata", {}).get("name", "unknown")
        spec = manifest.get("spec", {})
        template_spec = spec.get("template", {}).get("spec", {})
        containers = template_spec.get("containers", [])

        # Check selector
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

        # Check containers
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

            # Check image
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

            # Check resources
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

            # Check security context
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

            # Check probes
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

    def _validate_service(
        self, manifest: Dict[str, Any], file_path: str
    ) -> List[ValidationResult]:
        """Validate Service resources."""
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

    def _validate_config_resource(
        self, manifest: Dict[str, Any], file_path: str
    ) -> List[ValidationResult]:
        """Validate ConfigMap/Secret resources."""
        results: List[ValidationResult] = []
        kind = manifest.get("kind", "")
        name = manifest.get("metadata", {}).get("name", "unknown")

        # Check for empty data
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

    def _validate_ingress(
        self, manifest: Dict[str, Any], file_path: str
    ) -> List[ValidationResult]:
        """Validate Ingress resources."""
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

        # Check for TLS
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

    def _build_report(
        self,
        files: List[str],
        results: List[ValidationResult],
        start_time: float,
    ) -> ValidationReport:
        """Build validation report."""
        duration_ms = int((time.time() - start_time) * 1000)

        error_count = sum(1 for r in results if r.severity == ValidationSeverity.ERROR)
        warning_count = sum(1 for r in results if r.severity == ValidationSeverity.WARNING)
        info_count = sum(1 for r in results if r.severity == ValidationSeverity.INFO)

        # Calculate score (start at 100, subtract for issues)
        score = 100.0
        score -= error_count * 10
        score -= warning_count * 3
        score -= info_count * 1
        score = max(0.0, score)

        # Build file summaries
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
            context=self.context,
        )
