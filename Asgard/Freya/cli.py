"""
Freya CLI

Command-line interface for visual and UI testing.

Usage:
    python -m Freya --help
    python -m Freya accessibility audit <url>
    python -m Freya accessibility contrast <url>
    python -m Freya visual capture <url>
    python -m Freya visual compare <baseline> <current>
    python -m Freya responsive breakpoints <url>
    python -m Freya performance audit <url>
    python -m Freya performance load-time <url>
    python -m Freya seo audit <url>
    python -m Freya seo meta <url>
    python -m Freya security headers <url>
    python -m Freya console errors <url>
    python -m Freya links validate <url>
    python -m Freya images audit <url>
    python -m Freya images alt-text <url>
    python -m Freya images performance <url>
    python -m Freya test <url>
    python -m Freya baseline update <url>
"""

import argparse
import asyncio
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import List

from Asgard.Freya.Accessibility.models.accessibility_models import (
    AccessibilityConfig,
    WCAGLevel,
    ViolationSeverity,
)
from Asgard.Freya.Accessibility.services.wcag_validator import WCAGValidator
from Asgard.Freya.Accessibility.services.color_contrast import ColorContrastChecker
from Asgard.Freya.Accessibility.services.keyboard_nav import KeyboardNavigationTester
from Asgard.Freya.Accessibility.services.screen_reader import ScreenReaderValidator
from Asgard.Freya.Accessibility.services.aria_validator import ARIAValidator

from Asgard.Freya.Visual.services import (
    ScreenshotCapture,
    VisualRegressionTester,
    LayoutValidator,
    StyleValidator,
)

from Asgard.Freya.Responsive.services import (
    BreakpointTester,
    TouchTargetValidator,
    ViewportTester,
    MobileCompatibilityTester,
)

from Asgard.Freya.Integration.models.integration_models import (
    TestCategory,
    TestSeverity,
    UnifiedTestConfig,
    ReportFormat,
    CrawlConfig,
    BrowserConfig,
)
from Asgard.Freya.Integration.services import (
    UnifiedTester,
    HTMLReporter,
    BaselineManager,
)
from Asgard.Freya.Integration.services.site_crawler import SiteCrawler

from Asgard.Freya.Performance.services.page_load_analyzer import PageLoadAnalyzer
from Asgard.Freya.Performance.services.resource_timing_analyzer import ResourceTimingAnalyzer
from Asgard.Freya.Performance.models.performance_models import PerformanceConfig

from Asgard.Freya.SEO.services.meta_tag_analyzer import MetaTagAnalyzer
from Asgard.Freya.SEO.services.structured_data_validator import StructuredDataValidator
from Asgard.Freya.SEO.services.robots_analyzer import RobotsAnalyzer
from Asgard.Freya.SEO.models.seo_models import SEOConfig

from Asgard.Freya.Security.services.security_header_scanner import SecurityHeaderScanner
from Asgard.Freya.Security.services.csp_analyzer import CSPAnalyzer
from Asgard.Freya.Security.models.security_header_models import SecurityConfig

from Asgard.Freya.Console.services.console_capture import ConsoleCapture
from Asgard.Freya.Console.models.console_models import ConsoleConfig

from Asgard.Freya.Links.services.link_validator import LinkValidator
from Asgard.Freya.Links.models.link_models import LinkConfig

from Asgard.Freya.Images.services.image_optimization_scanner import ImageOptimizationScanner
from Asgard.Freya.Images.models.image_models import ImageConfig


SEVERITY_MARKERS = {
    ViolationSeverity.CRITICAL.value: "[CRITICAL]",
    ViolationSeverity.SERIOUS.value: "[SERIOUS]",
    ViolationSeverity.MODERATE.value: "[MODERATE]",
    ViolationSeverity.MINOR.value: "[MINOR]",
    ViolationSeverity.INFO.value: "[INFO]",
}


