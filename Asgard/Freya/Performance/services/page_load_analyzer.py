"""
Freya Page Load Analyzer

Analyzes page load timing using the Navigation Timing API and
Performance Observer for Core Web Vitals.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, cast

from playwright.async_api import Page, async_playwright

from Asgard.Freya.Performance.models.performance_models import (
    NavigationTiming,
    PageLoadMetrics,
    PerformanceConfig,
    PerformanceGrade,
    PerformanceIssue,
    PerformanceReport,
)
from Asgard.Freya.Performance.services._page_load_helpers import (
    build_metrics,
    identify_issues,
    calculate_score,
    calculate_lcp_score,
    calculate_fid_score,
    calculate_cls_score,
    score_to_grade,
)


class PageLoadAnalyzer:
    """
    Analyzes page load timing and Core Web Vitals.

    Uses Playwright to load pages and extract performance metrics
    from the Navigation Timing API and Performance Observer.
    """

    def __init__(self, config: Optional[PerformanceConfig] = None):
        """
        Initialize the page load analyzer.

        Args:
            config: Performance configuration
        """
        self.config = config or PerformanceConfig()

    async def analyze(self, url: str) -> PageLoadMetrics:
        """
        Analyze page load timing for a URL.

        Args:
            url: URL to analyze

        Returns:
            PageLoadMetrics with timing information
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

                nav_timing = await self._extract_navigation_timing(page)
                web_vitals = await self._extract_web_vitals(page)
                metrics = build_metrics(url, nav_timing, web_vitals)

                return metrics

            finally:
                await browser.close()

    async def analyze_page(self, page: Page, url: str) -> PageLoadMetrics:
        """
        Analyze a page that is already loaded.

        Args:
            page: Playwright Page object
            url: URL of the page

        Returns:
            PageLoadMetrics with timing information
        """
        nav_timing = await self._extract_navigation_timing(page)
        web_vitals = await self._extract_web_vitals(page)
        return build_metrics(url, nav_timing, web_vitals)

    async def get_performance_report(self, url: str) -> PerformanceReport:
        """
        Get a full performance report for a URL.

        Args:
            url: URL to analyze

        Returns:
            PerformanceReport with metrics and issues
        """
        start_time = datetime.now()

        metrics = await self.analyze(url)
        issues = identify_issues(metrics, self.config)

        score = calculate_score(metrics)
        grade = score_to_grade(score)

        analysis_duration = (datetime.now() - start_time).total_seconds() * 1000

        return PerformanceReport(
            url=url,
            performance_score=score,
            performance_grade=grade,
            page_load_metrics=metrics,
            lcp_score=calculate_lcp_score(metrics),
            fid_score=calculate_fid_score(metrics),
            cls_score=calculate_cls_score(metrics),
            issues=issues,
            critical_count=sum(1 for i in issues if i.severity == "critical"),
            warning_count=sum(1 for i in issues if i.severity == "warning"),
            analysis_duration_ms=analysis_duration,
        )

    async def _extract_navigation_timing(self, page: Page) -> NavigationTiming:
        """Extract navigation timing from the page."""
        timing_data = await page.evaluate("""
            () => {
                const timing = performance.timing;
                const navStart = timing.navigationStart;
                return {
                    navigation_start: navStart,
                    unload_event_start: timing.unloadEventStart - navStart,
                    unload_event_end: timing.unloadEventEnd - navStart,
                    redirect_start: timing.redirectStart ? timing.redirectStart - navStart : 0,
                    redirect_end: timing.redirectEnd ? timing.redirectEnd - navStart : 0,
                    fetch_start: timing.fetchStart - navStart,
                    domain_lookup_start: timing.domainLookupStart - navStart,
                    domain_lookup_end: timing.domainLookupEnd - navStart,
                    connect_start: timing.connectStart - navStart,
                    connect_end: timing.connectEnd - navStart,
                    secure_connection_start: timing.secureConnectionStart ?
                        timing.secureConnectionStart - navStart : 0,
                    request_start: timing.requestStart - navStart,
                    response_start: timing.responseStart - navStart,
                    response_end: timing.responseEnd - navStart,
                    dom_loading: timing.domLoading - navStart,
                    dom_interactive: timing.domInteractive - navStart,
                    dom_content_loaded_event_start: timing.domContentLoadedEventStart - navStart,
                    dom_content_loaded_event_end: timing.domContentLoadedEventEnd - navStart,
                    dom_complete: timing.domComplete - navStart,
                    load_event_start: timing.loadEventStart - navStart,
                    load_event_end: timing.loadEventEnd - navStart,
                };
            }
        """)

        return NavigationTiming(**timing_data)

    async def _extract_web_vitals(self, page: Page) -> dict:
        """Extract Core Web Vitals from the page."""
        try:
            vitals = await page.evaluate("""
                () => {
                    const vitals = {};

                    const lcpEntries = performance.getEntriesByType('largest-contentful-paint');
                    if (lcpEntries && lcpEntries.length > 0) {
                        vitals.lcp = lcpEntries[lcpEntries.length - 1].startTime;
                    }

                    const paintEntries = performance.getEntriesByType('paint');
                    for (const entry of paintEntries) {
                        if (entry.name === 'first-contentful-paint') {
                            vitals.fcp = entry.startTime;
                        }
                    }

                    const layoutShiftEntries = performance.getEntriesByType('layout-shift');
                    if (layoutShiftEntries && layoutShiftEntries.length > 0) {
                        vitals.cls = layoutShiftEntries.reduce(
                            (sum, entry) => sum + (entry.hadRecentInput ? 0 : entry.value),
                            0
                        );
                    }

                    return vitals;
                }
            """)
            return cast(Dict[Any, Any], vitals)
        except Exception:
            return {}

    def _build_metrics(self, url: str, nav_timing: NavigationTiming, web_vitals: dict) -> PageLoadMetrics:
        """Build PageLoadMetrics from raw timing data."""
        return build_metrics(url, nav_timing, web_vitals)

    def _identify_issues(self, metrics: PageLoadMetrics) -> List[PerformanceIssue]:
        """Identify performance issues from metrics."""
        return identify_issues(metrics, self.config)

    def _calculate_score(self, metrics: PageLoadMetrics) -> float:
        """Calculate overall performance score (0-100)."""
        return calculate_score(metrics)

    def _calculate_lcp_score(self, metrics: PageLoadMetrics) -> Optional[float]:
        """Calculate LCP score (0-100)."""
        return calculate_lcp_score(metrics)

    def _calculate_fid_score(self, metrics: PageLoadMetrics) -> Optional[float]:
        """Calculate FID score (0-100)."""
        return calculate_fid_score(metrics)

    def _calculate_cls_score(self, metrics: PageLoadMetrics) -> Optional[float]:
        """Calculate CLS score (0-100)."""
        return calculate_cls_score(metrics)

    def _score_to_grade(self, score: float) -> PerformanceGrade:
        """Convert score to grade."""
        return score_to_grade(score)
