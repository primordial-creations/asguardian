"""
ArgoCD Generator Service

Generates ArgoCD Application manifests with best practices
for GitOps deployments.
"""

import hashlib
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, cast

import yaml  # type: ignore[import-untyped]

from Asgard.Volundr.GitOps.models.gitops_models import (
    ArgoApplication,
    ArgoSource,
    ArgoDestination,
    SyncPolicy,
    GeneratedGitOpsConfig,
    GitOpsProvider,
)


class ArgoCDGenerator:
    """Generates ArgoCD Application manifests."""

    def __init__(self, output_dir: Optional[str] = None):
        """
        Initialize the ArgoCD generator.

        Args:
            output_dir: Directory for saving generated manifests
        """
        self.output_dir = output_dir or "argocd"

    def generate(self, app: ArgoApplication) -> GeneratedGitOpsConfig:
        """
        Generate ArgoCD Application manifest.

        Args:
            app: ArgoCD application configuration

        Returns:
            GeneratedGitOpsConfig with generated manifest
        """
        config_json = app.model_dump_json()
        config_hash = hashlib.sha256(config_json.encode()).hexdigest()[:16]
        app_id = f"{app.name}-{config_hash}"

        files: Dict[str, str] = {}

        # Generate Application manifest
        files[f"{app.name}-application.yaml"] = self._generate_application_manifest(app)

        validation_results = self._validate_application(app)
        best_practice_score = self._calculate_best_practice_score(app)

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
        """
        Generate ArgoCD Application from repository configuration.

        Args:
            name: Application name
            repo_url: Git repository URL
            path: Path within repository
            target_namespace: Target namespace for deployment
            target_revision: Git revision (branch/tag/commit)
            project: ArgoCD project
            automated: Enable automated sync
            prune: Enable pruning
            self_heal: Enable self-healing

        Returns:
            GeneratedGitOpsConfig with generated manifest
        """
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
        """
        Generate ArgoCD App of Apps pattern manifest.

        Args:
            name: Parent application name
            repo_url: Git repository URL
            apps_path: Path to child app manifests
            target_revision: Git revision
            project: ArgoCD project

        Returns:
            GeneratedGitOpsConfig with generated manifest
        """
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
        """
        Generate multiple ArgoCD Application manifests.

        Args:
            apps: List of application configurations

        Returns:
            GeneratedGitOpsConfig with all generated manifests
        """
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

    def _generate_application_manifest(self, app: ArgoApplication) -> str:
        """Generate ArgoCD Application manifest YAML."""
        manifest: Dict[str, Any] = {
            "apiVersion": "argoproj.io/v1alpha1",
            "kind": "Application",
            "metadata": {
                "name": app.name,
                "namespace": app.namespace,
                "labels": app.labels,
                "finalizers": app.finalizers,
            },
            "spec": {
                "project": app.project,
                "source": self._build_source_spec(app.source),
                "destination": {
                    "server": app.destination.server,
                    "namespace": app.destination.namespace,
                },
            },
        }

        if app.destination.name:
            manifest["spec"]["destination"]["name"] = app.destination.name
            del manifest["spec"]["destination"]["server"]

        if app.annotations:
            manifest["metadata"]["annotations"] = app.annotations

        # Build sync policy
        if app.sync_policy:
            sync_policy: Dict[str, Any] = {}

            if app.sync_policy.automated:
                sync_policy["automated"] = {
                    "prune": app.sync_policy.prune,
                    "selfHeal": app.sync_policy.self_heal,
                    "allowEmpty": app.sync_policy.allow_empty,
                }

            if app.sync_policy.sync_options:
                sync_policy["syncOptions"] = app.sync_policy.sync_options

            if app.sync_policy.retry_limit > 0:
                sync_policy["retry"] = {
                    "limit": app.sync_policy.retry_limit,
                    "backoff": {
                        "duration": app.sync_policy.retry_backoff_duration,
                        "factor": app.sync_policy.retry_backoff_factor,
                        "maxDuration": app.sync_policy.retry_backoff_max_duration,
                    },
                }

            manifest["spec"]["syncPolicy"] = sync_policy

        if app.ignore_differences:
            manifest["spec"]["ignoreDifferences"] = app.ignore_differences

        if app.info:
            manifest["spec"]["info"] = app.info

        return cast(str, yaml.dump(manifest, default_flow_style=False, sort_keys=False))

    def _build_source_spec(self, source: ArgoSource) -> Dict[str, Any]:
        """Build source specification."""
        spec: Dict[str, Any] = {
            "repoURL": source.repo_url,
            "targetRevision": source.target_revision,
            "path": source.path,
        }

        if source.helm:
            helm_spec: Dict[str, Any] = {}
            if source.helm.values_files:
                helm_spec["valueFiles"] = source.helm.values_files
            if source.helm.values:
                helm_spec["values"] = yaml.dump(source.helm.values)
            if source.helm.parameters:
                helm_spec["parameters"] = source.helm.parameters
            if source.helm.release_name:
                helm_spec["releaseName"] = source.helm.release_name
            if helm_spec:
                spec["helm"] = helm_spec

        if source.kustomize:
            kustomize_spec: Dict[str, Any] = {}
            if source.kustomize.images:
                kustomize_spec["images"] = source.kustomize.images
            if source.kustomize.name_prefix:
                kustomize_spec["namePrefix"] = source.kustomize.name_prefix
            if source.kustomize.name_suffix:
                kustomize_spec["nameSuffix"] = source.kustomize.name_suffix
            if source.kustomize.common_labels:
                kustomize_spec["commonLabels"] = source.kustomize.common_labels
            if source.kustomize.common_annotations:
                kustomize_spec["commonAnnotations"] = source.kustomize.common_annotations
            if kustomize_spec:
                spec["kustomize"] = kustomize_spec

        if source.directory:
            spec["directory"] = source.directory

        return spec

    def _validate_application(self, app: ArgoApplication) -> List[str]:
        """Validate the ArgoCD application configuration."""
        issues: List[str] = []

        if not app.name:
            issues.append("Application name is required")

        if not app.source.repo_url:
            issues.append("Source repository URL is required")

        if not app.destination.namespace:
            issues.append("Destination namespace is required")

        if app.sync_policy.automated and not app.sync_policy.prune:
            issues.append("Automated sync without pruning may leave orphaned resources")

        if not app.finalizers:
            issues.append("Missing finalizers - resources may not be cleaned up properly")

        return issues

    def _calculate_best_practice_score(self, app: ArgoApplication) -> float:
        """Calculate a best practice score for the application."""
        score = 0.0
        max_score = 0.0

        # Automated sync
        max_score += 20
        if app.sync_policy.automated:
            score += 20

        # Prune enabled
        max_score += 15
        if app.sync_policy.prune:
            score += 15

        # Self-heal enabled
        max_score += 15
        if app.sync_policy.self_heal:
            score += 15

        # Retry policy configured
        max_score += 10
        if app.sync_policy.retry_limit > 0:
            score += 10

        # Finalizers configured
        max_score += 15
        if app.finalizers:
            score += 15

        # Labels configured
        max_score += 10
        if app.labels:
            score += 10

        # Sync options configured
        max_score += 10
        if app.sync_policy.sync_options:
            score += 10

        # Target revision not HEAD
        max_score += 5
        if app.source.target_revision and app.source.target_revision != "HEAD":
            score += 5

        return (score / max_score) * 100 if max_score > 0 else 0.0

    def save_to_directory(
        self, config: GeneratedGitOpsConfig, output_dir: Optional[str] = None
    ) -> str:
        """
        Save generated manifests to directory.

        Args:
            config: Generated GitOps configuration to save
            output_dir: Override output directory

        Returns:
            Path to the saved directory
        """
        target_dir = output_dir or self.output_dir
        os.makedirs(target_dir, exist_ok=True)

        for file_path, content in config.files.items():
            full_path = os.path.join(target_dir, file_path)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)

        return target_dir
