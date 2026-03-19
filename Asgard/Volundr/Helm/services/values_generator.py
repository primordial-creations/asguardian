"""
Helm Values Generator Service

Generates values.yaml files with environment-specific overrides
and best practice configurations.
"""

import hashlib
from datetime import datetime
from typing import Any, Dict, List, Optional, cast

import yaml  # type: ignore[import-untyped]

from Asgard.Volundr.Helm.models.helm_models import (
    HelmValues,
    ResourceSpec,
    ResourceRequirements,
    AutoscalingConfig,
    ProbeConfig,
    ServiceConfig,
    IngressConfig,
    SecurityContextConfig,
)


class ValuesGenerator:
    """Generates Helm values.yaml files."""

    # Environment-specific defaults
    ENV_DEFAULTS: Dict[str, Dict[str, Any]] = {
        "development": {
            "replica_count": 1,
            "resources": ResourceRequirements(
                limits=ResourceSpec(cpu="200m", memory="256Mi"),
                requests=ResourceSpec(cpu="100m", memory="128Mi"),
            ),
            "autoscaling": AutoscalingConfig(enabled=False),
            "liveness_probe": ProbeConfig(initial_delay_seconds=30),
            "readiness_probe": ProbeConfig(initial_delay_seconds=10),
        },
        "staging": {
            "replica_count": 2,
            "resources": ResourceRequirements(
                limits=ResourceSpec(cpu="500m", memory="512Mi"),
                requests=ResourceSpec(cpu="250m", memory="256Mi"),
            ),
            "autoscaling": AutoscalingConfig(enabled=True, min_replicas=2, max_replicas=5),
            "liveness_probe": ProbeConfig(initial_delay_seconds=20),
            "readiness_probe": ProbeConfig(initial_delay_seconds=5),
        },
        "production": {
            "replica_count": 3,
            "resources": ResourceRequirements(
                limits=ResourceSpec(cpu="1000m", memory="1Gi"),
                requests=ResourceSpec(cpu="500m", memory="512Mi"),
            ),
            "autoscaling": AutoscalingConfig(enabled=True, min_replicas=3, max_replicas=20),
            "liveness_probe": ProbeConfig(initial_delay_seconds=15, failure_threshold=5),
            "readiness_probe": ProbeConfig(initial_delay_seconds=5, success_threshold=2),
        },
    }

    def __init__(self, output_dir: Optional[str] = None):
        """
        Initialize the values generator.

        Args:
            output_dir: Directory for saving generated values files
        """
        self.output_dir = output_dir or "."

    def generate(
        self,
        image_repository: str,
        environment: str = "development",
        image_tag: str = "latest",
        service_port: int = 8080,
        ingress_enabled: bool = False,
        ingress_host: Optional[str] = None,
        extra_values: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Generate values.yaml content for a specific environment.

        Args:
            image_repository: Container image repository
            environment: Target environment (development, staging, production)
            image_tag: Container image tag
            service_port: Service port
            ingress_enabled: Enable ingress
            ingress_host: Ingress host
            extra_values: Additional values to merge

        Returns:
            Dictionary containing values.yaml content
        """
        env_defaults = self.ENV_DEFAULTS.get(environment, self.ENV_DEFAULTS["development"])

        values = HelmValues(
            replica_count=env_defaults["replica_count"],
            image_repository=image_repository,
            image_tag=image_tag,
            image_pull_policy="Always" if environment == "development" else "IfNotPresent",
            resources=env_defaults["resources"],
            autoscaling=env_defaults["autoscaling"],
            liveness_probe=env_defaults["liveness_probe"],
            readiness_probe=env_defaults["readiness_probe"],
            service=ServiceConfig(port=service_port),
            ingress=IngressConfig(
                enabled=ingress_enabled,
                hosts=[{"host": ingress_host or "chart-example.local", "paths": [{"path": "/", "pathType": "Prefix"}]}]
                if ingress_enabled else [],
            ),
            security_context=SecurityContextConfig(
                run_as_non_root=True,
                run_as_user=1000,
                read_only_root_filesystem=True,
                allow_privilege_escalation=False,
            ),
        )

        values_dict = self._values_to_dict(values)

        if extra_values:
            values_dict = self._deep_merge(values_dict, extra_values)

        return values_dict

    def generate_yaml(
        self,
        image_repository: str,
        environment: str = "development",
        **kwargs,
    ) -> str:
        """
        Generate values.yaml content as YAML string.

        Args:
            image_repository: Container image repository
            environment: Target environment
            **kwargs: Additional arguments passed to generate()

        Returns:
            YAML string
        """
        values_dict = self.generate(image_repository, environment, **kwargs)
        return cast(str, yaml.dump(values_dict, default_flow_style=False, sort_keys=False))

    def generate_environment_overlay(
        self,
        base_values: Dict[str, Any],
        environment: str,
        overrides: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Generate environment-specific value overrides.

        Args:
            base_values: Base values dictionary
            environment: Target environment
            overrides: Additional overrides

        Returns:
            Environment-specific values overlay
        """
        env_defaults = self.ENV_DEFAULTS.get(environment, {})

        overlay: Dict[str, Any] = {}

        if "replica_count" in env_defaults:
            overlay["replicaCount"] = env_defaults["replica_count"]

        if "resources" in env_defaults:
            resources = env_defaults["resources"]
            overlay["resources"] = {
                "limits": {"cpu": resources.limits.cpu, "memory": resources.limits.memory},
                "requests": {"cpu": resources.requests.cpu, "memory": resources.requests.memory},
            }

        if "autoscaling" in env_defaults:
            autoscaling = env_defaults["autoscaling"]
            overlay["autoscaling"] = {
                "enabled": autoscaling.enabled,
                "minReplicas": autoscaling.min_replicas,
                "maxReplicas": autoscaling.max_replicas,
                "targetCPUUtilizationPercentage": autoscaling.target_cpu_utilization,
            }

        if overrides:
            overlay = self._deep_merge(overlay, overrides)

        return overlay

    def _values_to_dict(self, values: HelmValues) -> Dict[str, Any]:
        """Convert HelmValues to dictionary for YAML output."""
        return {
            "replicaCount": values.replica_count,
            "image": {
                "repository": values.image_repository,
                "pullPolicy": values.image_pull_policy,
                "tag": values.image_tag,
            },
            "imagePullSecrets": [{"name": s} for s in values.image_pull_secrets] if values.image_pull_secrets else [],
            "nameOverride": values.name_override,
            "fullnameOverride": values.fullname_override,
            "serviceAccount": {
                "create": values.service_account_create,
                "annotations": values.service_account_annotations,
                "name": values.service_account_name,
            },
            "podAnnotations": values.pod_annotations,
            "podLabels": values.pod_labels,
            "podSecurityContext": {
                "fsGroup": values.pod_security_context.fs_group,
            },
            "securityContext": {
                "runAsNonRoot": values.security_context.run_as_non_root,
                "runAsUser": values.security_context.run_as_user,
                "readOnlyRootFilesystem": values.security_context.read_only_root_filesystem,
                "allowPrivilegeEscalation": values.security_context.allow_privilege_escalation,
                "capabilities": {"drop": ["ALL"]},
            },
            "service": {
                "type": values.service.type,
                "port": values.service.port,
            },
            "ingress": {
                "enabled": values.ingress.enabled,
                "className": values.ingress.class_name or "",
                "annotations": values.ingress.annotations,
                "hosts": values.ingress.hosts,
                "tls": values.ingress.tls,
            },
            "resources": {
                "limits": {
                    "cpu": values.resources.limits.cpu,
                    "memory": values.resources.limits.memory,
                },
                "requests": {
                    "cpu": values.resources.requests.cpu,
                    "memory": values.resources.requests.memory,
                },
            },
            "autoscaling": {
                "enabled": values.autoscaling.enabled,
                "minReplicas": values.autoscaling.min_replicas,
                "maxReplicas": values.autoscaling.max_replicas,
                "targetCPUUtilizationPercentage": values.autoscaling.target_cpu_utilization,
            },
            "livenessProbe": {
                "httpGet": {
                    "path": values.liveness_probe.path,
                    "port": values.liveness_probe.port,
                },
                "initialDelaySeconds": values.liveness_probe.initial_delay_seconds,
                "periodSeconds": values.liveness_probe.period_seconds,
                "timeoutSeconds": values.liveness_probe.timeout_seconds,
                "failureThreshold": values.liveness_probe.failure_threshold,
            },
            "readinessProbe": {
                "httpGet": {
                    "path": values.readiness_probe.path,
                    "port": values.readiness_probe.port,
                },
                "initialDelaySeconds": values.readiness_probe.initial_delay_seconds,
                "periodSeconds": values.readiness_probe.period_seconds,
                "timeoutSeconds": values.readiness_probe.timeout_seconds,
                "successThreshold": values.readiness_probe.success_threshold,
            },
            "nodeSelector": values.node_selector,
            "tolerations": values.tolerations,
            "affinity": values.affinity,
        }

    def _deep_merge(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge two dictionaries."""
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result
