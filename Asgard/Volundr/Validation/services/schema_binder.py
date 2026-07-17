"""
Tier 2 — versioned schema binding for Kubernetes manifests.

Structural validation is pinned to ``ValidationContext.kubernetes_version``.
Unknown fields are errors (default-deny, kubeconform ``-strict`` style)
UNLESS the target version is newer than the newest version this engine
knows about (version skew, V_target > V_known): then unknown-field errors
are downgraded to WARN and the affected document is marked ``<tainted>``
so downstream policies do not fail-open on it (Protobuf-style lenient
forward compatibility).

Everything here is offline and vendored — no network in the default path.
A user-supplied ``schema_dir`` of JSON schema fragments can extend the
known field sets.
"""

import json
import os
from typing import Any, Dict, List, Optional, Set, Tuple

from Asgard.Volundr.Validation.models.validation_models import (
    ValidationCategory,
    ValidationContext,
    ValidationResult,
    ValidationSeverity,
)

# Newest K8s minor version whose schemas are vendored into this engine.
KNOWN_MAX_KUBERNETES_VERSION = (1, 33)

# Supported (current, non-deprecated) apiVersions per kind.
SUPPORTED_API_VERSIONS: Dict[str, Set[str]] = {
    "Pod": {"v1"},
    "Deployment": {"apps/v1"},
    "StatefulSet": {"apps/v1"},
    "DaemonSet": {"apps/v1"},
    "ReplicaSet": {"apps/v1"},
    "Job": {"batch/v1"},
    "CronJob": {"batch/v1"},
    "Service": {"v1"},
    "ConfigMap": {"v1"},
    "Secret": {"v1"},
    "Ingress": {"networking.k8s.io/v1"},
    "NetworkPolicy": {"networking.k8s.io/v1"},
    "PodDisruptionBudget": {"policy/v1"},
    "HorizontalPodAutoscaler": {"autoscaling/v2"},
    "ServiceAccount": {"v1"},
    "PersistentVolumeClaim": {"v1"},
}

# Deprecated/removed apiVersions -> replacement (pluto-style knowledge).
DEPRECATED_API_VERSIONS: Dict[str, str] = {
    "extensions/v1beta1": "apps/v1 or networking.k8s.io/v1",
    "apps/v1beta1": "apps/v1",
    "apps/v1beta2": "apps/v1",
    "batch/v1beta1": "batch/v1",
    "policy/v1beta1": "policy/v1",
    "networking.k8s.io/v1beta1": "networking.k8s.io/v1",
    "autoscaling/v2beta1": "autoscaling/v2",
    "autoscaling/v2beta2": "autoscaling/v2",
}

# Allowed top-level fields for any manifest.
TOP_LEVEL_FIELDS: Set[str] = {
    "apiVersion", "kind", "metadata", "spec", "data", "stringData",
    "binaryData", "type", "immutable", "status", "subsets", "rules",
    "roleRef", "subjects", "secrets", "imagePullSecrets",
    "automountServiceAccountToken", "webhooks",
}

# Allowed spec-level fields per workload kind (vendored subset).
SPEC_FIELDS: Dict[str, Set[str]] = {
    "Deployment": {
        "replicas", "selector", "template", "strategy", "minReadySeconds",
        "revisionHistoryLimit", "paused", "progressDeadlineSeconds",
    },
    "StatefulSet": {
        "replicas", "selector", "template", "serviceName", "updateStrategy",
        "podManagementPolicy", "revisionHistoryLimit", "minReadySeconds",
        "volumeClaimTemplates", "persistentVolumeClaimRetentionPolicy", "ordinals",
    },
    "DaemonSet": {
        "selector", "template", "updateStrategy", "minReadySeconds",
        "revisionHistoryLimit",
    },
    "Job": {
        "template", "parallelism", "completions", "activeDeadlineSeconds",
        "backoffLimit", "backoffLimitPerIndex", "maxFailedIndexes",
        "selector", "manualSelector", "ttlSecondsAfterFinished",
        "completionMode", "suspend", "podFailurePolicy", "podReplacementPolicy",
        "successPolicy", "managedBy",
    },
    "CronJob": {
        "schedule", "timeZone", "startingDeadlineSeconds", "concurrencyPolicy",
        "suspend", "jobTemplate", "successfulJobsHistoryLimit",
        "failedJobsHistoryLimit",
    },
}


def parse_version(version: str) -> Tuple[int, int]:
    """Parse '1.29' / 'v1.29.4' into a (major, minor) tuple."""
    text = version.lstrip("vV")
    parts = text.split(".")
    try:
        major = int(parts[0])
        minor = int(parts[1]) if len(parts) > 1 else 0
    except (ValueError, IndexError):
        return KNOWN_MAX_KUBERNETES_VERSION
    return (major, minor)


