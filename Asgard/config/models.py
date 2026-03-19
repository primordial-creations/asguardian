"""
Asgard Configuration Models

Pydantic models for unified configuration across all Asgard modules.
"""

from enum import Enum
from typing import Dict, List, Literal, Optional, cast

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, Field, model_validator


class OutputFormat(str, Enum):
    """Output format options for analysis results."""
    TEXT = "text"
    JSON = "json"
    MARKDOWN = "markdown"
    HTML = "html"
    GITHUB = "github"


class ScreenshotFormat(str, Enum):
    """Screenshot format options for visual testing."""
    PNG = "png"
    JPEG = "jpeg"
    WEBP = "webp"


class BrowserType(str, Enum):
    """Browser types for visual testing."""
    CHROMIUM = "chromium"
    FIREFOX = "firefox"
    WEBKIT = "webkit"


class CICDPlatform(str, Enum):
    """CI/CD platform options."""
    GITHUB_ACTIONS = "github_actions"
    GITLAB_CI = "gitlab_ci"
    JENKINS = "jenkins"
    AZURE_DEVOPS = "azure_devops"
    CIRCLECI = "circleci"


class TerraformBackend(str, Enum):
    """Terraform backend options."""
    LOCAL = "local"
    S3 = "s3"
    GCS = "gcs"
    AZURE_BLOB = "azure_blob"
    CONSUL = "consul"
    KUBERNETES = "kubernetes"


class GlobalConfig(BaseModel):
    """Global configuration shared across all modules."""
    model_config = {"use_enum_values": True}

    exclude_patterns: List[str] = Field(
        default_factory=lambda: [
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
        ],
        description="Glob patterns to exclude from analysis"
    )
    output_format: OutputFormat = Field(
        default=OutputFormat.TEXT,
        description="Default output format for analysis results"
    )
    verbose: bool = Field(default=False, description="Enable verbose output")
    parallel: bool = Field(default=False, description="Enable parallel processing")
    workers: Optional[int] = Field(default=None, description="Number of worker processes (defaults to CPU count - 1)")
    incremental: bool = Field(default=False, description="Enable incremental scanning using cache")
    cache_path: str = Field(default=".asgard-cache.json", description="Path to cache file")


class ForbiddenImportConfig(BaseModel):
    """Configuration for forbidden imports scanner."""
    model_config = {"use_enum_values": True}

    forbidden_modules: Dict[str, str] = Field(
        default_factory=dict,
        description="Mapping of forbidden module names to remediation messages"
    )
    allowed_paths: List[str] = Field(
        default_factory=lambda: [
            "**/wrappers/**",
        ],
        description="Glob patterns where forbidden imports are allowed (wrapper implementations)"
    )
    severity: str = Field(default="high", description="Default severity for forbidden import violations")


class DatetimeConfig(BaseModel):
    """Configuration for datetime usage scanner."""
    model_config = {"use_enum_values": True}

    check_utcnow: bool = Field(default=True, description="Check for deprecated datetime.utcnow()")
    check_now_no_tz: bool = Field(default=True, description="Check for datetime.now() without timezone")
    check_today_no_tz: bool = Field(default=True, description="Check for datetime.today() without timezone")
    allowed_patterns: List[str] = Field(
        default_factory=list,
        description="File patterns where datetime issues are allowed"
    )


class TypingCoverageConfig(BaseModel):
    """Configuration for type annotation coverage scanner."""
    model_config = {"use_enum_values": True}

    minimum_coverage: float = Field(
        default=80.0,
        description="Minimum percentage of functions that must have full type annotations",
        ge=0.0,
        le=100.0
    )
    require_return_type: bool = Field(default=True, description="Require return type annotations")
    require_parameter_types: bool = Field(default=True, description="Require parameter type annotations")
    exclude_private: bool = Field(default=False, description="Exclude private methods (_method)")
    exclude_dunder: bool = Field(default=True, description="Exclude dunder methods (__method__)")
    exclude_patterns: List[str] = Field(
        default_factory=lambda: ["**/test_*.py", "**/conftest.py"],
        description="File patterns to exclude from typing coverage"
    )


