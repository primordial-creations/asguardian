"""
Freya Integration Base Models

Browser config, device config, unified test config, result, report,
baseline, and crawl config models.
"""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class TestCategory(str, Enum):
    """Test categories."""
    ACCESSIBILITY = "accessibility"
    VISUAL = "visual"
    RESPONSIVE = "responsive"
    ALL = "all"


class TestSeverity(str, Enum):
    """Severity levels for filtering."""
    CRITICAL = "critical"
    SERIOUS = "serious"
    MODERATE = "moderate"
    MINOR = "minor"


class ReportFormat(str, Enum):
    """Output report formats."""
    JSON = "json"
    HTML = "html"
    JUNIT = "junit"
    MARKDOWN = "markdown"


class BrowserConfig(BaseModel):
    """Browser configuration for Playwright."""
    browser_type: str = Field(default="chromium", description="Browser type")
    headless: bool = Field(default=True, description="Run in headless mode")
    slow_mo: int = Field(default=0, description="Slow down operations (ms)")
    timeout: int = Field(default=30000, description="Default timeout (ms)")
    viewport_width: int = Field(default=1920, description="Default viewport width")
    viewport_height: int = Field(default=1080, description="Default viewport height")
    device_scale_factor: float = Field(default=1.0, description="Device scale factor")
    user_agent: Optional[str] = Field(default=None, description="Custom user agent")
    locale: str = Field(default="en-US", description="Browser locale")


class DeviceConfig(BaseModel):
    """Device emulation configuration."""
    name: str = Field(description="Device name")
    width: int = Field(description="Viewport width")
    height: int = Field(description="Viewport height")
    device_scale_factor: float = Field(default=2.0, description="Device pixel ratio")
    is_mobile: bool = Field(default=True, description="Is mobile device")
    has_touch: bool = Field(default=True, description="Has touch support")
    user_agent: Optional[str] = Field(default=None, description="Device user agent")


class UnifiedTestConfig(BaseModel):
    """Configuration for unified testing."""
    url: str = Field(description="URL to test")
    categories: List[TestCategory] = Field(
        default=[TestCategory.ALL],
        description="Test categories to run"
    )
    min_severity: TestSeverity = Field(
        default=TestSeverity.MINOR,
        description="Minimum severity to report"
    )
    devices: List[str] = Field(
        default=["desktop", "tablet", "mobile"],
        description="Devices to test"
    )
    capture_screenshots: bool = Field(
        default=True,
        description="Capture screenshots during testing"
    )
    output_directory: str = Field(
        default="./freya_output",
        description="Output directory for reports"
    )
    browser_config: BrowserConfig = Field(
        default_factory=BrowserConfig,
        description="Browser configuration"
    )
    parallel: bool = Field(
        default=False,
        description="Run tests in parallel"
    )


class UnifiedTestResult(BaseModel):
    """Result from a single test."""
    category: TestCategory = Field(description="Test category")
    test_name: str = Field(description="Name of the test")
    passed: bool = Field(description="Whether the test passed")
    severity: Optional[TestSeverity] = Field(default=None, description="Issue severity")
    message: str = Field(description="Result message")
    element_selector: Optional[str] = Field(default=None, description="Affected element")
    suggested_fix: Optional[str] = Field(default=None, description="How to fix")
    wcag_reference: Optional[str] = Field(default=None, description="WCAG guideline")
    screenshot_path: Optional[str] = Field(default=None, description="Screenshot path")
    details: Dict[str, Any] = Field(default_factory=dict, description="Additional details")


