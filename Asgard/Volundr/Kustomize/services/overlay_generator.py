"""
Kustomize Overlay Generator Service

Generates environment-specific Kustomize overlays with
image overrides, replica scaling, and resource patches.
"""

import hashlib
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, cast

import yaml  # type: ignore[import-untyped]

from Asgard.Volundr.Kustomize.models.kustomize_models import (
    GeneratedKustomization,
    KustomizeOverlay,
    ReplicaTransformer,
    ImageTransformer,
)


class OverlayGenerator:
    """Generates Kustomize overlay configurations."""

    # Environment-specific defaults
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

    def __init__(self, output_dir: Optional[str] = None):
        """
        Initialize the overlay generator.

        Args:
            output_dir: Directory for saving generated configurations
        """
        self.output_dir = output_dir or "kustomize"

    def generate(
        self,
        overlay: KustomizeOverlay,
        base_path: str = "../../base",
        app_name: Optional[str] = None,
    ) -> GeneratedKustomization:
        """
        Generate a Kustomize overlay configuration.

        Args:
            overlay: Overlay configuration
            base_path: Relative path to base
            app_name: Application name (for patch generation)

        Returns:
            GeneratedKustomization with all generated files
        """
        config_json = overlay.model_dump_json()
        config_hash = hashlib.sha256(config_json.encode()).hexdigest()[:16]
        overlay_id = f"{overlay.name}-overlay-{config_hash}"

        files: Dict[str, str] = {}

        # Generate overlay kustomization.yaml
        overlay_path = f"overlays/{overlay.name}"
        files[f"{overlay_path}/kustomization.yaml"] = self._generate_overlay_kustomization(
            overlay, base_path
        )

        # Generate resource patches if replicas or resources are overridden
        env_defaults = self.ENV_DEFAULTS.get(overlay.name, {})
        if overlay.replicas or env_defaults.get("replicas"):
            files[f"{overlay_path}/replica-patch.yaml"] = self._generate_replica_patch(
                overlay, app_name, env_defaults
            )

        if env_defaults.get("resources"):
            files[f"{overlay_path}/resource-patch.yaml"] = self._generate_resource_patch(
                overlay, app_name, env_defaults
            )

        validation_results = self._validate_overlay(files, overlay)
        best_practice_score = self._calculate_best_practice_score(files, overlay)

        return GeneratedKustomization(
            id=overlay_id,
            config_hash=config_hash,
            files=files,
            validation_results=validation_results,
            best_practice_score=best_practice_score,
            created_at=datetime.now(),
        )

    def generate_all_environments(
        self,
        app_name: str,
        image: str,
        base_path: str = "../../base",
        environments: Optional[List[str]] = None,
    ) -> GeneratedKustomization:
        """
        Generate overlays for all standard environments.

        Args:
            app_name: Application name
            image: Container image
            base_path: Relative path to base
            environments: List of environments to generate (default: dev, staging, prod)

        Returns:
            GeneratedKustomization with all overlay files
        """
        if environments is None:
            environments = ["development", "staging", "production"]

        all_files: Dict[str, str] = {}
        all_issues: List[str] = []

        for env in environments:
            env_defaults = self.ENV_DEFAULTS.get(env, self.ENV_DEFAULTS["development"])

            overlay = KustomizeOverlay(
                name=env,
                bases=[base_path],
                namespace=env,
                common_labels={"environment": env},
                images=[ImageTransformer(name=image, new_tag=f"{env}-latest")],
                replicas=[ReplicaTransformer(name=app_name, count=env_defaults["replicas"])],
            )

            result = self.generate(overlay, base_path, app_name)
            all_files.update(result.files)
            all_issues.extend(result.validation_results)

        config_hash = hashlib.sha256(str(all_files).encode()).hexdigest()[:16]

        return GeneratedKustomization(
            id=f"{app_name}-overlays-{config_hash}",
            config_hash=config_hash,
            files=all_files,
            validation_results=all_issues,
            best_practice_score=self._calculate_overall_score(all_files),
            created_at=datetime.now(),
        )

    def _generate_overlay_kustomization(
        self, overlay: KustomizeOverlay, base_path: str
    ) -> str:
        """Generate kustomization.yaml for overlay."""
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

        # Add patches
        patches = ["replica-patch.yaml", "resource-patch.yaml"]
        env_defaults = self.ENV_DEFAULTS.get(overlay.name, {})
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

    def _generate_replica_patch(
        self,
        overlay: KustomizeOverlay,
        app_name: Optional[str],
        env_defaults: Dict[str, Any],
    ) -> str:
        """Generate replica count patch."""
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

    def _generate_resource_patch(
        self,
        overlay: KustomizeOverlay,
        app_name: Optional[str],
        env_defaults: Dict[str, Any],
    ) -> str:
        """Generate resource limits patch."""
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

    def _validate_overlay(
        self, files: Dict[str, str], overlay: KustomizeOverlay
    ) -> List[str]:
        """Validate the generated overlay configuration."""
        issues: List[str] = []

        kustomization_path = f"overlays/{overlay.name}/kustomization.yaml"
        if kustomization_path not in files:
            issues.append(f"Missing kustomization.yaml for overlay {overlay.name}")

        kustomization = files.get(kustomization_path, "")
        if "resources:" not in kustomization:
            issues.append(f"Overlay {overlay.name} has no base resources defined")

        return issues

    def _calculate_best_practice_score(
        self, files: Dict[str, str], overlay: KustomizeOverlay
    ) -> float:
        """Calculate a best practice score for the generated overlay."""
        score = 0.0
        max_score = 0.0

        kustomization_path = f"overlays/{overlay.name}/kustomization.yaml"

        # kustomization.yaml present
        max_score += 30
        if kustomization_path in files:
            score += 30

            kustomization = files[kustomization_path]

            # Namespace isolation
            max_score += 20
            if "namespace:" in kustomization:
                score += 20

            # Environment labels
            max_score += 15
            if "commonLabels:" in kustomization:
                score += 15

            # Image pinning
            max_score += 20
            if "images:" in kustomization:
                score += 20

            # Resource scaling
            max_score += 15
            if "replicas:" in kustomization or "patches:" in kustomization:
                score += 15

        return (score / max_score) * 100 if max_score > 0 else 0.0

    def _calculate_overall_score(self, files: Dict[str, str]) -> float:
        """Calculate overall best practice score for all overlays."""
        if not files:
            return 0.0

        total_score = 0.0
        overlay_count = 0

        for path in files.keys():
            if "kustomization.yaml" in path and "overlays/" in path:
                overlay_count += 1
                kustomization = files[path]

                # Basic checks
                if "namespace:" in kustomization:
                    total_score += 25
                if "commonLabels:" in kustomization:
                    total_score += 25
                if "images:" in kustomization:
                    total_score += 25
                if "patches:" in kustomization or "replicas:" in kustomization:
                    total_score += 25

        return total_score / overlay_count if overlay_count > 0 else 0.0

    def save_to_directory(
        self, kustomization: GeneratedKustomization, output_dir: Optional[str] = None
    ) -> str:
        """
        Save generated overlay configuration to directory.

        Args:
            kustomization: Generated kustomization to save
            output_dir: Override output directory

        Returns:
            Path to the saved configuration directory
        """
        target_dir = output_dir or self.output_dir

        for file_path, content in kustomization.files.items():
            full_path = os.path.join(target_dir, file_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)

        return target_dir