class HeimdallQualityConfig(BaseModel):
    """Configuration for Heimdall quality analysis."""
    model_config = {"use_enum_values": True}

    # Complexity thresholds
    cyclomatic_complexity_threshold: int = Field(default=10, description="Maximum cyclomatic complexity")
    cognitive_complexity_threshold: int = Field(default=15, description="Maximum cognitive complexity")

    # File length thresholds
    max_file_lines: int = Field(default=500, description="Maximum lines per file")
    max_function_lines: int = Field(default=50, description="Maximum lines per function")

    # Duplication thresholds
    min_duplicate_lines: int = Field(default=6, description="Minimum lines for duplication detection")
    min_duplicate_tokens: int = Field(default=50, description="Minimum tokens for duplication detection")

    # Code smell detection
    enable_smell_detection: bool = Field(default=True, description="Enable code smell detection")
    smell_categories: List[str] = Field(
        default_factory=lambda: ["bloaters", "oo_abusers", "change_preventers", "dispensables", "couplers"],
        description="Code smell categories to check"
    )

    # Technical debt
    enable_debt_calculation: bool = Field(default=True, description="Enable technical debt calculation")
    debt_cost_per_hour: float = Field(default=50.0, description="Cost per hour for debt calculation")

    # Lazy imports
    check_lazy_imports: bool = Field(default=True, description="Check for lazy imports")

    # Env fallbacks
    check_env_fallbacks: bool = Field(default=True, description="Check for environment variable fallbacks")

    # New scanner configs
    forbidden_imports: ForbiddenImportConfig = Field(
        default_factory=ForbiddenImportConfig,
        description="Forbidden imports scanner configuration"
    )
    datetime: DatetimeConfig = Field(
        default_factory=DatetimeConfig,
        description="Datetime usage scanner configuration"
    )
    typing_coverage: TypingCoverageConfig = Field(
        default_factory=TypingCoverageConfig,
        description="Type annotation coverage configuration"
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

    # Module-level settings
    include_tests: bool = Field(default=False, description="Include test files in analysis")
    fail_on_error: bool = Field(default=True, description="Exit with error code if issues found")


# =============================================================================
# Freya Configuration (Visual Testing)
# =============================================================================

class ViewportConfig(BaseModel):
    """Viewport configuration for visual testing."""
    model_config = {"use_enum_values": True}

    width: int = Field(default=1920, description="Viewport width in pixels", ge=320, le=3840)
    height: int = Field(default=1080, description="Viewport height in pixels", ge=240, le=2160)
    device_scale_factor: float = Field(default=1.0, description="Device scale factor for HiDPI displays", ge=0.5, le=4.0)
    is_mobile: bool = Field(default=False, description="Emulate mobile viewport")
    has_touch: bool = Field(default=False, description="Enable touch events")


class AccessibilityConfig(BaseModel):
    """Accessibility testing configuration for Freya."""
    model_config = {"use_enum_values": True}

    enabled: bool = Field(default=True, description="Enable accessibility testing")
    wcag_level: Literal["A", "AA", "AAA"] = Field(default="AA", description="WCAG conformance level to test against")
    include_warnings: bool = Field(default=True, description="Include accessibility warnings in results")
    include_notices: bool = Field(default=False, description="Include accessibility notices in results")
    rules_to_skip: List[str] = Field(
        default_factory=list,
        description="List of accessibility rule IDs to skip"
    )
    elements_to_skip: List[str] = Field(
        default_factory=list,
        description="CSS selectors for elements to exclude from accessibility testing"
    )
    color_contrast_threshold: float = Field(
        default=4.5,
        description="Minimum color contrast ratio for normal text",
        ge=1.0,
        le=21.0
    )
    large_text_contrast_threshold: float = Field(
        default=3.0,
        description="Minimum color contrast ratio for large text",
        ge=1.0,
        le=21.0
    )


class FreyaConfig(BaseModel):
    """
    Configuration for Freya visual testing module.

    Freya handles visual regression testing, screenshot comparison,
    and accessibility validation.
    """
    model_config = {"use_enum_values": True}

    # Browser settings
    browser: BrowserType = Field(default=BrowserType.CHROMIUM, description="Browser to use for testing")
    headless: bool = Field(default=True, description="Run browser in headless mode")
    slow_mo_ms: int = Field(default=0, description="Slow down browser operations by this many milliseconds", ge=0)
    timeout_ms: int = Field(default=30000, description="Default timeout for browser operations in milliseconds", ge=1000, le=300000)

    # Viewport settings
    default_viewport: ViewportConfig = Field(
        default_factory=ViewportConfig,
        description="Default viewport configuration"
    )
    additional_viewports: List[ViewportConfig] = Field(
        default_factory=list,
        description="Additional viewports to test against"
    )

    # Screenshot settings
    screenshot_format: ScreenshotFormat = Field(default=ScreenshotFormat.PNG, description="Screenshot format")
    screenshot_quality: int = Field(
        default=90,
        description="Screenshot quality for JPEG/WebP formats (1-100)",
        ge=1,
        le=100
    )
    full_page_screenshots: bool = Field(default=False, description="Capture full page screenshots")

    # Visual comparison settings
    diff_threshold: float = Field(
        default=0.1,
        description="Pixel difference threshold for visual comparison (0.0-1.0)",
        ge=0.0,
        le=1.0
    )
    anti_aliasing_tolerance: float = Field(
        default=0.1,
        description="Tolerance for anti-aliased pixels",
        ge=0.0,
        le=1.0
    )
    ignore_colors: bool = Field(default=False, description="Ignore color differences, compare structure only")
    ignore_regions: List[Dict[str, int]] = Field(
        default_factory=list,
        description="Regions to ignore in comparisons (list of {x, y, width, height})"
    )

    # Baseline management
    baseline_path: str = Field(default=".freya/baselines", description="Path to baseline images")
    diff_output_path: str = Field(default=".freya/diffs", description="Path to store diff images")
    auto_update_baselines: bool = Field(default=False, description="Automatically update baselines on failure")

    # Accessibility testing
    accessibility: AccessibilityConfig = Field(
        default_factory=AccessibilityConfig,
        description="Accessibility testing configuration"
    )

    # Performance
    parallel_captures: int = Field(
        default=4,
        description="Number of parallel screenshot captures",
        ge=1,
        le=16
    )
    retry_on_failure: int = Field(
        default=2,
        description="Number of retries for flaky screenshots",
        ge=0,
        le=5
    )


# =============================================================================
# Forseti Configuration (API Validation)
# =============================================================================

class SchemaValidationConfig(BaseModel):
    """Schema validation configuration for Forseti."""
    model_config = {"use_enum_values": True}

    validate_request_body: bool = Field(default=True, description="Validate request body schemas")
    validate_response_body: bool = Field(default=True, description="Validate response body schemas")
    validate_query_params: bool = Field(default=True, description="Validate query parameter schemas")
    validate_path_params: bool = Field(default=True, description="Validate path parameter schemas")
    validate_headers: bool = Field(default=True, description="Validate header schemas")
    additional_properties_allowed: bool = Field(
        default=False,
        description="Allow additional properties not defined in schema"
    )


class ForsetiConfig(BaseModel):
    """
    Configuration for Forseti API validation module.

    Forseti handles OpenAPI/Swagger validation, schema compliance,
    and API contract testing.
    """
    model_config = {"use_enum_values": True}

    # OpenAPI settings
    openapi_version: str = Field(default="3.0.0", description="OpenAPI specification version")
    spec_paths: List[str] = Field(
        default_factory=lambda: ["**/openapi.yaml", "**/openapi.json", "**/swagger.yaml", "**/swagger.json"],
        description="Glob patterns for OpenAPI specification files"
    )

    # Validation modes
    strict_mode: bool = Field(default=False, description="Enable strict validation mode")
    allow_deprecated: bool = Field(default=True, description="Allow deprecated endpoints and parameters")

    # Schema validation
    schema_validation: SchemaValidationConfig = Field(
        default_factory=SchemaValidationConfig,
        description="Schema validation configuration"
    )
    validate_examples: bool = Field(default=True, description="Validate example values in specs")
    validate_schemas: bool = Field(default=True, description="Validate JSON schemas")

    # Performance thresholds
    max_response_time_ms: int = Field(
        default=5000,
        description="Maximum acceptable response time in milliseconds",
        ge=100,
        le=60000
    )

    # Caching
    schema_cache_ttl: int = Field(
        default=3600,
        description="Schema cache time-to-live in seconds",
        ge=0,
        le=86400
    )
    enable_schema_cache: bool = Field(default=True, description="Enable schema caching")

    # Response codes
    allowed_response_codes: List[int] = Field(
        default_factory=lambda: [200, 201, 204, 400, 401, 403, 404, 422, 500],
        description="Allowed HTTP response codes"
    )
    required_error_schema: bool = Field(
        default=True,
        description="Require error responses to follow a standard schema"
    )

    # Security validation
    validate_security_schemes: bool = Field(default=True, description="Validate security scheme definitions")
    require_authentication: bool = Field(default=False, description="Require all endpoints to have authentication")


# =============================================================================
# Verdandi Configuration (Performance Metrics)
# =============================================================================

class WebVitalsConfig(BaseModel):
    """Web Vitals thresholds configuration for Verdandi."""
    model_config = {"use_enum_values": True}

    # Core Web Vitals
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

    # Additional metrics
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

    # Tracking settings
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

    # Profiling settings
    enable_profiling: bool = Field(default=True, description="Enable code profiling")
    profile_depth: int = Field(default=10, description="Call stack depth for profiling", ge=1, le=100)
    sample_rate: float = Field(
        default=1.0,
        description="Sampling rate for profiling (0.0-1.0)",
        ge=0.01,
        le=1.0
    )

    # APDEX configuration
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

    # SLA settings
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

    # Resource thresholds
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

    # Cache metrics
    cache_hit_rate_threshold: float = Field(
        default=0.8,
        description="Minimum acceptable cache hit rate (0.0-1.0)",
        ge=0.0,
        le=1.0
    )
    track_cache_metrics: bool = Field(default=True, description="Track cache hit/miss metrics")

    # Web Vitals
    web_vitals: WebVitalsConfig = Field(
        default_factory=WebVitalsConfig,
        description="Web Vitals thresholds configuration"
    )

    # Output settings
    generate_flamegraphs: bool = Field(default=False, description="Generate flamegraph visualizations")
    flamegraph_output_path: str = Field(default=".verdandi/flamegraphs", description="Path for flamegraph output")

    # Historical tracking
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


# =============================================================================
# Volundr Configuration (Infrastructure Generation)
# =============================================================================

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

    # General settings
    templates_path: str = Field(default="", description="Custom templates path")
    output_path: str = Field(default=".volundr/generated", description="Path for generated files")
    dry_run: bool = Field(default=False, description="Generate without writing files")

    # Docker settings
    docker: DockerConfig = Field(
        default_factory=DockerConfig,
        description="Docker configuration"
    )
    # Legacy field for backwards compatibility
    default_registry: str = Field(
        default="",
        description="Default Docker registry (deprecated, use docker.default_registry)"
    )

    # Kubernetes settings
    kubernetes: KubernetesConfig = Field(
        default_factory=KubernetesConfig,
        description="Kubernetes configuration"
    )
    # Legacy fields for backwards compatibility
    kubernetes_version: str = Field(
        default="1.28",
        description="Target Kubernetes version (deprecated, use kubernetes.version)"
    )
    kubernetes_namespace: str = Field(
        default="default",
        description="Kubernetes namespace (deprecated, use kubernetes.namespace)"
    )

    # Helm settings
    helm_chart_version: str = Field(default="0.1.0", description="Default Helm chart version")
    helm_repository: str = Field(default="", description="Default Helm repository URL")
    enable_helm_generation: bool = Field(default=True, description="Generate Helm charts")

    # Terraform settings
    terraform: TerraformConfig = Field(
        default_factory=TerraformConfig,
        description="Terraform configuration"
    )
    # Legacy field for backwards compatibility
    terraform_backend: TerraformBackend = Field(
        default=TerraformBackend.LOCAL,
        description="Terraform backend (deprecated, use terraform.backend)"
    )

    # CI/CD settings
    cicd: CICDConfig = Field(
        default_factory=CICDConfig,
        description="CI/CD configuration"
    )
    # Legacy field for backwards compatibility
    cicd_platform: CICDPlatform = Field(
        default=CICDPlatform.GITHUB_ACTIONS,
        description="CI/CD platform (deprecated, use cicd.platform)"
    )

    # Validation
    validate_generated: bool = Field(default=True, description="Validate generated configurations")
    fail_on_validation_error: bool = Field(default=True, description="Fail if validation errors occur")

    @model_validator(mode="after")
    def sync_legacy_fields(self) -> "VolundrConfig":
        """Sync legacy fields with nested configs for backwards compatibility."""
        # Sync docker registry
        if self.default_registry and not self.docker.default_registry:
            self.docker.default_registry = self.default_registry
        elif self.docker.default_registry:
            self.default_registry = self.docker.default_registry

        # Sync kubernetes settings
        if self.kubernetes_version != "1.28" and self.kubernetes.version == "1.28":
            self.kubernetes.version = self.kubernetes_version
        elif self.kubernetes.version != "1.28":
            self.kubernetes_version = self.kubernetes.version

        if self.kubernetes_namespace != "default" and self.kubernetes.namespace == "default":
            self.kubernetes.namespace = self.kubernetes_namespace
        elif self.kubernetes.namespace != "default":
            self.kubernetes_namespace = self.kubernetes.namespace

        # Sync terraform backend
        if self.terraform_backend != TerraformBackend.LOCAL and self.terraform.backend == TerraformBackend.LOCAL:
            self.terraform.backend = self.terraform_backend
        elif self.terraform.backend != TerraformBackend.LOCAL:
            self.terraform_backend = self.terraform.backend

        # Sync cicd platform
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
