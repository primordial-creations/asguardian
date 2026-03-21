"""
Recommendation helpers for CoreWebVitalsCalculator.

Contains recommendation generation functions extracted from the vitals calculator.
"""

from typing import List

from Asgard.Verdandi.Web.models.web_models import VitalsRating


def lcp_recommendations(lcp_ms: float, rating: VitalsRating, lcp_poor: float) -> List[str]:
    """Generate LCP improvement recommendations."""
    if rating == VitalsRating.GOOD:
        return []

    recs = []
    if lcp_ms > lcp_poor:
        recs.append("Critical: LCP is poor. Optimize largest content element loading.")
    recs.extend([
        "Optimize server response time (TTFB)",
        "Use a CDN for static assets",
        "Preload critical resources with <link rel='preload'>",
        "Optimize images with modern formats (WebP, AVIF)",
    ])
    return recs


def fid_recommendations(fid_ms: float, rating: VitalsRating) -> List[str]:
    """Generate FID improvement recommendations."""
    if rating == VitalsRating.GOOD:
        return []

    return [
        "Break up long JavaScript tasks into smaller chunks",
        "Use web workers for heavy computations",
        "Defer non-critical JavaScript",
        "Minimize main thread work",
    ]


def cls_recommendations(cls: float, rating: VitalsRating) -> List[str]:
    """Generate CLS improvement recommendations."""
    if rating == VitalsRating.GOOD:
        return []

    return [
        "Always include size attributes on images and videos",
        "Reserve space for ad slots and embeds",
        "Avoid inserting content above existing content",
        "Use CSS transform for animations instead of layout properties",
    ]


def inp_recommendations(inp_ms: float, rating: VitalsRating) -> List[str]:
    """Generate INP improvement recommendations."""
    if rating == VitalsRating.GOOD:
        return []

    return [
        "Optimize event handlers to respond quickly",
        "Reduce JavaScript execution during interactions",
        "Use requestIdleCallback for non-urgent work",
        "Consider using a framework with efficient rendering",
    ]


def ttfb_recommendations(ttfb_ms: float, rating: VitalsRating) -> List[str]:
    """Generate TTFB improvement recommendations."""
    if rating == VitalsRating.GOOD:
        return []

    return [
        "Optimize server-side processing",
        "Use edge caching or CDN",
        "Enable HTTP/2 or HTTP/3",
        "Consider connection preloading with preconnect",
    ]


def fcp_recommendations(fcp_ms: float, rating: VitalsRating) -> List[str]:
    """Generate FCP improvement recommendations."""
    if rating == VitalsRating.GOOD:
        return []

    return [
        "Eliminate render-blocking resources",
        "Inline critical CSS",
        "Defer non-critical CSS",
        "Minimize document size",
    ]
