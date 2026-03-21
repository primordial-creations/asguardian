"""
ArgoCD Generator Service

Generates ArgoCD Application manifests with best practices
for GitOps deployments.
"""

import hashlib
import os
from datetime import datetime
from typing import Dict, List, Optional

from Asgard.Volundr.GitOps.models.gitops_models import (
    ArgoApplication,
    ArgoDestination,
    ArgoSource,
    GeneratedGitOpsConfig,
    GitOpsProvider,
    SyncPolicy,
)
from Asgard.Volundr.GitOps.services.argocd_generator_helpers import (
    calculate_best_practice_score,
    generate_application_manifest,
    validate_application,
)


class ArgoCDGenerator:
    """Generates ArgoCD Application manifests."""

    def __init__(self, output_dir: Optional[str] = None):
        self.output_dir = output_dir or "argocd"

    def generate(self, app: ArgoApplication) -> GeneratedGitOpsConfig:
        config_json = app.model_dump_json()
        config_hash = hashlib.sha256(config_json.encode()).hexdigest()[:16]
        app_id = f"{app.name}-{config_hash}"

        files: Dict[str, str] = {}
        files[f"{app.name}-application.yaml"] = generate_application_manifest(app)

        validation_results = validate_application(app)
        best_practice_score = calculate_best_practice_score(app)

        return GeneratedGitOpsConfig(
            id=app_id,
            config_hash=config_hash,
            provider=GitOpsProvider.ARGOCD,
            files=files,
            validation_results=validation_results,
            best_practice_score=best_practice_score,
            created_at=datetime.now(),
        )

    def generate_from_repo(
        self,
        name: str,
        repo_url: str,
        path: str,
        target_namespace: str,
        target_revision: str = "HEAD",
        project: str = "default",
        automated: bool = True,
        prune: bool = True,
        self_heal: bool = True,
    ) -> GeneratedGitOpsConfig:
        app = ArgoApplication(
            name=name,
            project=project,
            source=ArgoSource(
                repo_url=repo_url,
                target_revision=target_revision,
                path=path,
            ),
            destination=ArgoDestination(namespace=target_namespace),
            sync_policy=SyncPolicy(
                automated=automated,
                prune=prune,
                self_heal=self_heal,
            ),
            labels={
                "app.kubernetes.io/name": name,
                "app.kubernetes.io/managed-by": "argocd",
            },
        )

        return self.generate(app)

    def generate_app_of_apps(
        self,
        name: str,
        repo_url: str,
        apps_path: str = "apps",
        target_revision: str = "HEAD",
        project: str = "default",
    ) -> GeneratedGitOpsConfig:
        app = ArgoApplication(
            name=name,
            project=project,
            source=ArgoSource(
                repo_url=repo_url,
                target_revision=target_revision,
                path=apps_path,
            ),
            destination=ArgoDestination(
                namespace="argocd",
            ),
            sync_policy=SyncPolicy(
                automated=True,
                prune=True,
                self_heal=True,
                sync_options=["CreateNamespace=true"],
            ),
            labels={
                "app.kubernetes.io/name": name,
                "app.kubernetes.io/component": "app-of-apps",
                "app.kubernetes.io/managed-by": "argocd",
            },
            annotations={
                "argocd.argoproj.io/manifest-generate-paths": apps_path,
            },
        )

        return self.generate(app)

    def generate_batch(
        self, apps: List[ArgoApplication]
    ) -> GeneratedGitOpsConfig:
        all_files: Dict[str, str] = {}
        all_issues: List[str] = []
        total_score = 0.0

        for app in apps:
            result = self.generate(app)
            all_files.update(result.files)
            all_issues.extend(result.validation_results)
            total_score += result.best_practice_score

        config_hash = hashlib.sha256(str(all_files).encode()).hexdigest()[:16]
        avg_score = total_score / len(apps) if apps else 0.0

        return GeneratedGitOpsConfig(
            id=f"argocd-apps-{config_hash}",
            config_hash=config_hash,
            provider=GitOpsProvider.ARGOCD,
            files=all_files,
            validation_results=all_issues,
            best_practice_score=avg_score,
            created_at=datetime.now(),
        )

    def save_to_directory(
        self, config: GeneratedGitOpsConfig, output_dir: Optional[str] = None
    ) -> str:
        target_dir = output_dir or self.output_dir
        os.makedirs(target_dir, exist_ok=True)

        for file_path, content in config.files.items():
            full_path = os.path.join(target_dir, file_path)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)

        return target_dir
