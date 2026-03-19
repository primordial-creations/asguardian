"""
Kustomize Patch Generator Service

Generates strategic merge patches and JSON6902 patches
for Kustomize overlays.
"""

import hashlib
from datetime import datetime
from typing import Any, Dict, List, Optional, Union, cast

import yaml  # type: ignore[import-untyped]

from Asgard.Volundr.Kustomize.models.kustomize_models import (
    GeneratedKustomization,
    KustomizePatch,
    PatchType,
    PatchTarget,
    JsonPatchOperation,
)


class PatchGenerator:
    """Generates Kustomize patches."""

    def __init__(self, output_dir: Optional[str] = None):
        """
        Initialize the patch generator.

        Args:
            output_dir: Directory for saving generated patches
        """
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
        """
        Generate a strategic merge patch.

        Args:
            name: Patch file name
            kind: Resource kind (e.g., Deployment, Service)
            api_version: API version (e.g., apps/v1)
            resource_name: Name of the resource to patch
            spec_overrides: Spec fields to override
            metadata_overrides: Metadata fields to override

        Returns:
            YAML string of the patch
        """
        patch: Dict[str, Any] = {
            "apiVersion": api_version,
            "kind": kind,
            "metadata": {"name": resource_name},
        }

        if metadata_overrides:
            patch["metadata"].update(metadata_overrides)

        if spec_overrides:
            patch["spec"] = spec_overrides

        return cast(str, yaml.dump(patch, default_flow_style=False, sort_keys=False))

    def generate_json6902_patch(
        self,
        target: PatchTarget,
        operations: List[JsonPatchOperation],
    ) -> Dict[str, Any]:
        """
        Generate a JSON6902 patch configuration.

        Args:
            target: Target resource for the patch
            operations: List of patch operations

        Returns:
            Dictionary containing patch configuration
        """
        patch_config: Dict[str, Any] = {
            "target": {
                "kind": target.kind,
                "name": target.name,
                "version": target.version,
            },
            "patch": [
                {"op": op.op, "path": op.path, "value": op.value}
                if op.value is not None
                else {"op": op.op, "path": op.path}
                for op in operations
            ],
        }

        if target.group:
            patch_config["target"]["group"] = target.group

        if target.namespace:
            patch_config["target"]["namespace"] = target.namespace

        return patch_config

    def generate_replica_patch(
        self,
        resource_name: str,
        replicas: int,
        kind: str = "Deployment",
    ) -> str:
        """
        Generate a replica count patch.

        Args:
            resource_name: Name of the deployment/statefulset
            replicas: Desired replica count
            kind: Resource kind (Deployment or StatefulSet)

        Returns:
            YAML string of the patch
        """
        return self.generate_strategic_merge_patch(
            name=f"{resource_name}-replicas",
            kind=kind,
            api_version="apps/v1",
            resource_name=resource_name,
            spec_overrides={"replicas": replicas},
        )

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
        """
        Generate a resource limits/requests patch.

        Args:
            resource_name: Name of the deployment/statefulset
            container_name: Name of the container
            cpu_request: CPU request
            cpu_limit: CPU limit
            memory_request: Memory request
            memory_limit: Memory limit
            kind: Resource kind

        Returns:
            YAML string of the patch
        """
        return self.generate_strategic_merge_patch(
            name=f"{resource_name}-resources",
            kind=kind,
            api_version="apps/v1",
            resource_name=resource_name,
            spec_overrides={
                "template": {
                    "spec": {
                        "containers": [
                            {
                                "name": container_name,
                                "resources": {
                                    "requests": {
                                        "cpu": cpu_request,
                                        "memory": memory_request,
                                    },
                                    "limits": {
                                        "cpu": cpu_limit,
                                        "memory": memory_limit,
                                    },
                                },
                            }
                        ]
                    }
                }
            },
        )

    def generate_image_patch(
        self,
        resource_name: str,
        container_name: str,
        image: str,
        kind: str = "Deployment",
    ) -> str:
        """
        Generate an image override patch.

        Args:
            resource_name: Name of the deployment/statefulset
            container_name: Name of the container
            image: New container image
            kind: Resource kind

        Returns:
            YAML string of the patch
        """
        return self.generate_strategic_merge_patch(
            name=f"{resource_name}-image",
            kind=kind,
            api_version="apps/v1",
            resource_name=resource_name,
            spec_overrides={
                "template": {
                    "spec": {
                        "containers": [
                            {
                                "name": container_name,
                                "image": image,
                            }
                        ]
                    }
                }
            },
        )

    def generate_env_patch(
        self,
        resource_name: str,
        container_name: str,
        env_vars: Dict[str, str],
        kind: str = "Deployment",
    ) -> str:
        """
        Generate an environment variable patch.

        Args:
            resource_name: Name of the deployment/statefulset
            container_name: Name of the container
            env_vars: Environment variables to set
            kind: Resource kind

        Returns:
            YAML string of the patch
        """
        env_list = [{"name": k, "value": v} for k, v in env_vars.items()]

        return self.generate_strategic_merge_patch(
            name=f"{resource_name}-env",
            kind=kind,
            api_version="apps/v1",
            resource_name=resource_name,
            spec_overrides={
                "template": {
                    "spec": {
                        "containers": [
                            {
                                "name": container_name,
                                "env": env_list,
                            }
                        ]
                    }
                }
            },
        )

    def generate_annotation_patch(
        self,
        resource_name: str,
        annotations: Dict[str, str],
        kind: str = "Deployment",
        api_version: str = "apps/v1",
        pod_annotations: bool = True,
    ) -> str:
        """
        Generate an annotation patch.

        Args:
            resource_name: Name of the resource
            annotations: Annotations to add/update
            kind: Resource kind
            api_version: API version
            pod_annotations: Apply to pod template (for Deployments)

        Returns:
            YAML string of the patch
        """
        if pod_annotations and kind in ["Deployment", "StatefulSet", "DaemonSet"]:
            return self.generate_strategic_merge_patch(
                name=f"{resource_name}-annotations",
                kind=kind,
                api_version=api_version,
                resource_name=resource_name,
                spec_overrides={
                    "template": {
                        "metadata": {
                            "annotations": annotations,
                        }
                    }
                },
            )
        else:
            return self.generate_strategic_merge_patch(
                name=f"{resource_name}-annotations",
                kind=kind,
                api_version=api_version,
                resource_name=resource_name,
                spec_overrides={},
                metadata_overrides={"annotations": annotations},
            )

    def generate_label_patch(
        self,
        resource_name: str,
        labels: Dict[str, str],
        kind: str = "Deployment",
        api_version: str = "apps/v1",
        pod_labels: bool = True,
    ) -> str:
        """
        Generate a label patch.

        Args:
            resource_name: Name of the resource
            labels: Labels to add/update
            kind: Resource kind
            api_version: API version
            pod_labels: Apply to pod template (for Deployments)

        Returns:
            YAML string of the patch
        """
        if pod_labels and kind in ["Deployment", "StatefulSet", "DaemonSet"]:
            return self.generate_strategic_merge_patch(
                name=f"{resource_name}-labels",
                kind=kind,
                api_version=api_version,
                resource_name=resource_name,
                spec_overrides={
                    "template": {
                        "metadata": {
                            "labels": labels,
                        }
                    }
                },
            )
        else:
            return self.generate_strategic_merge_patch(
                name=f"{resource_name}-labels",
                kind=kind,
                api_version=api_version,
                resource_name=resource_name,
                spec_overrides={},
                metadata_overrides={"labels": labels},
            )

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
        """
        Generate a security context patch.

        Args:
            resource_name: Name of the deployment/statefulset
            container_name: Name of the container
            run_as_non_root: Require non-root user
            run_as_user: User ID to run as
            run_as_group: Group ID to run as
            read_only_root_filesystem: Make root filesystem read-only
            allow_privilege_escalation: Allow privilege escalation
            drop_capabilities: Capabilities to drop
            kind: Resource kind

        Returns:
            YAML string of the patch
        """
        if drop_capabilities is None:
            drop_capabilities = ["ALL"]

        security_context: Dict[str, Any] = {
            "runAsNonRoot": run_as_non_root,
            "runAsUser": run_as_user,
            "runAsGroup": run_as_group,
            "readOnlyRootFilesystem": read_only_root_filesystem,
            "allowPrivilegeEscalation": allow_privilege_escalation,
            "capabilities": {"drop": drop_capabilities},
        }

        return self.generate_strategic_merge_patch(
            name=f"{resource_name}-security-context",
            kind=kind,
            api_version="apps/v1",
            resource_name=resource_name,
            spec_overrides={
                "template": {
                    "spec": {
                        "containers": [
                            {
                                "name": container_name,
                                "securityContext": security_context,
                            }
                        ]
                    }
                }
            },
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
        """
        Generate a health probe patch.

        Args:
            resource_name: Name of the deployment/statefulset
            container_name: Name of the container
            liveness_path: HTTP path for liveness probe
            readiness_path: HTTP path for readiness probe
            port: Port name or number
            initial_delay: Initial delay in seconds
            period: Probe period in seconds
            kind: Resource kind

        Returns:
            YAML string of the patch
        """
        return self.generate_strategic_merge_patch(
            name=f"{resource_name}-probes",
            kind=kind,
            api_version="apps/v1",
            resource_name=resource_name,
            spec_overrides={
                "template": {
                    "spec": {
                        "containers": [
                            {
                                "name": container_name,
                                "livenessProbe": {
                                    "httpGet": {"path": liveness_path, "port": port},
                                    "initialDelaySeconds": initial_delay,
                                    "periodSeconds": period,
                                },
                                "readinessProbe": {
                                    "httpGet": {"path": readiness_path, "port": port},
                                    "initialDelaySeconds": initial_delay // 2,
                                    "periodSeconds": period,
                                },
                            }
                        ]
                    }
                }
            },
        )

    def generate_batch(
        self, patches: List[KustomizePatch]
    ) -> GeneratedKustomization:
        """
        Generate multiple patches as a batch.

        Args:
            patches: List of patch configurations

        Returns:
            GeneratedKustomization with all patch files
        """
        files: Dict[str, str] = {}
        all_issues: List[str] = []

        for patch in patches:
            if patch.patch_type == PatchType.STRATEGIC_MERGE and patch.patch_content:
                files[f"{patch.name}.yaml"] = patch.patch_content
            elif patch.patch_type == PatchType.JSON6902 and patch.target and patch.operations:
                patch_config = self.generate_json6902_patch(patch.target, patch.operations)
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