class SchemaBindingOutcome:
    """Result of binding one manifest against the versioned schema."""

    def __init__(self, results: List[ValidationResult], tainted: bool):
        self.results = results
        self.tainted = tainted


class SchemaBinder:
    """Tier 2 versioned structural validation with skew downgrade."""

    def __init__(self, context: Optional[ValidationContext] = None):
        self.context = context or ValidationContext()
        self._extra_spec_fields: Dict[str, Set[str]] = {}
        schema_dir = getattr(self.context, "schema_dir", None)
        if schema_dir:
            self._load_schema_dir(schema_dir)

    def _load_schema_dir(self, schema_dir: str) -> None:
        """Load user-supplied schema fragments: {kind: [spec field names]}."""
        if not os.path.isdir(schema_dir):
            return
        for entry in os.listdir(schema_dir):
            if not entry.endswith(".json"):
                continue
            try:
                with open(os.path.join(schema_dir, entry), "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(data, dict):
                for kind, fields in data.items():
                    if isinstance(fields, list):
                        self._extra_spec_fields.setdefault(kind, set()).update(
                            str(x) for x in fields
                        )

    @property
    def version_skew(self) -> bool:
        """True if the target K8s version is newer than the vendored schemas."""
        target = parse_version(self.context.kubernetes_version)
        return target > KNOWN_MAX_KUBERNETES_VERSION

    def bind(
        self, manifest: Dict[str, Any], file_path: Optional[str] = None
    ) -> SchemaBindingOutcome:
        """Validate structure of one manifest; report unknown fields."""
        results: List[ValidationResult] = []
        tainted = False
        kind = manifest.get("kind", "")
        api_version = manifest.get("apiVersion", "")
        name = (manifest.get("metadata") or {}).get("name", "unknown")
        skew = self.version_skew

        unknown_severity = (
            ValidationSeverity.WARNING if skew else ValidationSeverity.ERROR
        )

        if api_version in DEPRECATED_API_VERSIONS:
            results.append(ValidationResult(
                rule_id="VOL-K8S-0012",
                message=(
                    f"apiVersion '{api_version}' is deprecated/removed; "
                    f"use {DEPRECATED_API_VERSIONS[api_version]}"
                ),
                severity=ValidationSeverity.ERROR,
                category=ValidationCategory.SCHEMA,
                file_path=file_path, resource_kind=kind, resource_name=name,
            ))
        elif kind in SUPPORTED_API_VERSIONS and api_version not in SUPPORTED_API_VERSIONS[kind]:
            severity = ValidationSeverity.WARNING if skew else ValidationSeverity.ERROR
            if skew:
                tainted = True
            results.append(ValidationResult(
                rule_id="VOL-K8S-0012",
                message=f"apiVersion '{api_version}' is not a known version for kind {kind}",
                severity=severity,
                category=ValidationCategory.SCHEMA,
                file_path=file_path, resource_kind=kind, resource_name=name,
            ))

        for field in manifest:
            if field not in TOP_LEVEL_FIELDS:
                if skew:
                    tainted = True
                results.append(ValidationResult(
                    rule_id="VOL-K8S-0011",
                    message=(
                        f"Unknown top-level field '{field}' for target "
                        f"Kubernetes {self.context.kubernetes_version}"
                        + (" (version skew: downgraded to warning, node tainted)" if skew else "")
                    ),
                    severity=unknown_severity,
                    category=ValidationCategory.SCHEMA,
                    file_path=file_path, resource_kind=kind, resource_name=name,
                    context={"field": field, "tainted": skew},
                ))

        spec = manifest.get("spec")
        allowed = SPEC_FIELDS.get(kind)
        if allowed is not None and isinstance(spec, dict):
            allowed = allowed | self._extra_spec_fields.get(kind, set())
            for field in spec:
                if field not in allowed:
                    if skew:
                        tainted = True
                    results.append(ValidationResult(
                        rule_id="VOL-K8S-0011",
                        message=(
                            f"Unknown field 'spec.{field}' for {kind} at target "
                            f"Kubernetes {self.context.kubernetes_version}"
                            + (" (version skew: downgraded to warning, node tainted)" if skew else "")
                        ),
                        severity=unknown_severity,
                        category=ValidationCategory.SCHEMA,
                        file_path=file_path, resource_kind=kind, resource_name=name,
                        context={"field": f"spec.{field}", "tainted": skew},
                    ))

        return SchemaBindingOutcome(results, tainted)
