"""
Kustomize Overlay Generator Service

Generates environment-specific Kustomize overlays with
image overrides, replica scaling, and resource patches.
"""

import hashlib
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from Asgard.Volundr.Kustomize.models.kustomize_models import (
    GeneratedKustomization,
    ImageTransformer,
    KustomizeOverlay,
    ReplicaTransformer,
)
from Asgard.Volundr.Kustomize.services.overlay_generator_helpers import (
    ENV_DEFAULTS,
    calculate_best_practice_score,
    calculate_overall_score,
    generate_overlay_kustomization,
    generate_replica_patch,
    generate_resource_patch,
    validate_overlay,
)


class OverlayGenerator:
    """Generates Kustomize overlay configurations."""

    def __init__(self, output_dir: Optional[str] = None):
        self.output_dir = output_dir or "kustomize"

    def generate(
        self,
        overlay: KustomizeOverlay,
        base_path: str = "../../base",
        app_name: Optional[str] = None,
    ) -> GeneratedKustomization:
        config_json = overlay.model_dump_json()
        config_hash = hashlib.sha256(config_json.encode()).hexdigest()[:16]
        overlay_id = f"{overlay.name}-overlay-{config_hash}"

        files: Dict[str, str] = {}

        overlay_path = f"overlays/{overlay.name}"
        files[f"{overlay_path}/kustomization.yaml"] = generate_overlay_kustomization(
            overlay, base_path
        )

        env_defaults = ENV_DEFAULTS.get(overlay.name, {})
        if overlay.replicas or env_defaults.get("replicas"):
            files[f"{overlay_path}/replica-patch.yaml"] = generate_replica_patch(
                overlay, app_name, env_defaults
            )

        if env_defaults.get("resources"):
            files[f"{overlay_path}/resource-patch.yaml"] = generate_resource_patch(
                overlay, app_name, env_defaults
            )

        validation_results = validate_overlay(files, overlay)
        best_practice_score = calculate_best_practice_score(files, overlay)

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
        if environments is None:
            environments = ["development", "staging", "production"]

        all_files: Dict[str, str] = {}
        all_issues: List[str] = []

        for env in environments:
            env_defaults = ENV_DEFAULTS.get(env, ENV_DEFAULTS["development"])

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
            best_practice_score=calculate_overall_score(all_files),
            created_at=datetime.now(),
        )

    def save_to_directory(
        self, kustomization: GeneratedKustomization, output_dir: Optional[str] = None
    ) -> str:
        target_dir = output_dir or self.output_dir

        for file_path, content in kustomization.files.items():
            full_path = os.path.join(target_dir, file_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)

        return target_dir
