from typing import Any, Dict, List, cast

import yaml  # type: ignore[import-untyped]

from Asgard.Volundr.GitOps.models.gitops_models import (
    ArgoApplication,
    ArgoSource,
)


def build_source_spec(source: ArgoSource) -> Dict[str, Any]:
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


def generate_application_manifest(app: ArgoApplication) -> str:
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
            "source": build_source_spec(app.source),
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


def validate_application(app: ArgoApplication) -> List[str]:
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


def calculate_best_practice_score(app: ArgoApplication) -> float:
    score = 0.0
    max_score = 0.0

    max_score += 20
    if app.sync_policy.automated:
        score += 20

    max_score += 15
    if app.sync_policy.prune:
        score += 15

    max_score += 15
    if app.sync_policy.self_heal:
        score += 15

    max_score += 10
    if app.sync_policy.retry_limit > 0:
        score += 10

    max_score += 15
    if app.finalizers:
        score += 15

    max_score += 10
    if app.labels:
        score += 10

    max_score += 10
    if app.sync_policy.sync_options:
        score += 10

    max_score += 5
    if app.source.target_revision and app.source.target_revision != "HEAD":
        score += 5

    return (score / max_score) * 100 if max_score > 0 else 0.0
