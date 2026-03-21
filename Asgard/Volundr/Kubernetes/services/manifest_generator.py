"""
Kubernetes Manifest Generator Service

Generates comprehensive Kubernetes manifests for various workloads
with best practices, security configurations, and operational readiness.
"""

import hashlib
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import yaml  # type: ignore[import-untyped]

from Asgard.Volundr.Kubernetes.models.kubernetes_models import (
    EnvironmentType,
    GeneratedManifest,
    ManifestConfig,
    SecurityProfile,
    WorkloadType,
)
from Asgard.Volundr.Kubernetes.services.manifest_generator_helpers import (
    calculate_best_practice_score,
    generate_configmap,
    generate_network_policy,
    generate_pdb,
    generate_secret,
    generate_service,
    validate_manifests,
)


class ManifestGenerator:
    """Generates Kubernetes manifests from configuration."""

    def __init__(self, output_dir: Optional[str] = None):
        self.output_dir = output_dir or "manifests"

    def generate(self, config: ManifestConfig) -> GeneratedManifest:
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
            manifests["service"] = generate_service(config, base_labels)

        for cm_name in config.config_maps:
            manifests[f"configmap-{cm_name}"] = generate_configmap(config, base_labels, cm_name)

        for secret_name in config.secrets:
            manifests[f"secret-{secret_name}"] = generate_secret(config, base_labels, secret_name)

        if config.security_profile in [SecurityProfile.ENHANCED, SecurityProfile.STRICT, SecurityProfile.ZERO_TRUST]:
            manifests["networkpolicy"] = generate_network_policy(config, base_labels)

        if config.environment == EnvironmentType.PRODUCTION and config.replicas > 1:
            manifests["poddisruptionbudget"] = generate_pdb(config, base_labels)

        yaml_docs = []
        for manifest in manifests.values():
            yaml_docs.append(yaml.dump(manifest, default_flow_style=False, sort_keys=False))

        yaml_content = "---\n".join(yaml_docs)

        validation_results = validate_manifests(manifests, config)
        best_practice_score = calculate_best_practice_score(manifests, config)

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
        ports_list = [
            {"name": p.name, "containerPort": p.container_port, "protocol": p.protocol}
            for p in config.ports
        ]

        container_spec: Dict[str, Any] = {
            "name": config.name,
            "image": config.image,
            "ports": ports_list,
            "resources": {
                "requests": {"cpu": config.resources.cpu_request, "memory": config.resources.memory_request},
                "limits": {"cpu": config.resources.cpu_limit, "memory": config.resources.memory_limit},
            },
            "securityContext": {
                "runAsUser": config.security_context.run_as_user,
                "runAsGroup": config.security_context.run_as_group,
                "runAsNonRoot": config.security_context.run_as_non_root,
                "readOnlyRootFilesystem": config.security_context.read_only_root_filesystem,
                "allowPrivilegeEscalation": config.security_context.allow_privilege_escalation,
                "capabilities": {"drop": config.security_context.drop_capabilities},
            },
        }

        if config.security_context.add_capabilities:
            container_spec["securityContext"]["capabilities"]["add"] = config.security_context.add_capabilities

        if config.env_vars:
            container_spec["env"] = [{"name": k, "value": v} for k, v in config.env_vars.items()]

        if config.liveness_probe.enabled:
            container_spec["livenessProbe"] = {
                "httpGet": {"path": config.liveness_probe.http_path, "port": config.liveness_probe.http_port},
                "initialDelaySeconds": config.liveness_probe.initial_delay_seconds,
                "periodSeconds": config.liveness_probe.period_seconds,
                "timeoutSeconds": config.liveness_probe.timeout_seconds,
                "failureThreshold": config.liveness_probe.failure_threshold,
            }

        if config.readiness_probe.enabled:
            container_spec["readinessProbe"] = {
                "httpGet": {"path": config.readiness_probe.http_path, "port": config.readiness_probe.http_port},
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
            "securityContext": {"fsGroup": 2000, "seccompProfile": {"type": "RuntimeDefault"}},
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
                "selector": {"matchLabels": {"app": config.name}},
                "template": {
                    "metadata": {"labels": base_labels, "annotations": config.annotations},
                    "spec": pod_spec,
                },
            },
        }

        if config.workload_type == WorkloadType.DEPLOYMENT:
            manifest["spec"]["replicas"] = config.replicas
            manifest["spec"]["strategy"] = {
                "type": "RollingUpdate",
                "rollingUpdate": {"maxUnavailable": "25%", "maxSurge": "25%"},
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
        container_spec: Dict[str, Any] = {
            "name": config.name,
            "image": config.image,
            "resources": {
                "requests": {"cpu": config.resources.cpu_request, "memory": config.resources.memory_request},
                "limits": {"cpu": config.resources.cpu_limit, "memory": config.resources.memory_limit},
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
                "spec": {"containers": [container_spec], "restartPolicy": "OnFailure"},
            },
        }

        if config.workload_type == WorkloadType.JOB:
            return {
                "apiVersion": "batch/v1",
                "kind": "Job",
                "metadata": {"name": config.name, "namespace": config.namespace, "labels": base_labels, "annotations": config.annotations},
                "spec": job_spec,
            }
        else:
            return {
                "apiVersion": "batch/v1",
                "kind": "CronJob",
                "metadata": {"name": config.name, "namespace": config.namespace, "labels": base_labels, "annotations": config.annotations},
                "spec": {"schedule": config.cron_schedule or "0 0 * * *", "jobTemplate": {"spec": job_spec}},
            }

    def save_to_file(self, manifest: GeneratedManifest, output_dir: Optional[str] = None) -> str:
        target_dir = output_dir or self.output_dir
        os.makedirs(target_dir, exist_ok=True)
        file_path = os.path.join(target_dir, f"{manifest.id}.yaml")

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(manifest.yaml_content)

        return file_path