def add_performance_flags(parser: argparse.ArgumentParser) -> None:
    """Add performance-related flags to a parser (parallel, incremental, baseline)."""
    parser.add_argument(
        "--parallel",
        "-P",
        action="store_true",
        help="Enable parallel processing for faster analysis",
    )
    parser.add_argument(
        "--workers",
        "-W",
        type=int,
        default=None,
        help="Number of worker processes (default: CPU count - 1)",
    )
    parser.add_argument(
        "--incremental",
        "-I",
        action="store_true",
        help="Enable incremental scanning (skip unchanged pages/resources)",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable caching even if incremental mode is enabled",
    )
    parser.add_argument(
        "--baseline",
        "-B",
        type=str,
        default=None,
        help="Path to baseline file for filtering known issues",
    )


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        prog="freya",
        description="Freya - Visual and UI Testing",
        epilog="Named after the Norse goddess of beauty and love.",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output",
    )

    parser.add_argument(
        "--version",
        action="version",
        version="Freya 2.0.0",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    _add_accessibility_parser(subparsers)
    _add_visual_parser(subparsers)
    _add_responsive_parser(subparsers)
    _add_performance_parser(subparsers)
    _add_seo_parser(subparsers)
    _add_security_parser(subparsers)
    _add_console_parser(subparsers)
    _add_links_parser(subparsers)
    _add_images_parser(subparsers)
    _add_test_parser(subparsers)
    _add_crawl_parser(subparsers)
    _add_baseline_parser(subparsers)
    _add_config_parser(subparsers)

    return parser


def _add_accessibility_parser(subparsers) -> None:
    """Add accessibility command group."""
    accessibility_parser = subparsers.add_parser(
        "accessibility",
        help="Accessibility testing commands"
    )
    accessibility_subparsers = accessibility_parser.add_subparsers(
        dest="accessibility_command",
        help="Accessibility commands"
    )

    audit_parser = accessibility_subparsers.add_parser(
        "audit",
        help="Run full accessibility audit"
    )
    _add_accessibility_common_args(audit_parser)

    contrast_parser = accessibility_subparsers.add_parser(
        "contrast",
        help="Check color contrast"
    )
    _add_accessibility_common_args(contrast_parser)

    keyboard_parser = accessibility_subparsers.add_parser(
        "keyboard",
        help="Test keyboard navigation"
    )
    _add_accessibility_common_args(keyboard_parser)

    aria_parser = accessibility_subparsers.add_parser(
        "aria",
        help="Validate ARIA implementation"
    )
    _add_accessibility_common_args(aria_parser)

    screen_reader_parser = accessibility_subparsers.add_parser(
        "screen-reader",
        help="Test screen reader compatibility"
    )
    _add_accessibility_common_args(screen_reader_parser)


def _add_accessibility_common_args(parser: argparse.ArgumentParser) -> None:
    """Add common accessibility arguments."""
    parser.add_argument(
        "url",
        type=str,
        help="URL to test",
    )
    parser.add_argument(
        "--level",
        "-l",
        choices=["A", "AA", "AAA"],
        default="AA",
        help="WCAG conformance level (default: AA)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json", "markdown", "html"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        help="Output file path",
    )
    parser.add_argument(
        "--severity",
        "-s",
        choices=["critical", "serious", "moderate", "minor", "info"],
        default="minor",
        help="Minimum severity to report (default: minor)",
    )


def _add_visual_parser(subparsers) -> None:
    """Add visual command group."""
    visual_parser = subparsers.add_parser(
        "visual",
        help="Visual testing commands"
    )
    visual_subparsers = visual_parser.add_subparsers(
        dest="visual_command",
        help="Visual commands"
    )

    capture_parser = visual_subparsers.add_parser(
        "capture",
        help="Capture screenshot"
    )
    capture_parser.add_argument("url", type=str, help="URL to capture")
    capture_parser.add_argument(
        "--output", "-o", type=str, help="Output file path"
    )
    capture_parser.add_argument(
        "--full-page", action="store_true", help="Capture full page"
    )
    capture_parser.add_argument(
        "--device", "-d", type=str, help="Device to emulate"
    )
    capture_parser.add_argument(
        "--width", "-w", type=int, default=1920, help="Viewport width"
    )
    capture_parser.add_argument(
        "--height", "-H", type=int, default=1080, help="Viewport height"
    )

    compare_parser = visual_subparsers.add_parser(
        "compare",
        help="Compare two images"
    )
    compare_parser.add_argument("baseline", type=str, help="Baseline image path")
    compare_parser.add_argument("current", type=str, help="Current image path")
    compare_parser.add_argument(
        "--threshold", "-t", type=float, default=0.95,
        help="Similarity threshold (default: 0.95)"
    )
    compare_parser.add_argument(
        "--format", "-f", choices=["text", "json"], default="text",
        help="Output format"
    )

    layout_parser = visual_subparsers.add_parser(
        "layout",
        help="Validate layout"
    )
    layout_parser.add_argument("url", type=str, help="URL to test")
    layout_parser.add_argument(
        "--format", "-f", choices=["text", "json"], default="text"
    )
    layout_parser.add_argument(
        "--output", "-o", type=str, help="Output file path"
    )

    style_parser = visual_subparsers.add_parser(
        "style",
        help="Check style consistency"
    )
    style_parser.add_argument("url", type=str, help="URL to test")
    style_parser.add_argument(
        "--theme", type=str, help="Theme file to validate against"
    )
    style_parser.add_argument(
        "--format", "-f", choices=["text", "json"], default="text"
    )
    style_parser.add_argument(
        "--output", "-o", type=str, help="Output file path"
    )


def _add_responsive_parser(subparsers) -> None:
    """Add responsive command group."""
    responsive_parser = subparsers.add_parser(
        "responsive",
        help="Responsive testing commands"
    )
    responsive_subparsers = responsive_parser.add_subparsers(
        dest="responsive_command",
        help="Responsive commands"
    )

    breakpoints_parser = responsive_subparsers.add_parser(
        "breakpoints",
        help="Test breakpoints"
    )
    breakpoints_parser.add_argument("url", type=str, help="URL to test")
    breakpoints_parser.add_argument(
        "--format", "-f", choices=["text", "json"], default="text"
    )
    breakpoints_parser.add_argument(
        "--screenshots", action="store_true", help="Capture screenshots"
    )
    breakpoints_parser.add_argument(
        "--output", "-o", type=str, help="Output file path"
    )

    touch_parser = responsive_subparsers.add_parser(
        "touch",
        help="Validate touch targets"
    )
    touch_parser.add_argument("url", type=str, help="URL to test")
    touch_parser.add_argument(
        "--min-size", type=int, default=44,
        help="Minimum touch target size in pixels (default: 44)"
    )
    touch_parser.add_argument(
        "--format", "-f", choices=["text", "json"], default="text"
    )
    touch_parser.add_argument(
        "--output", "-o", type=str, help="Output file path"
    )

    viewport_parser = responsive_subparsers.add_parser(
        "viewport",
        help="Test viewport behavior"
    )
    viewport_parser.add_argument("url", type=str, help="URL to test")
    viewport_parser.add_argument(
        "--format", "-f", choices=["text", "json"], default="text"
    )
    viewport_parser.add_argument(
        "--output", "-o", type=str, help="Output file path"
    )

    mobile_parser = responsive_subparsers.add_parser(
        "mobile",
        help="Test mobile compatibility"
    )
    mobile_parser.add_argument("url", type=str, help="URL to test")
    mobile_parser.add_argument(
        "--devices", "-d", type=str, nargs="+",
        help="Devices to test (e.g., iphone-14 pixel-7)"
    )
    mobile_parser.add_argument(
        "--format", "-f", choices=["text", "json"], default="text"
    )
    mobile_parser.add_argument(
        "--output", "-o", type=str, help="Output file path"
    )


def _add_performance_parser(subparsers) -> None:
    """Add performance command group."""
    performance_parser = subparsers.add_parser(
        "performance",
        help="Performance testing commands"
    )
    performance_subparsers = performance_parser.add_subparsers(
        dest="performance_command",
        help="Performance commands"
    )

    audit_parser = performance_subparsers.add_parser(
        "audit",
        help="Run full performance audit"
    )
    audit_parser.add_argument("url", type=str, help="URL to test")
    audit_parser.add_argument(
        "--format", "-f", choices=["text", "json", "github"], default="text"
    )
    audit_parser.add_argument(
        "--output", "-o", type=str, help="Output file path"
    )

    loadtime_parser = performance_subparsers.add_parser(
        "load-time",
        help="Measure page load timing"
    )
    loadtime_parser.add_argument("url", type=str, help="URL to test")
    loadtime_parser.add_argument(
        "--format", "-f", choices=["text", "json"], default="text"
    )
    loadtime_parser.add_argument(
        "--output", "-o", type=str, help="Output file path"
    )

    resources_parser = performance_subparsers.add_parser(
        "resources",
        help="Analyze resource loading"
    )
    resources_parser.add_argument("url", type=str, help="URL to test")
    resources_parser.add_argument(
        "--format", "-f", choices=["text", "json"], default="text"
    )
    resources_parser.add_argument(
        "--output", "-o", type=str, help="Output file path"
    )


def _add_seo_parser(subparsers) -> None:
    """Add SEO command group."""
    seo_parser = subparsers.add_parser(
        "seo",
        help="SEO analysis commands"
    )
    seo_subparsers = seo_parser.add_subparsers(
        dest="seo_command",
        help="SEO commands"
    )

    audit_parser = seo_subparsers.add_parser(
        "audit",
        help="Run full SEO audit"
    )
    audit_parser.add_argument("url", type=str, help="URL to test")
    audit_parser.add_argument(
        "--format", "-f", choices=["text", "json", "github"], default="text"
    )
    audit_parser.add_argument(
        "--output", "-o", type=str, help="Output file path"
    )

    meta_parser = seo_subparsers.add_parser(
        "meta",
        help="Analyze meta tags"
    )
    meta_parser.add_argument("url", type=str, help="URL to test")
    meta_parser.add_argument(
        "--format", "-f", choices=["text", "json"], default="text"
    )
    meta_parser.add_argument(
        "--output", "-o", type=str, help="Output file path"
    )

    structured_parser = seo_subparsers.add_parser(
        "structured-data",
        help="Validate structured data"
    )
    structured_parser.add_argument("url", type=str, help="URL to test")
    structured_parser.add_argument(
        "--format", "-f", choices=["text", "json"], default="text"
    )
    structured_parser.add_argument(
        "--output", "-o", type=str, help="Output file path"
    )

    robots_parser = seo_subparsers.add_parser(
        "robots",
        help="Analyze robots.txt and sitemap"
    )
    robots_parser.add_argument("url", type=str, help="Site URL")
    robots_parser.add_argument(
        "--format", "-f", choices=["text", "json"], default="text"
    )
    robots_parser.add_argument(
        "--output", "-o", type=str, help="Output file path"
    )


def _add_security_parser(subparsers) -> None:
    """Add security command group."""
    security_parser = subparsers.add_parser(
        "security",
        help="Security header analysis commands"
    )
    security_subparsers = security_parser.add_subparsers(
        dest="security_command",
        help="Security commands"
    )

    headers_parser = security_subparsers.add_parser(
        "headers",
        help="Analyze security headers"
    )
    headers_parser.add_argument("url", type=str, help="URL to test")
    headers_parser.add_argument(
        "--format", "-f", choices=["text", "json", "github"], default="text"
    )
    headers_parser.add_argument(
        "--output", "-o", type=str, help="Output file path"
    )

    csp_parser = security_subparsers.add_parser(
        "csp",
        help="Deep CSP analysis"
    )
    csp_parser.add_argument("url", type=str, help="URL to test")
    csp_parser.add_argument(
        "--format", "-f", choices=["text", "json"], default="text"
    )
    csp_parser.add_argument(
        "--output", "-o", type=str, help="Output file path"
    )


def _add_console_parser(subparsers) -> None:
    """Add console command group."""
    console_parser = subparsers.add_parser(
        "console",
        help="JavaScript console capture commands"
    )
    console_subparsers = console_parser.add_subparsers(
        dest="console_command",
        help="Console commands"
    )

    errors_parser = console_subparsers.add_parser(
        "errors",
        help="Capture JavaScript errors"
    )
    errors_parser.add_argument("url", type=str, help="URL to test")
    errors_parser.add_argument(
        "--format", "-f", choices=["text", "json", "github"], default="text"
    )
    errors_parser.add_argument(
        "--output", "-o", type=str, help="Output file path"
    )
    errors_parser.add_argument(
        "--wait", "-w", type=int, default=3000,
        help="Wait time in ms for messages (default: 3000)"
    )
    errors_parser.add_argument(
        "--include-warnings", action="store_true",
        help="Also capture warnings"
    )


def _add_links_parser(subparsers) -> None:
    """Add links command group."""
    links_parser = subparsers.add_parser(
        "links",
        help="Link validation commands"
    )
    links_subparsers = links_parser.add_subparsers(
        dest="links_command",
        help="Links commands"
    )

    validate_parser = links_subparsers.add_parser(
        "validate",
        help="Validate links on a page"
    )
    validate_parser.add_argument("url", type=str, help="URL to test")
    validate_parser.add_argument(
        "--format", "-f", choices=["text", "json", "github"], default="text"
    )
    validate_parser.add_argument(
        "--output", "-o", type=str, help="Output file path"
    )
    validate_parser.add_argument(
        "--external", "-e", action="store_true",
        help="Also check external links"
    )
    validate_parser.add_argument(
        "--max-links", "-m", type=int, default=500,
        help="Maximum links to check (default: 500)"
    )
    validate_parser.add_argument(
        "--timeout", "-t", type=int, default=10000,
        help="Timeout per link in ms (default: 10000)"
    )
    add_performance_flags(validate_parser)


def _add_images_parser(subparsers) -> None:
    """Add images command group."""
    images_parser = subparsers.add_parser(
        "images",
        help="Image optimization scanning commands"
    )
    images_subparsers = images_parser.add_subparsers(
        dest="images_command",
        help="Images commands"
    )

    # Audit subcommand - full image audit
    audit_parser = images_subparsers.add_parser(
        "audit",
        help="Run full image optimization audit"
    )
    audit_parser.add_argument("url", type=str, help="URL to scan")
    audit_parser.add_argument(
        "--format", "-f", choices=["text", "json", "github"], default="text",
        help="Output format (default: text)"
    )
    audit_parser.add_argument(
        "--output", "-o", type=str, help="Output file path"
    )
    audit_parser.add_argument(
        "--include-all", action="store_true",
        help="Include all images in report, not just those with issues"
    )
    add_performance_flags(audit_parser)

    # Alt-text subcommand - check alt text only
    alt_text_parser = images_subparsers.add_parser(
        "alt-text",
        help="Check image alt text only"
    )
    alt_text_parser.add_argument("url", type=str, help="URL to scan")
    alt_text_parser.add_argument(
        "--format", "-f", choices=["text", "json", "github"], default="text",
        help="Output format (default: text)"
    )
    alt_text_parser.add_argument(
        "--output", "-o", type=str, help="Output file path"
    )

    # Performance subcommand - check performance issues only
    performance_parser = images_subparsers.add_parser(
        "performance",
        help="Check image performance issues only"
    )
    performance_parser.add_argument("url", type=str, help="URL to scan")
    performance_parser.add_argument(
        "--format", "-f", choices=["text", "json", "github"], default="text",
        help="Output format (default: text)"
    )
    performance_parser.add_argument(
        "--output", "-o", type=str, help="Output file path"
    )
    performance_parser.add_argument(
        "--oversized-threshold", type=float, default=1.5,
        help="Ratio threshold for oversized detection (default: 1.5)"
    )


def _add_test_parser(subparsers) -> None:
    """Add unified test command."""
    test_parser = subparsers.add_parser(
        "test",
        help="Run all tests (accessibility, visual, responsive)"
    )
    test_parser.add_argument("url", type=str, help="URL to test")
    test_parser.add_argument(
        "--level", "-l", choices=["A", "AA", "AAA"], default="AA",
        help="WCAG conformance level"
    )
    test_parser.add_argument(
        "--format", "-f", choices=["text", "json", "html", "junit"],
        default="text", help="Output format"
    )
    test_parser.add_argument(
        "--output", "-o", type=str, help="Output file path"
    )
    test_parser.add_argument(
        "--severity", "-s",
        choices=["critical", "serious", "moderate", "minor"],
        default="minor", help="Minimum severity to report"
    )
    test_parser.add_argument(
        "--skip-accessibility", action="store_true",
        help="Skip accessibility tests"
    )
    test_parser.add_argument(
        "--skip-visual", action="store_true",
        help="Skip visual tests"
    )
    test_parser.add_argument(
        "--skip-responsive", action="store_true",
        help="Skip responsive tests"
    )
    add_performance_flags(test_parser)


def _add_crawl_parser(subparsers) -> None:
    """Add site crawl command."""
    crawl_parser = subparsers.add_parser(
        "crawl",
        help="Crawl and test entire site"
    )
    crawl_parser.add_argument("url", type=str, help="Starting URL to crawl")
    crawl_parser.add_argument(
        "--depth", "-d", type=int, default=3,
        help="Maximum crawl depth (default: 3)"
    )
    crawl_parser.add_argument(
        "--max-pages", "-m", type=int, default=100,
        help="Maximum pages to crawl (default: 100)"
    )
    crawl_parser.add_argument(
        "--output", "-o", type=str, default="./freya_crawl_output",
        help="Output directory for reports"
    )
    crawl_parser.add_argument(
        "--delay", type=float, default=0.5,
        help="Delay between requests in seconds (default: 0.5)"
    )
    crawl_parser.add_argument(
        "--no-screenshots", action="store_true",
        help="Skip capturing screenshots"
    )
    crawl_parser.add_argument(
        "--include", type=str, action="append", default=[],
        help="URL patterns to include (regex, can be repeated)"
    )
    crawl_parser.add_argument(
        "--exclude", type=str, action="append", default=[],
        help="URL patterns to exclude (regex, can be repeated)"
    )
    crawl_parser.add_argument(
        "--login-url", type=str,
        help="URL of login page for authentication"
    )
    crawl_parser.add_argument(
        "--username", type=str,
        help="Username for authentication"
    )
    crawl_parser.add_argument(
        "--password", type=str,
        help="Password for authentication"
    )
    crawl_parser.add_argument(
        "--username-selector", type=str, default='input[name="username"]',
        help="CSS selector for username field"
    )
    crawl_parser.add_argument(
        "--password-selector", type=str, default='input[name="password"]',
        help="CSS selector for password field"
    )
    crawl_parser.add_argument(
        "--submit-selector", type=str, default='button[type="submit"]',
        help="CSS selector for submit button"
    )
    crawl_parser.add_argument(
        "--headless", action="store_true", default=True,
        help="Run browser in headless mode (default: true)"
    )
    crawl_parser.add_argument(
        "--no-headless", action="store_true",
        help="Show browser window during crawl"
    )
    crawl_parser.add_argument(
        "--routes", type=str, action="append", default=[],
        help="Additional routes to test (for SPAs), e.g., --routes /notes --routes /calendar"
    )
    crawl_parser.add_argument(
        "--discover-items", action="store_true", default=True,
        help="Auto-discover clickable items like notes, boards, etc. (default: true)"
    )
    crawl_parser.add_argument(
        "--no-discover-items", action="store_true",
        help="Disable auto-discovery of clickable items"
    )
    add_performance_flags(crawl_parser)


def _add_baseline_parser(subparsers) -> None:
    """Add baseline management commands."""
    baseline_parser = subparsers.add_parser(
        "baseline",
        help="Baseline management commands"
    )
    baseline_subparsers = baseline_parser.add_subparsers(
        dest="baseline_command",
        help="Baseline commands"
    )

    update_parser = baseline_subparsers.add_parser(
        "update",
        help="Create or update a baseline"
    )
    update_parser.add_argument("url", type=str, help="URL to capture")
    update_parser.add_argument("--name", "-n", type=str, required=True, help="Baseline name")
    update_parser.add_argument("--device", "-d", type=str, help="Device to emulate")
    update_parser.add_argument("--width", "-w", type=int, default=1920, help="Viewport width")
    update_parser.add_argument("--height", "-H", type=int, default=1080, help="Viewport height")

    compare_parser = baseline_subparsers.add_parser(
        "compare",
        help="Compare current page to baseline"
    )
    compare_parser.add_argument("url", type=str, help="URL to compare")
    compare_parser.add_argument("--name", "-n", type=str, required=True, help="Baseline name")
    compare_parser.add_argument("--device", "-d", type=str, help="Device to emulate")
    compare_parser.add_argument("--threshold", "-t", type=float, default=0.1, help="Difference threshold")

    list_parser = baseline_subparsers.add_parser(
        "list",
        help="List all baselines"
    )
    list_parser.add_argument("--url", type=str, help="Filter by URL")

    delete_parser = baseline_subparsers.add_parser(
        "delete",
        help="Delete a baseline"
    )
    delete_parser.add_argument("--name", "-n", type=str, required=True, help="Baseline name")
    delete_parser.add_argument("url", type=str, help="URL of baseline")
    delete_parser.add_argument("--device", "-d", type=str, help="Device of baseline")


def _add_config_parser(subparsers) -> None:
    """Add configuration commands."""
    config_parser = subparsers.add_parser(
        "config",
        help="Configuration commands"
    )
    config_subparsers = config_parser.add_subparsers(
        dest="config_command",
        help="Config commands"
    )

    config_subparsers.add_parser("show", help="Show current configuration")
    config_subparsers.add_parser("init", help="Initialize configuration file")


async def run_accessibility_audit(args: argparse.Namespace, verbose: bool = False) -> int:
    """Run accessibility audit."""
    wcag_level = WCAGLevel(args.level)
    config = AccessibilityConfig(
        wcag_level=wcag_level,
        output_format=args.format,
    )

    validator = WCAGValidator(config)

    print(f"\nRunning accessibility audit on: {args.url}")
    print(f"WCAG Level: {wcag_level.value}")
    print("-" * 60)

    result = await validator.validate(args.url)

    if args.format == "json":
        output = result.model_dump_json(indent=2)
    elif args.format == "markdown":
        output = format_accessibility_markdown(result)
    elif args.format == "html":
        output = format_accessibility_html(result)
    else:
        output = format_accessibility_text(result)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Report saved to: {args.output}")
    else:
        print(output)

    return 1 if result.has_violations else 0


async def run_contrast_check(args: argparse.Namespace, verbose: bool = False) -> int:
    """Run color contrast check."""
    wcag_level = WCAGLevel(args.level)
    config = AccessibilityConfig(wcag_level=wcag_level)

    checker = ColorContrastChecker(config)

    print(f"\nChecking color contrast on: {args.url}")
    print(f"WCAG Level: {wcag_level.value}")
    print("-" * 60)

    result = await checker.check(args.url)

    if args.format == "json":
        output = result.model_dump_json(indent=2)
    else:
        output = format_contrast_text(result)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Report saved to: {args.output}")
    else:
        print(output)

    return 1 if result.has_violations else 0


async def run_keyboard_test(args: argparse.Namespace, verbose: bool = False) -> int:
    """Run keyboard navigation test."""
    config = AccessibilityConfig(wcag_level=WCAGLevel(args.level))

    tester = KeyboardNavigationTester(config)

    print(f"\nTesting keyboard navigation on: {args.url}")
    print("-" * 60)

    result = await tester.test(args.url)

    if args.format == "json":
        output = result.model_dump_json(indent=2)
    else:
        output = format_keyboard_text(result)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Report saved to: {args.output}")
    else:
        print(output)

    return 1 if result.has_issues else 0


async def run_aria_validation(args: argparse.Namespace, verbose: bool = False) -> int:
    """Run ARIA validation."""
    config = AccessibilityConfig(wcag_level=WCAGLevel(args.level))

    validator = ARIAValidator(config)

    print(f"\nValidating ARIA implementation on: {args.url}")
    print("-" * 60)

    result = await validator.validate(args.url)

    if args.format == "json":
        output = result.model_dump_json(indent=2)
    else:
        output = format_aria_text(result)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Report saved to: {args.output}")
    else:
        print(output)

    return 1 if result.has_violations else 0


async def run_screen_reader_test(args: argparse.Namespace, verbose: bool = False) -> int:
    """Run screen reader compatibility test."""
    config = AccessibilityConfig(wcag_level=WCAGLevel(args.level))

    validator = ScreenReaderValidator(config)

    print(f"\nTesting screen reader compatibility on: {args.url}")
    print("-" * 60)

    result = await validator.validate(args.url)

    if args.format == "json":
        output = result.model_dump_json(indent=2)
    else:
        output = format_screen_reader_text(result)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Report saved to: {args.output}")
    else:
        print(output)

    return 1 if result.has_issues else 0


async def run_visual_capture(args: argparse.Namespace, verbose: bool = False) -> int:
    """Run screenshot capture."""
    output_dir = str(Path(args.output).parent) if args.output else "./screenshots"
    capture = ScreenshotCapture(output_directory=output_dir)

    print(f"\nCapturing screenshot: {args.url}")
    print("-" * 60)

    if args.device:
        results = await capture.capture_with_devices(
            args.url,
            devices=[args.device]
        )
        result = results[0] if results else None
        if result is None:
            print(f"Error: Device '{args.device}' not found")
            return 1
    else:
        if getattr(args, "full_page", False):
            result = await capture.capture_full_page(args.url)
        else:
            result = await capture.capture_viewport(args.url)

    if args.output:
        shutil.move(result.file_path, args.output)
        print(f"Screenshot saved to: {args.output}")
    else:
        print(f"Screenshot saved to: {result.file_path}")

    return 0


async def run_visual_compare(args: argparse.Namespace, verbose: bool = False) -> int:
    """Run visual comparison."""
    threshold = 1.0 - args.threshold
    tester = VisualRegressionTester(threshold=threshold)

    print(f"\nComparing images:")
    print(f"  Baseline: {args.baseline}")
    print(f"  Current:  {args.current}")
    print("-" * 60)

    result = tester.compare(args.baseline, args.current)

    if args.format == "json":
        print(result.model_dump_json(indent=2))
    else:
        print(f"\nMatch: {'Yes' if not result.has_difference else 'No'}")
        print(f"Difference: {result.difference_percentage:.2f}%")
        if result.diff_image_path:
            print(f"Diff image: {result.diff_image_path}")

    return 1 if result.has_difference else 0


async def run_layout_validation(args: argparse.Namespace, verbose: bool = False) -> int:
    """Run layout validation."""
    validator = LayoutValidator()

    print(f"\nValidating layout: {args.url}")
    print("-" * 60)

    result = await validator.validate(args.url)

    if args.format == "json":
        output = result.model_dump_json(indent=2)
    else:
        output = format_layout_text(result)

    if hasattr(args, "output") and args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Report saved to: {args.output}")
    else:
        print(output)

    return 1 if result.issues else 0


async def run_style_validation(args: argparse.Namespace, verbose: bool = False) -> int:
    """Run style validation."""
    theme_file = getattr(args, "theme", None)
    validator = StyleValidator(theme_file=theme_file)

    print(f"\nValidating styles: {args.url}")
    print("-" * 60)

    result = await validator.validate(args.url)

    if args.format == "json":
        output = result.model_dump_json(indent=2)
    else:
        output = format_style_text(result)

    if hasattr(args, "output") and args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Report saved to: {args.output}")
    else:
        print(output)

    return 1 if result.issues else 0


async def run_breakpoint_test(args: argparse.Namespace, verbose: bool = False) -> int:
    """Run breakpoint testing."""
    tester = BreakpointTester()

    print(f"\nTesting breakpoints: {args.url}")
    print("-" * 60)

    result = await tester.test(
        args.url,
        capture_screenshots=getattr(args, "screenshots", False)
    )

    if args.format == "json":
        output = result.model_dump_json(indent=2)
    else:
        output = format_breakpoint_text(result)

    if hasattr(args, "output") and args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Report saved to: {args.output}")
    else:
        print(output)

    return 1 if result.total_issues > 0 else 0


async def run_touch_validation(args: argparse.Namespace, verbose: bool = False) -> int:
    """Run touch target validation."""
    min_size = getattr(args, "min_size", 44)
    validator = TouchTargetValidator(min_touch_size=min_size)

    print(f"\nValidating touch targets: {args.url}")
    print("-" * 60)

    result = await validator.validate(args.url)

    if args.format == "json":
        output = result.model_dump_json(indent=2)
    else:
        output = format_touch_text(result)

    if hasattr(args, "output") and args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Report saved to: {args.output}")
    else:
        print(output)

    return 1 if result.issues else 0


async def run_viewport_test(args: argparse.Namespace, verbose: bool = False) -> int:
    """Run viewport testing."""
    tester = ViewportTester()

    print(f"\nTesting viewport: {args.url}")
    print("-" * 60)

    result = await tester.test(args.url)

    if args.format == "json":
        output = result.model_dump_json(indent=2)
    else:
        output = format_viewport_text(result)

    if hasattr(args, "output") and args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Report saved to: {args.output}")
    else:
        print(output)

    return 1 if result.issues else 0


async def run_mobile_test(args: argparse.Namespace, verbose: bool = False) -> int:
    """Run mobile compatibility test."""
    tester = MobileCompatibilityTester()

    devices = getattr(args, "devices", None)

    print(f"\nTesting mobile compatibility: {args.url}")
    print("-" * 60)

    result = await tester.test(args.url, devices=devices)

    if args.format == "json":
        output = result.model_dump_json(indent=2)
    else:
        output = format_mobile_text(result)

    if hasattr(args, "output") and args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Report saved to: {args.output}")
    else:
        print(output)

    return 1 if result.issues else 0


async def run_performance_audit(args: argparse.Namespace, verbose: bool = False) -> int:
    """Run performance audit."""
    analyzer = PageLoadAnalyzer()

    print(f"\nRunning performance audit on: {args.url}")
    print("-" * 60)

    result = await analyzer.get_performance_report(args.url)

    if args.format == "json":
        output = result.model_dump_json(indent=2)
    else:
        output = format_performance_text(result)

    if hasattr(args, "output") and args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Report saved to: {args.output}")
    else:
        print(output)

    return 1 if result.has_issues else 0


async def run_performance_load_time(args: argparse.Namespace, verbose: bool = False) -> int:
    """Run page load time analysis."""
    analyzer = PageLoadAnalyzer()

    print(f"\nMeasuring page load time: {args.url}")
    print("-" * 60)

    result = await analyzer.analyze(args.url)

    if args.format == "json":
        output = result.model_dump_json(indent=2)
    else:
        output = format_load_time_text(result)

    if hasattr(args, "output") and args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Report saved to: {args.output}")
    else:
        print(output)

    return 0


async def run_performance_resources(args: argparse.Namespace, verbose: bool = False) -> int:
    """Run resource timing analysis."""
    analyzer = ResourceTimingAnalyzer()

    print(f"\nAnalyzing resources: {args.url}")
    print("-" * 60)

    result = await analyzer.analyze(args.url)

    if args.format == "json":
        output = result.model_dump_json(indent=2)
    else:
        output = format_resources_text(result)

    if hasattr(args, "output") and args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Report saved to: {args.output}")
    else:
        print(output)

    return 1 if len(result.large_resources) > 0 or len(result.slow_resources) > 0 else 0


async def run_seo_audit(args: argparse.Namespace, verbose: bool = False) -> int:
    """Run SEO audit."""
    meta_analyzer = MetaTagAnalyzer()

    print(f"\nRunning SEO audit on: {args.url}")
    print("-" * 60)

    meta_result = await meta_analyzer.analyze(args.url)

    if args.format == "json":
        output = meta_result.model_dump_json(indent=2)
    else:
        output = format_seo_text(meta_result)

    if hasattr(args, "output") and args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Report saved to: {args.output}")
    else:
        print(output)

    return 1 if meta_result.has_issues else 0


async def run_seo_meta(args: argparse.Namespace, verbose: bool = False) -> int:
    """Run meta tag analysis."""
    analyzer = MetaTagAnalyzer()

    print(f"\nAnalyzing meta tags: {args.url}")
    print("-" * 60)

    result = await analyzer.analyze(args.url)

    if args.format == "json":
        output = result.model_dump_json(indent=2)
    else:
        output = format_meta_text(result)

    if hasattr(args, "output") and args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Report saved to: {args.output}")
    else:
        print(output)

    return 1 if result.has_issues else 0


async def run_seo_structured_data(args: argparse.Namespace, verbose: bool = False) -> int:
    """Run structured data validation."""
    validator = StructuredDataValidator()

    print(f"\nValidating structured data: {args.url}")
    print("-" * 60)

    result = await validator.validate(args.url)

    if args.format == "json":
        output = result.model_dump_json(indent=2)
    else:
        output = format_structured_data_text(result)

    if hasattr(args, "output") and args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Report saved to: {args.output}")
    else:
        print(output)

    return 1 if result.has_errors else 0


async def run_seo_robots(args: argparse.Namespace, verbose: bool = False) -> int:
    """Run robots.txt analysis."""
    analyzer = RobotsAnalyzer()

    print(f"\nAnalyzing robots.txt: {args.url}")
    print("-" * 60)

    robots_result = await analyzer.analyze_robots(args.url)
    sitemap_result = await analyzer.analyze_sitemap(args.url)

    if args.format == "json":
        output = json.dumps({
            "robots": robots_result.model_dump(),
            "sitemap": sitemap_result.model_dump(),
        }, indent=2, default=str)
    else:
        output = format_robots_text(robots_result, sitemap_result)

    if hasattr(args, "output") and args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Report saved to: {args.output}")
    else:
        print(output)

    await analyzer.close()

    return 1 if robots_result.has_issues or sitemap_result.has_issues else 0


async def run_security_headers(args: argparse.Namespace, verbose: bool = False) -> int:
    """Run security headers analysis."""
    scanner = SecurityHeaderScanner()

    print(f"\nScanning security headers: {args.url}")
    print("-" * 60)

    result = await scanner.scan(args.url)

    if args.format == "json":
        output = result.model_dump_json(indent=2)
    else:
        output = format_security_text(result)

    if hasattr(args, "output") and args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Report saved to: {args.output}")
    else:
        print(output)

    await scanner.close()

    return 1 if result.has_issues else 0


async def run_security_csp(args: argparse.Namespace, verbose: bool = False) -> int:
    """Run CSP analysis."""
    scanner = SecurityHeaderScanner()

    print(f"\nAnalyzing CSP: {args.url}")
    print("-" * 60)

    result = await scanner.scan(args.url)

    if result.csp_report:
        if args.format == "json":
            output = result.csp_report.model_dump_json(indent=2)
        else:
            output = format_csp_text(result.csp_report)
    else:
        output = "No Content-Security-Policy header found."

    if hasattr(args, "output") and args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Report saved to: {args.output}")
    else:
        print(output)

    await scanner.close()

    return 1 if result.csp_report and result.csp_report.has_issues else 0


async def run_console_errors(args: argparse.Namespace, verbose: bool = False) -> int:
    """Capture console errors."""
    config = ConsoleConfig(
        capture_warnings=getattr(args, "include_warnings", False),
        wait_time_ms=args.wait,
    )
    capture = ConsoleCapture(config)

    print(f"\nCapturing console errors: {args.url}")
    print("-" * 60)

    result = await capture.capture(args.url)

    if args.format == "json":
        output = result.model_dump_json(indent=2)
    else:
        output = format_console_text(result)

    if hasattr(args, "output") and args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Report saved to: {args.output}")
    else:
        print(output)

    return 1 if result.has_errors else 0


async def run_links_validate(args: argparse.Namespace, verbose: bool = False) -> int:
    """Validate links on a page."""
    config = LinkConfig(
        check_external=getattr(args, "external", True),
        max_links=args.max_links,
        timeout_ms=args.timeout,
    )
    validator = LinkValidator(config)

    print(f"\nValidating links: {args.url}")
    print("-" * 60)

    result = await validator.validate(args.url)

    if args.format == "json":
        output = result.model_dump_json(indent=2)
    else:
        output = format_links_text(result)

    if hasattr(args, "output") and args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Report saved to: {args.output}")
    else:
        print(output)

    await validator.close()

    return 1 if result.has_broken_links else 0


async def run_images_audit(args: argparse.Namespace, verbose: bool = False) -> int:
    """Run full image optimization audit."""
    config = ImageConfig(
        include_all_images=getattr(args, "include_all", False),
    )
    scanner = ImageOptimizationScanner(config)

    print(f"\nScanning images: {args.url}")
    print("-" * 60)

    result = await scanner.scan(args.url)

    if args.format == "json":
        output = result.model_dump_json(indent=2)
    else:
        output = format_images_text(result)

    if hasattr(args, "output") and args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Report saved to: {args.output}")
    else:
        print(output)

    await scanner.close()

    return 1 if result.has_critical_issues else 0


async def run_images_alt_text(args: argparse.Namespace, verbose: bool = False) -> int:
    """Check image alt text only."""
    scanner = ImageOptimizationScanner()

    print(f"\nChecking image alt text: {args.url}")
    print("-" * 60)

    result = await scanner.check_alt_text(args.url)

    if args.format == "json":
        output = result.model_dump_json(indent=2)
    else:
        output = format_images_alt_text(result)

    if hasattr(args, "output") and args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Report saved to: {args.output}")
    else:
        print(output)

    await scanner.close()

    return 1 if result.has_accessibility_issues else 0


async def run_images_performance(args: argparse.Namespace, verbose: bool = False) -> int:
    """Check image performance issues only."""
    config = ImageConfig(
        oversized_threshold=getattr(args, "oversized_threshold", 1.5),
    )
    scanner = ImageOptimizationScanner(config)

    print(f"\nChecking image performance: {args.url}")
    print("-" * 60)

    result = await scanner.check_performance(args.url)

    if args.format == "json":
        output = result.model_dump_json(indent=2)
    else:
        output = format_images_performance_text(result)

    if hasattr(args, "output") and args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Report saved to: {args.output}")
    else:
        print(output)

    await scanner.close()

    return 1 if result.warning_count > 0 else 0


async def run_unified_test(args: argparse.Namespace, verbose: bool = False) -> int:
    """Run unified test."""
    categories = []
    if not args.skip_accessibility:
        categories.append(TestCategory.ACCESSIBILITY)
    if not args.skip_visual:
        categories.append(TestCategory.VISUAL)
    if not args.skip_responsive:
        categories.append(TestCategory.RESPONSIVE)

    if not categories:
        categories = [TestCategory.ALL]

    severity_map = {
        "critical": TestSeverity.CRITICAL,
        "serious": TestSeverity.SERIOUS,
        "moderate": TestSeverity.MODERATE,
        "minor": TestSeverity.MINOR,
    }
    min_severity = severity_map.get(args.severity, TestSeverity.MINOR)

    tester = UnifiedTester()

    print(f"\nRunning unified tests on: {args.url}")
    print("-" * 60)

    result = await tester.test(
        args.url,
        categories=categories,
        min_severity=min_severity
    )

    if args.format == "json":
        output = result.model_dump_json(indent=2)
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(output)
            print(f"Report saved to: {args.output}")
        else:
            print(output)
    elif args.format == "html":
        reporter = HTMLReporter()
        output_path = args.output or "./freya_report.html"
        reporter.generate(result, output_path)
        print(f"HTML report saved to: {output_path}")
    elif args.format == "junit":
        reporter = HTMLReporter()
        output_path = args.output or "./freya_report.xml"
        reporter.generate_junit(result, output_path)
        print(f"JUnit report saved to: {output_path}")
    else:
        output = format_unified_text(result)
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(output)
            print(f"Report saved to: {args.output}")
        else:
            print(output)

    return 1 if result.failed > 0 else 0


async def run_baseline_update(args: argparse.Namespace, verbose: bool = False) -> int:
    """Update baseline."""
    manager = BaselineManager()

    print(f"\nUpdating baseline: {args.name}")
    print(f"URL: {args.url}")
    print("-" * 60)

    result = await manager.create_baseline(
        args.url,
        args.name,
        viewport_width=args.width,
        viewport_height=args.height,
        device=getattr(args, "device", None)
    )

    print(f"Baseline created: {result.screenshot_path}")
    print(f"Hash: {result.hash}")

    return 0


async def run_baseline_compare(args: argparse.Namespace, verbose: bool = False) -> int:
    """Compare to baseline."""
    manager = BaselineManager()

    print(f"\nComparing to baseline: {args.name}")
    print(f"URL: {args.url}")
    print("-" * 60)

    result = await manager.compare_to_baseline(
        args.url,
        args.name,
        device=getattr(args, "device", None),
        threshold=args.threshold
    )

    if not result["success"]:
        print(f"Error: {result['error']}")
        return 1

    print(f"Passed: {'Yes' if result['passed'] else 'No'}")
    print(f"Difference: {result['difference_percentage']:.2f}%")
    if result["diff_image_path"]:
        print(f"Diff image: {result['diff_image_path']}")

    return 0 if result["passed"] else 1


def run_baseline_list(args: argparse.Namespace, verbose: bool = False) -> int:
    """List baselines."""
    manager = BaselineManager()

    url_filter = getattr(args, "url", None)
    baselines = manager.list_baselines(url=url_filter)

    print("\nBaselines:")
    print("-" * 60)

    if not baselines:
        print("  No baselines found.")
    else:
        for baseline in baselines:
            print(f"  {baseline.name}")
            print(f"    URL: {baseline.url}")
            print(f"    Created: {baseline.created_at}")
            print(f"    Device: {baseline.device or 'desktop'}")
            print("")

    return 0


def run_baseline_delete(args: argparse.Namespace, verbose: bool = False) -> int:
    """Delete baseline."""
    manager = BaselineManager()

    success = manager.delete_baseline(
        args.url,
        args.name,
        device=getattr(args, "device", None)
    )

    if success:
        print(f"Baseline '{args.name}' deleted.")
        return 0
    else:
        print(f"Baseline '{args.name}' not found.")
        return 1


async def run_crawl(args: argparse.Namespace, verbose: bool = False) -> int:
    """Run site crawl and test."""
    print(f"\nCrawling and testing: {args.url}")
    print(f"Max depth: {args.depth}, Max pages: {args.max_pages}")
    print("-" * 60)

    auth_config = None
    if args.username and args.password:
        auth_config = {
            "login_url": args.login_url or args.url,
            "username": args.username,
            "password": args.password,
            "username_selector": args.username_selector,
            "password_selector": args.password_selector,
            "submit_selector": args.submit_selector,
        }

    exclude_patterns = [
        r".*\.(jpg|jpeg|png|gif|svg|ico|css|js|woff|woff2|ttf|eot)$",
        r".*#.*",
        r".*/api/.*",
        r".*logout.*",
    ]
    if args.exclude:
        exclude_patterns.extend(args.exclude)

    config = CrawlConfig(
        start_url=args.url,
        max_depth=args.depth,
        max_pages=args.max_pages,
        additional_routes=args.routes or [],
        discover_items=not getattr(args, 'no_discover_items', False),
        include_patterns=args.include or [],
        exclude_patterns=exclude_patterns,
        delay_between_requests=args.delay,
        capture_screenshots=not args.no_screenshots,
        auth_config=auth_config,
        output_directory=args.output,
        browser_config=BrowserConfig(
            headless=not args.no_headless
        ),
    )

    crawler = SiteCrawler(config)

    def progress_callback(message: str, current: int = 0, total: int = 0):
        if total > 0:
            print(f"  [{current}/{total}] {message}")
        else:
            print(f"  {message}")

    crawler.set_progress_callback(progress_callback)

    report = await crawler.crawl_and_test()

    print("")
    print("=" * 70)
    print("  FREYA SITE CRAWL REPORT")
    print("=" * 70)
    print("")
    print(f"  Start URL:        {report.start_url}")
    print(f"  Duration:         {report.total_duration_ms / 1000:.1f}s")
    print("")
    print(f"  Pages Discovered: {report.pages_discovered}")
    print(f"  Pages Tested:     {report.pages_tested}")
    print(f"  Pages Skipped:    {report.pages_skipped}")
    print(f"  Pages Errored:    {report.pages_errored}")
    print("")
    print("-" * 70)
    print("  SCORES (Average)")
    print("-" * 70)
    print(f"  Overall:        {report.average_overall_score:.0f}/100")
    print(f"  Accessibility:  {report.average_accessibility_score:.0f}/100")
    print(f"  Visual:         {report.average_visual_score:.0f}/100")
    print(f"  Responsive:     {report.average_responsive_score:.0f}/100")
    print("")
    print("-" * 70)
    print("  ISSUES")
    print("-" * 70)
    print(f"  Critical: {report.total_critical}")
    print(f"  Serious:  {report.total_serious}")
    print(f"  Moderate: {report.total_moderate}")
    print(f"  Minor:    {report.total_minor}")
    print("")

    if report.worst_pages:
        print("-" * 70)
        print("  WORST PAGES")
        print("-" * 70)
        for url in report.worst_pages[:5]:
            result = next((r for r in report.page_results if r.url == url), None)
            if result:
                print(f"  {result.overall_score:.0f}/100 - {url}")
        print("")

    if report.common_issues:
        print("-" * 70)
        print("  COMMON ISSUES")
        print("-" * 70)
        for issue in report.common_issues[:5]:
            print(f"  [{issue['count']}x] {issue['issue']}: {issue['message']}")
        print("")

    print("=" * 70)
    print(f"\nReports saved to: {args.output}")
    print(f"  - JSON: {args.output}/crawl_report.json")
    print(f"  - HTML: {args.output}/crawl_report.html")

    has_critical = report.total_critical > 0
    return 1 if has_critical else 0


def format_accessibility_text(result) -> str:
    """Format accessibility result as text."""
    lines = []
    lines.append("")
    lines.append("=" * 70)
    lines.append("  FREYA ACCESSIBILITY REPORT")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"  URL:          {result.url}")
    lines.append(f"  WCAG Level:   {result.wcag_level}")
    lines.append(f"  Score:        {result.score:.1f}%")
    lines.append(f"  Tested At:    {result.tested_at}")
    lines.append("")

    if result.has_violations:
        lines.append("-" * 70)
        lines.append("  VIOLATIONS")
        lines.append("-" * 70)
        lines.append("")

        for violation in result.violations:
            marker = SEVERITY_MARKERS.get(violation.severity, "[UNKNOWN]")
            lines.append(f"  {marker}")
            lines.append(f"    {violation.description}")
            lines.append(f"    WCAG: {violation.wcag_reference}")
            lines.append(f"    Element: {violation.element_selector}")
            lines.append(f"    Fix: {violation.suggested_fix}")
            lines.append("")
    else:
        lines.append("  No accessibility violations found!")
        lines.append("")

    lines.append("-" * 70)
    lines.append("  SUMMARY")
    lines.append("-" * 70)
    lines.append("")
    lines.append(f"  Total Violations:  {result.total_violations}")
    lines.append(f"  Critical:          {result.critical_count}")
    lines.append(f"  Serious:           {result.serious_count}")
    lines.append(f"  Moderate:          {result.moderate_count}")
    lines.append(f"  Minor:             {result.minor_count}")
    lines.append("")
    lines.append("=" * 70)

    return "\n".join(lines)


