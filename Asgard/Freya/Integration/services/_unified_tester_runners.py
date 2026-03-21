"""
Freya Unified Tester runner functions.

Test runner functions extracted from unified_tester.py.
"""

from pathlib import Path
from typing import Any, Dict, List

from Asgard.Freya.Integration.models.integration_models import (
    TestCategory,
    TestSeverity,
    UnifiedTestResult,
)
from Asgard.Freya.Accessibility.services import (
    WCAGValidator,
    ColorContrastChecker,
    KeyboardNavigationTester,
    ARIAValidator,
)
from Asgard.Freya.Visual.services import (
    LayoutValidator,
    StyleValidator,
)
from Asgard.Freya.Responsive.services import (
    BreakpointTester,
    TouchTargetValidator,
    ViewportTester,
    MobileCompatibilityTester,
)


def map_severity(severity_str: str) -> TestSeverity:
    """Map string severity to TestSeverity enum."""
    mapping = {
        "critical": TestSeverity.CRITICAL,
        "serious": TestSeverity.SERIOUS,
        "moderate": TestSeverity.MODERATE,
        "minor": TestSeverity.MINOR,
    }
    return mapping.get(severity_str.lower(), TestSeverity.MODERATE)


async def run_accessibility_tests(url: str) -> List[UnifiedTestResult]:
    """Run all accessibility tests."""
    results = []

    try:
        wcag = WCAGValidator()
        wcag_report = await wcag.validate(url)

        for violation in wcag_report.violations:
            results.append(UnifiedTestResult(
                category=TestCategory.ACCESSIBILITY,
                test_name="WCAG Validation",
                passed=False,
                severity=map_severity(violation.severity),
                message=violation.description,
                element_selector=violation.element_selector,
                suggested_fix=violation.suggested_fix,
                wcag_reference=violation.wcag_criterion,
                details={"rule": violation.rule_id},
            ))

        if not wcag_report.violations:
            results.append(UnifiedTestResult(
                category=TestCategory.ACCESSIBILITY,
                test_name="WCAG Validation",
                passed=True,
                message="No WCAG violations found",
            ))

    except Exception as e:
        results.append(UnifiedTestResult(
            category=TestCategory.ACCESSIBILITY,
            test_name="WCAG Validation",
            passed=False,
            severity=TestSeverity.CRITICAL,
            message=f"WCAG validation failed: {str(e)}",
        ))

    try:
        contrast = ColorContrastChecker()
        contrast_report = await contrast.check(url)

        for issue in contrast_report.issues:
            results.append(UnifiedTestResult(
                category=TestCategory.ACCESSIBILITY,
                test_name="Color Contrast",
                passed=False,
                severity=map_severity(issue.severity),
                message=issue.description,
                element_selector=issue.element_selector,
                suggested_fix=issue.suggested_fix,
                wcag_reference=issue.wcag_criterion,
                details={
                    "foreground": issue.foreground_color,
                    "background": issue.background_color,
                    "ratio": issue.contrast_ratio,
                },
            ))

        if not contrast_report.issues:
            results.append(UnifiedTestResult(
                category=TestCategory.ACCESSIBILITY,
                test_name="Color Contrast",
                passed=True,
                message="All color contrasts meet WCAG requirements",
            ))

    except Exception as e:
        results.append(UnifiedTestResult(
            category=TestCategory.ACCESSIBILITY,
            test_name="Color Contrast",
            passed=False,
            severity=TestSeverity.CRITICAL,
            message=f"Color contrast check failed: {str(e)}",
        ))

    try:
        keyboard = KeyboardNavigationTester()
        keyboard_report = await keyboard.test(url)

        for issue in keyboard_report.issues:
            results.append(UnifiedTestResult(
                category=TestCategory.ACCESSIBILITY,
                test_name="Keyboard Navigation",
                passed=False,
                severity=map_severity(issue.severity),
                message=issue.description,
                element_selector=issue.element_selector,
                suggested_fix=issue.suggested_fix,
                wcag_reference=issue.wcag_reference,
            ))

        if not keyboard_report.issues:
            results.append(UnifiedTestResult(
                category=TestCategory.ACCESSIBILITY,
                test_name="Keyboard Navigation",
                passed=True,
                message="Keyboard navigation is accessible",
            ))

    except Exception as e:
        results.append(UnifiedTestResult(
            category=TestCategory.ACCESSIBILITY,
            test_name="Keyboard Navigation",
            passed=False,
            severity=TestSeverity.CRITICAL,
            message=f"Keyboard navigation test failed: {str(e)}",
        ))

    try:
        aria = ARIAValidator()
        aria_report = await aria.validate(url)

        for violation in aria_report.violations:
            results.append(UnifiedTestResult(
                category=TestCategory.ACCESSIBILITY,
                test_name="ARIA Validation",
                passed=False,
                severity=map_severity(violation.severity),
                message=violation.description,
                element_selector=violation.element_selector,
                suggested_fix=violation.suggested_fix,
            ))

        if not aria_report.violations:
            results.append(UnifiedTestResult(
                category=TestCategory.ACCESSIBILITY,
                test_name="ARIA Validation",
                passed=True,
                message="ARIA implementation is valid",
            ))

    except Exception as e:
        results.append(UnifiedTestResult(
            category=TestCategory.ACCESSIBILITY,
            test_name="ARIA Validation",
            passed=False,
            severity=TestSeverity.CRITICAL,
            message=f"ARIA validation failed: {str(e)}",
        ))

    return results


