"""
Kubernetes Models for Manifest Generation

Provides Pydantic models for configuring and generating Kubernetes manifests
with secure-by-default (NSA/CISA + CIS 5.x) hardening, reified suppressions,
and operational readiness.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from Asgard.Volundr.Validation.models.suppression_models import Suppression


class WorkloadType(str, Enum):
    """Kubernetes workload types."""
    DEPLOYMENT = "Deployment"
    STATEFULSET = "StatefulSet"
    DAEMONSET = "DaemonSet"
    JOB = "Job"
    CRONJOB = "CronJob"


class SecurityProfile(str, Enum):
    """Security profile levels for generated manifests.

    NOTE: since the secure-by-default uplift, a profile is a *suppression
    preset*, not an alternate template. Every profile renders the identical
    maximally-hardened manifest; lower profiles merely pre-suppress a small
    set of completeness rules (with `preset:` receipts), so any relaxation
    is visible in the output.
    """
    BASIC = "basic"
    ENHANCED = "enhanced"
    STRICT = "strict"
    ZERO_TRUST = "zero-trust"


class EnvironmentType(str, Enum):
    """Deployment environment types."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"


class ResourceRequirements(BaseModel):
    """Container resource requirements."""
    cpu_request: str = Field(default="100m", description="CPU request")
    cpu_limit: str = Field(default="500m", description="CPU limit")
    memory_request: str = Field(default="128Mi", description="Memory request")
    memory_limit: str = Field(default="512Mi", description="Memory limit")
    storage_request: Optional[str] = Field(default=None, description="Storage request for PVCs")


class SecurityContext(BaseModel):
    """Container security context configuration. Defaults are maximal."""
    run_as_user: Optional[int] = Field(default=1000, description="UID to run as")
    run_as_group: Optional[int] = Field(default=3000, description="GID to run as")
    run_as_non_root: bool = Field(default=True, description="Require non-root user")
    read_only_root_filesystem: bool = Field(default=True, description="Read-only root filesystem")
    allow_privilege_escalation: bool = Field(default=False, description="Allow privilege escalation")
    drop_capabilities: List[str] = Field(default_factory=lambda: ["ALL"], description="Capabilities to drop")
    add_capabilities: List[str] = Field(default_factory=list, description="Capabilities to add")
    privileged: bool = Field(default=False, description="Privileged container (never default)")
    seccomp_profile: str = Field(
        default="RuntimeDefault",
        description="Container-level seccompProfile.type (RuntimeDefault/Localhost/Unconfined)",
    )
    apparmor_profile: str = Field(
        default="RuntimeDefault",
        description="AppArmor profile type (RuntimeDefault/Localhost/Unconfined)",
    )


class ProbeConfig(BaseModel):
    """Health probe configuration."""
    enabled: bool = Field(default=True, description="Enable the probe")
    initial_delay_seconds: int = Field(default=10, description="Initial delay before probing")
    period_seconds: int = Field(default=10, description="Probe interval")
    timeout_seconds: int = Field(default=5, description="Probe timeout")
    failure_threshold: int = Field(default=3, description="Failures before unhealthy")
    success_threshold: int = Field(default=1, description="Successes before healthy")
    http_path: Optional[str] = Field(default="/health", description="HTTP probe path")
    http_port: Optional[int] = Field(default=8080, description="HTTP probe port")


class PortConfig(BaseModel):
    """Container port configuration."""
    name: str = Field(default="http", description="Port name")
    container_port: int = Field(description="Container port number")
    service_port: Optional[int] = Field(default=None, description="Service port (defaults to container_port)")
    protocol: str = Field(default="TCP", description="Protocol (TCP/UDP)")


class EgressRule(BaseModel):
    """A declared egress need, rendered into the always-on NetworkPolicy."""
    description: str = Field(default="", description="Why this egress is needed")
    cidr: Optional[str] = Field(default=None, description="Destination CIDR (e.g. 10.0.0.0/8)")
    namespace_labels: Dict[str, str] = Field(
        default_factory=dict, description="Destination namespaceSelector matchLabels"
    )
    pod_labels: Dict[str, str] = Field(
        default_factory=dict, description="Destination podSelector matchLabels"
    )
    ports: List[int] = Field(default_factory=list, description="Destination ports")
    protocol: str = Field(default="TCP", description="Protocol (TCP/UDP)")


class PDBConfig(BaseModel):
    """PodDisruptionBudget configuration."""
    enabled: bool = Field(default=True, description="Generate a PDB when replicas > 1")
    min_available: Optional[Any] = Field(
        default=None, description="minAvailable (int or percentage string); default replicas//2 min 1"
    )
    max_unavailable: Optional[Any] = Field(
        default=None, description="maxUnavailable (mutually exclusive with min_available)"
    )


