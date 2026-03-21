"""
Freya Performance Timing Models

Navigation timing, page load metrics, and resource timing models.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class PerformanceMetricType(str, Enum):
    """Types of performance metrics."""
    TIMING = "timing"
    RESOURCE = "resource"
    PAINT = "paint"
    NAVIGATION = "navigation"
    CORE_WEB_VITALS = "core_web_vitals"


class PerformanceGrade(str, Enum):
    """Performance grade levels."""
    EXCELLENT = "excellent"  # 90-100
    GOOD = "good"  # 70-89
    NEEDS_IMPROVEMENT = "needs_improvement"  # 50-69
    POOR = "poor"  # 0-49


class ResourceType(str, Enum):
    """Types of web resources."""
    DOCUMENT = "document"
    SCRIPT = "script"
    STYLESHEET = "stylesheet"
    IMAGE = "image"
    FONT = "font"
    FETCH = "fetch"
    XHR = "xhr"
    WEBSOCKET = "websocket"
    MEDIA = "media"
    OTHER = "other"


class NavigationTiming(BaseModel):
    """Navigation timing metrics (Performance API)."""
    navigation_start: float = Field(0, description="Navigation start time")
    unload_event_start: float = Field(0, description="Unload event start")
    unload_event_end: float = Field(0, description="Unload event end")
    redirect_start: float = Field(0, description="Redirect start")
    redirect_end: float = Field(0, description="Redirect end")
    fetch_start: float = Field(0, description="Fetch start")
    domain_lookup_start: float = Field(0, description="DNS lookup start")
    domain_lookup_end: float = Field(0, description="DNS lookup end")
    connect_start: float = Field(0, description="Connection start")
    connect_end: float = Field(0, description="Connection end")
    secure_connection_start: float = Field(0, description="SSL handshake start")
    request_start: float = Field(0, description="Request start")
    response_start: float = Field(0, description="Response start (TTFB)")
    response_end: float = Field(0, description="Response end")
    dom_loading: float = Field(0, description="DOM loading")
    dom_interactive: float = Field(0, description="DOM interactive")
    dom_content_loaded_event_start: float = Field(0, description="DOMContentLoaded start")
    dom_content_loaded_event_end: float = Field(0, description="DOMContentLoaded end")
    dom_complete: float = Field(0, description="DOM complete")
    load_event_start: float = Field(0, description="Load event start")
    load_event_end: float = Field(0, description="Load event end")


class PageLoadMetrics(BaseModel):
    """Computed page load timing metrics."""
    url: str = Field(..., description="URL that was measured")
    measured_at: str = Field(default_factory=lambda: datetime.now().isoformat())

    # Key timing metrics in milliseconds
    dns_lookup: float = Field(0, description="DNS lookup time (ms)")
    tcp_connection: float = Field(0, description="TCP connection time (ms)")
    ssl_handshake: float = Field(0, description="SSL handshake time (ms)")
    time_to_first_byte: float = Field(0, description="Time to first byte (ms)")
    content_download: float = Field(0, description="Content download time (ms)")
    dom_interactive: float = Field(0, description="Time to DOM interactive (ms)")
    dom_content_loaded: float = Field(0, description="DOMContentLoaded time (ms)")
    page_load: float = Field(0, description="Total page load time (ms)")

    # Core Web Vitals
    largest_contentful_paint: Optional[float] = Field(
        None, description="Largest Contentful Paint (ms)"
    )
    first_input_delay: Optional[float] = Field(
        None, description="First Input Delay (ms)"
    )
    cumulative_layout_shift: Optional[float] = Field(
        None, description="Cumulative Layout Shift"
    )
    first_contentful_paint: Optional[float] = Field(
        None, description="First Contentful Paint (ms)"
    )
    time_to_interactive: Optional[float] = Field(
        None, description="Time to Interactive (ms)"
    )
    total_blocking_time: Optional[float] = Field(
        None, description="Total Blocking Time (ms)"
    )

    # Raw navigation timing
    navigation_timing: Optional[NavigationTiming] = Field(
        None, description="Raw navigation timing data"
    )

    @property
    def ttfb_grade(self) -> PerformanceGrade:
        """Get grade for time to first byte."""
        if self.time_to_first_byte <= 200:
            return PerformanceGrade.EXCELLENT
        elif self.time_to_first_byte <= 500:
            return PerformanceGrade.GOOD
        elif self.time_to_first_byte <= 1000:
            return PerformanceGrade.NEEDS_IMPROVEMENT
        return PerformanceGrade.POOR

    @property
    def lcp_grade(self) -> Optional[PerformanceGrade]:
        """Get grade for Largest Contentful Paint."""
        if self.largest_contentful_paint is None:
            return None
        if self.largest_contentful_paint <= 2500:
            return PerformanceGrade.EXCELLENT
        elif self.largest_contentful_paint <= 4000:
            return PerformanceGrade.NEEDS_IMPROVEMENT
        return PerformanceGrade.POOR

    @property
    def fid_grade(self) -> Optional[PerformanceGrade]:
        """Get grade for First Input Delay."""
        if self.first_input_delay is None:
            return None
        if self.first_input_delay <= 100:
            return PerformanceGrade.EXCELLENT
        elif self.first_input_delay <= 300:
            return PerformanceGrade.NEEDS_IMPROVEMENT
        return PerformanceGrade.POOR

    @property
    def cls_grade(self) -> Optional[PerformanceGrade]:
        """Get grade for Cumulative Layout Shift."""
        if self.cumulative_layout_shift is None:
            return None
        if self.cumulative_layout_shift <= 0.1:
            return PerformanceGrade.EXCELLENT
        elif self.cumulative_layout_shift <= 0.25:
            return PerformanceGrade.NEEDS_IMPROVEMENT
        return PerformanceGrade.POOR


class ResourceTiming(BaseModel):
    """Timing information for a single resource."""
    url: str = Field(..., description="Resource URL")
    resource_type: ResourceType = Field(..., description="Type of resource")
    name: str = Field(..., description="Resource name")

    # Timing in milliseconds
    start_time: float = Field(0, description="Start time relative to navigation")
    dns_lookup: float = Field(0, description="DNS lookup time")
    tcp_connection: float = Field(0, description="TCP connection time")
    ssl_handshake: float = Field(0, description="SSL handshake time")
    request_time: float = Field(0, description="Request time")
    response_time: float = Field(0, description="Response time")
    duration: float = Field(0, description="Total duration")

    # Size information
    transfer_size: int = Field(0, description="Transfer size in bytes")
    encoded_body_size: int = Field(0, description="Encoded body size in bytes")
    decoded_body_size: int = Field(0, description="Decoded body size in bytes")

    # Cache status
    from_cache: bool = Field(False, description="Whether loaded from cache")
    initiator_type: str = Field("other", description="What initiated the request")

    @property
    def is_blocking(self) -> bool:
        """Check if resource is render-blocking."""
        if self.resource_type == ResourceType.SCRIPT:
            return True
        if self.resource_type == ResourceType.STYLESHEET:
            return True
        return False

    @property
    def size_kb(self) -> float:
        """Get transfer size in KB."""
        return self.transfer_size / 1024
