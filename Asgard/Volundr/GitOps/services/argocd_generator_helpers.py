from fnmatch import fnmatchcase
from typing import Any, Dict, List, Optional, cast

import yaml  # type: ignore[import-untyped]

from Asgard.Volundr.GitOps.models.gitops_models import (
    ArgoApplication,
    ArgoAppProject,
    ArgoSource,
    GitOpsPolicy,
)

#: First-class ignoreDifferences presets (RESEARCH_02 §9).
IGNORE_DIFFERENCES_PRESETS: Dict[str, Dict[str, Any]] = {
    "hpa-replicas": {
        "group": "apps",
        "kind": "Deployment",
        "jsonPointers": ["/spec/replicas"],
    },
    "istio-sidecar-injection": {
        "group": "apps",
        "kind": "Deployment",
        "jqPathExpressions": [
            '.spec.template.spec.containers[] | select(.name == "istio-proxy")',
            '.spec.template.spec.initContainers[] | select(.name == "istio-init")',
        ],
    },
}


def ignore_differences_preset(name: str) -> Dict[str, Any]:
    """A named ignoreDifferences preset (KeyError for unknown names)."""
    return dict(IGNORE_DIFFERENCES_PRESETS[name])


def _is_exact_chart_version(revision: str) -> bool:
    """True when a Helm targetRevision is an exact version, not a range."""
    if not revision:
        return False
    return not any(ch in revision for ch in "*^~<>|, ") and not (
        revision.lower().startswith("x") or ".x" in revision.lower()
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

    # Mutating-webhook drift resilience by default (RESEARCH_02/05):
    # ServerSideDiff avoids false diffs from admission-time mutations.
    annotations = dict(app.annotations)
    annotations.setdefault(
        "argocd.argoproj.io/compare-options", "ServerSideDiff=true"
    )
    manifest["metadata"]["annotations"] = annotations

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


def generate_app_project_manifest(project: ArgoAppProject) -> str:
    """Render an AppProject with repo/destination allowlists."""
    spec: Dict[str, Any] = {
        "description": project.description or f"Scoped project {project.name}",
        "sourceRepos": list(project.source_repos) or [],
        "destinations": [dict(d) for d in project.destinations],
        "clusterResourceWhitelist": [
            dict(w) for w in project.cluster_resource_whitelist
        ],
        "namespaceResourceWhitelist": [
            dict(w) for w in project.namespace_resource_whitelist
        ],
    }
    manifest: Dict[str, Any] = {
        "apiVersion": "argoproj.io/v1alpha1",
        "kind": "AppProject",
        "metadata": {
            "name": project.name,
            "namespace": project.namespace,
            "labels": project.labels,
        },
        "spec": spec,
    }
    return cast(str, yaml.dump(manifest, default_flow_style=False, sort_keys=False))


def validate_application(
    app: ArgoApplication, policy: Optional[GitOpsPolicy] = None
) -> List[str]:
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

    if not app.source.target_revision or app.source.target_revision == "HEAD":
        issues.append(
            "VOL-GITOPS-0001: targetRevision must be pinned to a branch/tag/commit "
            "- 'HEAD' floats with the default branch and defeats auditability"
        )

    if app.project == "default":
        issues.append(
            "VOL-GITOPS-0002: Application uses the unrestricted 'default' AppProject "
            "- create a scoped AppProject with repo and destination allowlists"
        )

    # Helm chart revisions must be exact versions, never ranges
    # (RESEARCH_07 dependency pinning).
    if app.source.helm is not None and not _is_exact_chart_version(
        app.source.helm.target_revision
    ):
        issues.append(
            f"VOL-GITOPS-0005: Helm targetRevision "
            f"'{app.source.helm.target_revision}' is a range - pin an exact "
            "chart version"
        )

    # Org allowlists (repoURL hijack defense, RESEARCH_05).
    if policy is not None:
        if policy.allowed_repo_patterns and not any(
            fnmatchcase(app.source.repo_url, pattern)
            for pattern in policy.allowed_repo_patterns
        ):
            issues.append(
                f"VOL-GITOPS-0003: repoURL '{app.source.repo_url}' is not in the "
                "GitOpsPolicy repo allowlist"
            )
        if policy.allowed_destination_servers and not any(
            fnmatchcase(app.destination.server, pattern)
            for pattern in policy.allowed_destination_servers
        ):
            issues.append(
                f"VOL-GITOPS-0004: destination server '{app.destination.server}' "
                "is not in the GitOpsPolicy destination allowlist"
            )

    # Prune blast-radius guard (RESEARCH_09 pruning hazards).
    if app.sync_policy.automated and app.sync_policy.prune:
        issues.append(
            "VOL-GITOPS-0006: automated sync with prune enabled - a path "
            "refactor can cascade into mass deletion; review path changes as "
            "production changes"
        )

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

    max_score += 5
    if app.project and app.project != "default":
        score += 5

    return (score / max_score) * 100 if max_score > 0 else 0.0
