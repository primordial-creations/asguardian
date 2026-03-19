"""
Asgard Default Configuration Values

Provides default configuration values for all Asgard modules.
"""

from Asgard.config.models import (
    AccessibilityConfig,
    APDEXConfig,
    AsgardConfig,
    BrowserType,
    CICDConfig,
    CICDPlatform,
    DatetimeConfig,
    DockerConfig,
    ForbiddenImportConfig,
    ForsetiConfig,
    FreyaConfig,
    GlobalConfig,
    HeimdallConfig,
    HeimdallQualityConfig,
    HeimdallSecurityConfig,
    KubernetesConfig,
    OutputFormat,
    SchemaValidationConfig,
    ScreenshotFormat,
    TerraformBackend,
    TerraformConfig,
    TypingCoverageConfig,
    VerdandiConfig,
    ViewportConfig,
    VolundrConfig,
    WebVitalsConfig,
)


# Default forbidden imports (configurable per project via asgard.yaml)
DEFAULT_FORBIDDEN_IMPORTS: dict[str, list[str]] = {}

# Default exclude patterns
DEFAULT_EXCLUDE_PATTERNS = [
    "__pycache__",
    "node_modules",
    ".git",
    ".venv",
    "venv",
    "build",
    "dist",
    "*.pyc",
    "*.pyo",
    ".tox",
    ".eggs",
    "*.egg-info",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "htmlcov",
    ".coverage",
]

# Default allowed paths for forbidden imports (wrapper implementations)
DEFAULT_ALLOWED_PATHS = [
    "**/wrappers/**",
]


def get_default_global_config() -> GlobalConfig:
    """Get default global configuration."""
    return GlobalConfig(
        exclude_patterns=DEFAULT_EXCLUDE_PATTERNS,
        output_format=OutputFormat.TEXT,
        verbose=False,
        parallel=False,
        workers=None,
        incremental=False,
        cache_path=".asgard-cache.json",
    )


def get_default_forbidden_import_config() -> ForbiddenImportConfig:
    """Get default forbidden imports configuration."""
    return ForbiddenImportConfig(
        forbidden_modules=DEFAULT_FORBIDDEN_IMPORTS,
        allowed_paths=DEFAULT_ALLOWED_PATHS,
        severity="high",
    )


def get_default_datetime_config() -> DatetimeConfig:
    """Get default datetime configuration."""
    return DatetimeConfig(
        check_utcnow=True,
        check_now_no_tz=True,
        check_today_no_tz=True,
        allowed_patterns=[],
    )


def get_default_typing_coverage_config() -> TypingCoverageConfig:
    """Get default typing coverage configuration."""
    return TypingCoverageConfig(
        minimum_coverage=80.0,
        require_return_type=True,
        require_parameter_types=True,
        exclude_private=False,
        exclude_dunder=True,
        exclude_patterns=["**/test_*.py", "**/conftest.py"],
    )


def get_default_heimdall_quality_config() -> HeimdallQualityConfig:
    """Get default Heimdall quality configuration."""
    return HeimdallQualityConfig(
        cyclomatic_complexity_threshold=10,
        cognitive_complexity_threshold=15,
        max_file_lines=500,
        max_function_lines=50,
        min_duplicate_lines=6,
        min_duplicate_tokens=50,
        enable_smell_detection=True,
        smell_categories=["bloaters", "oo_abusers", "change_preventers", "dispensables", "couplers"],
        enable_debt_calculation=True,
        debt_cost_per_hour=50.0,
        check_lazy_imports=True,
        check_env_fallbacks=True,
        forbidden_imports=get_default_forbidden_import_config(),
        datetime=get_default_datetime_config(),
        typing_coverage=get_default_typing_coverage_config(),
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


# =============================================================================
# Freya Defaults
# =============================================================================

def get_default_viewport_config() -> ViewportConfig:
    """Get default viewport configuration."""
    return ViewportConfig(
        width=1920,
        height=1080,
        device_scale_factor=1.0,
        is_mobile=False,
        has_touch=False,
    )


def get_default_accessibility_config() -> AccessibilityConfig:
    """Get default accessibility configuration."""
    return AccessibilityConfig(
        enabled=True,
        wcag_level="AA",
        include_warnings=True,
        include_notices=False,
        rules_to_skip=[],
        elements_to_skip=[],
        color_contrast_threshold=4.5,
        large_text_contrast_threshold=3.0,
    )


def get_default_freya_config() -> FreyaConfig:
    """Get default Freya configuration."""
    return FreyaConfig(
        browser=BrowserType.CHROMIUM,
        headless=True,
        slow_mo_ms=0,
        timeout_ms=30000,
        default_viewport=get_default_viewport_config(),
        additional_viewports=[],
        screenshot_format=ScreenshotFormat.PNG,
        screenshot_quality=90,
        full_page_screenshots=False,
        diff_threshold=0.1,
        anti_aliasing_tolerance=0.1,
        ignore_colors=False,
        ignore_regions=[],
        baseline_path=".freya/baselines",
        diff_output_path=".freya/diffs",
        auto_update_baselines=False,
        accessibility=get_default_accessibility_config(),
        parallel_captures=4,
        retry_on_failure=2,
    )


# =============================================================================
# Forseti Defaults
# =============================================================================

def get_default_schema_validation_config() -> SchemaValidationConfig:
    """Get default schema validation configuration."""
    return SchemaValidationConfig(
        validate_request_body=True,
        validate_response_body=True,
        validate_query_params=True,
        validate_path_params=True,
        validate_headers=True,
        additional_properties_allowed=False,
    )


def get_default_forseti_config() -> ForsetiConfig:
    """Get default Forseti configuration."""
    return ForsetiConfig(
        openapi_version="3.0.0",
        spec_paths=["**/openapi.yaml", "**/openapi.json", "**/swagger.yaml", "**/swagger.json"],
        strict_mode=False,
        allow_deprecated=True,
        schema_validation=get_default_schema_validation_config(),
        validate_examples=True,
        validate_schemas=True,
        max_response_time_ms=5000,
        schema_cache_ttl=3600,
        enable_schema_cache=True,
        allowed_response_codes=[200, 201, 204, 400, 401, 403, 404, 422, 500],
        required_error_schema=True,
        validate_security_schemes=True,
        require_authentication=False,
    )


# =============================================================================
# Verdandi Defaults
# =============================================================================

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


# =============================================================================
# Volundr Defaults
# =============================================================================

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


# Singleton default configuration
DEFAULT_CONFIG = get_default_config()
