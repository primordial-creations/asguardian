"""
Asgard Configuration Models - Security and Infrastructure

Security-related configuration models and infrastructure/performance models
for Heimdall, Verdandi, and Volundr modules.
"""

from typing import Dict, List, Literal, cast

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, Field, model_validator

from Asgard.config.models_base import CICDPlatform, GlobalConfig, TerraformBackend
from Asgard.config.models_quality import (
    ForsetiConfig,
    FreyaConfig,
    HeimdallQualityConfig,
)


class HeimdallSecurityConfig(BaseModel):
    """Configuration for Heimdall security analysis."""
    model_config = {"use_enum_values": True}

    enable_bandit: bool = Field(default=True, description="Enable Bandit security scanner")
    bandit_severity: str = Field(default="low", description="Minimum Bandit severity to report")
    bandit_confidence: str = Field(default="low", description="Minimum Bandit confidence to report")
    check_hardcoded_secrets: bool = Field(default=True, description="Check for hardcoded secrets")
    check_sql_injection: bool = Field(default=True, description="Check for SQL injection vulnerabilities")
    check_xss: bool = Field(default=True, description="Check for XSS vulnerabilities")
    check_path_traversal: bool = Field(default=True, description="Check for path traversal vulnerabilities")


class HeimdallConfig(BaseModel):
    """Complete Heimdall configuration."""
    model_config = {"use_enum_values": True}

    quality: HeimdallQualityConfig = Field(
        default_factory=HeimdallQualityConfig,
        description="Quality analysis configuration"
    )
    security: HeimdallSecurityConfig = Field(
        default_factory=HeimdallSecurityConfig,
        description="Security analysis configuration"
    )
    include_tests: bool = Field(default=False, description="Include test files in analysis")
    fail_on_error: bool = Field(default=True, description="Exit with error code if issues found")


class WebVitalsConfig(BaseModel):
    """Web Vitals thresholds configuration for Verdandi."""
    model_config = {"use_enum_values": True}

    lcp_threshold_ms: int = Field(
        default=2500,
        description="Largest Contentful Paint threshold in milliseconds (good < 2500, poor > 4000)",
        ge=100,
        le=30000
    )
    fid_threshold_ms: int = Field(
        default=100,
        description="First Input Delay threshold in milliseconds (good < 100, poor > 300)",
        ge=10,
        le=5000
    )
    cls_threshold: float = Field(
        default=0.1,
        description="Cumulative Layout Shift threshold (good < 0.1, poor > 0.25)",
        ge=0.0,
        le=1.0
    )
    fcp_threshold_ms: int = Field(
        default=1800,
        description="First Contentful Paint threshold in milliseconds",
        ge=100,
        le=30000
    )
    ttfb_threshold_ms: int = Field(
        default=800,
        description="Time to First Byte threshold in milliseconds",
        ge=50,
        le=10000
    )
    inp_threshold_ms: int = Field(
        default=200,
        description="Interaction to Next Paint threshold in milliseconds",
        ge=10,
        le=5000
    )
    track_long_tasks: bool = Field(default=True, description="Track long-running JavaScript tasks")
    long_task_threshold_ms: int = Field(
        default=50,
        description="Threshold for long task detection in milliseconds",
        ge=10,
        le=1000
    )


class APDEXConfig(BaseModel):
    """APDEX (Application Performance Index) configuration."""
    model_config = {"use_enum_values": True}

    enabled: bool = Field(default=True, description="Enable APDEX calculation")
    satisfied_threshold_ms: int = Field(
        default=500,
        description="Response time threshold for 'satisfied' rating in milliseconds",
        ge=50,
        le=30000
    )
    tolerating_threshold_ms: int = Field(
        default=2000,
        description="Response time threshold for 'tolerating' rating in milliseconds",
        ge=100,
        le=60000
    )
    target_score: float = Field(
        default=0.85,
        description="Target APDEX score (0.0-1.0)",
        ge=0.0,
        le=1.0
    )


