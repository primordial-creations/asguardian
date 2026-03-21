"""
Freya Performance Report Models

ResourceTimingReport, PerformanceIssue, PerformanceReport, and PerformanceConfig.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from Asgard.Freya.Performance.models._performance_timing_models import (
    PageLoadMetrics,
    PerformanceGrade,
    ResourceTiming,
)


class ResourceTimingReport(BaseModel):
    """Report of resource timing analysis."""
    url: str = Field(..., description="Page URL")
    measured_at: str = Field(default_factory=lambda: datetime.now().isoformat())

    # Resources
    resources: List[ResourceTiming] = Field(default_factory=list)

    # Summary statistics
    total_resources: int = Field(0, description="Total number of resources")
    total_transfer_size: int = Field(0, description="Total transfer size in bytes")
    total_load_time: float = Field(0, description="Total resource load time (ms)")

    # By type counts
    script_count: int = Field(0, description="Number of scripts")
    stylesheet_count: int = Field(0, description="Number of stylesheets")
    image_count: int = Field(0, description="Number of images")
    font_count: int = Field(0, description="Number of fonts")
    other_count: int = Field(0, description="Number of other resources")

    # By type sizes
    script_size: int = Field(0, description="Total script size in bytes")
    stylesheet_size: int = Field(0, description="Total stylesheet size in bytes")
    image_size: int = Field(0, description="Total image size in bytes")
    font_size: int = Field(0, description="Total font size in bytes")
    other_size: int = Field(0, description="Total other resources size in bytes")

    # Optimization opportunities
    render_blocking_count: int = Field(0, description="Number of render-blocking resources")
    uncached_count: int = Field(0, description="Number of uncached resources")
    large_resources: List[str] = Field(
        default_factory=list, description="Resources over 100KB"
    )
    slow_resources: List[str] = Field(
        default_factory=list, description="Resources taking over 500ms"
    )

    @property
    def total_size_kb(self) -> float:
        """Get total transfer size in KB."""
        return self.total_transfer_size / 1024

    @property
    def total_size_mb(self) -> float:
        """Get total transfer size in MB."""
        return self.total_transfer_size / (1024 * 1024)


class PerformanceIssue(BaseModel):
    """A performance issue found during analysis."""
    issue_type: str = Field(..., description="Type of issue")
    severity: str = Field(..., description="Severity level")
    metric_name: str = Field(..., description="Name of the affected metric")
    actual_value: float = Field(..., description="Actual measured value")
    threshold_value: float = Field(..., description="Threshold value")
    description: str = Field(..., description="Issue description")
    suggested_fix: str = Field(..., description="Suggested remediation")
    resource_url: Optional[str] = Field(None, description="Related resource URL")


class PerformanceReport(BaseModel):
    """Complete performance analysis report."""
    url: str = Field(..., description="URL that was analyzed")
    measured_at: str = Field(default_factory=lambda: datetime.now().isoformat())

    # Overall score
    performance_score: float = Field(0, description="Overall performance score 0-100")
    performance_grade: PerformanceGrade = Field(
        PerformanceGrade.POOR, description="Overall performance grade"
    )

    # Component reports
    page_load_metrics: Optional[PageLoadMetrics] = Field(
        None, description="Page load timing metrics"
    )
    resource_timing_report: Optional[ResourceTimingReport] = Field(
        None, description="Resource timing analysis"
    )

    # Core Web Vitals summary
    lcp_score: Optional[float] = Field(None, description="LCP score 0-100")
    fid_score: Optional[float] = Field(None, description="FID score 0-100")
    cls_score: Optional[float] = Field(None, description="CLS score 0-100")

    # Issues found
    issues: List[PerformanceIssue] = Field(default_factory=list)
    critical_count: int = Field(0, description="Number of critical issues")
    warning_count: int = Field(0, description="Number of warnings")

    # Metadata
    analysis_duration_ms: float = Field(0, description="Time taken to analyze (ms)")
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def has_issues(self) -> bool:
        """Check if there are any performance issues."""
        return len(self.issues) > 0

    @property
    def passes_core_web_vitals(self) -> bool:
        """Check if page passes all Core Web Vitals thresholds."""
        if self.page_load_metrics is None:
            return False

        lcp_grade = self.page_load_metrics.lcp_grade
        cls_grade = self.page_load_metrics.cls_grade
        fid_grade = self.page_load_metrics.fid_grade

        # Must not be poor on any metric
        for grade in [lcp_grade, cls_grade, fid_grade]:
            if grade == PerformanceGrade.POOR:
                return False

        return True


class PerformanceConfig(BaseModel):
    """Configuration for performance testing."""
    # Thresholds (all in milliseconds unless otherwise noted)
    ttfb_threshold: float = Field(500, description="Time to First Byte threshold (ms)")
    lcp_threshold: float = Field(2500, description="Largest Contentful Paint threshold (ms)")
    fid_threshold: float = Field(100, description="First Input Delay threshold (ms)")
    cls_threshold: float = Field(0.1, description="Cumulative Layout Shift threshold")
    fcp_threshold: float = Field(1800, description="First Contentful Paint threshold (ms)")
    tti_threshold: float = Field(3800, description="Time to Interactive threshold (ms)")
    tbt_threshold: float = Field(200, description="Total Blocking Time threshold (ms)")

    # Resource thresholds
    max_resource_size_kb: int = Field(500, description="Max single resource size (KB)")
    max_total_size_kb: int = Field(5000, description="Max total page size (KB)")
    max_requests: int = Field(100, description="Max number of requests")
    max_render_blocking: int = Field(5, description="Max render-blocking resources")

    # Analysis options
    analyze_resources: bool = Field(True, description="Analyze resource timing")
    wait_for_network_idle: bool = Field(True, description="Wait for network idle")
    network_idle_timeout: int = Field(5000, description="Network idle timeout (ms)")

    # Output
    output_format: str = Field("text", description="Output format")