async def run_visual_tests(url: str) -> tuple[List[UnifiedTestResult], dict]:
    """Run all visual tests."""
    results = []
    screenshots: Dict[Any, Any] = {}

    try:
        layout = LayoutValidator()
        layout_report = await layout.validate(url)

        for issue in layout_report.issues:
            results.append(UnifiedTestResult(
                category=TestCategory.VISUAL,
                test_name="Layout Validation",
                passed=False,
                severity=map_severity(issue.severity),
                message=issue.description,
                element_selector=issue.element_selector,
                suggested_fix=issue.suggested_fix,
            ))

        if not layout_report.issues:
            results.append(UnifiedTestResult(
                category=TestCategory.VISUAL,
                test_name="Layout Validation",
                passed=True,
                message="No layout issues found",
            ))

    except Exception as e:
        results.append(UnifiedTestResult(
            category=TestCategory.VISUAL,
            test_name="Layout Validation",
            passed=False,
            severity=TestSeverity.CRITICAL,
            message=f"Layout validation failed: {str(e)}",
        ))

    try:
        style = StyleValidator()
        style_report = await style.validate(url)

        for issue in style_report.issues:
            results.append(UnifiedTestResult(
                category=TestCategory.VISUAL,
                test_name="Style Validation",
                passed=False,
                severity=map_severity(issue.severity),
                message=issue.description,
                element_selector=issue.element_selector,
                suggested_fix=issue.suggested_fix,
            ))

        if not style_report.issues:
            results.append(UnifiedTestResult(
                category=TestCategory.VISUAL,
                test_name="Style Validation",
                passed=True,
                message="Styles are consistent",
            ))

    except Exception as e:
        results.append(UnifiedTestResult(
            category=TestCategory.VISUAL,
            test_name="Style Validation",
            passed=False,
            severity=TestSeverity.CRITICAL,
            message=f"Style validation failed: {str(e)}",
        ))

    return results, screenshots


