"""
Kubernetes Manifest Generator Service — secure by default.

Every workload kind renders the SAME maximally-hardened template
(NSA/CISA + CIS 5.x static control matrix). SecurityProfile is a
suppression preset, never an alternate template; deviations are only
possible through reified suppressions (rule, target, reason) that leave
machine-readable receipts on the rendered objects.

Scoring and validation are fully delegated to the adversarial
``Asgard.Volundr.Validation`` engine — the generator never grades its
own intent, only hands over the rendered YAML.
"""

import hashlib
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import yaml  # type: ignore[import-untyped]

from Asgard.Volundr.Kubernetes.models.kubernetes_models import (
    GeneratedManifest,
    ManifestConfig,
    SecurityProfile,
    WorkloadType,
)
from Asgard.Volundr.Kubernetes.services.manifest_generator_helpers import (
    generate_configmap,
    generate_headless_service,
    generate_network_policy,
    generate_pdb,
    generate_secret,
    generate_service,
    generate_service_account,
)
from Asgard.Volundr.Validation.models.suppression_models import (
    Suppression,
    SuppressionSet,
)
from Asgard.Volundr.Validation.models.validation_models import (
    ValidationCategory,
    ValidationContext,
    ValidationReport,
    ValidationResult,
    ValidationSeverity,
)
from Asgard.Volundr.Validation.services.suppression_engine import (
    SuppressionEngine,
    annotate_k8s_manifest,
)
from Asgard.Volundr.Validation.services.schema_binder import parse_version
from Asgard.Volundr.Validation.services.validation_engine import ValidationEngine

#: Profile -> rule IDs pre-suppressed by that preset. All presets render the
#: identical hardened template; presets only annihilate completeness findings
#: the generator cannot resolve on its own (and receipts stay visible).
PROFILE_PRESET_RULES: Dict[SecurityProfile, List[str]] = {
    SecurityProfile.BASIC: ["VOL-K8S-0013", "VOL-K8S-0014", "VOL-K8S-0015"],
    SecurityProfile.ENHANCED: ["VOL-K8S-0013", "VOL-K8S-0015"],
    SecurityProfile.STRICT: ["VOL-K8S-0013"],
    SecurityProfile.ZERO_TRUST: [],
}


def preset_suppressions(profile: SecurityProfile) -> List[Suppression]:
    """A SecurityProfile reified as a suppression preset (DEEPTHINK_02)."""
    return [
        Suppression(
            rule=rule,
            target="*",
            reason=f"preset:{profile.value} — profile-level acceptance of this completeness gap",
        )
        for rule in PROFILE_PRESET_RULES.get(profile, [])
    ]


