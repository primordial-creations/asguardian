"""
Freya - Visual and UI Testing Package

Named after the Norse goddess of love and beauty,
Freya provides comprehensive visual and UI testing capabilities.

Modules:
    Accessibility: WCAG validation, color contrast, keyboard navigation,
                   screen reader compatibility, ARIA validation
    Visual: Screenshot capture, visual regression, layout validation,
            style consistency checking
    Responsive: Breakpoint testing, touch target validation,
                viewport testing, mobile compatibility
    Integration: Unified testing, HTML reporting, baseline management,
                 Playwright utilities
    Performance: Page load timing, Core Web Vitals, resource analysis
    SEO: Meta tags, structured data, robots.txt, sitemap validation
    Security: Security headers, CSP analysis, HSTS checking
    Console: JavaScript console error/warning capture
    Links: Broken link detection, redirect chain analysis

Usage:
    python -m Freya test <url>
    python -m Freya accessibility audit <url>
    python -m Freya visual capture <url>
    python -m Freya responsive breakpoints <url>
    python -m Freya performance audit <url>
    python -m Freya seo audit <url>
    python -m Freya security headers <url>
    python -m Freya console errors <url>
    python -m Freya links validate <url>
    python -m Freya baseline update <url> --name homepage
"""

__version__ = "2.0.0"
__author__ = "Asgard Contributors"

PACKAGE_INFO = {
    "name": "Freya",
    "version": __version__,
    "description": "Visual and UI testing package",
    "author": __author__,
    "sub_packages": [
        "Accessibility - WCAG compliance, color contrast, keyboard, screen reader, ARIA",
        "Visual - Screenshot capture, visual regression, layout, style",
        "Responsive - Breakpoint testing, touch targets, viewport, mobile",
        "Integration - Unified testing, HTML reports, baselines, Playwright utils",
        "Performance - Page load timing, Core Web Vitals, resource analysis",
        "SEO - Meta tags, structured data, robots.txt, sitemap validation",
        "Security - Security headers, CSP analysis, HSTS checking",
        "Console - JavaScript console error/warning capture",
        "Links - Broken link detection, redirect chain analysis",
        "Images - Image optimization, alt text, lazy loading, format detection",
    ]
}

from Asgard.Freya.Accessibility import (
    WCAGValidator,
    ColorContrastChecker,
    KeyboardNavigationTester,
    ScreenReaderValidator,
    ARIAValidator,
    AccessibilityConfig,
    AccessibilityViolation,
    AccessibilityReport,
    WCAGLevel,
    ViolationSeverity,
    AccessibilityCategory,
)

from Asgard.Freya.Visual import (
    ScreenshotCapture,
    VisualRegressionTester,
    LayoutValidator,
    StyleValidator,
    ScreenshotResult,
    VisualComparisonResult,
    LayoutIssue,
    LayoutReport,
    StyleIssue,
    StyleReport,
)

from Asgard.Freya.Responsive import (
    BreakpointTester,
    TouchTargetValidator,
    ViewportTester,
    MobileCompatibilityTester,
    Breakpoint,
    BreakpointIssue,
    BreakpointReport,
    TouchTargetIssue,
    TouchTargetReport,
    ViewportIssue,
    ViewportReport,
    MobileCompatibilityIssue,
    MobileCompatibilityReport,
    COMMON_BREAKPOINTS,
    MOBILE_DEVICES,
)

from Asgard.Freya.Integration import (
    UnifiedTester,
    HTMLReporter,
    BaselineManager,
    PlaywrightUtils,
)

from Asgard.Freya.Performance import (
    PageLoadAnalyzer,
    ResourceTimingAnalyzer,
    PageLoadMetrics,
    PerformanceReport,
    PerformanceConfig,
    PerformanceGrade,
    ResourceTimingReport,
)

from Asgard.Freya.SEO import (
    MetaTagAnalyzer,
    StructuredDataValidator,
    RobotsAnalyzer,
    MetaTagReport,
    StructuredDataReport,
    SEOReport,
    SEOConfig,
)

