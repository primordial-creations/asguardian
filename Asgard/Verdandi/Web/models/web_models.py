"""
Web Performance Models

Pydantic models for web performance metrics.
"""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class VitalsRating(str, Enum):
    """Rating for Core Web Vitals metrics."""

    GOOD = "good"
    NEEDS_IMPROVEMENT = "needs_improvement"
    POOR = "poor"
    INSUFFICIENT_DATA = "insufficient_data"


class VitalsDistributionInput(BaseModel):
    """RUM sample distribution for one web-vitals metric."""

    metric: str = Field(
        ..., description="Metric name: lcp, inp, cls, fid, ttfb, or fcp"
    )
    samples: List[float] = Field(
        default_factory=list, description="Raw RUM samples (ms; unitless for CLS)"
    )
    phase: Optional[str] = Field(
        default=None, description="Optional phase/segment label"
    )


class VitalsDistributionResult(BaseModel):
    """Distribution-based (p75) assessment of one metric."""

    metric: str = Field(..., description="Metric name")
    p75: Optional[float] = Field(
        default=None, description="75th percentile of the samples"
    )
    rating: VitalsRating = Field(
        ..., description="Tri-band rating of the p75 (or INSUFFICIENT_DATA)"
    )
    good_fraction: Optional[float] = Field(
        default=None, description="Fraction of samples <= good threshold"
    )
    ni_fraction: Optional[float] = Field(
        default=None, description="Fraction of samples in the needs-improvement band"
    )
    poor_fraction: Optional[float] = Field(
        default=None, description="Fraction of samples > poor threshold"
    )
    sample_count: int = Field(default=0, description="Number of samples")
    insufficient_data: bool = Field(
        default=False,
        description="True when sample_count < MIN_SAMPLES; no rating is junk-banded",
    )
    recommendations: List[str] = Field(
        default_factory=list, description="Improvement recommendations"
    )


class CWVAssessment(BaseModel):
    """
    Page/origin-level Core Web Vitals assessment at the 75th percentile.

    Core = {LCP, INP, CLS} (INP replaced FID as a Core Web Vital in March
    2024). A page passes CWV iff all three core metrics are GOOD at p75.
    """

    lcp: Optional[VitalsDistributionResult] = Field(default=None)
    inp: Optional[VitalsDistributionResult] = Field(default=None)
    cls: Optional[VitalsDistributionResult] = Field(default=None)
    core_passing: Optional[bool] = Field(
        default=None,
        description=(
            "True iff LCP, INP and CLS are all GOOD at p75; None when any "
            "core metric is missing or has insufficient data"
        ),
    )
    diagnostics: Dict[str, VitalsDistributionResult] = Field(
        default_factory=dict,
        description="Non-core metrics (ttfb, fcp) and legacy FID",
    )
    legacy_fid_rating: Optional[VitalsRating] = Field(
        default=None,
        description=(
            "DEPRECATED: FID was replaced by INP as a Core Web Vital in "
            "March 2024; provided for backwards comparison only"
        ),
    )
    masking_warning: bool = Field(
        default=False,
        description=(
            "True when metric ratings disagree by >= 2 bands (e.g. GOOD LCP "
            "+ POOR INP): any single composite score would mask a bimodal "
            "user experience"
        ),
    )
    recommendations: List[str] = Field(default_factory=list)


class CoreWebVitalsInput(BaseModel):
    """Input data for Core Web Vitals calculation."""

    lcp_ms: Optional[float] = Field(
        default=None,
        description="Largest Contentful Paint in milliseconds",
    )
    fid_ms: Optional[float] = Field(
        default=None,
        description="First Input Delay in milliseconds",
    )
    cls: Optional[float] = Field(
        default=None,
        description="Cumulative Layout Shift (unitless)",
    )
    inp_ms: Optional[float] = Field(
        default=None,
        description="Interaction to Next Paint in milliseconds",
    )
    ttfb_ms: Optional[float] = Field(
        default=None,
        description="Time to First Byte in milliseconds",
    )
    fcp_ms: Optional[float] = Field(
        default=None,
        description="First Contentful Paint in milliseconds",
    )


