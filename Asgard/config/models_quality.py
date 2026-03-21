"""
Asgard Configuration Models - Quality

Quality-related configuration models for Heimdall, Freya, Forseti,
Verdandi, and Volundr modules.
"""

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field, model_validator

from Asgard.config.models_base import (
    BrowserType,
    CICDPlatform,
    ScreenshotFormat,
    TerraformBackend,
)


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

    cyclomatic_complexity_threshold: int = Field(default=10, description="Maximum cyclomatic complexity")
    cognitive_complexity_threshold: int = Field(default=15, description="Maximum cognitive complexity")
    max_file_lines: int = Field(default=500, description="Maximum lines per file")
    max_function_lines: int = Field(default=50, description="Maximum lines per function")
    min_duplicate_lines: int = Field(default=6, description="Minimum lines for duplication detection")
    min_duplicate_tokens: int = Field(default=50, description="Minimum tokens for duplication detection")
    enable_smell_detection: bool = Field(default=True, description="Enable code smell detection")
    smell_categories: List[str] = Field(
        default_factory=lambda: ["bloaters", "oo_abusers", "change_preventers", "dispensables", "couplers"],
        description="Code smell categories to check"
    )
    enable_debt_calculation: bool = Field(default=True, description="Enable technical debt calculation")
    debt_cost_per_hour: float = Field(default=50.0, description="Cost per hour for debt calculation")
    check_lazy_imports: bool = Field(default=True, description="Check for lazy imports")
    check_env_fallbacks: bool = Field(default=True, description="Check for environment variable fallbacks")
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

    browser: BrowserType = Field(default=BrowserType.CHROMIUM, description="Browser to use for testing")
    headless: bool = Field(default=True, description="Run browser in headless mode")
    slow_mo_ms: int = Field(default=0, description="Slow down browser operations by this many milliseconds", ge=0)
    timeout_ms: int = Field(default=30000, description="Default timeout for browser operations in milliseconds", ge=1000, le=300000)
    default_viewport: ViewportConfig = Field(
        default_factory=ViewportConfig,
        description="Default viewport configuration"
    )
    additional_viewports: List[ViewportConfig] = Field(
        default_factory=list,
        description="Additional viewports to test against"
    )
    screenshot_format: ScreenshotFormat = Field(default=ScreenshotFormat.PNG, description="Screenshot format")
    screenshot_quality: int = Field(
        default=90,
        description="Screenshot quality for JPEG/WebP formats (1-100)",
        ge=1,
        le=100
    )
    full_page_screenshots: bool = Field(default=False, description="Capture full page screenshots")
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
    baseline_path: str = Field(default=".freya/baselines", description="Path to baseline images")
    diff_output_path: str = Field(default=".freya/diffs", description="Path to store diff images")
    auto_update_baselines: bool = Field(default=False, description="Automatically update baselines on failure")
    accessibility: AccessibilityConfig = Field(
        default_factory=AccessibilityConfig,
        description="Accessibility testing configuration"
    )
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

    openapi_version: str = Field(default="3.0.0", description="OpenAPI specification version")
    spec_paths: List[str] = Field(
        default_factory=lambda: ["**/openapi.yaml", "**/openapi.json", "**/swagger.yaml", "**/swagger.json"],
        description="Glob patterns for OpenAPI specification files"
    )
    strict_mode: bool = Field(default=False, description="Enable strict validation mode")
    allow_deprecated: bool = Field(default=True, description="Allow deprecated endpoints and parameters")
    schema_validation: SchemaValidationConfig = Field(
        default_factory=SchemaValidationConfig,
        description="Schema validation configuration"
    )
    validate_examples: bool = Field(default=True, description="Validate example values in specs")
    validate_schemas: bool = Field(default=True, description="Validate JSON schemas")
    max_response_time_ms: int = Field(
        default=5000,
        description="Maximum acceptable response time in milliseconds",
        ge=100,
        le=60000
    )
    schema_cache_ttl: int = Field(
        default=3600,
        description="Schema cache time-to-live in seconds",
        ge=0,
        le=86400
    )
    enable_schema_cache: bool = Field(default=True, description="Enable schema caching")
    allowed_response_codes: List[int] = Field(
        default_factory=lambda: [200, 201, 204, 400, 401, 403, 404, 422, 500],
        description="Allowed HTTP response codes"
    )
    required_error_schema: bool = Field(
        default=True,
        description="Require error responses to follow a standard schema"
    )
    validate_security_schemes: bool = Field(default=True, description="Validate security scheme definitions")
    require_authentication: bool = Field(default=False, description="Require all endpoints to have authentication")
