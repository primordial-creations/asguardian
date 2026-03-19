"""
Freya Visual Models

Pydantic models for visual testing including screenshots,
visual regression, layout validation, and style checking.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field


class ComparisonMethod(str, Enum):
    """Methods for comparing images."""
    PIXEL_DIFF = "pixel_diff"
    STRUCTURAL_SIMILARITY = "structural_similarity"
    PERCEPTUAL_HASH = "perceptual_hash"
    HISTOGRAM_COMPARISON = "histogram_comparison"


class DifferenceType(str, Enum):
    """Types of visual differences."""
    ADDITION = "addition"
    REMOVAL = "removal"
    MODIFICATION = "modification"
    POSITION = "position"
    COLOR = "color"
    SIZE = "size"
    TEXT = "text"


class LayoutIssueType(str, Enum):
    """Types of layout issues."""
    OVERFLOW = "overflow"
    OVERLAP = "overlap"
    MISALIGNMENT = "misalignment"
    SPACING = "spacing"
    Z_INDEX = "z_index"
    VISIBILITY = "visibility"
    RESPONSIVE = "responsive"


class StyleIssueType(str, Enum):
    """Types of style issues."""
    COLOR_MISMATCH = "color_mismatch"
    FONT_MISMATCH = "font_mismatch"
    SPACING_MISMATCH = "spacing_mismatch"
    BORDER_MISMATCH = "border_mismatch"
    SHADOW_MISMATCH = "shadow_mismatch"
    UNKNOWN_COLOR = "unknown_color"
    UNKNOWN_FONT = "unknown_font"


class DeviceConfig(BaseModel):
    """Configuration for device emulation."""
    name: str = Field(..., description="Device name")
    width: int = Field(..., description="Viewport width")
    height: int = Field(..., description="Viewport height")
    device_scale_factor: float = Field(1.0, description="Device pixel ratio")
    is_mobile: bool = Field(False, description="Is mobile device")
    has_touch: bool = Field(False, description="Has touch screen")
    user_agent: Optional[str] = Field(None, description="Custom user agent")


COMMON_DEVICES = {
    "desktop-1080p": DeviceConfig(name="Desktop 1080p", width=1920, height=1080, device_scale_factor=1.0, is_mobile=False, has_touch=False, user_agent=None),
    "desktop-720p": DeviceConfig(name="Desktop 720p", width=1280, height=720, device_scale_factor=1.0, is_mobile=False, has_touch=False, user_agent=None),
    "laptop": DeviceConfig(name="Laptop", width=1366, height=768, device_scale_factor=1.0, is_mobile=False, has_touch=False, user_agent=None),
    "ipad": DeviceConfig(
        name="iPad",
        width=768,
        height=1024,
        is_mobile=True,
        has_touch=True,
        device_scale_factor=2,
        user_agent=None,
    ),
    "ipad-pro": DeviceConfig(
        name="iPad Pro",
        width=1024,
        height=1366,
        is_mobile=True,
        has_touch=True,
        device_scale_factor=2,
        user_agent=None,
    ),
    "iphone-14": DeviceConfig(
        name="iPhone 14",
        width=390,
        height=844,
        is_mobile=True,
        has_touch=True,
        device_scale_factor=3,
        user_agent=None,
    ),
    "iphone-14-pro-max": DeviceConfig(
        name="iPhone 14 Pro Max",
        width=430,
        height=932,
        is_mobile=True,
        has_touch=True,
        device_scale_factor=3,
        user_agent=None,
    ),
    "pixel-7": DeviceConfig(
        name="Pixel 7",
        width=412,
        height=915,
        is_mobile=True,
        has_touch=True,
        device_scale_factor=2.625,
        user_agent=None,
    ),
    "galaxy-s21": DeviceConfig(
        name="Galaxy S21",
        width=360,
        height=800,
        is_mobile=True,
        has_touch=True,
        device_scale_factor=3,
        user_agent=None,
    ),
}


class ScreenshotConfig(BaseModel):
    """Configuration for screenshot capture."""
    full_page: bool = Field(True, description="Capture full page")
    device: Optional[str] = Field(None, description="Device to emulate")
    custom_device: Optional[DeviceConfig] = Field(None, description="Custom device config")
    wait_for_selector: Optional[str] = Field(None, description="Wait for selector before capture")
    wait_for_timeout: int = Field(1000, description="Additional wait time in ms")
    hide_selectors: List[str] = Field(default_factory=list, description="Selectors to hide")
    clip: Optional[Dict[str, int]] = Field(None, description="Clip region {x, y, width, height}")
    quality: int = Field(100, description="Image quality (JPEG only)")
    format: str = Field("png", description="Image format (png or jpeg)")


class ScreenshotResult(BaseModel):
    """Result of a screenshot capture."""
    url: str = Field(..., description="URL that was captured")
    file_path: str = Field(..., description="Path to saved screenshot")
    width: int = Field(..., description="Screenshot width")
    height: int = Field(..., description="Screenshot height")
    device: Optional[str] = Field(None, description="Device used")
    captured_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    file_size_bytes: int = Field(0, description="File size in bytes")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DifferenceRegion(BaseModel):
    """A region of visual difference."""
    x: int = Field(..., description="X coordinate")
    y: int = Field(..., description="Y coordinate")
    width: int = Field(..., description="Region width")
    height: int = Field(..., description="Region height")
    difference_type: DifferenceType = Field(..., description="Type of difference")
    confidence: float = Field(..., description="Confidence score 0-1")
    description: str = Field(..., description="Description of difference")
    pixel_count: int = Field(0, description="Number of different pixels")
    average_difference: float = Field(0.0, description="Average color difference")


class ComparisonConfig(BaseModel):
    """Configuration for image comparison."""
    threshold: float = Field(0.95, description="Similarity threshold 0-1")
    method: ComparisonMethod = Field(
        ComparisonMethod.STRUCTURAL_SIMILARITY,
        description="Comparison method"
    )
    ignore_regions: List[Dict[str, int]] = Field(
        default_factory=list,
        description="Regions to ignore {x, y, width, height}"
    )
    blur_radius: int = Field(0, description="Blur before comparison")
    color_tolerance: int = Field(10, description="Color difference tolerance")
    anti_aliasing_detection: bool = Field(True, description="Detect anti-aliasing")


class VisualComparisonResult(BaseModel):
    """Result of visual comparison."""
    baseline_path: str = Field(..., description="Path to baseline image")
    comparison_path: str = Field(..., description="Path to comparison image")
    similarity_score: float = Field(..., description="Similarity score 0-1")
    is_similar: bool = Field(..., description="Whether images are similar")
    difference_regions: List[DifferenceRegion] = Field(default_factory=list)
    diff_image_path: Optional[str] = Field(None, description="Path to diff image")
    annotated_image_path: Optional[str] = Field(None, description="Path to annotated image")
    comparison_method: ComparisonMethod = Field(ComparisonMethod.STRUCTURAL_SIMILARITY)
    analysis_time: float = Field(0.0, description="Analysis time in seconds")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RegressionTestCase(BaseModel):
    """A single regression test case."""
    name: str = Field(..., description="Test case name")
    url: str = Field(..., description="URL to test")
    selector: Optional[str] = Field(None, description="Element selector to capture")
    device: Optional[str] = Field(None, description="Device to emulate")
    wait_for: Optional[str] = Field(None, description="Wait for selector")
    threshold: float = Field(0.95, description="Similarity threshold")


class RegressionTestSuite(BaseModel):
    """A suite of regression tests."""
    name: str = Field(..., description="Suite name")
    baseline_directory: str = Field(..., description="Baseline images directory")
    output_directory: str = Field(..., description="Output directory")
    test_cases: List[RegressionTestCase] = Field(default_factory=list)
    default_threshold: float = Field(0.95, description="Default similarity threshold")
    comparison_method: ComparisonMethod = Field(ComparisonMethod.STRUCTURAL_SIMILARITY)


class RegressionReport(BaseModel):
    """Report for a regression test run."""
    suite_name: str = Field(..., description="Suite name")
    total_comparisons: int = Field(0, description="Total comparisons")
    passed_comparisons: int = Field(0, description="Passed comparisons")
    failed_comparisons: int = Field(0, description="Failed comparisons")
    skipped_comparisons: int = Field(0, description="Skipped comparisons")
    results: List[VisualComparisonResult] = Field(default_factory=list)
    overall_similarity: float = Field(0.0, description="Average similarity")
    critical_failures: int = Field(0, description="Critical failures count")
    report_timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    report_path: Optional[str] = Field(None, description="Path to HTML report")


class ElementBox(BaseModel):
    """Bounding box for an element."""
    x: float = Field(..., description="X coordinate")
    y: float = Field(..., description="Y coordinate")
    width: float = Field(..., description="Element width")
    height: float = Field(..., description="Element height")
    selector: str = Field(..., description="CSS selector")


class LayoutIssue(BaseModel):
    """A layout issue found during validation."""
    issue_type: LayoutIssueType = Field(..., description="Type of issue")
    element_selector: str = Field(..., description="Element selector")
    description: str = Field(..., description="Issue description")
    severity: str = Field(..., description="Severity level")
    affected_area: Optional[ElementBox] = Field(None, description="Affected area")
    related_elements: List[str] = Field(default_factory=list, description="Related elements")
    suggested_fix: str = Field(..., description="Suggested fix")


class LayoutReport(BaseModel):
    """Report from layout validation."""
    url: str = Field(..., description="URL tested")
    viewport_width: int = Field(..., description="Viewport width")
    viewport_height: int = Field(..., description="Viewport height")
    tested_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    total_elements: int = Field(0, description="Total elements analyzed")
    issues: List[LayoutIssue] = Field(default_factory=list)
    overflow_elements: List[str] = Field(default_factory=list)
    overlapping_elements: List[Tuple[str, str]] = Field(default_factory=list)

    @property
    def has_issues(self) -> bool:
        """Check if there are layout issues."""
        return len(self.issues) > 0


class StyleIssue(BaseModel):
    """A style consistency issue."""
    issue_type: StyleIssueType = Field(..., description="Type of issue")
    element_selector: str = Field(..., description="Element selector")
    property_name: str = Field(..., description="CSS property name")
    actual_value: str = Field(..., description="Actual value found")
    expected_value: Optional[str] = Field(None, description="Expected value")
    description: str = Field(..., description="Issue description")
    severity: str = Field(..., description="Severity level")


class StyleReport(BaseModel):
    """Report from style validation."""
    url: str = Field(..., description="URL tested")
    tested_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    theme_file: Optional[str] = Field(None, description="Theme file used")
    total_elements: int = Field(0, description="Total elements analyzed")
    issues: List[StyleIssue] = Field(default_factory=list)
    colors_found: Dict[str, int] = Field(default_factory=dict, description="Colors found with count")
    fonts_found: Dict[str, int] = Field(default_factory=dict, description="Fonts found with count")
    unknown_colors: List[str] = Field(default_factory=list)
    unknown_fonts: List[str] = Field(default_factory=list)

    @property
    def has_issues(self) -> bool:
        """Check if there are style issues."""
        return len(self.issues) > 0