from Asgard.Freya.Security import (
    SecurityHeaderScanner,
    CSPAnalyzer,
    SecurityHeaderReport,
    CSPReport,
    SecurityConfig,
)

from Asgard.Freya.Console import (
    ConsoleCapture,
    ConsoleReport,
    ConsoleConfig,
    ConsoleMessage,
)

from Asgard.Freya.Links import (
    LinkValidator,
    LinkReport,
    LinkConfig,
    BrokenLink,
    RedirectChain,
)

from Asgard.Freya.Scoring import (
    Finding,
    GateConfig,
    GateResult,
    GradeCalculator,
    GradedScore,
    QualityGate,
    QualityGrade,
    SeverityMapper,
    UniversalSeverity,
)

from Asgard.Freya.Images import (
    ImageOptimizationScanner,
    ImageConfig,
    ImageFormat,
    ImageInfo,
    ImageIssue,
    ImageIssueSeverity,
    ImageIssueType,
    ImageReport,
)

__all__ = [
    # Version info
    "__version__",
    "__author__",
    "PACKAGE_INFO",
    # Accessibility Services
    "WCAGValidator",
    "ColorContrastChecker",
    "KeyboardNavigationTester",
    "ScreenReaderValidator",
    "ARIAValidator",
    # Accessibility Models
    "AccessibilityConfig",
    "AccessibilityViolation",
    "AccessibilityReport",
    "WCAGLevel",
    "ViolationSeverity",
    "AccessibilityCategory",
    # Visual Services
    "ScreenshotCapture",
    "VisualRegressionTester",
    "LayoutValidator",
    "StyleValidator",
    # Visual Models
    "ScreenshotResult",
    "VisualComparisonResult",
    "LayoutIssue",
    "LayoutReport",
    "StyleIssue",
    "StyleReport",
    # Responsive Services
    "BreakpointTester",
    "TouchTargetValidator",
    "ViewportTester",
    "MobileCompatibilityTester",
    # Responsive Models
    "Breakpoint",
    "BreakpointIssue",
    "BreakpointReport",
    "TouchTargetIssue",
    "TouchTargetReport",
    "ViewportIssue",
    "ViewportReport",
    "MobileCompatibilityIssue",
    "MobileCompatibilityReport",
    "COMMON_BREAKPOINTS",
    "MOBILE_DEVICES",
    # Integration Services
    "UnifiedTester",
    "HTMLReporter",
    "BaselineManager",
    "PlaywrightUtils",
    # Performance
    "PageLoadAnalyzer",
    "ResourceTimingAnalyzer",
    "PageLoadMetrics",
    "PerformanceReport",
    "PerformanceConfig",
    "PerformanceGrade",
    "ResourceTimingReport",
    # SEO
    "MetaTagAnalyzer",
    "StructuredDataValidator",
    "RobotsAnalyzer",
    "MetaTagReport",
    "StructuredDataReport",
    "SEOReport",
    "SEOConfig",
    # Security
    "SecurityHeaderScanner",
    "CSPAnalyzer",
    "SecurityHeaderReport",
    "CSPReport",
    "SecurityConfig",
    # Console
    "ConsoleCapture",
    "ConsoleReport",
    "ConsoleConfig",
    "ConsoleMessage",
    # Links
    "LinkValidator",
    "LinkReport",
    "LinkConfig",
    "BrokenLink",
    "RedirectChain",
    # Scoring (universal severity / grading)
    "Finding",
    "GateConfig",
    "GateResult",
    "GradeCalculator",
    "GradedScore",
    "QualityGate",
    "QualityGrade",
    "SeverityMapper",
    "UniversalSeverity",
    # Images
    "ImageOptimizationScanner",
    "ImageConfig",
    "ImageFormat",
    "ImageInfo",
    "ImageIssue",
    "ImageIssueSeverity",
    "ImageIssueType",
    "ImageReport",
]
