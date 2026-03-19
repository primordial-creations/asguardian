"""
Flux Generator Service

Generates Flux GitRepository and Kustomization manifests
with best practices for GitOps deployments.
"""

import hashlib
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, cast

import yaml  # type: ignore[import-untyped]

from Asgard.Volundr.GitOps.models.gitops_models import (
    FluxGitRepository,
    FluxKustomization,
    GeneratedGitOpsConfig,
    GitOpsProvider,
)


class FluxGenerator:
    """Generates Flux GitOps manifests."""

    def __init__(self, output_dir: Optional[str] = None):
        """
        Initialize the Flux generator.

        Args:
            output_dir: Directory for saving generated manifests
        """
        self.output_dir = output_dir or "flux"

    def generate_git_repository(
        self, git_repo: FluxGitRepository
    ) -> GeneratedGitOpsConfig:
        """
        Generate Flux GitRepository manifest.

        Args:
            git_repo: GitRepository configuration

        Returns:
            GeneratedGitOpsConfig with generated manifest
        """
        config_json = git_repo.model_dump_json()
        config_hash = hashlib.sha256(config_json.encode()).hexdigest()[:16]
        repo_id = f"{git_repo.name}-gitrepo-{config_hash}"

        files: Dict[str, str] = {}
        files[f"{git_repo.name}-gitrepository.yaml"] = self._generate_git_repository_manifest(
            git_repo
        )

        validation_results = self._validate_git_repository(git_repo)
        best_practice_score = self._calculate_git_repo_score(git_repo)

        return GeneratedGitOpsConfig(
            id=repo_id,
            config_hash=config_hash,
            provider=GitOpsProvider.FLUX,
            files=files,
            validation_results=validation_results,
            best_practice_score=best_practice_score,
            created_at=datetime.now(),
        )

    def generate_kustomization(
        self, kustomization: FluxKustomization
    ) -> GeneratedGitOpsConfig:
        """
        Generate Flux Kustomization manifest.

        Args:
            kustomization: Kustomization configuration

        Returns:
            GeneratedGitOpsConfig with generated manifest
        """
        config_json = kustomization.model_dump_json()
        config_hash = hashlib.sha256(config_json.encode()).hexdigest()[:16]
        ks_id = f"{kustomization.name}-kustomization-{config_hash}"

        files: Dict[str, str] = {}
        files[f"{kustomization.name}-kustomization.yaml"] = self._generate_kustomization_manifest(
            kustomization
        )

        validation_results = self._validate_kustomization(kustomization)
        best_practice_score = self._calculate_kustomization_score(kustomization)

        return GeneratedGitOpsConfig(
            id=ks_id,
            config_hash=config_hash,
            provider=GitOpsProvider.FLUX,
            files=files,
            validation_results=validation_results,
            best_practice_score=best_practice_score,
            created_at=datetime.now(),
        )

    def generate_from_repo(
        self,
        name: str,
        repo_url: str,
        path: str = "./",
        branch: str = "main",
        target_namespace: Optional[str] = None,
        interval: str = "10m",
        prune: bool = True,
    ) -> GeneratedGitOpsConfig:
        """
        Generate complete Flux configuration from repository.

        Args:
            name: Application name
            repo_url: Git repository URL
            path: Path within repository
            branch: Git branch
            target_namespace: Target namespace for resources
            interval: Reconciliation interval
            prune: Enable pruning

        Returns:
            GeneratedGitOpsConfig with both GitRepository and Kustomization
        """
        git_repo = FluxGitRepository(
            name=name,
            url=repo_url,
            branch=branch,
            interval="1m",
            labels={
                "app.kubernetes.io/name": name,
                "app.kubernetes.io/managed-by": "flux",
            },
        )

        kustomization = FluxKustomization(
            name=name,
            source_ref_name=name,
            path=path,
            target_namespace=target_namespace,
            interval=interval,
            prune=prune,
            labels={
                "app.kubernetes.io/name": name,
                "app.kubernetes.io/managed-by": "flux",
            },
        )

        files: Dict[str, str] = {}

        # Generate GitRepository
        files[f"{name}-gitrepository.yaml"] = self._generate_git_repository_manifest(git_repo)

        # Generate Kustomization
        files[f"{name}-kustomization.yaml"] = self._generate_kustomization_manifest(kustomization)

        config_hash = hashlib.sha256(str(files).encode()).hexdigest()[:16]

        return GeneratedGitOpsConfig(
            id=f"{name}-flux-{config_hash}",
            config_hash=config_hash,
            provider=GitOpsProvider.FLUX,
            files=files,
            validation_results=[],
            best_practice_score=self._calculate_combined_score(git_repo, kustomization),
            created_at=datetime.now(),
        )

    def generate_multi_env(
        self,
        name: str,
        repo_url: str,
        base_path: str = "kustomize",
        environments: Optional[List[str]] = None,
        branch: str = "main",
    ) -> GeneratedGitOpsConfig:
        """
        Generate Flux configuration for multiple environments.

        Args:
            name: Application name
            repo_url: Git repository URL
            base_path: Base path for kustomize overlays
            environments: List of environments
            branch: Git branch

        Returns:
            GeneratedGitOpsConfig with configurations for all environments
        """
        if environments is None:
            environments = ["development", "staging", "production"]

        files: Dict[str, str] = {}
        all_issues: List[str] = []

        # Generate shared GitRepository
        git_repo = FluxGitRepository(
            name=f"{name}-repo",
            url=repo_url,
            branch=branch,
            interval="1m",
            labels={
                "app.kubernetes.io/name": name,
                "app.kubernetes.io/managed-by": "flux",
            },
        )
        files[f"{name}-gitrepository.yaml"] = self._generate_git_repository_manifest(git_repo)

        # Generate Kustomization for each environment
        for env in environments:
            depends_on = []
            if env == "staging":
                depends_on = [{"name": f"{name}-development"}]
            elif env == "production":
                depends_on = [{"name": f"{name}-staging"}]

            kustomization = FluxKustomization(
                name=f"{name}-{env}",
                source_ref_name=f"{name}-repo",
                path=f"./{base_path}/overlays/{env}",
                target_namespace=env,
                interval="10m" if env == "production" else "5m",
                prune=True,
                depends_on=depends_on,
                health_checks=[
                    {
                        "apiVersion": "apps/v1",
                        "kind": "Deployment",
                        "name": name,
                        "namespace": env,
                    }
                ],
                labels={
                    "app.kubernetes.io/name": name,
                    "app.kubernetes.io/environment": env,
                    "app.kubernetes.io/managed-by": "flux",
                },
            )
            files[f"{name}-{env}-kustomization.yaml"] = self._generate_kustomization_manifest(
                kustomization
            )

        config_hash = hashlib.sha256(str(files).encode()).hexdigest()[:16]

        return GeneratedGitOpsConfig(
            id=f"{name}-multi-env-{config_hash}",
            config_hash=config_hash,
            provider=GitOpsProvider.FLUX,
            files=files,
            validation_results=all_issues,
            best_practice_score=90.0,  # Multi-env with dependencies is best practice
            created_at=datetime.now(),
        )

    def _generate_git_repository_manifest(self, git_repo: FluxGitRepository) -> str:
        """Generate Flux GitRepository manifest YAML."""
        manifest: Dict[str, Any] = {
            "apiVersion": "source.toolkit.fluxcd.io/v1",
            "kind": "GitRepository",
            "metadata": {
                "name": git_repo.name,
                "namespace": git_repo.namespace,
            },
            "spec": {
                "interval": git_repo.interval,
                "url": git_repo.url,
                "ref": {},
            },
        }

        if git_repo.labels:
            manifest["metadata"]["labels"] = git_repo.labels

        if git_repo.annotations:
            manifest["metadata"]["annotations"] = git_repo.annotations

        # Set ref
        if git_repo.tag:
            manifest["spec"]["ref"]["tag"] = git_repo.tag
        elif git_repo.semver:
            manifest["spec"]["ref"]["semver"] = git_repo.semver
        else:
            manifest["spec"]["ref"]["branch"] = git_repo.branch

        if git_repo.timeout:
            manifest["spec"]["timeout"] = git_repo.timeout

        if git_repo.secret_ref:
            manifest["spec"]["secretRef"] = {"name": git_repo.secret_ref}

        if git_repo.ignore_paths:
            manifest["spec"]["ignore"] = "\n".join(git_repo.ignore_paths)

        if git_repo.recurse_submodules:
            manifest["spec"]["recurseSubmodules"] = True

        if git_repo.verify_commits:
            manifest["spec"]["verify"] = {"mode": "head"}

        return cast(str, yaml.dump(manifest, default_flow_style=False, sort_keys=False))

    def _generate_kustomization_manifest(self, ks: FluxKustomization) -> str:
        """Generate Flux Kustomization manifest YAML."""
        manifest: Dict[str, Any] = {
            "apiVersion": "kustomize.toolkit.fluxcd.io/v1",
            "kind": "Kustomization",
            "metadata": {
                "name": ks.name,
                "namespace": ks.namespace,
            },
            "spec": {
                "interval": ks.interval,
                "sourceRef": {
                    "kind": ks.source_ref_kind,
                    "name": ks.source_ref_name,
                },
                "path": ks.path,
                "prune": ks.prune,
            },
        }

        if ks.labels:
            manifest["metadata"]["labels"] = ks.labels

        if ks.annotations:
            manifest["metadata"]["annotations"] = ks.annotations

        if ks.source_ref_namespace:
            manifest["spec"]["sourceRef"]["namespace"] = ks.source_ref_namespace

        if ks.target_namespace:
            manifest["spec"]["targetNamespace"] = ks.target_namespace

        if ks.timeout:
            manifest["spec"]["timeout"] = ks.timeout

        if ks.force:
            manifest["spec"]["force"] = True

        if ks.health_checks:
            manifest["spec"]["healthChecks"] = ks.health_checks

        if ks.patches:
            manifest["spec"]["patches"] = ks.patches

        if ks.images:
            manifest["spec"]["images"] = ks.images

        if ks.depends_on:
            manifest["spec"]["dependsOn"] = ks.depends_on

        if ks.service_account_name:
            manifest["spec"]["serviceAccountName"] = ks.service_account_name

        if ks.decryption:
            manifest["spec"]["decryption"] = ks.decryption

        if ks.post_build:
            manifest["spec"]["postBuild"] = ks.post_build

        return cast(str, yaml.dump(manifest, default_flow_style=False, sort_keys=False))

    def _validate_git_repository(self, git_repo: FluxGitRepository) -> List[str]:
        """Validate the GitRepository configuration."""
        issues: List[str] = []

        if not git_repo.name:
            issues.append("GitRepository name is required")

        if not git_repo.url:
            issues.append("GitRepository URL is required")

        if git_repo.url.startswith("git@") and not git_repo.secret_ref:
            issues.append("SSH URL requires secretRef for authentication")

        return issues

    def _validate_kustomization(self, ks: FluxKustomization) -> List[str]:
        """Validate the Kustomization configuration."""
        issues: List[str] = []

        if not ks.name:
            issues.append("Kustomization name is required")

        if not ks.source_ref_name:
            issues.append("Kustomization sourceRef name is required")

        if not ks.prune:
            issues.append("Pruning is disabled - orphaned resources may remain")

        return issues

    def _calculate_git_repo_score(self, git_repo: FluxGitRepository) -> float:
        """Calculate best practice score for GitRepository."""
        score = 0.0
        max_score = 0.0

        # Short interval for faster reconciliation
        max_score += 20
        interval = git_repo.interval
        if interval.endswith("s"):
            score += 20
        elif interval.endswith("m"):
            minutes = int(interval.rstrip("m"))
            if minutes <= 5:
                score += 15
            elif minutes <= 10:
                score += 10

        # Labels configured
        max_score += 20
        if git_repo.labels:
            score += 20

        # Using specific branch/tag instead of main
        max_score += 15
        if git_repo.tag or git_repo.semver:
            score += 15
        elif git_repo.branch != "main":
            score += 10

        # Timeout configured
        max_score += 15
        if git_repo.timeout:
            score += 15

        # Verify commits enabled
        max_score += 15
        if git_repo.verify_commits:
            score += 15

        # Ignore paths configured
        max_score += 15
        if git_repo.ignore_paths:
            score += 15

        return (score / max_score) * 100 if max_score > 0 else 0.0

    def _calculate_kustomization_score(self, ks: FluxKustomization) -> float:
        """Calculate best practice score for Kustomization."""
        score = 0.0
        max_score = 0.0

        # Prune enabled
        max_score += 25
        if ks.prune:
            score += 25

        # Health checks configured
        max_score += 20
        if ks.health_checks:
            score += 20

        # Labels configured
        max_score += 15
        if ks.labels:
            score += 15

        # Dependencies configured (for multi-env)
        max_score += 15
        if ks.depends_on:
            score += 15

        # Target namespace specified
        max_score += 10
        if ks.target_namespace:
            score += 10

        # Timeout configured
        max_score += 10
        if ks.timeout:
            score += 10

        # Service account for RBAC
        max_score += 5
        if ks.service_account_name:
            score += 5

        return (score / max_score) * 100 if max_score > 0 else 0.0

    def _calculate_combined_score(
        self, git_repo: FluxGitRepository, ks: FluxKustomization
    ) -> float:
        """Calculate combined best practice score."""
        git_score = self._calculate_git_repo_score(git_repo)
        ks_score = self._calculate_kustomization_score(ks)
        return (git_score + ks_score) / 2

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