class ManifestGenerator:
    """Generates hardened Kubernetes manifests from configuration."""

    def __init__(self, output_dir: Optional[str] = None):
        self.output_dir = output_dir or "manifests"

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def generate(self, config: ManifestConfig) -> GeneratedManifest:
        config_json = config.model_dump_json()
        config_hash = hashlib.sha256(config_json.encode()).hexdigest()[:16]
        manifest_id = f"{config.name}-{config_hash}"

        manifests: Dict[str, Dict[str, Any]] = {}

        base_labels = {
            "app": config.name,
            "version": "v1",
            "environment": config.environment.value,
            "app.kubernetes.io/name": config.name,
            "app.kubernetes.io/instance": config.name,
            "app.kubernetes.io/managed-by": "volundr",
            **config.labels,
        }

        completeness: List[ValidationResult] = []

        # Dedicated ServiceAccount (CIS 5.1.5/5.1.6) — always, unless the
        # user points at an existing one.
        if config.service_account is None:
            manifests["serviceaccount"] = generate_service_account(config, base_labels)

        workload_key = config.workload_type.value.lower()
        if config.workload_type in [WorkloadType.DEPLOYMENT, WorkloadType.STATEFULSET, WorkloadType.DAEMONSET]:
            manifests[workload_key] = self._generate_workload(config, base_labels)
        elif config.workload_type in [WorkloadType.JOB, WorkloadType.CRONJOB]:
            manifests[workload_key] = self._generate_job(config, base_labels)

        if config.ports:
            manifests["service"] = generate_service(config, base_labels)

        if config.workload_type == WorkloadType.STATEFULSET:
            manifests["service-headless"] = generate_headless_service(config, base_labels)

        for cm_name in config.config_maps:
            manifests[f"configmap-{cm_name}"] = generate_configmap(config, base_labels, cm_name)

        for secret_name in config.secrets:
            secret = generate_secret(config, base_labels, secret_name)
            manifests[f"secret-{secret_name}"] = secret
            if not secret.get("stringData"):
                completeness.append(ValidationResult(
                    rule_id="VOL-K8S-0014",
                    message=(
                        f"Secret '{secret_name}' has no stringData — the generator "
                        "will not fabricate secret material; populate it out-of-band"
                    ),
                    severity=ValidationSeverity.INFO,
                    category=ValidationCategory.BEST_PRACTICE,
                    resource_kind="Secret",
                    resource_name=secret_name,
                    context={"target": secret_name},
                ))

        # Always-on companions: default-deny NetworkPolicy; PDB when it can help.
        manifests["networkpolicy"] = generate_network_policy(config, base_labels)

        if config.replicas > 1 and config.pdb.enabled:
            manifests["poddisruptionbudget"] = generate_pdb(config, base_labels)
            if config.pdb.min_available is None and config.pdb.max_unavailable is None:
                completeness.append(ValidationResult(
                    rule_id="VOL-K8S-0015",
                    message=(
                        f"PDB for '{config.name}' defaulted minAvailable to "
                        f"{max(1, config.replicas // 2)} — the generator cannot know "
                        "the workload's real availability requirement"
                    ),
                    severity=ValidationSeverity.HINT,
                    category=ValidationCategory.RELIABILITY,
                    resource_kind="PodDisruptionBudget",
                    resource_name=f"{config.name}-pdb",
                    context={"target": config.name},
                ))

        if config.image_digest is None:
            completeness.append(ValidationResult(
                rule_id="VOL-K8S-0013",
                message=(
                    f"Image '{config.image}' is pinned by tag, not digest — provide "
                    "image_digest (sha256:...) for immutable supply-chain pinning"
                ),
                severity=ValidationSeverity.WARNING,
                category=ValidationCategory.BEST_PRACTICE,
                resource_kind=config.workload_type.value,
                resource_name=config.name,
                context={"target": config.name, "container": config.name},
            ))

        # ------------------------------------------------------------------
        # Adversarial validation + reified suppressions
        # ------------------------------------------------------------------
        yaml_content = self._dump(manifests)

        engine = ValidationEngine(
            context=ValidationContext(kubernetes_version=config.target_k8s_version),
        )
        raw_report = engine.validate_kubernetes(yaml_content, source=f"{config.name}.yaml")
        findings = list(raw_report.results) + completeness

        # 1) user suppressions: full hygiene contract (stale/expired/unknown).
        user_engine = SuppressionEngine(SuppressionSet(suppressions=config.suppressions))
        user_outcome = user_engine.apply(findings)
        # 2) profile preset: hygiene discarded (presets are static code, a
        #    non-firing preset rule is expected, not stale).
        preset = preset_suppressions(config.security_profile)
        preset_engine = SuppressionEngine(SuppressionSet(suppressions=preset))
        preset_outcome = preset_engine.apply(user_outcome.results)

        final_results = preset_outcome.results + user_outcome.hygiene
        applied = user_outcome.applied + preset_outcome.applied

        # Receipts on the workload object (the primary artifact).
        if applied:
            workload_manifest = manifests.get(workload_key)
            if workload_manifest is not None:
                annotate_k8s_manifest(
                    workload_manifest, [s for s, _ in applied]
                )
            yaml_content = self._dump(manifests)

        errors = sum(1 for r in final_results if r.severity == ValidationSeverity.ERROR)
        warns = sum(1 for r in final_results if r.severity == ValidationSeverity.WARNING)
        infos = sum(1 for r in final_results if r.severity == ValidationSeverity.INFO)
        score = max(0.0, 100.0 - errors * 10 - warns * 3 - infos * 1)

        report = raw_report.model_copy(update={
            "results": final_results,
            "total_errors": errors,
            "total_warnings": warns,
            "total_info": infos,
            "passed": errors == 0,
            "score": score,
        })

        return GeneratedManifest(
            id=manifest_id,
            config_hash=config_hash,
            manifests=manifests,
            yaml_content=yaml_content,
            validation_results=[f"{r.rule_id}: {r.message}" for r in final_results],
            best_practice_score=score,
            created_at=datetime.now(),
            applied_suppressions=sorted({s.rule for s, _ in applied}),
            validation_report=report,
        )

    @staticmethod
    def _dump(manifests: Dict[str, Dict[str, Any]]) -> str:
        return "---\n".join(
            yaml.dump(m, default_flow_style=False, sort_keys=False)
            for m in manifests.values()
        )

    # ------------------------------------------------------------------
    # Unified pod spec (all five workload kinds share the full matrix)
    # ------------------------------------------------------------------

    def _pinned_image(self, config: ManifestConfig) -> str:
        if not config.image_digest:
            return config.image
        repo = config.image.split("@", 1)[0]
        head, _, tail = repo.rpartition("/")
        if ":" in tail:
            tail = tail.split(":", 1)[0]
        repo = f"{head}/{tail}" if head else tail
        digest = config.image_digest
        if not digest.startswith("sha256:"):
            digest = f"sha256:{digest}"
        return f"{repo}@{digest}"

    def _build_pod_spec(
        self, config: ManifestConfig, for_job: bool
    ) -> Tuple[Dict[str, Any], Dict[str, str]]:
        """Build the hardened PodSpec shared by every workload kind.

        Returns (pod_spec, extra_template_annotations).
        """
        sc = config.security_context

        container_spec: Dict[str, Any] = {
            "name": config.name,
            "image": self._pinned_image(config),
            "imagePullPolicy": "Always",
        }

        if not for_job and config.ports:
            container_spec["ports"] = [
                {"name": p.name, "containerPort": p.container_port, "protocol": p.protocol}
                for p in config.ports
            ]

        container_spec["resources"] = {
            "requests": {"cpu": config.resources.cpu_request, "memory": config.resources.memory_request},
            "limits": {"cpu": config.resources.cpu_limit, "memory": config.resources.memory_limit},
        }

        container_sc: Dict[str, Any] = {
            "runAsUser": sc.run_as_user,
            "runAsGroup": sc.run_as_group,
            "runAsNonRoot": sc.run_as_non_root,
            "readOnlyRootFilesystem": sc.read_only_root_filesystem,
            "allowPrivilegeEscalation": sc.allow_privilege_escalation,
            "privileged": sc.privileged,
            "capabilities": {"drop": sc.drop_capabilities},
            "seccompProfile": {"type": sc.seccomp_profile},
        }
        if sc.add_capabilities:
            container_sc["capabilities"]["add"] = sc.add_capabilities
        container_spec["securityContext"] = container_sc

        if config.env_vars:
            container_spec["env"] = [{"name": k, "value": v} for k, v in config.env_vars.items()]

        if not for_job:
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

        volume_mounts: List[Dict[str, Any]] = []
        volumes: List[Dict[str, Any]] = []

        for volume in config.volumes:
            volumes.append(volume)
            if "mountPath" in volume:
                volume_mounts.append({
                    "name": volume["name"],
                    "mountPath": volume["mountPath"],
                    "readOnly": volume.get("readOnly", False),
                })

        # Auto emptyDir for writable paths with a read-only root filesystem
        # (RESEARCH_03 "Immutable Root Filesystems" edge case).
        if sc.read_only_root_filesystem:
            mounted = {m.get("mountPath") for m in volume_mounts}
            for i, path in enumerate(config.writable_paths):
                if path in mounted:
                    continue
                sanitized = path.strip("/").replace("/", "-").replace("_", "-") or f"writable-{i}"
                vol_name = f"volundr-writable-{sanitized}"
                volumes.append({"name": vol_name, "emptyDir": {}})
                volume_mounts.append({"name": vol_name, "mountPath": path})

        if volume_mounts:
            container_spec["volumeMounts"] = volume_mounts

        pod_sc: Dict[str, Any] = {
            "runAsNonRoot": sc.run_as_non_root,
            "fsGroup": config.fs_group,
            "seccompProfile": {"type": "RuntimeDefault"},
        }
        if config.fs_group_change_policy:
            pod_sc["fsGroupChangePolicy"] = config.fs_group_change_policy

        extra_annotations: Dict[str, str] = {}
        if config.apparmor:
            profile = sc.apparmor_profile
            if parse_version(config.target_k8s_version) >= (1, 30):
                pod_sc["appArmorProfile"] = {"type": profile}
            else:
                # Annotation fallback for clusters < 1.30.
                legacy = "runtime/default" if profile == "RuntimeDefault" else profile
                extra_annotations[
                    f"container.apparmor.security.beta.kubernetes.io/{config.name}"
                ] = legacy

        pod_spec: Dict[str, Any] = {
            "automountServiceAccountToken": config.automount_service_account_token,
            "serviceAccountName": config.service_account or config.name,
            "containers": [container_spec],
            "securityContext": pod_sc,
        }
        if config.tolerations:
            pod_spec["tolerations"] = config.tolerations
        if config.affinity:
            pod_spec["affinity"] = config.affinity
        if volumes:
            pod_spec["volumes"] = volumes
        if for_job:
            pod_spec["restartPolicy"] = "OnFailure"

        return pod_spec, extra_annotations

    def _template_metadata(
        self, config: ManifestConfig, base_labels: Dict[str, str], extra: Dict[str, str]
    ) -> Dict[str, Any]:
        return {
            "labels": base_labels,
            "annotations": {**config.annotations, **extra},
        }

    def _generate_workload(self, config: ManifestConfig, base_labels: Dict[str, str]) -> Dict[str, Any]:
        pod_spec, extra = self._build_pod_spec(config, for_job=False)

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
                    "metadata": self._template_metadata(config, base_labels, extra),
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
        pod_spec, extra = self._build_pod_spec(config, for_job=True)

        job_spec: Dict[str, Any] = {
            "template": {
                "metadata": self._template_metadata(config, base_labels, extra),
                "spec": pod_spec,
            },
        }

        metadata = {
            "name": config.name,
            "namespace": config.namespace,
            "labels": base_labels,
            "annotations": config.annotations,
        }
        if config.workload_type == WorkloadType.JOB:
            return {
                "apiVersion": "batch/v1",
                "kind": "Job",
                "metadata": metadata,
                "spec": job_spec,
            }
        return {
            "apiVersion": "batch/v1",
            "kind": "CronJob",
            "metadata": metadata,
            "spec": {
                "schedule": config.cron_schedule or "0 0 * * *",
                "jobTemplate": {"spec": job_spec},
            },
        }

    def save_to_file(self, manifest: GeneratedManifest, output_dir: Optional[str] = None) -> str:
        target_dir = output_dir or self.output_dir
        os.makedirs(target_dir, exist_ok=True)
        file_path = os.path.join(target_dir, f"{manifest.id}.yaml")

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(manifest.yaml_content)

        return file_path
