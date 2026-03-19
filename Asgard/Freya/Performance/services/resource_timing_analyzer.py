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


class ResourceTimingAnalyzer:
    """
    Analyzes resource loading performance.

    Uses Playwright to load pages and extract resource timing data
    from the Resource Timing API.
    """

    # Threshold for "large" resources in bytes
    LARGE_RESOURCE_THRESHOLD = 100 * 1024  # 100KB

    # Threshold for "slow" resources in milliseconds
    SLOW_RESOURCE_THRESHOLD = 500  # 500ms

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
                # Navigate to the page
                if self.config.wait_for_network_idle:
                    await page.goto(
                        url,
                        wait_until="networkidle",
                        timeout=self.config.network_idle_timeout + 30000,
                    )
                else:
                    await page.goto(url, wait_until="load", timeout=30000)

                # Extract resource timing
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
        resources = [self._parse_resource(r) for r in raw_resources]

        return self._build_report(url, resources)

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
        name = raw.get("name", "")
        initiator = raw.get("initiatorType", "other")

        # Determine resource type
        resource_type = self._get_resource_type(name, initiator)

        # Calculate timing phases
        dns_lookup = max(
            0, raw.get("domainLookupEnd", 0) - raw.get("domainLookupStart", 0)
        )
        tcp_connection = max(
            0, raw.get("connectEnd", 0) - raw.get("connectStart", 0)
        )
        ssl_handshake = 0
        if raw.get("secureConnectionStart", 0) > 0:
            ssl_handshake = max(
                0, raw.get("connectEnd", 0) - raw.get("secureConnectionStart", 0)
            )
        request_time = max(
            0, raw.get("responseStart", 0) - raw.get("requestStart", 0)
        )
        response_time = max(
            0, raw.get("responseEnd", 0) - raw.get("responseStart", 0)
        )

        # Determine if from cache
        from_cache = raw.get("transferSize", 0) == 0 and raw.get("decodedBodySize", 0) > 0

        return ResourceTiming(
            url=name,
            resource_type=resource_type,
            name=name.split("/")[-1].split("?")[0] or name,
            start_time=raw.get("startTime", 0),
            dns_lookup=dns_lookup,
            tcp_connection=tcp_connection,
            ssl_handshake=ssl_handshake,
            request_time=request_time,
            response_time=response_time,
            duration=raw.get("duration", 0),
            transfer_size=raw.get("transferSize", 0),
            encoded_body_size=raw.get("encodedBodySize", 0),
            decoded_body_size=raw.get("decodedBodySize", 0),
            from_cache=from_cache,
            initiator_type=initiator,
        )

    def _get_resource_type(self, url: str, initiator: str) -> ResourceType:
        """Determine resource type from URL and initiator."""
        url_lower = url.lower()

        if initiator == "script" or url_lower.endswith(".js"):
            return ResourceType.SCRIPT
        elif initiator == "link" and ".css" in url_lower:
            return ResourceType.STYLESHEET
        elif initiator == "css" or url_lower.endswith(".css"):
            return ResourceType.STYLESHEET
        elif initiator == "img" or any(
            url_lower.endswith(ext)
            for ext in [".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico"]
        ):
            return ResourceType.IMAGE
        elif any(
            url_lower.endswith(ext)
            for ext in [".woff", ".woff2", ".ttf", ".otf", ".eot"]
        ):
            return ResourceType.FONT
        elif initiator == "fetch":
            return ResourceType.FETCH
        elif initiator == "xmlhttprequest":
            return ResourceType.XHR
        elif any(
            url_lower.endswith(ext) for ext in [".mp4", ".webm", ".mp3", ".wav"]
        ):
            return ResourceType.MEDIA
        elif initiator == "document":
            return ResourceType.DOCUMENT

        return ResourceType.OTHER

    def _build_report(self, url: str, resources: List[ResourceTiming]) -> ResourceTimingReport:
        """Build ResourceTimingReport from parsed resources."""
        # Count by type
        script_count = sum(1 for r in resources if r.resource_type == ResourceType.SCRIPT)
        stylesheet_count = sum(
            1 for r in resources if r.resource_type == ResourceType.STYLESHEET
        )
        image_count = sum(1 for r in resources if r.resource_type == ResourceType.IMAGE)
        font_count = sum(1 for r in resources if r.resource_type == ResourceType.FONT)
        other_count = len(resources) - script_count - stylesheet_count - image_count - font_count

        # Size by type
        script_size = sum(
            r.transfer_size for r in resources if r.resource_type == ResourceType.SCRIPT
        )
        stylesheet_size = sum(
            r.transfer_size for r in resources if r.resource_type == ResourceType.STYLESHEET
        )
        image_size = sum(
            r.transfer_size for r in resources if r.resource_type == ResourceType.IMAGE
        )
        font_size = sum(
            r.transfer_size for r in resources if r.resource_type == ResourceType.FONT
        )
        other_size = sum(
            r.transfer_size
            for r in resources
            if r.resource_type
            not in [
                ResourceType.SCRIPT,
                ResourceType.STYLESHEET,
                ResourceType.IMAGE,
                ResourceType.FONT,
            ]
        )

        # Totals
        total_transfer_size = sum(r.transfer_size for r in resources)
        total_load_time = max((r.start_time + r.duration for r in resources), default=0)

        # Optimization opportunities
        render_blocking = [r for r in resources if r.is_blocking]
        uncached = [r for r in resources if not r.from_cache]
        large_resources = [
            r.url for r in resources if r.transfer_size > self.LARGE_RESOURCE_THRESHOLD
        ]
        slow_resources = [
            r.url for r in resources if r.duration > self.SLOW_RESOURCE_THRESHOLD
        ]

        return ResourceTimingReport(
            url=url,
            resources=resources,
            total_resources=len(resources),
            total_transfer_size=total_transfer_size,
            total_load_time=total_load_time,
            script_count=script_count,
            stylesheet_count=stylesheet_count,
            image_count=image_count,
            font_count=font_count,
            other_count=other_count,
            script_size=script_size,
            stylesheet_size=stylesheet_size,
            image_size=image_size,
            font_size=font_size,
            other_size=other_size,
            render_blocking_count=len(render_blocking),
            uncached_count=len(uncached),
            large_resources=large_resources,
            slow_resources=slow_resources,
        )

    def get_issues(self, report: ResourceTimingReport) -> List[PerformanceIssue]:
        """
        Identify performance issues from resource timing report.

        Args:
            report: ResourceTimingReport to analyze

        Returns:
            List of PerformanceIssue objects
        """
        issues = []

        # Too many requests
        if report.total_resources > self.config.max_requests:
            issues.append(PerformanceIssue(
                issue_type="too_many_requests",
                severity="warning",
                metric_name="Total Requests",
                actual_value=report.total_resources,
                threshold_value=self.config.max_requests,
                description=(
                    f"Page makes {report.total_resources} requests, "
                    f"exceeds threshold of {self.config.max_requests}"
                ),
                suggested_fix=(
                    "Bundle JavaScript and CSS files, use image sprites, "
                    "implement lazy loading"
                ),
            ))

        # Too large total size
        total_size_kb = report.total_size_kb
        if total_size_kb > self.config.max_total_size_kb:
            issues.append(PerformanceIssue(
                issue_type="large_page_size",
                severity="warning",
                metric_name="Total Page Size",
                actual_value=total_size_kb,
                threshold_value=self.config.max_total_size_kb,
                description=(
                    f"Total page size is {total_size_kb:.0f}KB, "
                    f"exceeds threshold of {self.config.max_total_size_kb}KB"
                ),
                suggested_fix=(
                    "Compress images, minify CSS/JS, enable gzip compression, "
                    "remove unused code"
                ),
            ))

        # Too many render-blocking resources
        if report.render_blocking_count > self.config.max_render_blocking:
            issues.append(PerformanceIssue(
                issue_type="render_blocking",
                severity="warning",
                metric_name="Render-Blocking Resources",
                actual_value=report.render_blocking_count,
                threshold_value=self.config.max_render_blocking,
                description=(
                    f"Page has {report.render_blocking_count} render-blocking resources"
                ),
                suggested_fix=(
                    "Defer non-critical JavaScript, inline critical CSS, "
                    "use async/defer attributes"
                ),
            ))

        # Large resources
        for resource_url in report.large_resources:
            resource = next(
                (r for r in report.resources if r.url == resource_url), None
            )
            if resource:
                issues.append(PerformanceIssue(
                    issue_type="large_resource",
                    severity="info",
                    metric_name="Resource Size",
                    actual_value=resource.transfer_size / 1024,
                    threshold_value=self.config.max_resource_size_kb,
                    description=(
                        f"Resource is {resource.transfer_size / 1024:.0f}KB: "
                        f"{resource.name}"
                    ),
                    suggested_fix=(
                        "Compress or optimize this resource, "
                        "consider lazy loading if not critical"
                    ),
                    resource_url=resource_url,
                ))

        # Slow resources
        for resource_url in report.slow_resources:
            resource = next(
                (r for r in report.resources if r.url == resource_url), None
            )
            if resource:
                issues.append(PerformanceIssue(
                    issue_type="slow_resource",
                    severity="info",
                    metric_name="Resource Load Time",
                    actual_value=resource.duration,
                    threshold_value=self.SLOW_RESOURCE_THRESHOLD,
                    description=(
                        f"Resource took {resource.duration:.0f}ms to load: "
                        f"{resource.name}"
                    ),
                    suggested_fix=(
                        "Check server response time, enable CDN, "
                        "preload critical resources"
                    ),
                    resource_url=resource_url,
                ))

        return issues

    def get_optimization_suggestions(
        self, report: ResourceTimingReport
    ) -> List[str]:
        """
        Get actionable optimization suggestions.

        Args:
            report: ResourceTimingReport to analyze

        Returns:
            List of optimization suggestion strings
        """
        suggestions = []

        # Check for compression
        if report.total_size_kb > 1000:
            suggestions.append(
                "Enable gzip/brotli compression on your server to reduce transfer sizes"
            )

        # Check image optimization
        if report.image_size > 500 * 1024:
            suggestions.append(
                "Optimize images: consider WebP format, resize to display size, "
                "use responsive images"
            )

        # Check JavaScript size
        if report.script_size > 500 * 1024:
            suggestions.append(
                "Reduce JavaScript bundle size: code splitting, tree shaking, "
                "lazy loading modules"
            )

        # Check font loading
        if report.font_count > 3:
            suggestions.append(
                "Reduce font variants: limit font weights and styles, "
                "use font-display: swap"
            )

        # Check caching
        if report.uncached_count > 10:
            suggestions.append(
                "Configure cache headers for static assets "
                "(Cache-Control, ETag, Last-Modified)"
            )

        # Check render-blocking
        if report.render_blocking_count > 3:
            suggestions.append(
                "Reduce render-blocking resources: "
                "inline critical CSS, defer non-critical scripts"
            )

        # Check request count
        if report.total_resources > 50:
            suggestions.append(
                "Reduce HTTP requests: bundle files, use image sprites, "
                "implement HTTP/2 multiplexing"
            )

        return suggestions
