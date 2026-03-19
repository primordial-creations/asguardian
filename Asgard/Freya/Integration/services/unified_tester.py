"""
Freya Unified Tester

Runs all accessibility, visual, and responsive tests on a URL.
"""

import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from Asgard.Freya.Integration.models.integration_models import (
    TestCategory,
    TestSeverity,
    UnifiedTestConfig,
    UnifiedTestResult,
    UnifiedTestReport,
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


class UnifiedTester:
    """
    Unified testing service.

    Runs all Freya tests and aggregates results.
    """

    def __init__(self, config: Optional[UnifiedTestConfig] = None):
        """
        Initialize the Unified Tester.

        Args:
            config: Test configuration
        """
        self.config = config or UnifiedTestConfig(url="")
        self.output_dir = Path(self.config.output_directory)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def test(
        self,
        url: str,
        categories: Optional[List[TestCategory]] = None,
        min_severity: TestSeverity = TestSeverity.MINOR
    ) -> UnifiedTestReport:
        """
        Run unified tests on a URL.

        Args:
            url: URL to test
            categories: Categories to test (default: all)
            min_severity: Minimum severity to include

        Returns:
            UnifiedTestReport with all findings
        """
        start_time = time.time()

        if categories is None:
            categories = [TestCategory.ALL]

        self.config.url = url
        self.config.categories = categories
        self.config.min_severity = min_severity

        accessibility_results: List[Any] = []
        visual_results: List[Any] = []
        responsive_results: List[Any] = []
        screenshots: Dict[Any, Any] = {}

        run_all = TestCategory.ALL in categories

        if run_all or TestCategory.ACCESSIBILITY in categories:
            accessibility_results = await self._run_accessibility_tests(url)

        if run_all or TestCategory.VISUAL in categories:
            visual_results, visual_screenshots = await self._run_visual_tests(url)
            screenshots.update(visual_screenshots)

        if run_all or TestCategory.RESPONSIVE in categories:
            responsive_results, responsive_screenshots = await self._run_responsive_tests(url)
            screenshots.update(responsive_screenshots)

        all_results = accessibility_results + visual_results + responsive_results
        filtered_results = self._filter_by_severity(all_results, min_severity)

        duration_ms = int((time.time() - start_time) * 1000)

        passed = len([r for r in filtered_results if r.passed])
        failed = len([r for r in filtered_results if not r.passed])

        critical = len([r for r in filtered_results if r.severity == TestSeverity.CRITICAL])
        serious = len([r for r in filtered_results if r.severity == TestSeverity.SERIOUS])
        moderate = len([r for r in filtered_results if r.severity == TestSeverity.MODERATE])
        minor = len([r for r in filtered_results if r.severity == TestSeverity.MINOR])

        accessibility_score = self._calculate_category_score(
            [r for r in filtered_results if r.category == TestCategory.ACCESSIBILITY]
        )
        visual_score = self._calculate_category_score(
            [r for r in filtered_results if r.category == TestCategory.VISUAL]
        )
        responsive_score = self._calculate_category_score(
            [r for r in filtered_results if r.category == TestCategory.RESPONSIVE]
        )

        overall_score = (accessibility_score + visual_score + responsive_score) / 3

        return UnifiedTestReport(
            url=url,
            tested_at=datetime.now().isoformat(),
            duration_ms=duration_ms,
            total_tests=len(filtered_results),
            passed=passed,
            failed=failed,
            accessibility_results=[r for r in filtered_results if r.category == TestCategory.ACCESSIBILITY],
            visual_results=[r for r in filtered_results if r.category == TestCategory.VISUAL],
            responsive_results=[r for r in filtered_results if r.category == TestCategory.RESPONSIVE],
            critical_count=critical,
            serious_count=serious,
            moderate_count=moderate,
            minor_count=minor,
            accessibility_score=accessibility_score,
            visual_score=visual_score,
            responsive_score=responsive_score,
            overall_score=overall_score,
            config=self.config,
            screenshots=screenshots,
        )

    async def _run_accessibility_tests(self, url: str) -> List[UnifiedTestResult]:
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
                    severity=self._map_severity(violation.severity),
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
                    severity=self._map_severity(issue.severity),
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
                    severity=self._map_severity(issue.severity),
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
                    severity=self._map_severity(violation.severity),
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

    async def _run_visual_tests(self, url: str) -> tuple[List[UnifiedTestResult], dict]:
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
                    severity=self._map_severity(issue.severity),
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
                    severity=self._map_severity(issue.severity),
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

    async def _run_responsive_tests(self, url: str) -> tuple[List[UnifiedTestResult], dict]:
        """Run all responsive tests."""
        results = []
        screenshots = {}

        try:
            breakpoints = BreakpointTester(output_directory=str(self.output_dir / "breakpoints"))
            bp_report = await breakpoints.test(url, capture_screenshots=self.config.capture_screenshots)

            for result in bp_report.results:
                for issue in result.issues:
                    results.append(UnifiedTestResult(
                        category=TestCategory.RESPONSIVE,
                        test_name=f"Breakpoint: {result.breakpoint.name}",
                        passed=False,
                        severity=self._map_severity(issue.severity),
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
                    severity=self._map_severity(issue.severity),
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
                    severity=self._map_severity(issue.severity),
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
                    severity=self._map_severity(issue.severity),
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

    def _map_severity(self, severity_str: str) -> TestSeverity:
        """Map string severity to TestSeverity enum."""
        mapping = {
            "critical": TestSeverity.CRITICAL,
            "serious": TestSeverity.SERIOUS,
            "moderate": TestSeverity.MODERATE,
            "minor": TestSeverity.MINOR,
        }
        return mapping.get(severity_str.lower(), TestSeverity.MODERATE)

    def _filter_by_severity(
        self,
        results: List[UnifiedTestResult],
        min_severity: TestSeverity
    ) -> List[UnifiedTestResult]:
        """Filter results by minimum severity."""
        severity_order = [
            TestSeverity.CRITICAL,
            TestSeverity.SERIOUS,
            TestSeverity.MODERATE,
            TestSeverity.MINOR,
        ]
        min_index = severity_order.index(min_severity)
        allowed = set(severity_order[:min_index + 1])

        filtered = []
        for result in results:
            if result.passed:
                filtered.append(result)
            elif result.severity in allowed:
                filtered.append(result)

        return filtered

    def _calculate_category_score(self, results: List[UnifiedTestResult]) -> float:
        """Calculate score for a category."""
        if not results:
            return 100.0

        total = len(results)
        passed = len([r for r in results if r.passed])

        severity_penalties = {
            TestSeverity.CRITICAL: 20,
            TestSeverity.SERIOUS: 10,
            TestSeverity.MODERATE: 5,
            TestSeverity.MINOR: 2,
        }

        score = 100.0
        for result in results:
            if not result.passed and result.severity:
                penalty = severity_penalties.get(result.severity, 5)
                score -= penalty

        return max(0, min(100, score))
