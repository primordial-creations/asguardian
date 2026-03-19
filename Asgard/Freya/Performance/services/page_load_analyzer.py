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
                # Navigate to the page
                if self.config.wait_for_network_idle:
                    await page.goto(
                        url,
                        wait_until="networkidle",
                        timeout=self.config.network_idle_timeout + 30000,
                    )
                else:
                    await page.goto(url, wait_until="load", timeout=30000)

                # Extract navigation timing
                nav_timing = await self._extract_navigation_timing(page)

                # Extract Core Web Vitals if available
                web_vitals = await self._extract_web_vitals(page)

                # Build metrics
                metrics = self._build_metrics(url, nav_timing, web_vitals)

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
        return self._build_metrics(url, nav_timing, web_vitals)

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
        issues = self._identify_issues(metrics)

        # Calculate score
        score = self._calculate_score(metrics)
        grade = self._score_to_grade(score)

        analysis_duration = (datetime.now() - start_time).total_seconds() * 1000

        return PerformanceReport(
            url=url,
            performance_score=score,
            performance_grade=grade,
            page_load_metrics=metrics,
            lcp_score=self._calculate_lcp_score(metrics),
            fid_score=self._calculate_fid_score(metrics),
            cls_score=self._calculate_cls_score(metrics),
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

                    // Try to get LCP from PerformanceObserver entries
                    const lcpEntries = performance.getEntriesByType('largest-contentful-paint');
                    if (lcpEntries && lcpEntries.length > 0) {
                        vitals.lcp = lcpEntries[lcpEntries.length - 1].startTime;
                    }

                    // Get FCP from paint entries
                    const paintEntries = performance.getEntriesByType('paint');
                    for (const entry of paintEntries) {
                        if (entry.name === 'first-contentful-paint') {
                            vitals.fcp = entry.startTime;
                        }
                    }

                    // CLS is harder to get, estimate from layout-shift entries
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

    def _build_metrics(
        self,
        url: str,
        nav_timing: NavigationTiming,
        web_vitals: dict,
    ) -> PageLoadMetrics:
        """Build PageLoadMetrics from raw timing data."""
        # Calculate derived metrics
        dns_lookup = nav_timing.domain_lookup_end - nav_timing.domain_lookup_start
        tcp_connection = nav_timing.connect_end - nav_timing.connect_start
        ssl_handshake = (
            nav_timing.connect_end - nav_timing.secure_connection_start
            if nav_timing.secure_connection_start > 0 else 0
        )
        ttfb = nav_timing.response_start
        content_download = nav_timing.response_end - nav_timing.response_start
        dom_interactive = nav_timing.dom_interactive
        dom_content_loaded = nav_timing.dom_content_loaded_event_end
        page_load = nav_timing.load_event_end

        return PageLoadMetrics(
            url=url,
            dns_lookup=max(0, dns_lookup),
            tcp_connection=max(0, tcp_connection),
            ssl_handshake=max(0, ssl_handshake),
            time_to_first_byte=max(0, ttfb),
            content_download=max(0, content_download),
            dom_interactive=max(0, dom_interactive),
            dom_content_loaded=max(0, dom_content_loaded),
            page_load=max(0, page_load),
            largest_contentful_paint=web_vitals.get("lcp"),
            first_contentful_paint=web_vitals.get("fcp"),
            cumulative_layout_shift=web_vitals.get("cls"),
            navigation_timing=nav_timing,
        )

    def _identify_issues(self, metrics: PageLoadMetrics) -> List[PerformanceIssue]:
        """Identify performance issues from metrics."""
        issues = []

        # TTFB check
        if metrics.time_to_first_byte > self.config.ttfb_threshold:
            severity = (
                "critical" if metrics.time_to_first_byte > self.config.ttfb_threshold * 2
                else "warning"
            )
            issues.append(PerformanceIssue(
                issue_type="slow_ttfb",
                severity=severity,
                metric_name="Time to First Byte",
                actual_value=metrics.time_to_first_byte,
                threshold_value=self.config.ttfb_threshold,
                description=(
                    f"Time to First Byte is {metrics.time_to_first_byte:.0f}ms, "
                    f"exceeds threshold of {self.config.ttfb_threshold:.0f}ms"
                ),
                suggested_fix=(
                    "Optimize server response time, use CDN, enable caching, "
                    "or reduce server processing time"
                ),
            ))

        # LCP check
        if metrics.largest_contentful_paint is not None:
            if metrics.largest_contentful_paint > self.config.lcp_threshold:
                severity = (
                    "critical" if metrics.largest_contentful_paint > 4000
                    else "warning"
                )
                issues.append(PerformanceIssue(
                    issue_type="slow_lcp",
                    severity=severity,
                    metric_name="Largest Contentful Paint",
                    actual_value=metrics.largest_contentful_paint,
                    threshold_value=self.config.lcp_threshold,
                    description=(
                        f"LCP is {metrics.largest_contentful_paint:.0f}ms, "
                        f"exceeds threshold of {self.config.lcp_threshold:.0f}ms"
                    ),
                    suggested_fix=(
                        "Optimize largest element loading, preload critical assets, "
                        "use efficient image formats, reduce render-blocking resources"
                    ),
                ))

        # FCP check
        if metrics.first_contentful_paint is not None:
            if metrics.first_contentful_paint > self.config.fcp_threshold:
                issues.append(PerformanceIssue(
                    issue_type="slow_fcp",
                    severity="warning",
                    metric_name="First Contentful Paint",
                    actual_value=metrics.first_contentful_paint,
                    threshold_value=self.config.fcp_threshold,
                    description=(
                        f"FCP is {metrics.first_contentful_paint:.0f}ms, "
                        f"exceeds threshold of {self.config.fcp_threshold:.0f}ms"
                    ),
                    suggested_fix=(
                        "Eliminate render-blocking resources, inline critical CSS, "
                        "defer non-critical JavaScript"
                    ),
                ))

        # CLS check
        if metrics.cumulative_layout_shift is not None:
            if metrics.cumulative_layout_shift > self.config.cls_threshold:
                severity = (
                    "critical" if metrics.cumulative_layout_shift > 0.25
                    else "warning"
                )
                issues.append(PerformanceIssue(
                    issue_type="high_cls",
                    severity=severity,
                    metric_name="Cumulative Layout Shift",
                    actual_value=metrics.cumulative_layout_shift,
                    threshold_value=self.config.cls_threshold,
                    description=(
                        f"CLS is {metrics.cumulative_layout_shift:.3f}, "
                        f"exceeds threshold of {self.config.cls_threshold:.2f}"
                    ),
                    suggested_fix=(
                        "Set explicit dimensions on images and embeds, "
                        "avoid inserting content above existing content, "
                        "use CSS transform instead of properties that trigger layout"
                    ),
                ))

        # Page load time check
        if metrics.page_load > 5000:
            severity = "critical" if metrics.page_load > 10000 else "warning"
            issues.append(PerformanceIssue(
                issue_type="slow_page_load",
                severity=severity,
                metric_name="Total Page Load Time",
                actual_value=metrics.page_load,
                threshold_value=5000,
                description=f"Total page load time is {metrics.page_load:.0f}ms",
                suggested_fix=(
                    "Reduce resource count, optimize critical rendering path, "
                    "enable compression, leverage browser caching"
                ),
            ))

        return issues

    def _calculate_score(self, metrics: PageLoadMetrics) -> float:
        """Calculate overall performance score (0-100)."""
        scores = []

        # TTFB score
        ttfb_score = max(0, 100 - (metrics.time_to_first_byte / 10))
        scores.append(ttfb_score * 0.15)

        # LCP score
        if metrics.largest_contentful_paint is not None:
            lcp_score = max(0, 100 - (metrics.largest_contentful_paint / 50))
            scores.append(lcp_score * 0.25)

        # FCP score
        if metrics.first_contentful_paint is not None:
            fcp_score = max(0, 100 - (metrics.first_contentful_paint / 36))
            scores.append(fcp_score * 0.15)

        # CLS score
        if metrics.cumulative_layout_shift is not None:
            cls_score = max(0, 100 - (metrics.cumulative_layout_shift * 400))
            scores.append(cls_score * 0.25)

        # Page load score
        load_score = max(0, 100 - (metrics.page_load / 100))
        scores.append(load_score * 0.20)

        return min(100, sum(scores) / (len(scores) / 5) if scores else 0)

    def _calculate_lcp_score(self, metrics: PageLoadMetrics) -> Optional[float]:
        """Calculate LCP score (0-100)."""
        lcp = cast(Optional[float], metrics.largest_contentful_paint)
        if lcp is None:
            return None
        if lcp <= 2500:
            return 100
        elif lcp <= 4000:
            return 50 + 50 * (4000 - lcp) / 1500
        else:
            return max(0, 50 * (8000 - lcp) / 4000)

    def _calculate_fid_score(self, metrics: PageLoadMetrics) -> Optional[float]:
        """Calculate FID score (0-100)."""
        fid = cast(Optional[float], metrics.first_input_delay)
        if fid is None:
            return None
        if fid <= 100:
            return 100
        elif fid <= 300:
            return 50 + 50 * (300 - fid) / 200
        else:
            return max(0, 50 * (600 - fid) / 300)

    def _calculate_cls_score(self, metrics: PageLoadMetrics) -> Optional[float]:
        """Calculate CLS score (0-100)."""
        cls = cast(Optional[float], metrics.cumulative_layout_shift)
        if cls is None:
            return None
        if cls <= 0.1:
            return 100
        elif cls <= 0.25:
            return 50 + 50 * (0.25 - cls) / 0.15
        else:
            return max(0, 50 * (0.5 - cls) / 0.25)

    def _score_to_grade(self, score: float) -> PerformanceGrade:
        """Convert score to grade."""
        if score >= 90:
            return PerformanceGrade.EXCELLENT
        elif score >= 70:
            return PerformanceGrade.GOOD
        elif score >= 50:
            return PerformanceGrade.NEEDS_IMPROVEMENT
        return PerformanceGrade.POOR
