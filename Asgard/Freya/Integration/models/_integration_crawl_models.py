"""
Freya Integration Crawl Models

Models for site crawling and per-page test result aggregation.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


from pydantic import BaseModel, Field

from Asgard.Freya.Integration.models._integration_base_models import CrawlConfig


class PageStatus(str, Enum):
    """Status of a crawled page."""
    PENDING = "pending"
    CRAWLING = "crawling"
    TESTED = "tested"
    SKIPPED = "skipped"
    ERROR = "error"


class CrawledPage(BaseModel):
    """A discovered page during crawl."""
    url: str = Field(description="Page URL")
    title: Optional[str] = Field(default=None, description="Page title")
    depth: int = Field(description="Crawl depth from start")
    parent_url: Optional[str] = Field(default=None, description="Parent page URL")
    status: PageStatus = Field(default=PageStatus.PENDING, description="Page status")
    discovered_at: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="Discovery timestamp"
    )
    links_found: List[str] = Field(
        default_factory=list,
        description="Links found on this page"
    )
    error_message: Optional[str] = Field(default=None, description="Error if any")


class PageTestResult(BaseModel):
    """Test results for a single crawled page."""
    url: str = Field(description="Page URL")
    title: Optional[str] = Field(default=None, description="Page title")
    tested_at: str = Field(description="Test timestamp")
    duration_ms: int = Field(description="Test duration")
    screenshot_path: Optional[str] = Field(default=None, description="Screenshot path")

    # Scores
    accessibility_score: float = Field(default=0.0, description="Accessibility score")
    visual_score: float = Field(default=0.0, description="Visual score")
    responsive_score: float = Field(default=0.0, description="Responsive score")
    overall_score: float = Field(default=0.0, description="Overall score")

    # Issue counts
    critical_issues: int = Field(default=0, description="Critical issues")
    serious_issues: int = Field(default=0, description="Serious issues")
    moderate_issues: int = Field(default=0, description="Moderate issues")
    minor_issues: int = Field(default=0, description="Minor issues")

    # Detailed results
    issues: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="All issues found"
    )

    # Status
    passed: bool = Field(default=True, description="Did page pass all tests")
    error: Optional[str] = Field(default=None, description="Error if testing failed")


class SiteCrawlReport(BaseModel):
    """Complete site crawl and test report."""
    start_url: str = Field(description="Starting URL")
    crawl_started: str = Field(description="Crawl start time")
    crawl_completed: str = Field(description="Crawl completion time")
    total_duration_ms: int = Field(description="Total duration")

    # Crawl stats
    pages_discovered: int = Field(description="Total pages discovered")
    pages_tested: int = Field(description="Pages tested")
    pages_skipped: int = Field(description="Pages skipped")
    pages_errored: int = Field(description="Pages with errors")

    # Aggregate scores
    average_accessibility_score: float = Field(default=0.0)
    average_visual_score: float = Field(default=0.0)
    average_responsive_score: float = Field(default=0.0)
    average_overall_score: float = Field(default=0.0)

    # Total issues
    total_critical: int = Field(default=0, description="Total critical issues")
    total_serious: int = Field(default=0, description="Total serious issues")
    total_moderate: int = Field(default=0, description="Total moderate issues")
    total_minor: int = Field(default=0, description="Total minor issues")

    # Page results
    page_results: List[PageTestResult] = Field(
        default_factory=list,
        description="Results for each page"
    )

    # Pages with issues (for quick reference)
    worst_pages: List[str] = Field(
        default_factory=list,
        description="URLs of worst-scoring pages"
    )

    # Common issues across site
    common_issues: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Most common issues across all pages"
    )

    # Config used
    config: CrawlConfig = Field(description="Crawl configuration")
