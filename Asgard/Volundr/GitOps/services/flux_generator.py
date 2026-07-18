"""
Flux Generator Service

Generates Flux GitRepository and Kustomization manifests
with best practices for GitOps deployments.
"""

import hashlib
import os
from datetime import datetime
from typing import Dict, List, Optional

from Asgard.Volundr.GitOps.models.gitops_models import (
    FluxGitRepository,
    FluxKustomization,
    GeneratedGitOpsConfig,
    GitOpsProvider,
)
from Asgard.Volundr.GitOps.services.argocd_generator import _issues_to_findings
from Asgard.Volundr.GitOps.services.flux_generator_helpers import (
    calculate_combined_score,  # noqa: F401  (deprecated, kept for API compat)
    calculate_git_repo_score,  # noqa: F401  (deprecated, kept for API compat)
    calculate_kustomization_score,  # noqa: F401  (deprecated, kept for API compat)
    generate_git_repository_manifest,
    generate_kustomization_manifest,
    validate_git_repository,
    validate_kustomization,
)
from Asgard.Volundr.Validation.services.scoring_engine import ScoringEngine


class FluxGenerator:
    """Generates Flux GitOps manifests."""

    def __init__(self, output_dir: Optional[str] = None):
        self.output_dir = output_dir or "flux"

    def generate_git_repository(
        self, git_repo: FluxGitRepository
    ) -> GeneratedGitOpsConfig:
        config_json = git_repo.model_dump_json()
        config_hash = hashlib.sha256(config_json.encode()).hexdigest()[:16]
        repo_id = f"{git_repo.name}-gitrepo-{config_hash}"

        files: Dict[str, str] = {}
        files[f"{git_repo.name}-gitrepository.yaml"] = generate_git_repository_manifest(git_repo)

        validation_results = validate_git_repository(git_repo)
        findings = _issues_to_findings(validation_results, git_repo.name)
        score_report = ScoringEngine().score(findings, resources=[git_repo.name])
        best_practice_score = score_report.composite

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
        config_json = kustomization.model_dump_json()
        config_hash = hashlib.sha256(config_json.encode()).hexdigest()[:16]
        ks_id = f"{kustomization.name}-kustomization-{config_hash}"

        files: Dict[str, str] = {}
        files[f"{kustomization.name}-kustomization.yaml"] = generate_kustomization_manifest(kustomization)

        validation_results = validate_kustomization(kustomization)
        findings = _issues_to_findings(validation_results, kustomization.name)
        score_report = ScoringEngine().score(findings, resources=[kustomization.name])
        best_practice_score = score_report.composite

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
        files[f"{name}-gitrepository.yaml"] = generate_git_repository_manifest(git_repo)
        files[f"{name}-kustomization.yaml"] = generate_kustomization_manifest(kustomization)

        config_hash = hashlib.sha256(str(files).encode()).hexdigest()[:16]

        validation_results = validate_git_repository(git_repo) + validate_kustomization(kustomization)
        findings = _issues_to_findings(validation_results, name)
        score_report = ScoringEngine().score(findings, resources=[name])

        return GeneratedGitOpsConfig(
            id=f"{name}-flux-{config_hash}",
            config_hash=config_hash,
            provider=GitOpsProvider.FLUX,
            files=files,
            validation_results=validation_results,
            best_practice_score=score_report.composite,
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
        if environments is None:
            environments = ["development", "staging", "production"]

        files: Dict[str, str] = {}
        all_issues: List[str] = []

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
        files[f"{name}-gitrepository.yaml"] = generate_git_repository_manifest(git_repo)
        all_issues.extend(validate_git_repository(git_repo))

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
            files[f"{name}-{env}-kustomization.yaml"] = generate_kustomization_manifest(kustomization)
            all_issues.extend(validate_kustomization(kustomization))

        config_hash = hashlib.sha256(str(files).encode()).hexdigest()[:16]

        # Never grade the generator's own intent (plan 07): score the
        # real accumulated findings across the repo + every environment's
        # Kustomization instead of the previous hardcoded 90.0.
        findings = _issues_to_findings(all_issues, name)
        score_report = ScoringEngine().score(findings, resources=[name])

        return GeneratedGitOpsConfig(
            id=f"{name}-multi-env-{config_hash}",
            config_hash=config_hash,
            provider=GitOpsProvider.FLUX,
            files=files,
            validation_results=all_issues,
            best_practice_score=score_report.composite,
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