class ManifestConfig(BaseModel):
    """Configuration for generating Kubernetes manifests."""
    name: str = Field(description="Application/workload name")
    namespace: str = Field(default="default", description="Kubernetes namespace")
    workload_type: WorkloadType = Field(default=WorkloadType.DEPLOYMENT, description="Workload type")
    image: str = Field(description="Container image")
    image_digest: Optional[str] = Field(
        default=None,
        description="Image digest (sha256:...); when given the image is pinned as repo@digest",
    )
    replicas: int = Field(default=1, ge=0, description="Number of replicas")
    environment: EnvironmentType = Field(default=EnvironmentType.DEVELOPMENT, description="Environment type")
    security_profile: SecurityProfile = Field(
        default=SecurityProfile.BASIC,
        description="Suppression preset (all profiles render the same hardened template)",
    )
    resources: ResourceRequirements = Field(default_factory=ResourceRequirements, description="Resource requirements")
    security_context: SecurityContext = Field(default_factory=SecurityContext, description="Security context")
    liveness_probe: ProbeConfig = Field(default_factory=ProbeConfig, description="Liveness probe config")
    readiness_probe: ProbeConfig = Field(default_factory=ProbeConfig, description="Readiness probe config")
    labels: Dict[str, str] = Field(default_factory=dict, description="Additional labels")
    annotations: Dict[str, str] = Field(default_factory=dict, description="Annotations")
    env_vars: Dict[str, str] = Field(default_factory=dict, description="Environment variables")
    config_maps: List[str] = Field(default_factory=list, description="ConfigMaps to mount")
    configmap_data: Dict[str, Dict[str, str]] = Field(
        default_factory=dict,
        description="Explicit data per ConfigMap name (replaces fabricated stub content)",
    )
    secrets: List[str] = Field(default_factory=list, description="Secrets to mount")
    secret_string_data: Dict[str, Dict[str, str]] = Field(
        default_factory=dict,
        description="Explicit stringData per Secret name; empty secrets yield completeness findings",
    )
    volumes: List[Dict[str, Any]] = Field(default_factory=list, description="Volume definitions")
    service_account: Optional[str] = Field(
        default=None,
        description="Existing ServiceAccount name; when None a dedicated SA is generated",
    )
    automount_service_account_token: bool = Field(
        default=False, description="Pod-level automountServiceAccountToken"
    )
    ports: List[PortConfig] = Field(
        default_factory=lambda: [PortConfig(container_port=8080)],
        description="Container ports"
    )
    cron_schedule: Optional[str] = Field(default=None, description="Cron schedule for CronJob workloads")
    target_k8s_version: str = Field(
        default="1.30", description="Target Kubernetes version (drives AppArmor shape and schema binding)"
    )
    writable_paths: List[str] = Field(
        default_factory=lambda: ["/tmp"],
        description="Paths that get an auto emptyDir when readOnlyRootFilesystem is true",
    )
    egress_rules: List[EgressRule] = Field(
        default_factory=list, description="Declared egress needs for the NetworkPolicy"
    )
    fs_group: int = Field(default=2000, description="Pod-level fsGroup")
    fs_group_change_policy: Optional[str] = Field(
        default="OnRootMismatch", description="fsGroupChangePolicy (OnRootMismatch/Always/None)"
    )
    apparmor: bool = Field(default=True, description="Emit AppArmor RuntimeDefault profile")
    pdb: PDBConfig = Field(default_factory=PDBConfig, description="PodDisruptionBudget config")
    tolerations: List[Dict[str, Any]] = Field(default_factory=list, description="Pod tolerations")
    affinity: Optional[Dict[str, Any]] = Field(default=None, description="Pod affinity block")
    suppressions: List[Suppression] = Field(
        default_factory=list,
        description="Reified suppressions (rule, target, reason); the only sanctioned relaxation path",
    )


class GeneratedManifest(BaseModel):
    """Result of manifest generation."""
    id: str = Field(description="Unique manifest ID")
    config_hash: str = Field(description="Hash of the configuration")
    manifests: Dict[str, Dict[str, Any]] = Field(description="Generated manifest objects")
    yaml_content: str = Field(description="Combined YAML content")
    validation_results: List[str] = Field(default_factory=list, description="Validation issues found")
    best_practice_score: float = Field(ge=0, le=100, description="Best practice compliance score")
    created_at: datetime = Field(default_factory=datetime.now, description="Creation timestamp")
    file_path: Optional[str] = Field(default=None, description="Path where manifest was saved")
    applied_suppressions: List[str] = Field(
        default_factory=list,
        description="Rule IDs annihilated by suppressions (receipts are in the manifests)",
    )
    validation_report: Optional[Any] = Field(
        default=None, description="Full ValidationReport from the adversarial validation engine"
    )
    score_report: Optional[Any] = Field(
        default=None,
        description="Composite ScoreReport (plan 07): dimensions, grades, veto, receipts",
    )

    @property
    def has_issues(self) -> bool:
        """Check if there are validation issues."""
        return len(self.validation_results) > 0

    @property
    def is_production_ready(self) -> bool:
        """Production readiness (plan 07): Security grade >= B AND
        composite >= 80 AND zero un-suppressed CRITICAL findings
        (no critical security veto). Falls back to the legacy
        score-and-issues heuristic when no ScoreReport is attached."""
        if self.score_report is not None:
            report = self.score_report
            security = next(
                (d for d in report.dimensions if d.dimension.value == "security"),
                None,
            )
            security_ok = security is None or security.grade in ("A", "B")
            return (
                report.composite >= 80
                and security_ok
                and report.veto_applied != "critical"
            )
        return self.best_practice_score >= 80 and not self.has_issues