class VerdandiConfig(BaseModel):
    """
    Configuration for Verdandi performance metrics module.

    Verdandi handles performance profiling, resource monitoring,
    and SLA compliance checking.
    """
    model_config = {"use_enum_values": True}

    enable_profiling: bool = Field(default=True, description="Enable code profiling")
    profile_depth: int = Field(default=10, description="Call stack depth for profiling", ge=1, le=100)
    sample_rate: float = Field(
        default=1.0,
        description="Sampling rate for profiling (0.0-1.0)",
        ge=0.01,
        le=1.0
    )
    apdex: APDEXConfig = Field(
        default_factory=APDEXConfig,
        description="APDEX configuration"
    )
    apdex_threshold_ms: int = Field(
        default=500,
        description="APDEX threshold in milliseconds (deprecated, use apdex.satisfied_threshold_ms)",
        ge=50,
        le=30000
    )
    sla_percentile: float = Field(
        default=95.0,
        description="Percentile for SLA calculations (e.g., 95.0 for P95)",
        ge=50.0,
        le=99.99
    )
    sla_response_time_ms: int = Field(
        default=1000,
        description="SLA response time threshold in milliseconds",
        ge=50,
        le=60000
    )
    memory_threshold_mb: float = Field(default=100.0, description="Memory usage warning threshold in MB", ge=1.0)
    cpu_threshold_percent: float = Field(
        default=80.0,
        description="CPU usage warning threshold",
        ge=1.0,
        le=100.0
    )
    response_time_threshold_ms: float = Field(
        default=1000.0,
        description="Response time warning threshold in ms",
        ge=1.0
    )
    cache_hit_rate_threshold: float = Field(
        default=0.8,
        description="Minimum acceptable cache hit rate (0.0-1.0)",
        ge=0.0,
        le=1.0
    )
    track_cache_metrics: bool = Field(default=True, description="Track cache hit/miss metrics")
    web_vitals: WebVitalsConfig = Field(
        default_factory=WebVitalsConfig,
        description="Web Vitals thresholds configuration"
    )
    generate_flamegraphs: bool = Field(default=False, description="Generate flamegraph visualizations")
    flamegraph_output_path: str = Field(default=".verdandi/flamegraphs", description="Path for flamegraph output")
    retain_metrics_days: int = Field(
        default=30,
        description="Number of days to retain metrics history",
        ge=1,
        le=365
    )
    baseline_comparison: bool = Field(
        default=True,
        description="Enable comparison against performance baselines"
    )


class KubernetesConfig(BaseModel):
    """Kubernetes-specific configuration for Volundr."""
    model_config = {"use_enum_values": True}

    version: str = Field(default="1.28", description="Target Kubernetes version")
    namespace: str = Field(default="default", description="Default Kubernetes namespace")
    enable_network_policies: bool = Field(default=True, description="Generate network policies")
    enable_pod_security: bool = Field(default=True, description="Enable Pod Security Standards")
    pod_security_level: Literal["privileged", "baseline", "restricted"] = Field(
        default="baseline",
        description="Pod Security Standard level"
    )
    resource_quotas_enabled: bool = Field(default=False, description="Generate resource quotas")
    default_replicas: int = Field(default=1, description="Default number of replicas", ge=1, le=100)
    enable_hpa: bool = Field(default=False, description="Enable Horizontal Pod Autoscaler generation")
    hpa_min_replicas: int = Field(default=1, description="HPA minimum replicas", ge=1)
    hpa_max_replicas: int = Field(default=10, description="HPA maximum replicas", ge=1, le=1000)


class DockerConfig(BaseModel):
    """Docker-specific configuration for Volundr."""
    model_config = {"use_enum_values": True}

    default_registry: str = Field(default="", description="Default Docker registry URL")
    base_image: str = Field(default="python:3.11-slim", description="Default base image for Python projects")
    enable_multi_stage: bool = Field(default=True, description="Use multi-stage builds")
    enable_buildkit: bool = Field(default=True, description="Enable BuildKit features")
    cache_from: List[str] = Field(default_factory=list, description="Images to use as cache sources")
    labels: Dict[str, str] = Field(default_factory=dict, description="Default labels to add to images")
    security_scan_enabled: bool = Field(default=True, description="Enable security scanning in generated configs")


