"""
Freya Page Load Analyzer helper functions.

Helper functions extracted from page_load_analyzer.py.
"""

from typing import List, Optional, cast

from Asgard.Freya.Performance.models.performance_models import (
    PageLoadMetrics,
    NavigationTiming,
    PerformanceConfig,
    PerformanceGrade,
    PerformanceIssue,
)


def build_metrics(
    url: str,
    nav_timing: NavigationTiming,
    web_vitals: dict,
) -> PageLoadMetrics:
    """Build PageLoadMetrics from raw timing data."""
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


def identify_issues(metrics: PageLoadMetrics, config: PerformanceConfig) -> List[PerformanceIssue]:
    """Identify performance issues from metrics."""
    issues = []

    if metrics.time_to_first_byte > config.ttfb_threshold:
        severity = (
            "critical" if metrics.time_to_first_byte > config.ttfb_threshold * 2
            else "warning"
        )
        issues.append(PerformanceIssue(
            issue_type="slow_ttfb",
            severity=severity,
            metric_name="Time to First Byte",
            actual_value=metrics.time_to_first_byte,
            threshold_value=config.ttfb_threshold,
            description=(
                f"Time to First Byte is {metrics.time_to_first_byte:.0f}ms, "
                f"exceeds threshold of {config.ttfb_threshold:.0f}ms"
            ),
            suggested_fix=(
                "Optimize server response time, use CDN, enable caching, "
                "or reduce server processing time"
            ),
        ))

    if metrics.largest_contentful_paint is not None:
        if metrics.largest_contentful_paint > config.lcp_threshold:
            severity = (
                "critical" if metrics.largest_contentful_paint > 4000
                else "warning"
            )
            issues.append(PerformanceIssue(
                issue_type="slow_lcp",
                severity=severity,
                metric_name="Largest Contentful Paint",
                actual_value=metrics.largest_contentful_paint,
                threshold_value=config.lcp_threshold,
                description=(
                    f"LCP is {metrics.largest_contentful_paint:.0f}ms, "
                    f"exceeds threshold of {config.lcp_threshold:.0f}ms"
                ),
                suggested_fix=(
                    "Optimize largest element loading, preload critical assets, "
                    "use efficient image formats, reduce render-blocking resources"
                ),
            ))

    if metrics.first_contentful_paint is not None:
        if metrics.first_contentful_paint > config.fcp_threshold:
            issues.append(PerformanceIssue(
                issue_type="slow_fcp",
                severity="warning",
                metric_name="First Contentful Paint",
                actual_value=metrics.first_contentful_paint,
                threshold_value=config.fcp_threshold,
                description=(
                    f"FCP is {metrics.first_contentful_paint:.0f}ms, "
                    f"exceeds threshold of {config.fcp_threshold:.0f}ms"
                ),
                suggested_fix=(
                    "Eliminate render-blocking resources, inline critical CSS, "
                    "defer non-critical JavaScript"
                ),
            ))

    if metrics.cumulative_layout_shift is not None:
        if metrics.cumulative_layout_shift > config.cls_threshold:
            severity = (
                "critical" if metrics.cumulative_layout_shift > 0.25
                else "warning"
            )
            issues.append(PerformanceIssue(
                issue_type="high_cls",
                severity=severity,
                metric_name="Cumulative Layout Shift",
                actual_value=metrics.cumulative_layout_shift,
                threshold_value=config.cls_threshold,
                description=(
                    f"CLS is {metrics.cumulative_layout_shift:.3f}, "
                    f"exceeds threshold of {config.cls_threshold:.2f}"
                ),
                suggested_fix=(
                    "Set explicit dimensions on images and embeds, "
                    "avoid inserting content above existing content, "
                    "use CSS transform instead of properties that trigger layout"
                ),
            ))

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


def calculate_score(metrics: PageLoadMetrics) -> float:
    """Calculate overall performance score (0-100)."""
    scores = []

    ttfb_score = max(0, 100 - (metrics.time_to_first_byte / 10))
    scores.append(ttfb_score * 0.15)

    if metrics.largest_contentful_paint is not None:
        lcp_score = max(0, 100 - (metrics.largest_contentful_paint / 50))
        scores.append(lcp_score * 0.25)

    if metrics.first_contentful_paint is not None:
        fcp_score = max(0, 100 - (metrics.first_contentful_paint / 36))
        scores.append(fcp_score * 0.15)

    if metrics.cumulative_layout_shift is not None:
        cls_score = max(0, 100 - (metrics.cumulative_layout_shift * 400))
        scores.append(cls_score * 0.25)

    load_score = max(0, 100 - (metrics.page_load / 100))
    scores.append(load_score * 0.20)

    return min(100, sum(scores) / (len(scores) / 5) if scores else 0)


def calculate_lcp_score(metrics: PageLoadMetrics) -> Optional[float]:
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


def calculate_fid_score(metrics: PageLoadMetrics) -> Optional[float]:
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


def calculate_cls_score(metrics: PageLoadMetrics) -> Optional[float]:
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


def score_to_grade(score: float) -> PerformanceGrade:
    """Convert score to grade."""
    if score >= 90:
        return PerformanceGrade.EXCELLENT
    elif score >= 70:
        return PerformanceGrade.GOOD
    elif score >= 50:
        return PerformanceGrade.NEEDS_IMPROVEMENT
    return PerformanceGrade.POOR