class WebVitalsResult(BaseModel):
    """Result of Core Web Vitals calculation."""

    lcp_ms: Optional[float] = Field(default=None, description="LCP value in ms")
    lcp_rating: Optional[VitalsRating] = Field(default=None, description="LCP rating")
    fid_ms: Optional[float] = Field(default=None, description="FID value in ms")
    fid_rating: Optional[VitalsRating] = Field(default=None, description="FID rating")
    cls: Optional[float] = Field(default=None, description="CLS value")
    cls_rating: Optional[VitalsRating] = Field(default=None, description="CLS rating")
    inp_ms: Optional[float] = Field(default=None, description="INP value in ms")
    inp_rating: Optional[VitalsRating] = Field(default=None, description="INP rating")
    ttfb_ms: Optional[float] = Field(default=None, description="TTFB value in ms")
    ttfb_rating: Optional[VitalsRating] = Field(default=None, description="TTFB rating")
    fcp_ms: Optional[float] = Field(default=None, description="FCP value in ms")
    fcp_rating: Optional[VitalsRating] = Field(default=None, description="FCP rating")
    overall_rating: VitalsRating = Field(..., description="Overall page rating")
    score: float = Field(..., ge=0, le=100, description="Overall score 0-100")
    recommendations: List[str] = Field(
        default_factory=list,
        description="Improvement recommendations",
    )


class NavigationTimingInput(BaseModel):
    """Input data for Navigation Timing calculation."""

    dns_start_ms: float = Field(..., description="DNS lookup start time")
    dns_end_ms: float = Field(..., description="DNS lookup end time")
    connect_start_ms: float = Field(..., description="Connection start time")
    connect_end_ms: float = Field(..., description="Connection end time")
    ssl_start_ms: Optional[float] = Field(default=None, description="SSL handshake start")
    ssl_end_ms: Optional[float] = Field(default=None, description="SSL handshake end")
    request_start_ms: float = Field(..., description="Request start time")
    response_start_ms: float = Field(..., description="Response start time")
    response_end_ms: float = Field(..., description="Response end time")
    dom_interactive_ms: float = Field(..., description="DOM interactive time")
    dom_complete_ms: float = Field(..., description="DOM complete time")
    load_event_start_ms: float = Field(..., description="Load event start")
    load_event_end_ms: float = Field(..., description="Load event end")


class NavigationTimingResult(BaseModel):
    """Result of Navigation Timing calculation."""

    dns_lookup_ms: float = Field(..., description="DNS lookup duration")
    tcp_connection_ms: float = Field(..., description="TCP connection duration")
    ssl_handshake_ms: Optional[float] = Field(default=None, description="SSL handshake duration")
    ttfb_ms: float = Field(..., description="Time to First Byte")
    content_download_ms: float = Field(..., description="Content download duration")
    dom_processing_ms: float = Field(..., description="DOM processing duration")
    page_load_ms: float = Field(..., description="Total page load time")
    frontend_time_ms: float = Field(..., description="Frontend processing time")
    backend_time_ms: float = Field(..., description="Backend/network time")
    bottleneck: str = Field(..., description="Primary bottleneck identified")
    recommendations: List[str] = Field(
        default_factory=list,
        description="Improvement recommendations",
    )


class ResourceTimingInput(BaseModel):
    """Input data for a single resource timing entry."""

    name: str = Field(..., description="Resource URL or name")
    initiator_type: str = Field(..., description="Resource type (script, css, img, etc)")
    start_time_ms: float = Field(..., description="Start time relative to navigation")
    duration_ms: float = Field(..., description="Total duration")
    transfer_size_bytes: int = Field(..., description="Transfer size in bytes")
    encoded_body_size_bytes: int = Field(..., description="Encoded body size")
    decoded_body_size_bytes: int = Field(..., description="Decoded body size")
    dns_lookup_ms: Optional[float] = Field(default=None)
    tcp_connection_ms: Optional[float] = Field(default=None)
    ttfb_ms: Optional[float] = Field(default=None)


class ResourceTimingResult(BaseModel):
    """Result of Resource Timing analysis."""

    total_resources: int = Field(..., description="Total resources analyzed")
    total_transfer_bytes: int = Field(..., description="Total bytes transferred")
    total_duration_ms: float = Field(..., description="Total loading time")
    by_type: Dict[str, Dict[str, float]] = Field(
        default_factory=dict,
        description="Breakdown by resource type",
    )
    largest_resources: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Top 5 largest resources",
    )
    slowest_resources: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Top 5 slowest resources",
    )
    blocking_resources: List[str] = Field(
        default_factory=list,
        description="Render-blocking resources",
    )
    cache_hit_rate: float = Field(..., description="Estimated cache hit rate")
    recommendations: List[str] = Field(
        default_factory=list,
        description="Optimization recommendations",
    )
