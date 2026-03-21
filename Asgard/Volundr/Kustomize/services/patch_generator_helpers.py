from typing import Any, Dict, List, Optional, Union, cast

import yaml  # type: ignore[import-untyped]

from Asgard.Volundr.Kustomize.models.kustomize_models import (
    JsonPatchOperation,
    PatchTarget,
)


def build_strategic_merge_patch(
    kind: str,
    api_version: str,
    resource_name: str,
    spec_overrides: Dict[str, Any],
    metadata_overrides: Optional[Dict[str, Any]] = None,
) -> str:
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


def build_json6902_patch(
    target: PatchTarget,
    operations: List[JsonPatchOperation],
) -> Dict[str, Any]:
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


def build_replica_patch(resource_name: str, replicas: int, kind: str = "Deployment") -> str:
    return build_strategic_merge_patch(
        kind=kind,
        api_version="apps/v1",
        resource_name=resource_name,
        spec_overrides={"replicas": replicas},
    )


def build_resource_patch(
    resource_name: str,
    container_name: str,
    cpu_request: str,
    cpu_limit: str,
    memory_request: str,
    memory_limit: str,
    kind: str = "Deployment",
) -> str:
    return build_strategic_merge_patch(
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


def build_image_patch(
    resource_name: str, container_name: str, image: str, kind: str = "Deployment"
) -> str:
    return build_strategic_merge_patch(
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


def build_env_patch(
    resource_name: str,
    container_name: str,
    env_vars: Dict[str, str],
    kind: str = "Deployment",
) -> str:
    env_list = [{"name": k, "value": v} for k, v in env_vars.items()]

    return build_strategic_merge_patch(
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


def build_annotation_patch(
    resource_name: str,
    annotations: Dict[str, str],
    kind: str = "Deployment",
    api_version: str = "apps/v1",
    pod_annotations: bool = True,
) -> str:
    if pod_annotations and kind in ["Deployment", "StatefulSet", "DaemonSet"]:
        return build_strategic_merge_patch(
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
        return build_strategic_merge_patch(
            kind=kind,
            api_version=api_version,
            resource_name=resource_name,
            spec_overrides={},
            metadata_overrides={"annotations": annotations},
        )


def build_label_patch(
    resource_name: str,
    labels: Dict[str, str],
    kind: str = "Deployment",
    api_version: str = "apps/v1",
    pod_labels: bool = True,
) -> str:
    if pod_labels and kind in ["Deployment", "StatefulSet", "DaemonSet"]:
        return build_strategic_merge_patch(
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
        return build_strategic_merge_patch(
            kind=kind,
            api_version=api_version,
            resource_name=resource_name,
            spec_overrides={},
            metadata_overrides={"labels": labels},
        )


def build_security_context_patch(
    resource_name: str,
    container_name: str,
    run_as_non_root: bool,
    run_as_user: int,
    run_as_group: int,
    read_only_root_filesystem: bool,
    allow_privilege_escalation: bool,
    drop_capabilities: List[str],
    kind: str = "Deployment",
) -> str:
    security_context: Dict[str, Any] = {
        "runAsNonRoot": run_as_non_root,
        "runAsUser": run_as_user,
        "runAsGroup": run_as_group,
        "readOnlyRootFilesystem": read_only_root_filesystem,
        "allowPrivilegeEscalation": allow_privilege_escalation,
        "capabilities": {"drop": drop_capabilities},
    }

    return build_strategic_merge_patch(
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


def build_probe_patch(
    resource_name: str,
    container_name: str,
    liveness_path: str,
    readiness_path: str,
    port: Union[int, str],
    initial_delay: int,
    period: int,
    kind: str = "Deployment",
) -> str:
    return build_strategic_merge_patch(
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