class UnifiedTestReport(BaseModel):
    """Complete unified test report."""
    url: str = Field(description="Tested URL")
    tested_at: str = Field(description="Test timestamp")
    duration_ms: int = Field(description="Total test duration")

    # Summary
    total_tests: int = Field(description="Total tests run")
    passed: int = Field(description="Tests passed")
    failed: int = Field(description="Tests failed")

    # By category
    accessibility_results: List[UnifiedTestResult] = Field(
        default_factory=list,
        description="Accessibility test results"
    )
    visual_results: List[UnifiedTestResult] = Field(
        default_factory=list,
        description="Visual test results"
    )
    responsive_results: List[UnifiedTestResult] = Field(
        default_factory=list,
        description="Responsive test results"
    )

    # By severity
    critical_count: int = Field(default=0, description="Critical issues")
    serious_count: int = Field(default=0, description="Serious issues")
    moderate_count: int = Field(default=0, description="Moderate issues")
    minor_count: int = Field(default=0, description="Minor issues")

    # Scores
    accessibility_score: float = Field(default=0.0, description="Accessibility score")
    visual_score: float = Field(default=0.0, description="Visual score")
    responsive_score: float = Field(default=0.0, description="Responsive score")
    overall_score: float = Field(default=0.0, description="Overall score")

    # Metadata
    config: UnifiedTestConfig = Field(description="Test configuration")
    screenshots: Dict[str, str] = Field(default_factory=dict, description="Screenshots")


class ReportConfig(BaseModel):
    """Configuration for report generation."""
    format: ReportFormat = Field(default=ReportFormat.HTML, description="Report format")
    output_path: str = Field(description="Output file path")
    include_screenshots: bool = Field(default=True, description="Include screenshots")
    include_details: bool = Field(default=True, description="Include detailed findings")
    theme: str = Field(default="default", description="Report theme")
    title: str = Field(default="Freya Test Report", description="Report title")


class BaselineEntry(BaseModel):
    """A baseline entry for visual comparison."""
    url: str = Field(description="Page URL")
    name: str = Field(description="Baseline name")
    created_at: str = Field(description="Creation timestamp")
    updated_at: str = Field(description="Last update timestamp")
    screenshot_path: str = Field(description="Baseline screenshot path")
    viewport_width: int = Field(description="Viewport width")
    viewport_height: int = Field(description="Viewport height")
    device: Optional[str] = Field(default=None, description="Device name")
    hash: str = Field(description="Image hash for quick comparison")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class BaselineConfig(BaseModel):
    """Configuration for baseline management."""
    storage_directory: str = Field(
        default="./freya_baselines",
        description="Baseline storage directory"
    )
    auto_update: bool = Field(
        default=False,
        description="Automatically update baselines on failure"
    )
    version_baselines: bool = Field(
        default=True,
        description="Keep versioned history of baselines"
    )
    max_versions: int = Field(
        default=10,
        description="Maximum versions to keep"
    )
    diff_threshold: float = Field(
        default=0.1,
        description="Difference threshold for comparison"
    )


class CrawlConfig(BaseModel):
    """Configuration for site crawling."""
    start_url: str = Field(description="Starting URL for crawl")
    max_depth: int = Field(default=3, description="Maximum crawl depth")
    max_pages: int = Field(default=100, description="Maximum pages to crawl")
    additional_routes: List[str] = Field(
        default_factory=list,
        description="Additional routes to test (for SPAs)"
    )
    discover_items: bool = Field(
        default=True,
        description="Auto-discover clickable items (notes, boards, etc.) in SPAs"
    )
    include_patterns: List[str] = Field(
        default_factory=list,
        description="URL patterns to include (regex)"
    )
    exclude_patterns: List[str] = Field(
        default_factory=lambda: [
            r".*\.(jpg|jpeg|png|gif|svg|ico|css|js|woff|woff2|ttf|eot)$",
            r".*#.*",
            r".*/api/.*",
            r".*logout.*",
        ],
        description="URL patterns to exclude (regex)"
    )
    same_domain_only: bool = Field(
        default=True,
        description="Only crawl same domain"
    )
    respect_robots_txt: bool = Field(
        default=False,
        description="Respect robots.txt"
    )
    delay_between_requests: float = Field(
        default=0.5,
        description="Delay between page loads (seconds)"
    )
    auth_config: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Authentication configuration"
    )
    test_categories: List[TestCategory] = Field(
        default=[TestCategory.ALL],
        description="Test categories to run on each page"
    )
    capture_screenshots: bool = Field(
        default=True,
        description="Capture screenshot of each page"
    )
    browser_config: BrowserConfig = Field(
        default_factory=BrowserConfig,
        description="Browser configuration"
    )
    output_directory: str = Field(
        default="./freya_crawl_output",
        description="Output directory for crawl results"
    )
