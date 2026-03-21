"""
Freya Resource Timing Analyzer

Analyzes resource loading performance using the Resource Timing API.
Identifies slow resources, render-blocking content, and optimization opportunities.
"""

from typing import Any, List, Optional, cast

from playwright.async_api import Page, async_playwright

from Asgard.Freya.Performance.models.performance_models import (
    PerformanceConfig,
    PerformanceIssue,
    ResourceTiming,
    ResourceTimingReport,
    ResourceType,
)
from Asgard.Freya.Performance.services._resource_timing_helpers import (
    LARGE_RESOURCE_THRESHOLD,
    SLOW_RESOURCE_THRESHOLD,
    build_report,
    get_issues,
    get_optimization_suggestions,
    get_resource_type,
    parse_resource,
)


class ResourceTimingAnalyzer:
    """
    Analyzes resource loading performance.

    Uses Playwright to load pages and extract resource timing data
    from the Resource Timing API.
    """

    LARGE_RESOURCE_THRESHOLD = LARGE_RESOURCE_THRESHOLD
    SLOW_RESOURCE_THRESHOLD = SLOW_RESOURCE_THRESHOLD

    def __init__(self, config: Optional[PerformanceConfig] = None):
        """
        Initialize the resource timing analyzer.

        Args:
            config: Performance configuration
        """
        self.config = config or PerformanceConfig()

    async def analyze(self, url: str) -> ResourceTimingReport:
        """
        Analyze resource timing for a URL.

        Args:
            url: URL to analyze

        Returns:
            ResourceTimingReport with resource timing information
        """
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()

            try:
                if self.config.wait_for_network_idle:
                    await page.goto(
                        url,
                        wait_until="networkidle",
                        timeout=self.config.network_idle_timeout + 30000,
                    )
                else:
                    await page.goto(url, wait_until="load", timeout=30000)

                return await self.analyze_page(page, url)

            finally:
                await browser.close()

    async def analyze_page(self, page: Page, url: str) -> ResourceTimingReport:
        """
        Analyze resources for a page that is already loaded.

        Args:
            page: Playwright Page object
            url: URL of the page

        Returns:
            ResourceTimingReport with resource timing information
        """
        raw_resources = await self._extract_resource_timing(page)
        resources = [parse_resource(r) for r in raw_resources]
        return build_report(url, resources)

    async def _extract_resource_timing(self, page: Page) -> List[dict]:
        """Extract resource timing entries from the page."""
        return cast(List[dict], await page.evaluate("""
            () => {
                const entries = performance.getEntriesByType('resource');
                return entries.map(entry => ({
                    name: entry.name,
                    initiatorType: entry.initiatorType,
                    startTime: entry.startTime,
                    domainLookupStart: entry.domainLookupStart,
                    domainLookupEnd: entry.domainLookupEnd,
                    connectStart: entry.connectStart,
                    connectEnd: entry.connectEnd,
                    secureConnectionStart: entry.secureConnectionStart,
                    requestStart: entry.requestStart,
                    responseStart: entry.responseStart,
                    responseEnd: entry.responseEnd,
                    duration: entry.duration,
                    transferSize: entry.transferSize || 0,
                    encodedBodySize: entry.encodedBodySize || 0,
                    decodedBodySize: entry.decodedBodySize || 0,
                }));
            }
        """))

    def _parse_resource(self, raw: dict) -> ResourceTiming:
        """Parse raw resource data into ResourceTiming model."""
        return parse_resource(raw)

    def _get_resource_type(self, url: str, initiator: str) -> ResourceType:
        """Determine resource type from URL and initiator."""
        return get_resource_type(url, initiator)

    def _build_report(self, url: str, resources: List[ResourceTiming]) -> ResourceTimingReport:
        """Build ResourceTimingReport from parsed resources."""
        return build_report(url, resources)

    def get_issues(self, report: ResourceTimingReport) -> List[PerformanceIssue]:
        """
        Identify performance issues from resource timing report.

        Args:
            report: ResourceTimingReport to analyze

        Returns:
            List of PerformanceIssue objects
        """
        return get_issues(report, self.config)

    def get_optimization_suggestions(self, report: ResourceTimingReport) -> List[str]:
        """
        Get actionable optimization suggestions.

        Args:
            report: ResourceTimingReport to analyze

        Returns:
            List of optimization suggestion strings
        """
        return get_optimization_suggestions(report)
