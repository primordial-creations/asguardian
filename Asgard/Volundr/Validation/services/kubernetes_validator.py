"""
Kubernetes Manifest Validator Service

Validates Kubernetes manifests for schema compliance,
best practices, and security configurations.
"""

import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml  # type: ignore[import-untyped]

from Asgard.Volundr.Validation.models.validation_models import (
    ValidationCategory,
    ValidationContext,
    ValidationReport,
    ValidationResult,
    ValidationSeverity,
)
from Asgard.Volundr.Validation.services.kubernetes_validator_helpers import (
    build_report,
    validate_config_resource,
    validate_ingress,
    validate_service,
    validate_workload,
)


class KubernetesValidator:
    """Validates Kubernetes manifests."""

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
        self.context = context or ValidationContext()

    def validate_file(self, file_path: str) -> ValidationReport:
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
            return build_report([file_path], results, start_time, self.context)

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
            return build_report([file_path], results, start_time, self.context)

        results.extend(self._validate_content(content, file_path))
        return build_report([file_path], results, start_time, self.context)

    def validate_directory(self, directory: str, pattern: str = "*.yaml") -> ValidationReport:
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
            return build_report([], results, start_time, self.context)

        for file_path in path.rglob(pattern):
            files_validated.append(str(file_path))
            file_results = self.validate_file(str(file_path))
            results.extend(file_results.results)

        for file_path in path.rglob("*.yml"):
            if str(file_path) not in files_validated:
                files_validated.append(str(file_path))
                file_results = self.validate_file(str(file_path))
                results.extend(file_results.results)

        return build_report(files_validated, results, start_time, self.context)

    def validate_content(self, content: str, source: str = "manifest") -> ValidationReport:
        start_time = time.time()
        results = self._validate_content(content, source)
        return build_report([source], results, start_time, self.context)

    def _validate_content(self, content: str, file_path: str) -> List[ValidationResult]:
        results: List[ValidationResult] = []

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
        results: List[ValidationResult] = []

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
            return results

        kind = manifest.get("kind", "")
        api_version = manifest.get("apiVersion", "")
        metadata = manifest.get("metadata", {})
        name = metadata.get("name", "unknown")

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

        if kind in ["Deployment", "StatefulSet", "DaemonSet"]:
            results.extend(validate_workload(manifest, file_path))
        elif kind == "Service":
            results.extend(validate_service(manifest, file_path))
        elif kind in ["ConfigMap", "Secret"]:
            results.extend(validate_config_resource(manifest, file_path))
        elif kind == "Ingress":
            results.extend(validate_ingress(manifest, file_path))

        return results
