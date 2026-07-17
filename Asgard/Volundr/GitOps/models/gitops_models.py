"""
GitOps Models for Configuration Generation

Provides Pydantic models for configuring and generating GitOps
resources for ArgoCD and Flux with best practices.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class GitOpsProvider(str, Enum):
    """Supported GitOps providers."""
    ARGOCD = "argocd"
    FLUX = "flux"


class SyncPolicyType(str, Enum):
    """Sync policy types."""
    MANUAL = "manual"
    AUTOMATED = "automated"


class PrunePolicy(str, Enum):
    """Prune policy options."""
    ENABLED = "enabled"
    DISABLED = "disabled"
    FOREGROUND = "foreground"
    BACKGROUND = "background"


class SelfHealPolicy(str, Enum):
    """Self-heal policy options."""
    ENABLED = "enabled"
    DISABLED = "disabled"


class HealthStatus(str, Enum):
    """Resource health statuses."""
    HEALTHY = "Healthy"
    PROGRESSING = "Progressing"
    DEGRADED = "Degraded"
    SUSPENDED = "Suspended"
    MISSING = "Missing"
    UNKNOWN = "Unknown"


class SyncPolicy(BaseModel):
    """ArgoCD sync policy configuration."""
    automated: bool = Field(default=True, description="Enable automated sync")
    prune: bool = Field(default=True, description="Enable pruning of orphaned resources")
    self_heal: bool = Field(default=True, description="Enable self-healing")
    allow_empty: bool = Field(default=False, description="Allow empty app to sync")
    sync_options: List[str] = Field(
        default_factory=lambda: ["CreateNamespace=true", "PruneLast=true"],
        description="Sync options"
    )
    retry_limit: int = Field(default=5, description="Number of sync retries")
    retry_backoff_duration: str = Field(default="5s", description="Retry backoff duration")
    retry_backoff_factor: int = Field(default=2, description="Retry backoff factor")
    retry_backoff_max_duration: str = Field(default="3m", description="Max retry backoff")


class HealthPolicy(BaseModel):
    """Health check policy configuration."""
    check_interval: str = Field(default="30s", description="Health check interval")
    timeout: str = Field(default="10s", description="Health check timeout")
    failure_threshold: int = Field(default=3, description="Failures before unhealthy")
    success_threshold: int = Field(default=1, description="Successes before healthy")


class ArgoSourceHelm(BaseModel):
    """Helm source configuration for ArgoCD."""
    chart: str = Field(description="Helm chart name")
    repo_url: str = Field(description="Helm repository URL")
    target_revision: str = Field(default="*", description="Chart version/revision")
    values_files: List[str] = Field(default_factory=list, description="Values files")
    values: Dict[str, Any] = Field(default_factory=dict, description="Inline values")
    parameters: List[Dict[str, str]] = Field(default_factory=list, description="Helm parameters")
    release_name: Optional[str] = Field(default=None, description="Override release name")


class ArgoSourceKustomize(BaseModel):
    """Kustomize source configuration for ArgoCD."""
    path: str = Field(description="Path to kustomization")
    images: List[str] = Field(default_factory=list, description="Image overrides")
    name_prefix: str = Field(default="", description="Name prefix")
    name_suffix: str = Field(default="", description="Name suffix")
    common_labels: Dict[str, str] = Field(default_factory=dict, description="Common labels")
    common_annotations: Dict[str, str] = Field(default_factory=dict, description="Common annotations")


class ArgoSource(BaseModel):
    """ArgoCD application source configuration."""
    repo_url: str = Field(description="Git repository URL")
    target_revision: str = Field(
        default="main",
        description=(
            "Target revision (branch/tag/commit). Must be pinned — 'HEAD' "
            "is a severe anti-pattern and fails validation (VOL-GITOPS-0001)."
        ),
    )
    path: str = Field(default=".", description="Path within repository")
    helm: Optional[ArgoSourceHelm] = Field(default=None, description="Helm configuration")
    kustomize: Optional[ArgoSourceKustomize] = Field(default=None, description="Kustomize configuration")
    directory: Optional[Dict[str, Any]] = Field(default=None, description="Directory configuration")


class ArgoDestination(BaseModel):
    """ArgoCD application destination configuration."""
    server: str = Field(default="https://kubernetes.default.svc", description="Kubernetes API server")
    namespace: str = Field(description="Target namespace")
    name: Optional[str] = Field(default=None, description="Cluster name (alternative to server)")


class ArgoApplication(BaseModel):
    """ArgoCD Application configuration."""
    name: str = Field(description="Application name")
    namespace: str = Field(default="argocd", description="ArgoCD namespace")
    project: str = Field(
        default="default",
        description=(
            "ArgoCD AppProject. Using the unrestricted 'default' project is "
            "an anti-pattern and is flagged by validation (VOL-GITOPS-0002); "
            "reference a scoped AppProject with repo/destination allowlists."
        ),
    )
    source: ArgoSource = Field(description="Application source")
    destination: ArgoDestination = Field(description="Application destination")
    sync_policy: SyncPolicy = Field(default_factory=SyncPolicy, description="Sync policy")
    health_policy: Optional[HealthPolicy] = Field(default=None, description="Health policy")
    labels: Dict[str, str] = Field(default_factory=dict, description="Application labels")
    annotations: Dict[str, str] = Field(default_factory=dict, description="Application annotations")
    finalizers: List[str] = Field(
        default_factory=lambda: ["resources-finalizer.argocd.argoproj.io"],
        description="Finalizers"
    )
    ignore_differences: List[Dict[str, Any]] = Field(
        default_factory=list, description="Fields to ignore in diff"
    )
    info: List[Dict[str, str]] = Field(default_factory=list, description="Application info")


class FluxGitRepository(BaseModel):
    """Flux GitRepository configuration."""
    name: str = Field(description="GitRepository name")
    namespace: str = Field(default="flux-system", description="Flux namespace")
    url: str = Field(description="Git repository URL")
    branch: str = Field(default="main", description="Git branch")
    tag: Optional[str] = Field(default=None, description="Git tag (alternative to branch)")
    semver: Optional[str] = Field(default=None, description="Semver range")
    interval: str = Field(default="1m", description="Reconciliation interval")
    timeout: str = Field(default="60s", description="Git operation timeout")
    secret_ref: Optional[str] = Field(default=None, description="Secret for authentication")
    ignore_paths: List[str] = Field(default_factory=list, description="Paths to ignore")
    include_paths: List[str] = Field(default_factory=list, description="Paths to include")
    recurse_submodules: bool = Field(default=False, description="Recurse into submodules")
    verify_commits: bool = Field(default=False, description="Verify commit signatures")
    labels: Dict[str, str] = Field(default_factory=dict, description="Resource labels")
    annotations: Dict[str, str] = Field(default_factory=dict, description="Resource annotations")


class FluxKustomization(BaseModel):
    """Flux Kustomization configuration."""
    name: str = Field(description="Kustomization name")
    namespace: str = Field(default="flux-system", description="Flux namespace")
    target_namespace: Optional[str] = Field(default=None, description="Target namespace for resources")
    source_ref_kind: str = Field(default="GitRepository", description="Source reference kind")
    source_ref_name: str = Field(description="Source reference name")
    source_ref_namespace: Optional[str] = Field(default=None, description="Source reference namespace")
    path: str = Field(default="./", description="Path to kustomization")
    interval: str = Field(default="10m", description="Reconciliation interval")
    timeout: str = Field(default="5m", description="Apply timeout")
    prune: bool = Field(default=True, description="Enable pruning")
    force: bool = Field(default=False, description="Force apply")
    health_checks: List[Dict[str, Any]] = Field(default_factory=list, description="Health checks")
    patches: List[Dict[str, Any]] = Field(default_factory=list, description="Inline patches")
    images: List[Dict[str, str]] = Field(default_factory=list, description="Image overrides")
    depends_on: List[Dict[str, str]] = Field(default_factory=list, description="Dependencies")
    service_account_name: Optional[str] = Field(default=None, description="Service account for impersonation")
    decryption: Optional[Dict[str, Any]] = Field(default=None, description="Decryption configuration")
    post_build: Optional[Dict[str, Any]] = Field(default=None, description="Post-build configuration")
    labels: Dict[str, str] = Field(default_factory=dict, description="Resource labels")
    annotations: Dict[str, str] = Field(default_factory=dict, description="Resource annotations")


class GitOpsConfig(BaseModel):
    """Complete GitOps configuration."""
    provider: GitOpsProvider = Field(description="GitOps provider")
    argo_applications: List[ArgoApplication] = Field(
        default_factory=list, description="ArgoCD applications"
    )
    flux_git_repositories: List[FluxGitRepository] = Field(
        default_factory=list, description="Flux GitRepositories"
    )
    flux_kustomizations: List[FluxKustomization] = Field(
        default_factory=list, description="Flux Kustomizations"
    )


class GeneratedGitOpsConfig(BaseModel):
    """Result of GitOps configuration generation."""
    id: str = Field(description="Unique configuration ID")
    config_hash: str = Field(description="Hash of the configuration")
    provider: GitOpsProvider = Field(description="GitOps provider used")
    files: Dict[str, str] = Field(description="Generated files (path -> content)")
    validation_results: List[str] = Field(default_factory=list, description="Validation issues found")
    best_practice_score: float = Field(ge=0, le=100, description="Best practice compliance score")
    created_at: datetime = Field(default_factory=datetime.now, description="Creation timestamp")
    output_path: Optional[str] = Field(default=None, description="Path where files were saved")

    @property
    def has_issues(self) -> bool:
        """Check if there are validation issues."""
        return len(self.validation_results) > 0

    @property
    def file_count(self) -> int:
        """Get the number of generated files."""
        return len(self.files)
