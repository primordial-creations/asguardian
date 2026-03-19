"""
Kubernetes Manifest Generator Service

Generates comprehensive Kubernetes manifests for various workloads
with best practices, security configurations, and operational readiness.
"""

import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml  # type: ignore[import-untyped]

from Asgard.Volundr.Kubernetes.models.kubernetes_models import (
    EnvironmentType,
    GeneratedManifest,
    ManifestConfig,
    SecurityProfile,
    WorkloadType,
)


class ManifestGenerator:
    """Generates Kubernetes manifests from configuration."""

    def __init__(self, output_dir: Optional[str] = None):
        """
        Initialize the manifest generator.

        Args:
            output_dir: Directory for saving generated manifests
        """
        self.output_dir = output_dir or "manifests"

    def generate(self, config: ManifestConfig) -> GeneratedManifest:
        """
        Generate Kubernetes manifests based on the provided configuration.

        Args:
            config: Manifest configuration

        Returns:
            GeneratedManifest with all generated resources
        """
        config_json = config.model_dump_json()
        config_hash = hashlib.sha256(config_json.encode()).hexdigest()[:16]
        manifest_id = f"{config.name}-{config_hash}"

        manifests: Dict[str, Dict[str, Any]] = {}

        base_labels = {
            "app": config.name,
            "version": "v1",
            "environment": config.environment.value,
            **config.labels,
        }

        if config.workload_type in [WorkloadType.DEPLOYMENT, WorkloadType.STATEFULSET, WorkloadType.DAEMONSET]:
            manifests[config.workload_type.value.lower()] = self._generate_workload(config, base_labels)
        elif config.workload_type in [WorkloadType.JOB, WorkloadType.CRONJOB]:
            manifests[config.workload_type.value.lower()] = self._generate_job(config, base_labels)

        if config.ports:
            manifests["service"] = self._generate_service(config, base_labels)

        for cm_name in config.config_maps:
            manifests[f"configmap-{cm_name}"] = self._generate_configmap(config, base_labels, cm_name)

        for secret_name in config.secrets:
            manifests[f"secret-{secret_name}"] = self._generate_secret(config, base_labels, secret_name)

        if config.security_profile in [SecurityProfile.ENHANCED, SecurityProfile.STRICT, SecurityProfile.ZERO_TRUST]:
            manifests["networkpolicy"] = self._generate_network_policy(config, base_labels)

        if config.environment == EnvironmentType.PRODUCTION and config.replicas > 1:
            manifests["poddisruptionbudget"] = self._generate_pdb(config, base_labels)

        yaml_docs = []
        for manifest in manifests.values():
            yaml_docs.append(yaml.dump(manifest, default_flow_style=False, sort_keys=False))

        yaml_content = "---\n".join(yaml_docs)

        validation_results = self._validate_manifests(manifests, config)
        best_practice_score = self._calculate_best_practice_score(manifests, config)

        return GeneratedManifest(
            id=manifest_id,
            config_hash=config_hash,
            manifests=manifests,
            yaml_content=yaml_content,
            validation_results=validation_results,
            best_practice_score=best_practice_score,
            created_at=datetime.now(),
        )

    def _generate_workload(self, config: ManifestConfig, base_labels: Dict[str, str]) -> Dict[str, Any]:
        """Generate workload manifest (Deployment, StatefulSet, or DaemonSet)."""
        ports_list = [
            {
                "name": p.name,
                "containerPort": p.container_port,
                "protocol": p.protocol,
            }
            for p in config.ports
        ]

        container_spec: Dict[str, Any] = {
            "name": config.name,
            "image": config.image,
            "ports": ports_list,
            "resources": {
                "requests": {
                    "cpu": config.resources.cpu_request,
                    "memory": config.resources.memory_request,
                },
                "limits": {
                    "cpu": config.resources.cpu_limit,
                    "memory": config.resources.memory_limit,
                },
            },
            "securityContext": {
                "runAsUser": config.security_context.run_as_user,
                "runAsGroup": config.security_context.run_as_group,
                "runAsNonRoot": config.security_context.run_as_non_root,
                "readOnlyRootFilesystem": config.security_context.read_only_root_filesystem,
                "allowPrivilegeEscalation": config.security_context.allow_privilege_escalation,
                "capabilities": {
                    "drop": config.security_context.drop_capabilities,
                },
            },
        }

        if config.security_context.add_capabilities:
            container_spec["securityContext"]["capabilities"]["add"] = config.security_context.add_capabilities

        if config.env_vars:
            container_spec["env"] = [{"name": k, "value": v} for k, v in config.env_vars.items()]

        if config.liveness_probe.enabled:
            container_spec["livenessProbe"] = {
                "httpGet": {
                    "path": config.liveness_probe.http_path,
                    "port": config.liveness_probe.http_port,
                },
                "initialDelaySeconds": config.liveness_probe.initial_delay_seconds,
                "periodSeconds": config.liveness_probe.period_seconds,
                "timeoutSeconds": config.liveness_probe.timeout_seconds,
                "failureThreshold": config.liveness_probe.failure_threshold,
            }

        if config.readiness_probe.enabled:
            container_spec["readinessProbe"] = {
                "httpGet": {
                    "path": config.readiness_probe.http_path,
                    "port": config.readiness_probe.http_port,
                },
                "initialDelaySeconds": config.readiness_probe.initial_delay_seconds,
                "periodSeconds": config.readiness_probe.period_seconds,
                "timeoutSeconds": config.readiness_probe.timeout_seconds,
                "failureThreshold": config.readiness_probe.failure_threshold,
                "successThreshold": config.readiness_probe.success_threshold,
            }

        if config.volumes:
            container_spec["volumeMounts"] = []
            for volume in config.volumes:
                if "mountPath" in volume:
                    container_spec["volumeMounts"].append({
                        "name": volume["name"],
                        "mountPath": volume["mountPath"],
                        "readOnly": volume.get("readOnly", False),
                    })

        pod_spec: Dict[str, Any] = {
            "containers": [container_spec],
            "securityContext": {
                "fsGroup": 2000,
                "seccompProfile": {"type": "RuntimeDefault"},
            },
        }

        if config.service_account:
            pod_spec["serviceAccountName"] = config.service_account

        if config.volumes:
            pod_spec["volumes"] = config.volumes

        manifest: Dict[str, Any] = {
            "apiVersion": "apps/v1",
            "kind": config.workload_type.value,
            "metadata": {
                "name": config.name,
                "namespace": config.namespace,
                "labels": base_labels,
                "annotations": config.annotations,
            },
            "spec": {
                "selector": {
                    "matchLabels": {"app": config.name},
                },
                "template": {
                    "metadata": {
                        "labels": base_labels,
                        "annotations": config.annotations,
                    },
                    "spec": pod_spec,
                },
            },
        }

        if config.workload_type == WorkloadType.DEPLOYMENT:
            manifest["spec"]["replicas"] = config.replicas
            manifest["spec"]["strategy"] = {
                "type": "RollingUpdate",
                "rollingUpdate": {
                    "maxUnavailable": "25%",
                    "maxSurge": "25%",
                },
            }
        elif config.workload_type == WorkloadType.STATEFULSET:
            manifest["spec"]["replicas"] = config.replicas
            manifest["spec"]["serviceName"] = f"{config.name}-headless"
            manifest["spec"]["updateStrategy"] = {
                "type": "RollingUpdate",
                "rollingUpdate": {"partition": 0},
            }

        return manifest

    def _generate_job(self, config: ManifestConfig, base_labels: Dict[str, str]) -> Dict[str, Any]:
        """Generate Job or CronJob manifest."""
        container_spec: Dict[str, Any] = {
            "name": config.name,
            "image": config.image,
            "resources": {
                "requests": {
                    "cpu": config.resources.cpu_request,
                    "memory": config.resources.memory_request,
                },
                "limits": {
                    "cpu": config.resources.cpu_limit,
                    "memory": config.resources.memory_limit,
                },
            },
            "securityContext": {
                "runAsUser": config.security_context.run_as_user,
                "runAsGroup": config.security_context.run_as_group,
                "runAsNonRoot": config.security_context.run_as_non_root,
                "readOnlyRootFilesystem": config.security_context.read_only_root_filesystem,
                "allowPrivilegeEscalation": config.security_context.allow_privilege_escalation,
            },
        }

        if config.env_vars:
            container_spec["env"] = [{"name": k, "value": v} for k, v in config.env_vars.items()]

        job_spec: Dict[str, Any] = {
            "template": {
                "metadata": {"labels": base_labels},
                "spec": {
                    "containers": [container_spec],
                    "restartPolicy": "OnFailure",
                },
            },
        }

        if config.workload_type == WorkloadType.JOB:
            return {
                "apiVersion": "batch/v1",
                "kind": "Job",
                "metadata": {
                    "name": config.name,
                    "namespace": config.namespace,
                    "labels": base_labels,
                    "annotations": config.annotations,
                },
                "spec": job_spec,
            }
        else:
            return {
                "apiVersion": "batch/v1",
                "kind": "CronJob",
                "metadata": {
                    "name": config.name,
                    "namespace": config.namespace,
                    "labels": base_labels,
                    "annotations": config.annotations,
                },
                "spec": {
                    "schedule": config.cron_schedule or "0 0 * * *",
                    "jobTemplate": {"spec": job_spec},
                },
            }

    def _generate_service(self, config: ManifestConfig, base_labels: Dict[str, str]) -> Dict[str, Any]:
        """Generate Service manifest."""
        return {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {
                "name": f"{config.name}-service",
                "namespace": config.namespace,
                "labels": base_labels,
                "annotations": config.annotations,
            },
            "spec": {
                "selector": {"app": config.name},
                "ports": [
                    {
                        "name": port.name,
                        "port": port.service_port or port.container_port,
                        "targetPort": port.container_port,
                        "protocol": port.protocol,
                    }
                    for port in config.ports
                ],
                "type": "ClusterIP",
            },
        }

    def _generate_configmap(
        self, config: ManifestConfig, base_labels: Dict[str, str], cm_name: str
    ) -> Dict[str, Any]:
        """Generate ConfigMap manifest."""
        return {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {
                "name": cm_name,
                "namespace": config.namespace,
                "labels": base_labels,
                "annotations": config.annotations,
            },
            "data": {
                "example.conf": f"# Configuration for {config.name}\napp_name: {config.name}\nenvironment: {config.environment.value}\n",
            },
        }

    def _generate_secret(
        self, config: ManifestConfig, base_labels: Dict[str, str], secret_name: str
    ) -> Dict[str, Any]:
        """Generate Secret manifest."""
        return {
            "apiVersion": "v1",
            "kind": "Secret",
            "metadata": {
                "name": secret_name,
                "namespace": config.namespace,
                "labels": base_labels,
                "annotations": config.annotations,
            },
            "type": "Opaque",
            "data": {},
        }

    def _generate_network_policy(self, config: ManifestConfig, base_labels: Dict[str, str]) -> Dict[str, Any]:
        """Generate NetworkPolicy for enhanced security."""
        ingress_ports = [
            {"protocol": port.protocol, "port": port.container_port}
            for port in config.ports
        ]

        return {
            "apiVersion": "networking.k8s.io/v1",
            "kind": "NetworkPolicy",
            "metadata": {
                "name": f"{config.name}-network-policy",
                "namespace": config.namespace,
                "labels": base_labels,
            },
            "spec": {
                "podSelector": {"matchLabels": {"app": config.name}},
                "policyTypes": ["Ingress", "Egress"],
                "ingress": [
                    {
                        "from": [{"namespaceSelector": {"matchLabels": {"name": config.namespace}}}],
                        "ports": ingress_ports,
                    }
                ],
                "egress": [
                    {
                        "to": [],
                        "ports": [
                            {"protocol": "TCP", "port": 53},
                            {"protocol": "UDP", "port": 53},
                        ],
                    }
                ],
            },
        }

    def _generate_pdb(self, config: ManifestConfig, base_labels: Dict[str, str]) -> Dict[str, Any]:
        """Generate PodDisruptionBudget manifest."""
        return {
            "apiVersion": "policy/v1",
            "kind": "PodDisruptionBudget",
            "metadata": {
                "name": f"{config.name}-pdb",
                "namespace": config.namespace,
                "labels": base_labels,
            },
            "spec": {
                "selector": {"matchLabels": {"app": config.name}},
                "minAvailable": max(1, config.replicas // 2),
            },
        }

    def _validate_manifests(
        self, manifests: Dict[str, Dict[str, Any]], config: ManifestConfig
    ) -> List[str]:
        """Validate generated manifests for common issues."""
        issues: List[str] = []

        workload_kinds = ["Deployment", "StatefulSet", "DaemonSet"]
        workload_manifest = next(
            (m for m in manifests.values() if m.get("kind") in workload_kinds), None
        )

        if workload_manifest:
            containers = (
                workload_manifest.get("spec", {})
                .get("template", {})
                .get("spec", {})
                .get("containers", [])
            )
            for container in containers:
                resources = container.get("resources", {})
                if not resources.get("limits"):
                    issues.append(f"Container {container.get('name')} missing resource limits")
                if not resources.get("requests"):
                    issues.append(f"Container {container.get('name')} missing resource requests")

        if config.security_profile in [SecurityProfile.ENHANCED, SecurityProfile.STRICT, SecurityProfile.ZERO_TRUST]:
            if workload_manifest:
                containers = (
                    workload_manifest.get("spec", {})
                    .get("template", {})
                    .get("spec", {})
                    .get("containers", [])
                )
                for container in containers:
                    sec_ctx = container.get("securityContext", {})
                    if not sec_ctx.get("runAsNonRoot"):
                        issues.append(f"Container {container.get('name')} not configured to run as non-root")
                    if not sec_ctx.get("readOnlyRootFilesystem"):
                        issues.append(f"Container {container.get('name')} not using read-only root filesystem")

        if workload_manifest:
            containers = (
                workload_manifest.get("spec", {})
                .get("template", {})
                .get("spec", {})
                .get("containers", [])
            )
            for container in containers:
                if not container.get("livenessProbe"):
                    issues.append(f"Container {container.get('name')} missing liveness probe")
                if not container.get("readinessProbe"):
                    issues.append(f"Container {container.get('name')} missing readiness probe")

        return issues

    def _calculate_best_practice_score(
        self, manifests: Dict[str, Dict[str, Any]], config: ManifestConfig
    ) -> float:
        """Calculate a best practice score for the generated manifests."""
        score = 0.0
        max_score = 0.0

        workload_kinds = ["Deployment", "StatefulSet", "DaemonSet"]
        workload_manifest = next(
            (m for m in manifests.values() if m.get("kind") in workload_kinds), None
        )

        if workload_manifest:
            containers = (
                workload_manifest.get("spec", {})
                .get("template", {})
                .get("spec", {})
                .get("containers", [])
            )

            for container in containers:
                max_score += 20
                resources = container.get("resources", {})
                if resources.get("limits") and resources.get("requests"):
                    score += 20
                elif resources.get("limits") or resources.get("requests"):
                    score += 10

                max_score += 25
                sec_ctx = container.get("securityContext", {})
                if sec_ctx.get("runAsNonRoot"):
                    score += 8
                if sec_ctx.get("readOnlyRootFilesystem"):
                    score += 8
                if not sec_ctx.get("allowPrivilegeEscalation", True):
                    score += 9

                max_score += 20
                if container.get("livenessProbe"):
                    score += 10
                if container.get("readinessProbe"):
                    score += 10

        max_score += 15
        if any("networkpolicy" in name for name in manifests.keys()):
            score += 15

        max_score += 10
        if any("service" in name for name in manifests.keys()):
            score += 10

        max_score += 10
        if config.environment == EnvironmentType.PRODUCTION:
            if any("poddisruptionbudget" in name for name in manifests.keys()):
                score += 10
        else:
            score += 10

        return (score / max_score) * 100 if max_score > 0 else 0.0

    def save_to_file(self, manifest: GeneratedManifest, output_dir: Optional[str] = None) -> str:
        """
        Save generated manifest YAML to file.

        Args:
            manifest: Generated manifest to save
            output_dir: Override output directory

        Returns:
            Path to the saved file
        """
        target_dir = output_dir or self.output_dir
        os.makedirs(target_dir, exist_ok=True)
        file_path = os.path.join(target_dir, f"{manifest.id}.yaml")

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(manifest.yaml_content)

        return file_path
