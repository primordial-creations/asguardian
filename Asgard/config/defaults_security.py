"""
Asgard Default Configuration Values - Security and Infrastructure

Default configuration values for security and infrastructure modules:
Heimdall security, Verdandi, and Volundr.
"""

from Asgard.config.models_base import CICDPlatform, TerraformBackend
from Asgard.config.models_security import (
    APDEXConfig,
    AsgardConfig,
    CICDConfig,
    DockerConfig,
    HeimdallConfig,
    HeimdallSecurityConfig,
    KubernetesConfig,
    TerraformConfig,
    VerdandiConfig,
    VolundrConfig,
    WebVitalsConfig,
)
from Asgard.config.defaults_quality import (
    get_default_forseti_config,
    get_default_freya_config,
    get_default_global_config,
    get_default_heimdall_quality_config,
)


def get_default_heimdall_security_config() -> HeimdallSecurityConfig:
    """Get default Heimdall security configuration."""
    return HeimdallSecurityConfig(
        enable_bandit=True,
        bandit_severity="low",
        bandit_confidence="low",
        check_hardcoded_secrets=True,
        check_sql_injection=True,
        check_xss=True,
        check_path_traversal=True,
    )


def get_default_heimdall_config() -> HeimdallConfig:
    """Get default Heimdall configuration."""
    return HeimdallConfig(
        quality=get_default_heimdall_quality_config(),
        security=get_default_heimdall_security_config(),
        include_tests=False,
        fail_on_error=True,
    )


def get_default_web_vitals_config() -> WebVitalsConfig:
    """Get default Web Vitals configuration."""
    return WebVitalsConfig(
        lcp_threshold_ms=2500,
        fid_threshold_ms=100,
        cls_threshold=0.1,
        fcp_threshold_ms=1800,
        ttfb_threshold_ms=800,
        inp_threshold_ms=200,
        track_long_tasks=True,
        long_task_threshold_ms=50,
    )


def get_default_apdex_config() -> APDEXConfig:
    """Get default APDEX configuration."""
    return APDEXConfig(
        enabled=True,
        satisfied_threshold_ms=500,
        tolerating_threshold_ms=2000,
        target_score=0.85,
    )


def get_default_verdandi_config() -> VerdandiConfig:
    """Get default Verdandi configuration."""
    return VerdandiConfig(
        enable_profiling=True,
        profile_depth=10,
        sample_rate=1.0,
        apdex=get_default_apdex_config(),
        apdex_threshold_ms=500,
        sla_percentile=95.0,
        sla_response_time_ms=1000,
        memory_threshold_mb=100.0,
        cpu_threshold_percent=80.0,
        response_time_threshold_ms=1000.0,
        cache_hit_rate_threshold=0.8,
        track_cache_metrics=True,
        web_vitals=get_default_web_vitals_config(),
        generate_flamegraphs=False,
        flamegraph_output_path=".verdandi/flamegraphs",
        retain_metrics_days=30,
        baseline_comparison=True,
    )


def get_default_kubernetes_config() -> KubernetesConfig:
    """Get default Kubernetes configuration."""
    return KubernetesConfig(
        version="1.28",
        namespace="default",
        enable_network_policies=True,
        enable_pod_security=True,
        pod_security_level="baseline",
        resource_quotas_enabled=False,
        default_replicas=1,
        enable_hpa=False,
        hpa_min_replicas=1,
        hpa_max_replicas=10,
    )


def get_default_docker_config() -> DockerConfig:
    """Get default Docker configuration."""
    return DockerConfig(
        default_registry="",
        base_image="python:3.11-slim",
        enable_multi_stage=True,
        enable_buildkit=True,
        cache_from=[],
        labels={},
        security_scan_enabled=True,
    )


def get_default_terraform_config() -> TerraformConfig:
    """Get default Terraform configuration."""
    return TerraformConfig(
        backend=TerraformBackend.LOCAL,
        backend_config={},
        version_constraint=">= 1.5.0",
        provider_versions={
            "aws": "~> 5.0",
            "google": "~> 5.0",
            "azurerm": "~> 3.0",
            "kubernetes": "~> 2.0",
        },
        enable_state_locking=True,
        workspace_prefix="",
    )


def get_default_cicd_config() -> CICDConfig:
    """Get default CI/CD configuration."""
    return CICDConfig(
        platform=CICDPlatform.GITHUB_ACTIONS,
        enable_caching=True,
        parallel_jobs=4,
        timeout_minutes=30,
        enable_security_scans=True,
        enable_lint_checks=True,
        enable_test_coverage=True,
        artifact_retention_days=30,
    )


def get_default_volundr_config() -> VolundrConfig:
    """Get default Volundr configuration."""
    return VolundrConfig(
        templates_path="",
        output_path=".volundr/generated",
        dry_run=False,
        docker=get_default_docker_config(),
        default_registry="",
        kubernetes=get_default_kubernetes_config(),
        kubernetes_version="1.28",
        kubernetes_namespace="default",
        helm_chart_version="0.1.0",
        helm_repository="",
        enable_helm_generation=True,
        terraform=get_default_terraform_config(),
        terraform_backend=TerraformBackend.LOCAL,
        cicd=get_default_cicd_config(),
        cicd_platform=CICDPlatform.GITHUB_ACTIONS,
        validate_generated=True,
        fail_on_validation_error=True,
    )


def get_default_config() -> AsgardConfig:
    """Get complete default Asgard configuration."""
    return AsgardConfig(
        version="1.0.0",
        global_config=get_default_global_config(),
        heimdall=get_default_heimdall_config(),
        forseti=get_default_forseti_config(),
        freya=get_default_freya_config(),
        verdandi=get_default_verdandi_config(),
        volundr=get_default_volundr_config(),
    )


DEFAULT_CONFIG = get_default_config()
