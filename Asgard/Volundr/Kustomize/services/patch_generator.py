"""
Kustomize Patch Generator Service

Generates strategic merge patches and JSON6902 patches
for Kustomize overlays.
"""

import hashlib
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

import yaml  # type: ignore[import-untyped]

from Asgard.Volundr.Kustomize.models.kustomize_models import (
    GeneratedKustomization,
    JsonPatchOperation,
    KustomizePatch,
    PatchTarget,
    PatchType,
)
from Asgard.Volundr.Kustomize.services.patch_generator_helpers import (
    build_annotation_patch,
    build_env_patch,
    build_image_patch,
    build_json6902_patch,
    build_label_patch,
    build_probe_patch,
    build_replica_patch,
    build_resource_patch,
    build_security_context_patch,
    build_strategic_merge_patch,
)


class PatchGenerator:
    """Generates Kustomize patches."""

    def __init__(self, output_dir: Optional[str] = None):
        self.output_dir = output_dir or "kustomize/patches"

    def generate_strategic_merge_patch(
        self,
        name: str,
        kind: str,
        api_version: str,
        resource_name: str,
        spec_overrides: Dict[str, Any],
        metadata_overrides: Optional[Dict[str, Any]] = None,
    ) -> str:
        return build_strategic_merge_patch(
            kind=kind,
            api_version=api_version,
            resource_name=resource_name,
            spec_overrides=spec_overrides,
            metadata_overrides=metadata_overrides,
        )

    def generate_json6902_patch(
        self,
        target: PatchTarget,
        operations: List[JsonPatchOperation],
    ) -> Dict[str, Any]:
        return build_json6902_patch(target, operations)

    def generate_replica_patch(
        self,
        resource_name: str,
        replicas: int,
        kind: str = "Deployment",
    ) -> str:
        return build_replica_patch(resource_name, replicas, kind)

    def generate_resource_patch(
        self,
        resource_name: str,
        container_name: str,
        cpu_request: str = "100m",
        cpu_limit: str = "500m",
        memory_request: str = "128Mi",
        memory_limit: str = "512Mi",
        kind: str = "Deployment",
    ) -> str:
        return build_resource_patch(
            resource_name, container_name,
            cpu_request, cpu_limit, memory_request, memory_limit, kind,
        )

    def generate_image_patch(
        self,
        resource_name: str,
        container_name: str,
        image: str,
        kind: str = "Deployment",
    ) -> str:
        return build_image_patch(resource_name, container_name, image, kind)

    def generate_env_patch(
        self,
        resource_name: str,
        container_name: str,
        env_vars: Dict[str, str],
        kind: str = "Deployment",
    ) -> str:
        return build_env_patch(resource_name, container_name, env_vars, kind)

    def generate_annotation_patch(
        self,
        resource_name: str,
        annotations: Dict[str, str],
        kind: str = "Deployment",
        api_version: str = "apps/v1",
        pod_annotations: bool = True,
    ) -> str:
        return build_annotation_patch(
            resource_name, annotations, kind, api_version, pod_annotations
        )

    def generate_label_patch(
        self,
        resource_name: str,
        labels: Dict[str, str],
        kind: str = "Deployment",
        api_version: str = "apps/v1",
        pod_labels: bool = True,
    ) -> str:
        return build_label_patch(resource_name, labels, kind, api_version, pod_labels)

    def generate_security_context_patch(
        self,
        resource_name: str,
        container_name: str,
        run_as_non_root: bool = True,
        run_as_user: int = 1000,
        run_as_group: int = 3000,
        read_only_root_filesystem: bool = True,
        allow_privilege_escalation: bool = False,
        drop_capabilities: Optional[List[str]] = None,
        kind: str = "Deployment",
    ) -> str:
        if drop_capabilities is None:
            drop_capabilities = ["ALL"]

        return build_security_context_patch(
            resource_name, container_name,
            run_as_non_root, run_as_user, run_as_group,
            read_only_root_filesystem, allow_privilege_escalation,
            drop_capabilities, kind,
        )

    def generate_probe_patch(
        self,
        resource_name: str,
        container_name: str,
        liveness_path: str = "/health",
        readiness_path: str = "/ready",
        port: Union[int, str] = "http",
        initial_delay: int = 10,
        period: int = 10,
        kind: str = "Deployment",
    ) -> str:
        return build_probe_patch(
            resource_name, container_name,
            liveness_path, readiness_path, port, initial_delay, period, kind,
        )

    def generate_batch(
        self, patches: List[KustomizePatch]
    ) -> GeneratedKustomization:
        files: Dict[str, str] = {}
        all_issues: List[str] = []

        for patch in patches:
            if patch.patch_type == PatchType.STRATEGIC_MERGE and patch.patch_content:
                files[f"{patch.name}.yaml"] = patch.patch_content
            elif patch.patch_type == PatchType.JSON6902 and patch.target and patch.operations:
                patch_config = build_json6902_patch(patch.target, patch.operations)
                files[f"{patch.name}.yaml"] = yaml.dump(
                    patch_config, default_flow_style=False, sort_keys=False
                )

        config_hash = hashlib.sha256(str(files).encode()).hexdigest()[:16]

        return GeneratedKustomization(
            id=f"patches-{config_hash}",
            config_hash=config_hash,
            files=files,
            validation_results=all_issues,
            best_practice_score=100.0 if files else 0.0,
            created_at=datetime.now(),
        )
