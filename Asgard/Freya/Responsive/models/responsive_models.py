"""
Freya Responsive Models

Pydantic models for responsive design testing.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class Breakpoint(BaseModel):
    """A responsive breakpoint definition."""
    name: str = Field(..., description="Breakpoint name")
    width: int = Field(..., description="Viewport width")
    height: int = Field(800, description="Viewport height")
    is_mobile: bool = Field(False, description="Is mobile breakpoint")
    device_scale_factor: float = Field(1.0, description="Device scale factor")


COMMON_BREAKPOINTS = [
    Breakpoint(name="mobile-sm", width=320, height=568, is_mobile=True, device_scale_factor=2),
    Breakpoint(name="mobile-md", width=375, height=667, is_mobile=True, device_scale_factor=2),
    Breakpoint(name="mobile-lg", width=414, height=896, is_mobile=True, device_scale_factor=3),
    Breakpoint(name="tablet", width=768, height=1024, is_mobile=True, device_scale_factor=2),
    Breakpoint(name="tablet-lg", width=1024, height=1366, is_mobile=True, device_scale_factor=2),
    Breakpoint(name="desktop-sm", width=1280, height=800, is_mobile=False, device_scale_factor=1.0),
    Breakpoint(name="desktop-md", width=1440, height=900, is_mobile=False, device_scale_factor=1.0),
    Breakpoint(name="desktop-lg", width=1920, height=1080, is_mobile=False, device_scale_factor=1.0),
    Breakpoint(name="desktop-xl", width=2560, height=1440, is_mobile=False, device_scale_factor=1.0),
]

MOBILE_DEVICES = {
    "iphone-se": Breakpoint(
        name="iPhone SE",
        width=375,
        height=667,
        is_mobile=True,
        device_scale_factor=2,
    ),
    "iphone-14": Breakpoint(
        name="iPhone 14",
        width=390,
        height=844,
        is_mobile=True,
        device_scale_factor=3,
    ),
    "iphone-14-pro-max": Breakpoint(
        name="iPhone 14 Pro Max",
        width=430,
        height=932,
        is_mobile=True,
        device_scale_factor=3,
    ),
    "pixel-7": Breakpoint(
        name="Pixel 7",
        width=412,
        height=915,
        is_mobile=True,
        device_scale_factor=2.625,
    ),
    "galaxy-s21": Breakpoint(
        name="Galaxy S21",
        width=360,
        height=800,
        is_mobile=True,
        device_scale_factor=3,
    ),
    "ipad": Breakpoint(
        name="iPad",
        width=768,
        height=1024,
        is_mobile=True,
        device_scale_factor=2,
    ),
    "ipad-pro": Breakpoint(
        name="iPad Pro",
        width=1024,
        height=1366,
        is_mobile=True,
        device_scale_factor=2,
    ),
}


class BreakpointIssueType(str, Enum):
    """Types of breakpoint issues."""
    HORIZONTAL_SCROLL = "horizontal_scroll"
    CONTENT_OVERFLOW = "content_overflow"
    HIDDEN_CONTENT = "hidden_content"
    OVERLAPPING_ELEMENTS = "overlapping_elements"
    TEXT_TRUNCATION = "text_truncation"
    IMAGE_SCALING = "image_scaling"
    LAYOUT_SHIFT = "layout_shift"
    MISSING_MEDIA_QUERY = "missing_media_query"


class BreakpointIssue(BaseModel):
    """An issue found at a specific breakpoint."""
    issue_type: BreakpointIssueType = Field(..., description="Type of issue")
    breakpoint: str = Field(..., description="Breakpoint name")
    viewport_width: int = Field(..., description="Viewport width")
    element_selector: str = Field(..., description="Affected element")
    description: str = Field(..., description="Issue description")
    severity: str = Field(..., description="Severity level")
    suggested_fix: str = Field(..., description="How to fix")
    screenshot_path: Optional[str] = Field(None, description="Screenshot showing issue")


class BreakpointTestResult(BaseModel):
    """Result for a single breakpoint test."""
    breakpoint: Breakpoint = Field(..., description="Breakpoint tested")
    issues: List[BreakpointIssue] = Field(default_factory=list)
    screenshot_path: Optional[str] = Field(None, description="Screenshot path")
    page_width: int = Field(0, description="Actual page content width")
    has_horizontal_scroll: bool = Field(False, description="Has horizontal scroll")


class BreakpointReport(BaseModel):
    """Report from breakpoint testing."""
    url: str = Field(..., description="URL tested")
    tested_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    breakpoints_tested: List[str] = Field(default_factory=list)
    total_issues: int = Field(0, description="Total issues found")
    results: List[BreakpointTestResult] = Field(default_factory=list)
    breakpoint_issues: Dict[str, List[BreakpointIssue]] = Field(default_factory=dict)
    screenshots: Dict[str, str] = Field(default_factory=dict)

    @property
    def has_issues(self) -> bool:
        """Check if there are any issues."""
        return self.total_issues > 0


class TouchTargetIssue(BaseModel):
    """A touch target sizing issue."""
    element_selector: str = Field(..., description="Element selector")
    element_type: str = Field(..., description="Element type (button, link, etc)")
    width: float = Field(..., description="Element width")
    height: float = Field(..., description="Element height")
    min_required: int = Field(44, description="Minimum required size")
    description: str = Field(..., description="Issue description")
    severity: str = Field(..., description="Severity level")
    suggested_fix: str = Field(..., description="How to fix")


class TouchTargetReport(BaseModel):
    """Report from touch target validation."""
    url: str = Field(..., description="URL tested")
    tested_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    viewport_width: int = Field(..., description="Viewport width")
    viewport_height: int = Field(..., description="Viewport height")
    total_interactive_elements: int = Field(0, description="Total interactive elements")
    passing_count: int = Field(0, description="Elements meeting size requirement")
    failing_count: int = Field(0, description="Elements below size requirement")
    issues: List[TouchTargetIssue] = Field(default_factory=list)
    min_touch_size: int = Field(44, description="Minimum touch target size used")

    @property
    def has_issues(self) -> bool:
        """Check if there are any issues."""
        return self.failing_count > 0


class ViewportIssueType(str, Enum):
    """Types of viewport issues."""
    MISSING_VIEWPORT_META = "missing_viewport_meta"
    FIXED_WIDTH_VIEWPORT = "fixed_width_viewport"
    USER_SCALABLE_DISABLED = "user_scalable_disabled"
    MAXIMUM_SCALE_TOO_LOW = "maximum_scale_too_low"
    CONTENT_WIDER_THAN_VIEWPORT = "content_wider_than_viewport"
    TEXT_TOO_SMALL = "text_too_small"


class ViewportIssue(BaseModel):
    """A viewport-related issue."""
    issue_type: ViewportIssueType = Field(..., description="Type of issue")
    description: str = Field(..., description="Issue description")
    severity: str = Field(..., description="Severity level")
    current_value: Optional[str] = Field(None, description="Current meta value")
    suggested_fix: str = Field(..., description="How to fix")
    wcag_reference: Optional[str] = Field(None, description="WCAG reference")


class ViewportReport(BaseModel):
    """Report from viewport testing."""
    url: str = Field(..., description="URL tested")
    tested_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    viewport_meta: Optional[str] = Field(None, description="Viewport meta content")
    content_width: int = Field(0, description="Content width")
    viewport_width: int = Field(0, description="Viewport width")
    has_horizontal_scroll: bool = Field(False, description="Has horizontal scroll")
    issues: List[ViewportIssue] = Field(default_factory=list)
    text_sizes: Dict[str, int] = Field(default_factory=dict, description="Text size distribution")
    minimum_text_size: Optional[float] = Field(None, description="Smallest text size found")

    @property
    def has_issues(self) -> bool:
        """Check if there are any issues."""
        return len(self.issues) > 0


class MobileCompatibilityIssueType(str, Enum):
    """Types of mobile compatibility issues."""
    FLASH_CONTENT = "flash_content"
    FIXED_POSITIONING = "fixed_positioning"
    HOVER_DEPENDENT = "hover_dependent"
    SMALL_TEXT = "small_text"
    UNPLAYABLE_MEDIA = "unplayable_media"
    SLOW_LOADING = "slow_loading"
    INCOMPATIBLE_PLUGIN = "incompatible_plugin"


class MobileCompatibilityIssue(BaseModel):
    """A mobile compatibility issue."""
    issue_type: MobileCompatibilityIssueType = Field(..., description="Type of issue")
    element_selector: Optional[str] = Field(None, description="Affected element")
    description: str = Field(..., description="Issue description")
    severity: str = Field(..., description="Severity level")
    suggested_fix: str = Field(..., description="How to fix")
    affected_devices: List[str] = Field(default_factory=list, description="Devices affected")


class MobileCompatibilityReport(BaseModel):
    """Report from mobile compatibility testing."""
    url: str = Field(..., description="URL tested")
    tested_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    devices_tested: List[str] = Field(default_factory=list)
    issues: List[MobileCompatibilityIssue] = Field(default_factory=list)
    load_time_ms: Optional[int] = Field(None, description="Page load time in ms")
    page_size_bytes: Optional[int] = Field(None, description="Total page size")
    resource_count: int = Field(0, description="Number of resources")
    mobile_friendly_score: float = Field(100.0, description="Mobile-friendly score 0-100")
    device_results: Dict[str, Dict[str, Any]] = Field(default_factory=dict)

    @property
    def has_issues(self) -> bool:
        """Check if there are any issues."""
        return len(self.issues) > 0