async def run_responsive_tests(
    url: str,
    output_dir: Path,
    capture_screenshots: bool,
) -> tuple[List[UnifiedTestResult], dict]:
    """Run all responsive tests."""
    results = []
    screenshots = {}

    try:
        breakpoints = BreakpointTester(output_directory=str(output_dir / "breakpoints"))
        bp_report = await breakpoints.test(url, capture_screenshots=capture_screenshots)

        for result in bp_report.results:
            for issue in result.issues:
                results.append(UnifiedTestResult(
                    category=TestCategory.RESPONSIVE,
                    test_name=f"Breakpoint: {result.breakpoint.name}",
                    passed=False,
                    severity=map_severity(issue.severity),
                    message=issue.description,
                    element_selector=issue.element_selector,
                    suggested_fix=issue.suggested_fix,
                    details={"breakpoint": result.breakpoint.name},
                ))

        screenshots.update(bp_report.screenshots)

        if bp_report.total_issues == 0:
            results.append(UnifiedTestResult(
                category=TestCategory.RESPONSIVE,
                test_name="Breakpoint Testing",
                passed=True,
                message="All breakpoints render correctly",
            ))

    except Exception as e:
        results.append(UnifiedTestResult(
            category=TestCategory.RESPONSIVE,
            test_name="Breakpoint Testing",
            passed=False,
            severity=TestSeverity.CRITICAL,
            message=f"Breakpoint testing failed: {str(e)}",
        ))

    try:
        touch = TouchTargetValidator()
        touch_report = await touch.validate(url)

        for issue in touch_report.issues:
            results.append(UnifiedTestResult(
                category=TestCategory.RESPONSIVE,
                test_name="Touch Targets",
                passed=False,
                severity=map_severity(issue.severity),
                message=issue.description,
                element_selector=issue.element_selector,
                suggested_fix=issue.suggested_fix,
                details={"width": issue.width, "height": issue.height},
            ))

        if not touch_report.issues:
            results.append(UnifiedTestResult(
                category=TestCategory.RESPONSIVE,
                test_name="Touch Targets",
                passed=True,
                message="All touch targets meet size requirements",
            ))

    except Exception as e:
        results.append(UnifiedTestResult(
            category=TestCategory.RESPONSIVE,
            test_name="Touch Targets",
            passed=False,
            severity=TestSeverity.CRITICAL,
            message=f"Touch target validation failed: {str(e)}",
        ))

    try:
        viewport = ViewportTester()
        vp_report = await viewport.test(url)

        for issue in vp_report.issues:
            results.append(UnifiedTestResult(
                category=TestCategory.RESPONSIVE,
                test_name="Viewport Configuration",
                passed=False,
                severity=map_severity(issue.severity),
                message=issue.description,
                suggested_fix=issue.suggested_fix,
                wcag_reference=issue.wcag_reference,
            ))

        if not vp_report.issues:
            results.append(UnifiedTestResult(
                category=TestCategory.RESPONSIVE,
                test_name="Viewport Configuration",
                passed=True,
                message="Viewport is properly configured",
            ))

    except Exception as e:
        results.append(UnifiedTestResult(
            category=TestCategory.RESPONSIVE,
            test_name="Viewport Configuration",
            passed=False,
            severity=TestSeverity.CRITICAL,
            message=f"Viewport testing failed: {str(e)}",
        ))

    try:
        mobile = MobileCompatibilityTester()
        mobile_report = await mobile.test(url)

        for issue in mobile_report.issues:
            results.append(UnifiedTestResult(
                category=TestCategory.RESPONSIVE,
                test_name="Mobile Compatibility",
                passed=False,
                severity=map_severity(issue.severity),
                message=issue.description,
                element_selector=issue.element_selector,
                suggested_fix=issue.suggested_fix,
                details={"devices": issue.affected_devices},
            ))

        if not mobile_report.issues:
            results.append(UnifiedTestResult(
                category=TestCategory.RESPONSIVE,
                test_name="Mobile Compatibility",
                passed=True,
                message="Page is mobile-friendly",
            ))

    except Exception as e:
        results.append(UnifiedTestResult(
            category=TestCategory.RESPONSIVE,
            test_name="Mobile Compatibility",
            passed=False,
            severity=TestSeverity.CRITICAL,
            message=f"Mobile compatibility test failed: {str(e)}",
        ))

    return results, screenshots
