"""
Freya Unified Tester responsive test runner.

Responsive test runner extracted from _unified_tester_runners.py.
"""

from pathlib import Path
from typing import Any, Dict, List

from Asgard.Freya.Integration.models.integration_models import (
    TestCategory,
    TestSeverity,
    UnifiedTestResult,
)
from Asgard.Freya.Integration.services._unified_tester_runners import map_severity
from Asgard.Freya.Responsive.services import (
    BreakpointTester,
    TouchTargetValidator,
    ViewportTester,
    MobileCompatibilityTester,
)


async def run_responsive_tests(
    url: str,
    output_dir: Path,
    capture_screenshots: bool,
) -> tuple[List[UnifiedTestResult], dict]:
    """Run all responsive tests."""
    results = []
    screenshots: Dict[Any, Any] = {}

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

        if not mobile_report.is_complete:
            results.append(UnifiedTestResult(
                category=TestCategory.RESPONSIVE,
                test_name="Mobile Compatibility",
                passed=False,
                severity=TestSeverity.CRITICAL,
                message="Mobile compatibility observations are incomplete",
                details={"is_complete": False},
            ))
        elif not mobile_report.issues:
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