class TerraformConfig(BaseModel):
    """Terraform-specific configuration for Volundr."""
    model_config = {"use_enum_values": True}

    backend: TerraformBackend = Field(default=TerraformBackend.LOCAL, description="Terraform backend type")
    backend_config: Dict[str, str] = Field(
        default_factory=dict,
        description="Backend-specific configuration options"
    )
    version_constraint: str = Field(default=">= 1.5.0", description="Terraform version constraint")
    provider_versions: Dict[str, str] = Field(
        default_factory=lambda: {
            "aws": "~> 5.0",
            "google": "~> 5.0",
            "azurerm": "~> 3.0",
            "kubernetes": "~> 2.0",
        },
        description="Provider version constraints"
    )
    enable_state_locking: bool = Field(default=True, description="Enable state locking")
    workspace_prefix: str = Field(default="", description="Prefix for Terraform workspaces")


class CICDConfig(BaseModel):
    """CI/CD configuration for Volundr."""
    model_config = {"use_enum_values": True}

    platform: CICDPlatform = Field(default=CICDPlatform.GITHUB_ACTIONS, description="CI/CD platform to generate configs for")
    enable_caching: bool = Field(default=True, description="Enable dependency caching in pipelines")
    parallel_jobs: int = Field(default=4, description="Number of parallel jobs", ge=1, le=50)
    timeout_minutes: int = Field(default=30, description="Default job timeout in minutes", ge=5, le=360)
    enable_security_scans: bool = Field(default=True, description="Include security scanning steps")
    enable_lint_checks: bool = Field(default=True, description="Include linting steps")
    enable_test_coverage: bool = Field(default=True, description="Include test coverage reporting")
    artifact_retention_days: int = Field(default=30, description="Days to retain build artifacts", ge=1, le=90)


class VolundrConfig(BaseModel):
    """
    Configuration for Volundr infrastructure generation module.

    Volundr handles Kubernetes manifests, Docker configurations,
    Terraform modules, and CI/CD pipeline generation.
    """
    model_config = {"use_enum_values": True}

    templates_path: str = Field(default="", description="Custom templates path")
    output_path: str = Field(default=".volundr/generated", description="Path for generated files")
    dry_run: bool = Field(default=False, description="Generate without writing files")
    docker: DockerConfig = Field(
        default_factory=DockerConfig,
        description="Docker configuration"
    )
    default_registry: str = Field(
        default="",
        description="Default Docker registry (deprecated, use docker.default_registry)"
    )
    kubernetes: KubernetesConfig = Field(
        default_factory=KubernetesConfig,
        description="Kubernetes configuration"
    )
    kubernetes_version: str = Field(
        default="1.28",
        description="Target Kubernetes version (deprecated, use kubernetes.version)"
    )
    kubernetes_namespace: str = Field(
        default="default",
        description="Kubernetes namespace (deprecated, use kubernetes.namespace)"
    )
    helm_chart_version: str = Field(default="0.1.0", description="Default Helm chart version")
    helm_repository: str = Field(default="", description="Default Helm repository URL")
    enable_helm_generation: bool = Field(default=True, description="Generate Helm charts")
    terraform: TerraformConfig = Field(
        default_factory=TerraformConfig,
        description="Terraform configuration"
    )
    terraform_backend: TerraformBackend = Field(
        default=TerraformBackend.LOCAL,
        description="Terraform backend (deprecated, use terraform.backend)"
    )
    cicd: CICDConfig = Field(
        default_factory=CICDConfig,
        description="CI/CD configuration"
    )
    cicd_platform: CICDPlatform = Field(
        default=CICDPlatform.GITHUB_ACTIONS,
        description="CI/CD platform (deprecated, use cicd.platform)"
    )
    validate_generated: bool = Field(default=True, description="Validate generated configurations")
    fail_on_validation_error: bool = Field(default=True, description="Fail if validation errors occur")

    @model_validator(mode="after")
    def sync_legacy_fields(self) -> "VolundrConfig":
        """Sync legacy fields with nested configs for backwards compatibility."""
        if self.default_registry and not self.docker.default_registry:
            self.docker.default_registry = self.default_registry
        elif self.docker.default_registry:
            self.default_registry = self.docker.default_registry

        if self.kubernetes_version != "1.28" and self.kubernetes.version == "1.28":
            self.kubernetes.version = self.kubernetes_version
        elif self.kubernetes.version != "1.28":
            self.kubernetes_version = self.kubernetes.version

        if self.kubernetes_namespace != "default" and self.kubernetes.namespace == "default":
            self.kubernetes.namespace = self.kubernetes_namespace
        elif self.kubernetes.namespace != "default":
            self.kubernetes_namespace = self.kubernetes.namespace

        if self.terraform_backend != TerraformBackend.LOCAL and self.terraform.backend == TerraformBackend.LOCAL:
            self.terraform.backend = self.terraform_backend
        elif self.terraform.backend != TerraformBackend.LOCAL:
            self.terraform_backend = self.terraform.backend

        if self.cicd_platform != CICDPlatform.GITHUB_ACTIONS and self.cicd.platform == CICDPlatform.GITHUB_ACTIONS:
            self.cicd.platform = self.cicd_platform
        elif self.cicd.platform != CICDPlatform.GITHUB_ACTIONS:
            self.cicd_platform = self.cicd.platform

        return self


