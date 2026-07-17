"""
Freya Page Load Analyzer

Analyzes page load timing using the Navigation Timing API and
Performance Observer for Core Web Vitals.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Protocol, cast, runtime_checkable

from playwright.async_api import Page, async_playwright

from Asgard.Freya.Performance.models.performance_models import (
    NavigationTiming,
    PageLoadMetrics,
    PerformanceConfig,
    PerformanceGrade,
    PerformanceIssue,
    PerformanceReport,
)
from Asgard.Freya.Performance.models._budget_models import default_budget_for
from Asgard.Freya.Performance.services._archetype_detector import (
    PAGE_SIGNALS_JS,
    detect_archetype,
)
from Asgard.Freya.Performance.services.budget_evaluator import (
    budget_evaluations_to_issues,
    collect_metric_values,
    evaluate_budget,
)
from Asgard.Freya.Performance.services.performance_delta import apply_delta_snapshot
from Asgard.Freya.Performance.services._page_load_helpers import (
    build_metrics,
    identify_issues,
    calculate_score,
    calculate_lcp_score,
    calculate_fid_score,
    calculate_cls_score,
    score_to_grade,
)


@runtime_checkable
class IBrowserProvider(Protocol):
    """
    Abstract interface for browser session management.

    Decouples PageLoadAnalyzer from the concrete Playwright driver (DIP),
    allowing injection of alternative drivers (Selenium, DevTools, test doubles)
    without modifying the analyzer logic.
    """

    async def fetch_page(self, url: str, config: PerformanceConfig) -> Page:
        """
        Navigate to url and return an open Playwright-compatible Page.

        The caller is responsible for managing the lifecycle of any
        browser/context resources created here.
        """
        ...

    async def close(self) -> None:
        """Release any resources held by this provider."""
        ...


class PlaywrightBrowserProvider:
    """
    IBrowserProvider implementation backed by Playwright chromium.

    All Playwright bootstrap logic (async_playwright, browser.launch,
    new_context) is contained here, keeping PageLoadAnalyzer free from
    direct Playwright coupling.
    """

    def __init__(self) -> None:
        self._playwright_ctx = None
        self._browser = None
        self._context = None

    async def fetch_page(self, url: str, config: PerformanceConfig) -> Page:
        """Launch a headless Chromium browser and navigate to the given URL."""
        self._playwright_ctx = await async_playwright().start()
        self._browser = await self._playwright_ctx.chromium.launch(headless=True)
        self._context = await self._browser.new_context()
        page = await self._context.new_page()

        # CPU throttling for TBT measurement (CDP; Chromium only —
        # silently skipped on engines without CDP support).
        if config.cpu_throttle and config.cpu_throttle > 1.0:
            try:
                cdp = await self._context.new_cdp_session(page)
                await cdp.send(
                    "Emulation.setCPUThrottlingRate",
                    {"rate": config.cpu_throttle},
                )
            except Exception:
                pass

        if config.wait_for_network_idle:
            await page.goto(
                url,
                wait_until="networkidle",
                timeout=config.network_idle_timeout + 30000,
            )
        else:
            await page.goto(url, wait_until="load", timeout=30000)

        return page

    async def close(self) -> None:
        """Close the browser and Playwright instance."""
        if self._browser is not None:
            await self._browser.close()
            self._browser = None
        if self._playwright_ctx is not None:
            await self._playwright_ctx.stop()
            self._playwright_ctx = None


class PageLoadAnalyzer:
    """
    Analyzes page load timing and Core Web Vitals.

    Uses a IBrowserProvider to load pages and extract performance metrics
    from the Navigation Timing API and Performance Observer.
    """

    def __init__(
        self,
        config: Optional[PerformanceConfig] = None,
        browser_provider: Optional[IBrowserProvider] = None,
    ):
        """
        Initialize the page load analyzer.

        Args:
            config: Performance configuration.
            browser_provider: Browser session provider. Defaults to
                PlaywrightBrowserProvider. Inject an alternative to swap
                the underlying driver or use a test double (DIP).
        """
        self.config = config or PerformanceConfig()
        self._browser_provider: IBrowserProvider = (
            browser_provider if browser_provider is not None else PlaywrightBrowserProvider()
        )
        self._last_page_signals: Optional[Dict[str, Any]] = None

    async def analyze(self, url: str) -> PageLoadMetrics:
        """
        Analyze page load timing for a URL.

        Args:
            url: URL to analyze

        Returns:
            PageLoadMetrics with timing information
        """
        provider = self._browser_provider
        try:
            page = await provider.fetch_page(url, self.config)
            nav_timing = await self._extract_navigation_timing(page)
            web_vitals = await self._extract_web_vitals(page)
            self._last_page_signals = await self._extract_page_signals(page)
            metrics = build_metrics(url, nav_timing, web_vitals)
            return metrics
        finally:
            await provider.close()

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
        self._last_page_signals = await self._extract_page_signals(page)
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

        # Route archetype: explicit config wins; heuristic fallback.
        if self.config.archetype is not None:
            archetype = self.config.archetype
            archetype_reason = (
                f"archetype: {archetype.value} (explicit — set in configuration)"
            )
        else:
            archetype, archetype_reason = detect_archetype(
                self._last_page_signals or {}
            )

        # Budget evaluation over lab-proxy metrics (Plan 03).
        budget = default_budget_for(archetype)
        values = collect_metric_values(metrics=metrics)
        evaluations = evaluate_budget(values, budget)
        issues.extend(budget_evaluations_to_issues(evaluations, archetype.value))

        score = calculate_score(metrics, evaluations)
        grade = score_to_grade(score)

        report = PerformanceReport(
            url=url,
            performance_score=score,
            performance_grade=grade,
            page_load_metrics=metrics,
            lcp_score=calculate_lcp_score(metrics),
            fid_score=None,  # FID deprecated: no longer graded (FID->INP)
            cls_score=calculate_cls_score(metrics),
            archetype=archetype,
            archetype_reason=archetype_reason,
            budget_evaluations=evaluations,
            issues=issues,
            critical_count=sum(1 for i in issues if i.severity == "critical"),
            warning_count=sum(
                1 for i in issues if i.severity in ("warning", "serious")
            ),
        )

        if self.config.baseline_path:
            try:
                report.metric_deltas = apply_delta_snapshot(
                    report, self.config.baseline_path
                )
            except Exception:
                report.metric_deltas = {}

        report.analysis_duration_ms = (
            datetime.now() - start_time
        ).total_seconds() * 1000
        return report

    async def _extract_page_signals(self, page: Page) -> Optional[Dict[str, Any]]:
        """Extract archetype-detection signals from the loaded page."""
        try:
            return cast(
                Optional[Dict[str, Any]],
                await page.evaluate(PAGE_SIGNALS_JS),
            )
        except Exception:
            return None

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

                    // Long tasks for TBT (buffered observer; the
                    // networkidle wait approximates interactive-settle)
                    try {
                        const longTasks = [];
                        const observer = new PerformanceObserver(() => {});
                        observer.observe({type: 'longtask', buffered: true});
                        for (const entry of observer.takeRecords()) {
                            longTasks.push({
                                start: entry.startTime,
                                duration: entry.duration,
                            });
                        }
                        observer.disconnect();
                        vitals.long_tasks = longTasks;
                    } catch (e) {
                        // longtask observation unsupported: leave unset
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
