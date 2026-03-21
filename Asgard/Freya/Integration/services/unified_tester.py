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
from Asgard.Freya.Integration.services._unified_tester_runners import (
    map_severity,
    run_accessibility_tests,
    run_visual_tests,
    run_responsive_tests,
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
            accessibility_results = await run_accessibility_tests(url)

        if run_all or TestCategory.VISUAL in categories:
            visual_results, visual_screenshots = await run_visual_tests(url)
            screenshots.update(visual_screenshots)

        if run_all or TestCategory.RESPONSIVE in categories:
            responsive_results, responsive_screenshots = await run_responsive_tests(
                url, self.output_dir, self.config.capture_screenshots
            )
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

    def _map_severity(self, severity_str: str) -> TestSeverity:
        """Map string severity to TestSeverity enum."""
        return map_severity(severity_str)

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