class AsgardConfig(BaseModel):
    """
    Unified Asgard configuration container.

    Holds configuration for all Asgard modules with a unified structure.
    """
    model_config = {
        "use_enum_values": True,
        "populate_by_name": True,
    }

    version: str = Field(default="1.0.0", description="Configuration schema version")
    global_config: GlobalConfig = Field(
        default_factory=GlobalConfig,
        alias="global",
        description="Global configuration"
    )
    heimdall: HeimdallConfig = Field(
        default_factory=HeimdallConfig,
        description="Heimdall configuration"
    )
    forseti: ForsetiConfig = Field(
        default_factory=ForsetiConfig,
        description="Forseti configuration"
    )
    freya: FreyaConfig = Field(
        default_factory=FreyaConfig,
        description="Freya configuration"
    )
    verdandi: VerdandiConfig = Field(
        default_factory=VerdandiConfig,
        description="Verdandi configuration"
    )
    volundr: VolundrConfig = Field(
        default_factory=VolundrConfig,
        description="Volundr configuration"
    )

    def to_yaml(self) -> str:
        """Export configuration as YAML string."""
        data = self.model_dump(by_alias=True)
        return cast(str, yaml.dump(data, default_flow_style=False, sort_keys=False))

    def to_toml(self) -> str:
        """Export configuration as TOML string for pyproject.toml."""
        lines = ["[tool.asgard]"]
        data = self.model_dump(by_alias=True)
        lines.extend(self._dict_to_toml(data, "tool.asgard"))
        return "\n".join(lines)

    def _dict_to_toml(self, data: dict, prefix: str, indent: int = 0) -> List[str]:
        """Convert dictionary to TOML format lines."""
        lines = []
        for key, value in data.items():
            full_key = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                lines.append(f"\n[{full_key}]")
                for k, v in value.items():
                    if isinstance(v, dict):
                        lines.extend(self._dict_to_toml({k: v}, full_key))
                    elif isinstance(v, list):
                        lines.append(f"{k} = {self._to_toml_value(v)}")
                    else:
                        lines.append(f"{k} = {self._to_toml_value(v)}")
            elif not prefix.endswith("tool.asgard"):
                lines.append(f"{key} = {self._to_toml_value(value)}")
        return lines

    def _to_toml_value(self, value) -> str:
        """Convert Python value to TOML representation."""
        if isinstance(value, str):
            return f'"{value}"'
        elif isinstance(value, bool):
            return "true" if value else "false"
        elif isinstance(value, list):
            items = [self._to_toml_value(v) for v in value]
            return f"[{', '.join(items)}]"
        elif value is None:
            return '""'
        return str(value)
