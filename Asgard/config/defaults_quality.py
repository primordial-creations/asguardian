"""
Asgard Default Configuration Values - Quality

Default configuration values for quality-related modules:
GlobalConfig, Heimdall quality, Freya, and Forseti.
"""

from Asgard.config.models_base import BrowserType, GlobalConfig, OutputFormat, ScreenshotFormat
from Asgard.config.models_quality import (
    AccessibilityConfig,
    DatetimeConfig,
    ForbiddenImportConfig,
    ForsetiConfig,
    FreyaConfig,
    HeimdallQualityConfig,
    SchemaValidationConfig,
    TypingCoverageConfig,
    ViewportConfig,
)


DEFAULT_FORBIDDEN_IMPORTS: dict[str, list[str]] = {}

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
