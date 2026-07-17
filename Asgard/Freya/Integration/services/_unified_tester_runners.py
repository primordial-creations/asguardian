"""
Freya Unified Tester runner functions.

Accessibility and visual test runners extracted from unified_tester.py.
Responsive test runners are in _unified_tester_responsive.py.
"""

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
                details={
                    "rule": violation.rule_id,
                    # Plan 02 -> Plan 01 hookup: criticality escalates severity.
                    "criticality": getattr(
                        getattr(violation, "criticality", None), "value", None
                    ),
                },
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
