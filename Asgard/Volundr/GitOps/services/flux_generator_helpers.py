from typing import Any, Dict, List, cast

import yaml  # type: ignore[import-untyped]

from Asgard.Volundr.GitOps.models.gitops_models import (
    FluxGitRepository,
    FluxKustomization,
)


def generate_git_repository_manifest(git_repo: FluxGitRepository) -> str:
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


def generate_kustomization_manifest(ks: FluxKustomization) -> str:
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


def validate_git_repository(git_repo: FluxGitRepository) -> List[str]:
    issues: List[str] = []

    if not git_repo.name:
        issues.append("GitRepository name is required")

    if not git_repo.url:
        issues.append("GitRepository URL is required")

    if git_repo.url.startswith("git@") and not git_repo.secret_ref:
        issues.append("SSH URL requires secretRef for authentication")

    return issues


def validate_kustomization(ks: FluxKustomization) -> List[str]:
    issues: List[str] = []

    if not ks.name:
        issues.append("Kustomization name is required")

    if not ks.source_ref_name:
        issues.append("Kustomization sourceRef name is required")

    if not ks.prune:
        issues.append("Pruning is disabled - orphaned resources may remain")

    return issues


def calculate_git_repo_score(git_repo: FluxGitRepository) -> float:
    score = 0.0
    max_score = 0.0

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

    max_score += 20
    if git_repo.labels:
        score += 20

    max_score += 15
    if git_repo.tag or git_repo.semver:
        score += 15
    elif git_repo.branch != "main":
        score += 10

    max_score += 15
    if git_repo.timeout:
        score += 15

    max_score += 15
    if git_repo.verify_commits:
        score += 15

    max_score += 15
    if git_repo.ignore_paths:
        score += 15

    return (score / max_score) * 100 if max_score > 0 else 0.0


def calculate_kustomization_score(ks: FluxKustomization) -> float:
    score = 0.0
    max_score = 0.0

    max_score += 25
    if ks.prune:
        score += 25

    max_score += 20
    if ks.health_checks:
        score += 20

    max_score += 15
    if ks.labels:
        score += 15

    max_score += 15
    if ks.depends_on:
        score += 15

    max_score += 10
    if ks.target_namespace:
        score += 10

    max_score += 10
    if ks.timeout:
        score += 10

    max_score += 5
    if ks.service_account_name:
        score += 5

    return (score / max_score) * 100 if max_score > 0 else 0.0


def calculate_combined_score(
    git_repo: FluxGitRepository, ks: FluxKustomization
) -> float:
    git_score = calculate_git_repo_score(git_repo)
    ks_score = calculate_kustomization_score(ks)
    return (git_score + ks_score) / 2
