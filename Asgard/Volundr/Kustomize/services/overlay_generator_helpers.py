from typing import Any, Dict, List, Optional, cast

import yaml  # type: ignore[import-untyped]

from Asgard.Volundr.Kustomize.models.kustomize_models import (
    KustomizeOverlay,
)

ENV_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "development": {
        "replicas": 1,
        "resources": {
            "requests": {"cpu": "100m", "memory": "128Mi"},
            "limits": {"cpu": "200m", "memory": "256Mi"},
        },
    },
    "staging": {
        "replicas": 2,
        "resources": {
            "requests": {"cpu": "250m", "memory": "256Mi"},
            "limits": {"cpu": "500m", "memory": "512Mi"},
        },
    },
    "production": {
        "replicas": 3,
        "resources": {
            "requests": {"cpu": "500m", "memory": "512Mi"},
            "limits": {"cpu": "1000m", "memory": "1Gi"},
        },
    },
}


def generate_overlay_kustomization(
    overlay: KustomizeOverlay, base_path: str
) -> str:
    kustomization: Dict[str, Any] = {
        "apiVersion": "kustomize.config.k8s.io/v1beta1",
        "kind": "Kustomization",
        "resources": overlay.bases if overlay.bases else [base_path],
    }

    if overlay.namespace:
        kustomization["namespace"] = overlay.namespace

    if overlay.name_prefix:
        kustomization["namePrefix"] = overlay.name_prefix

    if overlay.name_suffix:
        kustomization["nameSuffix"] = overlay.name_suffix

    if overlay.common_labels:
        kustomization["commonLabels"] = overlay.common_labels

    if overlay.common_annotations:
        kustomization["commonAnnotations"] = overlay.common_annotations

    if overlay.images:
        kustomization["images"] = []
        for img in overlay.images:
            img_entry: Dict[str, str] = {"name": img.name}
            if img.new_name:
                img_entry["newName"] = img.new_name
            if img.new_tag:
                img_entry["newTag"] = img.new_tag
            if img.digest:
                img_entry["digest"] = img.digest
            kustomization["images"].append(img_entry)

    if overlay.replicas:
        kustomization["replicas"] = [
            {"name": r.name, "count": r.count} for r in overlay.replicas
        ]

    env_defaults = ENV_DEFAULTS.get(overlay.name, {})
    if overlay.replicas or env_defaults.get("replicas"):
        if "patches" not in kustomization:
            kustomization["patches"] = []
        kustomization["patches"].append({"path": "replica-patch.yaml"})

    if env_defaults.get("resources"):
        if "patches" not in kustomization:
            kustomization["patches"] = []
        kustomization["patches"].append({"path": "resource-patch.yaml"})

    if overlay.config_map_generators:
        kustomization["configMapGenerator"] = []
        for cm in overlay.config_map_generators:
            cm_entry: Dict[str, Any] = {"name": cm.name}
            if cm.files:
                cm_entry["files"] = cm.files
            if cm.literals:
                cm_entry["literals"] = cm.literals
            kustomization["configMapGenerator"].append(cm_entry)

    if overlay.secret_generators:
        kustomization["secretGenerator"] = []
        for secret in overlay.secret_generators:
            secret_entry: Dict[str, Any] = {"name": secret.name, "type": secret.type}
            if secret.files:
                secret_entry["files"] = secret.files
            if secret.literals:
                secret_entry["literals"] = secret.literals
            kustomization["secretGenerator"].append(secret_entry)

    if overlay.components:
        kustomization["components"] = overlay.components

    if overlay.resources:
        kustomization["resources"].extend(overlay.resources)

    return cast(str, yaml.dump(kustomization, default_flow_style=False, sort_keys=False))


def generate_replica_patch(
    overlay: KustomizeOverlay,
    app_name: Optional[str],
    env_defaults: Dict[str, Any],
) -> str:
    replicas = env_defaults.get("replicas", 1)
    if overlay.replicas:
        replicas = overlay.replicas[0].count

    name = app_name
    if overlay.replicas:
        name = overlay.replicas[0].name

    patch = {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {"name": name or "app"},
        "spec": {"replicas": replicas},
    }

    return cast(str, yaml.dump(patch, default_flow_style=False, sort_keys=False))


def generate_resource_patch(
    overlay: KustomizeOverlay,
    app_name: Optional[str],
    env_defaults: Dict[str, Any],
) -> str:
    resources = env_defaults.get("resources", {})

    name = app_name
    if overlay.replicas:
        name = overlay.replicas[0].name

    patch = {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {"name": name or "app"},
        "spec": {
            "template": {
                "spec": {
                    "containers": [
                        {
                            "name": name or "app",
                            "resources": resources,
                        }
                    ]
                }
            }
        },
    }

    return cast(str, yaml.dump(patch, default_flow_style=False, sort_keys=False))


def validate_overlay(
    files: Dict[str, str], overlay: KustomizeOverlay
) -> List[str]:
    issues: List[str] = []

    kustomization_path = f"overlays/{overlay.name}/kustomization.yaml"
    if kustomization_path not in files:
        issues.append(f"Missing kustomization.yaml for overlay {overlay.name}")

    kustomization = files.get(kustomization_path, "")
    if "resources:" not in kustomization:
        issues.append(f"Overlay {overlay.name} has no base resources defined")

    return issues


def calculate_best_practice_score(
    files: Dict[str, str], overlay: KustomizeOverlay
) -> float:
    score = 0.0
    max_score = 0.0

    kustomization_path = f"overlays/{overlay.name}/kustomization.yaml"

    max_score += 30
    if kustomization_path in files:
        score += 30

        kustomization = files[kustomization_path]

        max_score += 20
        if "namespace:" in kustomization:
            score += 20

        max_score += 15
        if "commonLabels:" in kustomization:
            score += 15

        max_score += 20
        if "images:" in kustomization:
            score += 20

        max_score += 15
        if "replicas:" in kustomization or "patches:" in kustomization:
            score += 15

    return (score / max_score) * 100 if max_score > 0 else 0.0


def calculate_overall_score(files: Dict[str, str]) -> float:
    if not files:
        return 0.0

    total_score = 0.0
    overlay_count = 0

    for path in files.keys():
        if "kustomization.yaml" in path and "overlays/" in path:
            overlay_count += 1
            kustomization = files[path]

            if "namespace:" in kustomization:
                total_score += 25
            if "commonLabels:" in kustomization:
                total_score += 25
            if "images:" in kustomization:
                total_score += 25
            if "patches:" in kustomization or "replicas:" in kustomization:
                total_score += 25

    return total_score / overlay_count if overlay_count > 0 else 0.0
