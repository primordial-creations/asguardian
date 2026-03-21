"""
Freya Resource Timing Analyzer helper functions.

Helper functions extracted from resource_timing_analyzer.py.
"""

from typing import List

from Asgard.Freya.Performance.models.performance_models import (
    PerformanceConfig,
    PerformanceIssue,
    ResourceTiming,
    ResourceTimingReport,
    ResourceType,
)

LARGE_RESOURCE_THRESHOLD = 100 * 1024  # 100KB
SLOW_RESOURCE_THRESHOLD = 500  # 500ms


def parse_resource(raw: dict) -> ResourceTiming:
    """Parse raw resource data into ResourceTiming model."""
    name = raw.get("name", "")
    initiator = raw.get("initiatorType", "other")

    resource_type = get_resource_type(name, initiator)

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


def get_resource_type(url: str, initiator: str) -> ResourceType:
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


def build_report(url: str, resources: List[ResourceTiming]) -> ResourceTimingReport:
    """Build ResourceTimingReport from parsed resources."""
    script_count = sum(1 for r in resources if r.resource_type == ResourceType.SCRIPT)
    stylesheet_count = sum(
        1 for r in resources if r.resource_type == ResourceType.STYLESHEET
    )
    image_count = sum(1 for r in resources if r.resource_type == ResourceType.IMAGE)
    font_count = sum(1 for r in resources if r.resource_type == ResourceType.FONT)
    other_count = len(resources) - script_count - stylesheet_count - image_count - font_count

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

    total_transfer_size = sum(r.transfer_size for r in resources)
    total_load_time = max((r.start_time + r.duration for r in resources), default=0)

    render_blocking = [r for r in resources if r.is_blocking]
    uncached = [r for r in resources if not r.from_cache]
    large_resources = [
        r.url for r in resources if r.transfer_size > LARGE_RESOURCE_THRESHOLD
    ]
    slow_resources = [
        r.url for r in resources if r.duration > SLOW_RESOURCE_THRESHOLD
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


def get_issues(report: ResourceTimingReport, config: PerformanceConfig) -> List[PerformanceIssue]:
    """Identify performance issues from resource timing report."""
    issues = []

    if report.total_resources > config.max_requests:
        issues.append(PerformanceIssue(
            issue_type="too_many_requests",
            severity="warning",
            metric_name="Total Requests",
            actual_value=report.total_resources,
            threshold_value=config.max_requests,
            description=(
                f"Page makes {report.total_resources} requests, "
                f"exceeds threshold of {config.max_requests}"
            ),
            suggested_fix=(
                "Bundle JavaScript and CSS files, use image sprites, "
                "implement lazy loading"
            ),
        ))

    total_size_kb = report.total_size_kb
    if total_size_kb > config.max_total_size_kb:
        issues.append(PerformanceIssue(
            issue_type="large_page_size",
            severity="warning",
            metric_name="Total Page Size",
            actual_value=total_size_kb,
            threshold_value=config.max_total_size_kb,
            description=(
                f"Total page size is {total_size_kb:.0f}KB, "
                f"exceeds threshold of {config.max_total_size_kb}KB"
            ),
            suggested_fix=(
                "Compress images, minify CSS/JS, enable gzip compression, "
                "remove unused code"
            ),
        ))

    if report.render_blocking_count > config.max_render_blocking:
        issues.append(PerformanceIssue(
            issue_type="render_blocking",
            severity="warning",
            metric_name="Render-Blocking Resources",
            actual_value=report.render_blocking_count,
            threshold_value=config.max_render_blocking,
            description=(
                f"Page has {report.render_blocking_count} render-blocking resources"
            ),
            suggested_fix=(
                "Defer non-critical JavaScript, inline critical CSS, "
                "use async/defer attributes"
            ),
        ))

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
                threshold_value=config.max_resource_size_kb,
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
                threshold_value=SLOW_RESOURCE_THRESHOLD,
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


def get_optimization_suggestions(report: ResourceTimingReport) -> List[str]:
    """Get actionable optimization suggestions."""
    suggestions = []

    if report.total_size_kb > 1000:
        suggestions.append(
            "Enable gzip/brotli compression on your server to reduce transfer sizes"
        )

    if report.image_size > 500 * 1024:
        suggestions.append(
            "Optimize images: consider WebP format, resize to display size, "
            "use responsive images"
        )

    if report.script_size > 500 * 1024:
        suggestions.append(
            "Reduce JavaScript bundle size: code splitting, tree shaking, "
            "lazy loading modules"
        )

    if report.font_count > 3:
        suggestions.append(
            "Reduce font variants: limit font weights and styles, "
            "use font-display: swap"
        )

    if report.uncached_count > 10:
        suggestions.append(
            "Configure cache headers for static assets "
            "(Cache-Control, ETag, Last-Modified)"
        )

    if report.render_blocking_count > 3:
        suggestions.append(
            "Reduce render-blocking resources: "
            "inline critical CSS, defer non-critical scripts"
        )

    if report.total_resources > 50:
        suggestions.append(
            "Reduce HTTP requests: bundle files, use image sprites, "
            "implement HTTP/2 multiplexing"
        )

    return suggestions