def format_accessibility_markdown(result) -> str:
    """Format accessibility result as Markdown."""
    lines = []
    lines.append("# Freya Accessibility Report")
    lines.append("")
    lines.append(f"- **URL:** {result.url}")
    lines.append(f"- **WCAG Level:** {result.wcag_level}")
    lines.append(f"- **Score:** {result.score:.1f}%")
    lines.append(f"- **Tested At:** {result.tested_at}")
    lines.append("")

    if result.has_violations:
        lines.append("## Violations")
        lines.append("")
        lines.append("| Severity | WCAG | Description | Element |")
        lines.append("|----------|------|-------------|---------|")

        for v in result.violations:
            lines.append(f"| {v.severity} | {v.wcag_reference} | {v.description} | `{v.element_selector}` |")

        lines.append("")

    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **Total Violations:** {result.total_violations}")
    lines.append(f"- **Critical:** {result.critical_count}")
    lines.append(f"- **Serious:** {result.serious_count}")
    lines.append(f"- **Moderate:** {result.moderate_count}")
    lines.append(f"- **Minor:** {result.minor_count}")

    return "\n".join(lines)


def format_accessibility_html(result) -> str:
    """Format accessibility result as HTML."""
    score_class = "excellent" if result.score >= 90 else "good" if result.score >= 70 else "fair" if result.score >= 50 else "poor"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Freya Accessibility Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; }}
        .header {{ background: #f5f5f5; padding: 20px; border-radius: 5px; margin-bottom: 20px; }}
        .score {{ font-size: 2em; font-weight: bold; margin: 10px 0; }}
        .score.excellent {{ color: #4CAF50; }}
        .score.good {{ color: #8BC34A; }}
        .score.fair {{ color: #FF9800; }}
        .score.poor {{ color: #f44336; }}
        .violation {{ border: 1px solid #ddd; margin: 10px 0; padding: 15px; border-radius: 5px; }}
        .violation.critical {{ border-left: 4px solid #f44336; }}
        .violation.serious {{ border-left: 4px solid #FF9800; }}
        .violation.moderate {{ border-left: 4px solid #2196F3; }}
        .violation.minor {{ border-left: 4px solid #4CAF50; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Freya Accessibility Report</h1>
        <p><strong>URL:</strong> {result.url}</p>
        <p><strong>WCAG Level:</strong> {result.wcag_level}</p>
        <p><strong>Tested At:</strong> {result.tested_at}</p>
    </div>
    <div class="score {score_class}">
        Accessibility Score: {result.score:.1f}%
    </div>
"""

    if result.has_violations:
        html += "<h2>Violations</h2>"
        for v in result.violations:
            html += f"""
    <div class="violation {v.severity}">
        <h3>{v.description}</h3>
        <p><strong>Severity:</strong> {v.severity}</p>
        <p><strong>WCAG Reference:</strong> {v.wcag_reference}</p>
        <p><strong>Element:</strong> <code>{v.element_selector}</code></p>
        <p><strong>Suggested Fix:</strong> {v.suggested_fix}</p>
    </div>
"""

    html += "</body></html>"
    return html


def format_contrast_text(result) -> str:
    """Format contrast check result as text."""
    lines = []
    lines.append("")
    lines.append("=" * 70)
    lines.append("  FREYA COLOR CONTRAST REPORT")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"  URL:          {result.url}")
    lines.append(f"  Elements:     {result.total_elements}")
    lines.append(f"  Passing:      {result.passing_count}")
    lines.append(f"  Failing:      {result.failing_count}")
    lines.append("")

    if result.has_violations:
        lines.append("-" * 70)
        lines.append("  CONTRAST ISSUES")
        lines.append("-" * 70)
        for issue in result.issues:
            lines.append(f"\n  Element: {issue.element_selector}")
            lines.append(f"    Foreground: {issue.foreground_color}")
            lines.append(f"    Background: {issue.background_color}")
            lines.append(f"    Ratio: {issue.contrast_ratio:.2f}:1")
            lines.append(f"    Required: {issue.required_ratio}:1")

    lines.append("")
    lines.append("=" * 70)

    return "\n".join(lines)


def format_keyboard_text(result) -> str:
    """Format keyboard test result as text."""
    lines = []
    lines.append("")
    lines.append("=" * 70)
    lines.append("  FREYA KEYBOARD NAVIGATION REPORT")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"  URL:                    {result.url}")
    lines.append(f"  Focusable Elements:     {result.total_focusable}")
    lines.append(f"  Accessible Elements:    {result.accessible_count}")
    lines.append(f"  Issues Found:           {result.issue_count}")
    lines.append("")

    if result.has_issues:
        lines.append("-" * 70)
        lines.append("  ISSUES")
        lines.append("-" * 70)
        for issue in result.issues:
            lines.append(f"\n  {issue.issue_type}")
            lines.append(f"    Element: {issue.element_selector}")
            lines.append(f"    Description: {issue.description}")

    lines.append("")
    lines.append("=" * 70)

    return "\n".join(lines)


def format_aria_text(result) -> str:
    """Format ARIA validation result as text."""
    lines = []
    lines.append("")
    lines.append("=" * 70)
    lines.append("  FREYA ARIA VALIDATION REPORT")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"  URL:          {result.url}")
    lines.append(f"  Elements:     {result.total_aria_elements}")
    lines.append(f"  Valid:        {result.valid_count}")
    lines.append(f"  Invalid:      {result.invalid_count}")
    lines.append("")

    if result.has_violations:
        lines.append("-" * 70)
        lines.append("  ARIA VIOLATIONS")
        lines.append("-" * 70)
        for violation in result.violations:
            lines.append(f"\n  Element: {violation.element_selector}")
            lines.append(f"    Issue: {violation.description}")
            lines.append(f"    Fix: {violation.suggested_fix}")

    lines.append("")
    lines.append("=" * 70)

    return "\n".join(lines)


def format_screen_reader_text(result) -> str:
    """Format screen reader test result as text."""
    lines = []
    lines.append("")
    lines.append("=" * 70)
    lines.append("  FREYA SCREEN READER COMPATIBILITY REPORT")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"  URL:              {result.url}")
    lines.append(f"  Total Elements:   {result.total_elements}")
    lines.append(f"  Labeled:          {result.labeled_count}")
    lines.append(f"  Missing Labels:   {result.missing_labels}")
    lines.append("")

    if result.landmark_structure:
        lines.append("-" * 70)
        lines.append("  LANDMARK STRUCTURE")
        lines.append("-" * 70)
        for landmark, count in result.landmark_structure.items():
            lines.append(f"    {landmark}: {count}")

    if result.heading_structure:
        lines.append("")
        lines.append("-" * 70)
        lines.append("  HEADING STRUCTURE")
        lines.append("-" * 70)
        for heading in result.heading_structure:
            lines.append(f"    h{heading['level']}: {heading['text'][:50]}")

    lines.append("")
    lines.append("=" * 70)

    return "\n".join(lines)


def format_layout_text(result) -> str:
    """Format layout validation result as text."""
    lines = []
    lines.append("")
    lines.append("=" * 70)
    lines.append("  FREYA LAYOUT VALIDATION REPORT")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"  URL:          {result.url}")
    lines.append(f"  Issues:       {len(result.issues)}")
    lines.append("")

    if result.issues:
        lines.append("-" * 70)
        lines.append("  LAYOUT ISSUES")
        lines.append("-" * 70)
        for issue in result.issues:
            lines.append(f"\n  [{issue.severity.upper()}] {issue.issue_type}")
            lines.append(f"    Element: {issue.element_selector}")
            lines.append(f"    Description: {issue.description}")
            lines.append(f"    Fix: {issue.suggested_fix}")

    lines.append("")
    lines.append("=" * 70)

    return "\n".join(lines)


def format_style_text(result) -> str:
    """Format style validation result as text."""
    lines = []
    lines.append("")
    lines.append("=" * 70)
    lines.append("  FREYA STYLE VALIDATION REPORT")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"  URL:          {result.url}")
    lines.append(f"  Issues:       {len(result.issues)}")
    lines.append("")

    if result.issues:
        lines.append("-" * 70)
        lines.append("  STYLE ISSUES")
        lines.append("-" * 70)
        for issue in result.issues:
            lines.append(f"\n  [{issue.severity.upper()}] {issue.issue_type}")
            lines.append(f"    Element: {issue.element_selector}")
            lines.append(f"    Description: {issue.description}")

    lines.append("")
    lines.append("=" * 70)

    return "\n".join(lines)


def format_breakpoint_text(result) -> str:
    """Format breakpoint test result as text."""
    lines = []
    lines.append("")
    lines.append("=" * 70)
    lines.append("  FREYA BREAKPOINT TEST REPORT")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"  URL:              {result.url}")
    lines.append(f"  Breakpoints:      {len(result.breakpoints_tested)}")
    lines.append(f"  Total Issues:     {result.total_issues}")
    lines.append("")

    for bp_result in result.results:
        lines.append(f"  {bp_result.breakpoint.name} ({bp_result.breakpoint.width}x{bp_result.breakpoint.height})")
        lines.append(f"    Issues: {len(bp_result.issues)}")
        lines.append(f"    Horizontal Scroll: {'Yes' if bp_result.has_horizontal_scroll else 'No'}")

    lines.append("")
    lines.append("=" * 70)

    return "\n".join(lines)


def format_touch_text(result) -> str:
    """Format touch target validation result as text."""
    lines = []
    lines.append("")
    lines.append("=" * 70)
    lines.append("  FREYA TOUCH TARGET VALIDATION REPORT")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"  URL:              {result.url}")
    lines.append(f"  Interactive:      {result.total_interactive_elements}")
    lines.append(f"  Passing:          {result.passing_count}")
    lines.append(f"  Failing:          {result.failing_count}")
    lines.append(f"  Min Size:         {result.min_touch_size}px")
    lines.append("")

    if result.issues:
        lines.append("-" * 70)
        lines.append("  TOUCH TARGET ISSUES")
        lines.append("-" * 70)
        for issue in result.issues[:10]:
            lines.append(f"\n  [{issue.severity.upper()}] {issue.element_type}")
            lines.append(f"    Element: {issue.element_selector}")
            lines.append(f"    Size: {issue.width:.0f}x{issue.height:.0f}px")
            lines.append(f"    Required: {issue.min_required}x{issue.min_required}px")

    lines.append("")
    lines.append("=" * 70)

    return "\n".join(lines)


def format_viewport_text(result) -> str:
    """Format viewport test result as text."""
    lines = []
    lines.append("")
    lines.append("=" * 70)
    lines.append("  FREYA VIEWPORT TEST REPORT")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"  URL:              {result.url}")
    lines.append(f"  Viewport Meta:    {result.viewport_meta or 'MISSING'}")
    lines.append(f"  Content Width:    {result.content_width}px")
    lines.append(f"  Viewport Width:   {result.viewport_width}px")
    lines.append(f"  Horizontal Scroll: {'Yes' if result.has_horizontal_scroll else 'No'}")
    lines.append("")

    if result.issues:
        lines.append("-" * 70)
        lines.append("  VIEWPORT ISSUES")
        lines.append("-" * 70)
        for issue in result.issues:
            lines.append(f"\n  [{issue.severity.upper()}] {issue.issue_type}")
            lines.append(f"    Description: {issue.description}")
            lines.append(f"    Fix: {issue.suggested_fix}")

    lines.append("")
    lines.append("=" * 70)

    return "\n".join(lines)


def format_mobile_text(result) -> str:
    """Format mobile compatibility result as text."""
    lines = []
    lines.append("")
    lines.append("=" * 70)
    lines.append("  FREYA MOBILE COMPATIBILITY REPORT")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"  URL:              {result.url}")
    lines.append(f"  Devices Tested:   {', '.join(result.devices_tested)}")
    lines.append(f"  Load Time:        {result.load_time_ms}ms")
    lines.append(f"  Page Size:        {result.page_size_bytes / 1024:.1f} KB")
    lines.append(f"  Resources:        {result.resource_count}")
    lines.append(f"  Score:            {result.mobile_friendly_score:.0f}/100")
    lines.append("")

    if result.issues:
        lines.append("-" * 70)
        lines.append("  MOBILE ISSUES")
        lines.append("-" * 70)
        for issue in result.issues:
            lines.append(f"\n  [{issue.severity.upper()}] {issue.issue_type}")
            lines.append(f"    Description: {issue.description}")
            lines.append(f"    Devices: {', '.join(issue.affected_devices)}")
            lines.append(f"    Fix: {issue.suggested_fix}")

    lines.append("")
    lines.append("=" * 70)

    return "\n".join(lines)


def format_unified_text(result) -> str:
    """Format unified test result as text."""
    lines = []
    lines.append("")
    lines.append("=" * 70)
    lines.append("  FREYA UNIFIED TEST REPORT")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"  URL:              {result.url}")
    lines.append(f"  Duration:         {result.duration_ms}ms")
    lines.append(f"  Overall Score:    {result.overall_score:.0f}/100")
    lines.append("")
    lines.append("  SCORES")
    lines.append(f"    Accessibility:  {result.accessibility_score:.0f}/100")
    lines.append(f"    Visual:         {result.visual_score:.0f}/100")
    lines.append(f"    Responsive:     {result.responsive_score:.0f}/100")
    lines.append("")
    lines.append("  SUMMARY")
    lines.append(f"    Total Tests:    {result.total_tests}")
    lines.append(f"    Passed:         {result.passed}")
    lines.append(f"    Failed:         {result.failed}")
    lines.append("")
    lines.append("  BY SEVERITY")
    lines.append(f"    Critical:       {result.critical_count}")
    lines.append(f"    Serious:        {result.serious_count}")
    lines.append(f"    Moderate:       {result.moderate_count}")
    lines.append(f"    Minor:          {result.minor_count}")
    lines.append("")
    lines.append("=" * 70)

    return "\n".join(lines)


def format_performance_text(result) -> str:
    """Format performance report as text."""
    lines = []
    lines.append("")
    lines.append("=" * 70)
    lines.append("  FREYA PERFORMANCE REPORT")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"  URL:              {result.url}")
    lines.append(f"  Score:            {result.performance_score:.0f}/100")
    lines.append(f"  Grade:            {result.performance_grade.value.upper()}")
    lines.append("")

    if result.page_load_metrics:
        metrics = result.page_load_metrics
        lines.append("-" * 70)
        lines.append("  TIMING METRICS")
        lines.append("-" * 70)
        lines.append(f"    TTFB:           {metrics.time_to_first_byte:.0f}ms")
        lines.append(f"    DOM Interactive:{metrics.dom_interactive:.0f}ms")
        lines.append(f"    DOM Loaded:     {metrics.dom_content_loaded:.0f}ms")
        lines.append(f"    Page Load:      {metrics.page_load:.0f}ms")
        lines.append("")

        if metrics.largest_contentful_paint:
            lines.append("-" * 70)
            lines.append("  CORE WEB VITALS")
            lines.append("-" * 70)
            lines.append(f"    LCP:            {metrics.largest_contentful_paint:.0f}ms")
        if metrics.first_contentful_paint:
            lines.append(f"    FCP:            {metrics.first_contentful_paint:.0f}ms")
        if metrics.cumulative_layout_shift is not None:
            lines.append(f"    CLS:            {metrics.cumulative_layout_shift:.3f}")
        lines.append("")

    if result.issues:
        lines.append("-" * 70)
        lines.append("  ISSUES")
        lines.append("-" * 70)
        for issue in result.issues:
            lines.append(f"\n  [{issue.severity.upper()}] {issue.metric_name}")
            lines.append(f"    {issue.description}")
            lines.append(f"    Fix: {issue.suggested_fix}")

    lines.append("")
    lines.append("=" * 70)

    return "\n".join(lines)


def format_load_time_text(result) -> str:
    """Format load time metrics as text."""
    lines = []
    lines.append("")
    lines.append("=" * 70)
    lines.append("  FREYA PAGE LOAD TIMING")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"  URL:              {result.url}")
    lines.append("")
    lines.append("  TIMING BREAKDOWN")
    lines.append(f"    DNS Lookup:     {result.dns_lookup:.0f}ms")
    lines.append(f"    TCP Connection: {result.tcp_connection:.0f}ms")
    lines.append(f"    SSL Handshake:  {result.ssl_handshake:.0f}ms")
    lines.append(f"    TTFB:           {result.time_to_first_byte:.0f}ms")
    lines.append(f"    Content DL:     {result.content_download:.0f}ms")
    lines.append(f"    DOM Interactive:{result.dom_interactive:.0f}ms")
    lines.append(f"    DOM Loaded:     {result.dom_content_loaded:.0f}ms")
    lines.append(f"    Page Load:      {result.page_load:.0f}ms")
    lines.append("")
    lines.append("=" * 70)

    return "\n".join(lines)


def format_resources_text(result) -> str:
    """Format resource timing as text."""
    lines = []
    lines.append("")
    lines.append("=" * 70)
    lines.append("  FREYA RESOURCE TIMING REPORT")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"  URL:              {result.url}")
    lines.append(f"  Total Resources:  {result.total_resources}")
    lines.append(f"  Total Size:       {result.total_size_kb:.0f}KB")
    lines.append("")
    lines.append("  BY TYPE")
    lines.append(f"    Scripts:        {result.script_count} ({result.script_size / 1024:.0f}KB)")
    lines.append(f"    Stylesheets:    {result.stylesheet_count} ({result.stylesheet_size / 1024:.0f}KB)")
    lines.append(f"    Images:         {result.image_count} ({result.image_size / 1024:.0f}KB)")
    lines.append(f"    Fonts:          {result.font_count} ({result.font_size / 1024:.0f}KB)")
    lines.append("")

    if result.large_resources:
        lines.append("-" * 70)
        lines.append("  LARGE RESOURCES (>100KB)")
        lines.append("-" * 70)
        for url in result.large_resources[:10]:
            lines.append(f"    {url}")
        lines.append("")

    if result.slow_resources:
        lines.append("-" * 70)
        lines.append("  SLOW RESOURCES (>500ms)")
        lines.append("-" * 70)
        for url in result.slow_resources[:10]:
            lines.append(f"    {url}")

    lines.append("")
    lines.append("=" * 70)

    return "\n".join(lines)


def format_seo_text(result) -> str:
    """Format SEO report as text."""
    lines = []
    lines.append("")
    lines.append("=" * 70)
    lines.append("  FREYA SEO REPORT")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"  URL:              {result.url}")
    lines.append(f"  SEO Score:        {result.score:.0f}/100")
    lines.append("")

    if result.title:
        lines.append("-" * 70)
        lines.append("  TITLE")
        lines.append("-" * 70)
        lines.append(f"    Present: {'Yes' if result.title.is_present else 'No'}")
        if result.title.value:
            lines.append(f"    Value: {result.title.value[:60]}...")
            lines.append(f"    Length: {result.title.length} chars")
        for issue in result.title.issues:
            lines.append(f"    Issue: {issue}")

    if result.description:
        lines.append("")
        lines.append("-" * 70)
        lines.append("  DESCRIPTION")
        lines.append("-" * 70)
        lines.append(f"    Present: {'Yes' if result.description.is_present else 'No'}")
        if result.description.value:
            lines.append(f"    Value: {result.description.value[:60]}...")
            lines.append(f"    Length: {result.description.length} chars")
        for issue in result.description.issues:
            lines.append(f"    Issue: {issue}")

    if result.missing_required:
        lines.append("")
        lines.append("-" * 70)
        lines.append("  MISSING REQUIRED")
        lines.append("-" * 70)
        for tag in result.missing_required:
            lines.append(f"    - {tag}")

    lines.append("")
    lines.append("=" * 70)

    return "\n".join(lines)


def format_meta_text(result) -> str:
    """Format meta tag report as text."""
    return format_seo_text(result)


def format_structured_data_text(result) -> str:
    """Format structured data report as text."""
    lines = []
    lines.append("")
    lines.append("=" * 70)
    lines.append("  FREYA STRUCTURED DATA REPORT")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"  URL:              {result.url}")
    lines.append(f"  Total Items:      {result.total_items}")
    lines.append(f"  Valid:            {result.valid_items}")
    lines.append(f"  Invalid:          {result.invalid_items}")
    lines.append("")

    if result.schema_types:
        lines.append("-" * 70)
        lines.append("  SCHEMA TYPES FOUND")
        lines.append("-" * 70)
        for schema_type in result.schema_types:
            lines.append(f"    - {schema_type}")
        lines.append("")

    if result.errors:
        lines.append("-" * 70)
        lines.append("  ERRORS")
        lines.append("-" * 70)
        for error in result.errors:
            lines.append(f"    - {error}")
        lines.append("")

    if result.warnings:
        lines.append("-" * 70)
        lines.append("  WARNINGS")
        lines.append("-" * 70)
        for warning in result.warnings:
            lines.append(f"    - {warning}")

    lines.append("")
    lines.append("=" * 70)

    return "\n".join(lines)


def format_robots_text(robots_result, sitemap_result) -> str:
    """Format robots and sitemap report as text."""
    lines = []
    lines.append("")
    lines.append("=" * 70)
    lines.append("  FREYA ROBOTS/SITEMAP REPORT")
    lines.append("=" * 70)
    lines.append("")

    lines.append("-" * 70)
    lines.append("  ROBOTS.TXT")
    lines.append("-" * 70)
    lines.append(f"    Exists: {'Yes' if robots_result.exists else 'No'}")
    if robots_result.exists:
        lines.append(f"    User-Agents: {', '.join(robots_result.user_agents[:5])}")
        lines.append(f"    Disallow Rules: {len(robots_result.disallow_directives)}")
        lines.append(f"    Sitemaps: {len(robots_result.sitemap_urls)}")

    for issue in robots_result.issues:
        lines.append(f"    Issue: {issue}")

    lines.append("")
    lines.append("-" * 70)
    lines.append("  SITEMAP")
    lines.append("-" * 70)
    lines.append(f"    Exists: {'Yes' if sitemap_result.exists else 'No'}")
    if sitemap_result.exists:
        lines.append(f"    Valid XML: {'Yes' if sitemap_result.is_valid_xml else 'No'}")
        lines.append(f"    Total URLs: {sitemap_result.total_urls}")

    for issue in sitemap_result.issues:
        lines.append(f"    Issue: {issue}")

    lines.append("")
    lines.append("=" * 70)

    return "\n".join(lines)


def format_security_text(result) -> str:
    """Format security headers report as text."""
    lines = []
    lines.append("")
    lines.append("=" * 70)
    lines.append("  FREYA SECURITY HEADERS REPORT")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"  URL:              {result.url}")
    lines.append(f"  Score:            {result.security_score:.0f}/100")
    lines.append(f"  Grade:            {result.security_grade}")
    lines.append("")
    lines.append(f"  Headers Present:  {result.headers_present}")
    lines.append(f"  Headers Missing:  {result.headers_missing}")
    lines.append(f"  Headers Weak:     {result.headers_weak}")
    lines.append("")

    headers_to_show = [
        ("CSP", result.content_security_policy),
        ("HSTS", result.strict_transport_security),
        ("X-Frame-Options", result.x_frame_options),
        ("X-Content-Type-Options", result.x_content_type_options),
        ("Referrer-Policy", result.referrer_policy),
    ]

    lines.append("-" * 70)
    lines.append("  HEADERS STATUS")
    lines.append("-" * 70)
    for name, header in headers_to_show:
        if header:
            status = header.status.value.upper()
            lines.append(f"    {name}: {status}")
        else:
            lines.append(f"    {name}: NOT CHECKED")
    lines.append("")

    if result.critical_issues:
        lines.append("-" * 70)
        lines.append("  CRITICAL ISSUES")
        lines.append("-" * 70)
        for issue in result.critical_issues:
            lines.append(f"    - {issue}")
        lines.append("")

    if result.recommendations:
        lines.append("-" * 70)
        lines.append("  RECOMMENDATIONS")
        lines.append("-" * 70)
        for rec in result.recommendations[:10]:
            lines.append(f"    - {rec}")

    lines.append("")
    lines.append("=" * 70)

    return "\n".join(lines)


def format_csp_text(result) -> str:
    """Format CSP report as text."""
    lines = []
    lines.append("")
    lines.append("=" * 70)
    lines.append("  FREYA CSP ANALYSIS REPORT")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"  Score:            {result.security_score:.0f}/100")
    lines.append(f"  Uses Nonces:      {'Yes' if result.uses_nonces else 'No'}")
    lines.append(f"  Uses Hashes:      {'Yes' if result.uses_hashes else 'No'}")
    lines.append(f"  Strict Dynamic:   {'Yes' if result.uses_strict_dynamic else 'No'}")
    lines.append("")

    if result.directives:
        lines.append("-" * 70)
        lines.append("  DIRECTIVES")
        lines.append("-" * 70)
        for directive in result.directives[:15]:
            values = " ".join(directive.values[:5])
            lines.append(f"    {directive.name}: {values}")
        lines.append("")

    if result.critical_issues:
        lines.append("-" * 70)
        lines.append("  CRITICAL ISSUES")
        lines.append("-" * 70)
        for issue in result.critical_issues:
            lines.append(f"    - {issue}")
        lines.append("")

    if result.warnings:
        lines.append("-" * 70)
        lines.append("  WARNINGS")
        lines.append("-" * 70)
        for warning in result.warnings:
            lines.append(f"    - {warning}")

    lines.append("")
    lines.append("=" * 70)

    return "\n".join(lines)


def format_console_text(result) -> str:
    """Format console report as text."""
    lines = []
    lines.append("")
    lines.append("=" * 70)
    lines.append("  FREYA CONSOLE CAPTURE REPORT")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"  URL:              {result.url}")
    lines.append(f"  Total Messages:   {result.total_messages}")
    lines.append(f"  Errors:           {result.error_count}")
    lines.append(f"  Warnings:         {result.warning_count}")
    lines.append("")

    if result.errors:
        lines.append("-" * 70)
        lines.append("  PAGE ERRORS")
        lines.append("-" * 70)
        for error in result.errors[:10]:
            lines.append(f"    [{error.name}] {error.message[:100]}")
        lines.append("")

    if result.unique_errors:
        lines.append("-" * 70)
        lines.append("  UNIQUE CONSOLE ERRORS")
        lines.append("-" * 70)
        for error in result.unique_errors[:10]:
            lines.append(f"    - {error[:80]}")
        lines.append("")

    if result.resource_errors:
        lines.append("-" * 70)
        lines.append("  FAILED RESOURCES")
        lines.append("-" * 70)
        for error in result.resource_errors[:10]:
            lines.append(f"    - {error.url}")
        lines.append("")

    if result.suggestions:
        lines.append("-" * 70)
        lines.append("  SUGGESTIONS")
        lines.append("-" * 70)
        for suggestion in result.suggestions:
            lines.append(f"    - {suggestion}")

    lines.append("")
    lines.append("=" * 70)

    return "\n".join(lines)


def format_links_text(result) -> str:
    """Format links report as text."""
    lines = []
    lines.append("")
    lines.append("=" * 70)
    lines.append("  FREYA LINK VALIDATION REPORT")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"  URL:              {result.url}")
    lines.append(f"  Total Links:      {result.total_links}")
    lines.append(f"  Health Score:     {result.health_score:.0f}/100")
    lines.append("")
    lines.append("  STATUS")
    lines.append(f"    OK:             {result.ok_count}")
    lines.append(f"    Broken:         {result.broken_count}")
    lines.append(f"    Redirects:      {result.redirect_count}")
    lines.append(f"    Timeouts:       {result.timeout_count}")
    lines.append(f"    Errors:         {result.error_count}")
    lines.append("")

    if result.broken_links:
        lines.append("-" * 70)
        lines.append("  BROKEN LINKS")
        lines.append("-" * 70)
        for link in result.broken_links[:20]:
            status = f"({link.status_code})" if link.status_code else "(error)"
            lines.append(f"    [{link.severity.value.upper()}] {status} {link.url}")
            if link.link_text:
                lines.append(f"        Text: {link.link_text[:50]}")
        lines.append("")

    if result.redirect_chains:
        lines.append("-" * 70)
        lines.append("  REDIRECT CHAINS")
        lines.append("-" * 70)
        for chain in result.redirect_chains[:10]:
            lines.append(f"    {chain.chain_length} redirects: {chain.start_url}")
            lines.append(f"      -> {chain.final_url}")
        lines.append("")

    if result.suggestions:
        lines.append("-" * 70)
        lines.append("  SUGGESTIONS")
        lines.append("-" * 70)
        for suggestion in result.suggestions:
            lines.append(f"    - {suggestion}")

    lines.append("")
    lines.append("=" * 70)

    return "\n".join(lines)


def format_images_text(result) -> str:
    """Format full image optimization report as text."""
    lines = []
    lines.append("")
    lines.append("=" * 70)
    lines.append("  FREYA IMAGE OPTIMIZATION REPORT")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"  URL:              {result.url}")
    lines.append(f"  Total Images:     {result.total_images}")
    lines.append(f"  Optimization Score: {result.optimization_score:.0f}/100")
    lines.append("")
    lines.append("  ISSUE COUNTS")
    lines.append(f"    Critical:       {result.critical_count}")
    lines.append(f"    Warnings:       {result.warning_count}")
    lines.append(f"    Info:           {result.info_count}")
    lines.append("")
    lines.append("  ISSUE BREAKDOWN")
    lines.append(f"    Missing Alt:    {result.missing_alt_count}")
    lines.append(f"    No Lazy Load:   {result.missing_lazy_loading_count}")
    lines.append(f"    Non-Optimized:  {result.non_optimized_format_count}")
    lines.append(f"    No Dimensions:  {result.missing_dimensions_count}")
    lines.append(f"    Oversized:      {result.oversized_count}")
    lines.append(f"    No Srcset:      {result.missing_srcset_count}")
    lines.append("")

    if result.format_breakdown:
        lines.append("-" * 70)
        lines.append("  FORMAT BREAKDOWN")
        lines.append("-" * 70)
        for fmt, count in sorted(result.format_breakdown.items()):
            lines.append(f"    {fmt.upper():12} {count}")
        lines.append("")

    if result.issues:
        lines.append("-" * 70)
        lines.append("  ISSUES FOUND")
        lines.append("-" * 70)
        for issue in result.issues[:20]:
            severity = issue.severity.value.upper()
            lines.append(f"\n  [{severity}] {issue.issue_type.value}")
            lines.append(f"    Image: {issue.image_src[:60]}...")
            lines.append(f"    Description: {issue.description}")
            lines.append(f"    Fix: {issue.suggested_fix[:80]}")
        lines.append("")

    if result.suggestions:
        lines.append("-" * 70)
        lines.append("  SUGGESTIONS")
        lines.append("-" * 70)
        for suggestion in result.suggestions:
            lines.append(f"    - {suggestion}")

    lines.append("")
    lines.append("=" * 70)

    return "\n".join(lines)


def format_images_alt_text(result) -> str:
    """Format image alt text report as text."""
    lines = []
    lines.append("")
    lines.append("=" * 70)
    lines.append("  FREYA IMAGE ALT TEXT REPORT")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"  URL:              {result.url}")
    lines.append(f"  Total Images:     {result.total_images}")
    lines.append(f"  Missing Alt:      {result.missing_alt_count}")
    lines.append(f"  Empty Alt:        {result.empty_alt_count}")
    lines.append("")

    # Filter to only alt-text related issues
    alt_issues = [
        i for i in result.issues
        if i.issue_type.value in ["missing_alt", "empty_alt"]
    ]

    if alt_issues:
        lines.append("-" * 70)
        lines.append("  ALT TEXT ISSUES")
        lines.append("-" * 70)
        for issue in alt_issues[:20]:
            severity = issue.severity.value.upper()
            lines.append(f"\n  [{severity}] {issue.description}")
            lines.append(f"    Image: {issue.image_src[:60]}")
            if issue.wcag_reference:
                lines.append(f"    WCAG: {issue.wcag_reference}")
            lines.append(f"    Fix: {issue.suggested_fix}")
        lines.append("")
    else:
        lines.append("  No alt text issues found.")
        lines.append("")

    lines.append("=" * 70)

    return "\n".join(lines)


def format_images_performance_text(result) -> str:
    """Format image performance report as text."""
    lines = []
    lines.append("")
    lines.append("=" * 70)
    lines.append("  FREYA IMAGE PERFORMANCE REPORT")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"  URL:              {result.url}")
    lines.append(f"  Total Images:     {result.total_images}")
    lines.append(f"  Above Fold:       {result.images_above_fold}")
    lines.append(f"  With Lazy Load:   {result.images_with_lazy_loading}")
    lines.append(f"  With Srcset:      {result.images_with_srcset}")
    lines.append(f"  Optimized Format: {result.optimized_format_count}")
    lines.append("")
    lines.append("  PERFORMANCE ISSUES")
    lines.append(f"    No Lazy Load:   {result.missing_lazy_loading_count}")
    lines.append(f"    Non-Optimized:  {result.non_optimized_format_count}")
    lines.append(f"    No Dimensions:  {result.missing_dimensions_count}")
    lines.append(f"    Oversized:      {result.oversized_count}")
    lines.append(f"    No Srcset:      {result.missing_srcset_count}")
    lines.append("")

    # Filter to performance-related issues only
    perf_types = [
        "missing_lazy_loading", "non_optimized_format",
        "missing_dimensions", "oversized_image", "missing_srcset"
    ]
    perf_issues = [i for i in result.issues if i.issue_type.value in perf_types]

    if perf_issues:
        lines.append("-" * 70)
        lines.append("  PERFORMANCE ISSUES DETAIL")
        lines.append("-" * 70)
        for issue in perf_issues[:20]:
            severity = issue.severity.value.upper()
            lines.append(f"\n  [{severity}] {issue.issue_type.value.replace('_', ' ').title()}")
            lines.append(f"    Image: {issue.image_src[:60]}")
            lines.append(f"    Impact: {issue.impact}")
            lines.append(f"    Fix: {issue.suggested_fix[:80]}")
        lines.append("")
    else:
        lines.append("  No performance issues found.")
        lines.append("")

    if result.suggestions:
        lines.append("-" * 70)
        lines.append("  SUGGESTIONS")
        lines.append("-" * 70)
        for suggestion in result.suggestions:
            lines.append(f"    - {suggestion}")

    lines.append("")
    lines.append("=" * 70)

    return "\n".join(lines)


def main(args=None) -> int:
    """Main entry point.

    Args:
        args: Optional list of arguments. If None, uses sys.argv.

    Returns:
        Exit code (0 for success, non-zero for failure).
    """
    parser = create_parser()
    args = parser.parse_args(args)

    verbose = getattr(args, "verbose", False)

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    if args.command == "accessibility":
        if not hasattr(args, "accessibility_command") or args.accessibility_command is None:
            print("Error: Please specify an accessibility command (e.g., 'audit', 'contrast')")
            sys.exit(1)

        if args.accessibility_command == "audit":
            exit_code = asyncio.run(run_accessibility_audit(args, verbose))
        elif args.accessibility_command == "contrast":
            exit_code = asyncio.run(run_contrast_check(args, verbose))
        elif args.accessibility_command == "keyboard":
            exit_code = asyncio.run(run_keyboard_test(args, verbose))
        elif args.accessibility_command == "aria":
            exit_code = asyncio.run(run_aria_validation(args, verbose))
        elif args.accessibility_command == "screen-reader":
            exit_code = asyncio.run(run_screen_reader_test(args, verbose))
        else:
            print(f"Unknown accessibility command: {args.accessibility_command}")
            sys.exit(1)

        sys.exit(exit_code)

    elif args.command == "visual":
        if not hasattr(args, "visual_command") or args.visual_command is None:
            print("Error: Please specify a visual command (e.g., 'capture', 'compare')")
            sys.exit(1)

        if args.visual_command == "capture":
            exit_code = asyncio.run(run_visual_capture(args, verbose))
        elif args.visual_command == "compare":
            exit_code = asyncio.run(run_visual_compare(args, verbose))
        elif args.visual_command == "layout":
            exit_code = asyncio.run(run_layout_validation(args, verbose))
        elif args.visual_command == "style":
            exit_code = asyncio.run(run_style_validation(args, verbose))
        else:
            print(f"Unknown visual command: {args.visual_command}")
            sys.exit(1)

        sys.exit(exit_code)

    elif args.command == "responsive":
        if not hasattr(args, "responsive_command") or args.responsive_command is None:
            print("Error: Please specify a responsive command (e.g., 'breakpoints', 'touch')")
            sys.exit(1)

        if args.responsive_command == "breakpoints":
            exit_code = asyncio.run(run_breakpoint_test(args, verbose))
        elif args.responsive_command == "touch":
            exit_code = asyncio.run(run_touch_validation(args, verbose))
        elif args.responsive_command == "viewport":
            exit_code = asyncio.run(run_viewport_test(args, verbose))
        elif args.responsive_command == "mobile":
            exit_code = asyncio.run(run_mobile_test(args, verbose))
        else:
            print(f"Unknown responsive command: {args.responsive_command}")
            sys.exit(1)

        sys.exit(exit_code)

    elif args.command == "performance":
        if not hasattr(args, "performance_command") or args.performance_command is None:
            print("Error: Please specify a performance command (e.g., 'audit', 'load-time')")
            sys.exit(1)

        if args.performance_command == "audit":
            exit_code = asyncio.run(run_performance_audit(args, verbose))
        elif args.performance_command == "load-time":
            exit_code = asyncio.run(run_performance_load_time(args, verbose))
        elif args.performance_command == "resources":
            exit_code = asyncio.run(run_performance_resources(args, verbose))
        else:
            print(f"Unknown performance command: {args.performance_command}")
            sys.exit(1)

        sys.exit(exit_code)

    elif args.command == "seo":
        if not hasattr(args, "seo_command") or args.seo_command is None:
            print("Error: Please specify an SEO command (e.g., 'audit', 'meta')")
            sys.exit(1)

        if args.seo_command == "audit":
            exit_code = asyncio.run(run_seo_audit(args, verbose))
        elif args.seo_command == "meta":
            exit_code = asyncio.run(run_seo_meta(args, verbose))
        elif args.seo_command == "structured-data":
            exit_code = asyncio.run(run_seo_structured_data(args, verbose))
        elif args.seo_command == "robots":
            exit_code = asyncio.run(run_seo_robots(args, verbose))
        else:
            print(f"Unknown SEO command: {args.seo_command}")
            sys.exit(1)

        sys.exit(exit_code)

    elif args.command == "security":
        if not hasattr(args, "security_command") or args.security_command is None:
            print("Error: Please specify a security command (e.g., 'headers', 'csp')")
            sys.exit(1)

        if args.security_command == "headers":
            exit_code = asyncio.run(run_security_headers(args, verbose))
        elif args.security_command == "csp":
            exit_code = asyncio.run(run_security_csp(args, verbose))
        else:
            print(f"Unknown security command: {args.security_command}")
            sys.exit(1)

        sys.exit(exit_code)

    elif args.command == "console":
        if not hasattr(args, "console_command") or args.console_command is None:
            print("Error: Please specify a console command (e.g., 'errors')")
            sys.exit(1)

        if args.console_command == "errors":
            exit_code = asyncio.run(run_console_errors(args, verbose))
        else:
            print(f"Unknown console command: {args.console_command}")
            sys.exit(1)

        sys.exit(exit_code)

    elif args.command == "links":
        if not hasattr(args, "links_command") or args.links_command is None:
            print("Error: Please specify a links command (e.g., 'validate')")
            sys.exit(1)

        if args.links_command == "validate":
            exit_code = asyncio.run(run_links_validate(args, verbose))
        else:
            print(f"Unknown links command: {args.links_command}")
            sys.exit(1)

        sys.exit(exit_code)

    elif args.command == "images":
        if not hasattr(args, "images_command") or args.images_command is None:
            print("Error: Please specify an images command (e.g., 'audit', 'alt-text', 'performance')")
            sys.exit(1)

        if args.images_command == "audit":
            exit_code = asyncio.run(run_images_audit(args, verbose))
        elif args.images_command == "alt-text":
            exit_code = asyncio.run(run_images_alt_text(args, verbose))
        elif args.images_command == "performance":
            exit_code = asyncio.run(run_images_performance(args, verbose))
        else:
            print(f"Unknown images command: {args.images_command}")
            sys.exit(1)

        sys.exit(exit_code)

    elif args.command == "test":
        exit_code = asyncio.run(run_unified_test(args, verbose))
        sys.exit(exit_code)

    elif args.command == "crawl":
        exit_code = asyncio.run(run_crawl(args, verbose))
        sys.exit(exit_code)

    elif args.command == "baseline":
        if not hasattr(args, "baseline_command") or args.baseline_command is None:
            print("Error: Please specify a baseline command (e.g., 'update', 'compare')")
            sys.exit(1)

        if args.baseline_command == "update":
            exit_code = asyncio.run(run_baseline_update(args, verbose))
        elif args.baseline_command == "compare":
            exit_code = asyncio.run(run_baseline_compare(args, verbose))
        elif args.baseline_command == "list":
            exit_code = run_baseline_list(args, verbose)
        elif args.baseline_command == "delete":
            exit_code = run_baseline_delete(args, verbose)
        else:
            print(f"Unknown baseline command: {args.baseline_command}")
            sys.exit(1)

        sys.exit(exit_code)

    elif args.command == "config":
        if args.config_command == "show":
            print("Configuration: (defaults)")
            print("  WCAG Level: AA")
            print("  Output Format: text")
            print("  Baseline Directory: ./freya_baselines")
        elif args.config_command == "init":
            print("Configuration file created: .freyarc")
        else:
            print("Error: Please specify a config command (e.g., 'show', 'init')")
            sys.exit(1)
        sys.exit(0)

    else:
        print(f"Unknown command: {args.command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
