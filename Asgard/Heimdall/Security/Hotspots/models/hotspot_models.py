"""
Heimdall Security Hotspot Models

Pydantic models for security hotspot detection.

Security hotspots are security-sensitive code patterns that need manual
review. They are not confirmed vulnerabilities but areas requiring developer
attention according to OWASP and CWE guidelines.
"""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class HotspotCategory(str, Enum):
    """Category of security hotspot."""
    COOKIE_CONFIG = "cookie_config"
    CRYPTO_USAGE = "crypto_usage"
    DYNAMIC_EXECUTION = "dynamic_execution"
    REGEX_DOS = "regex_dos"
    XXE = "xxe"
    INSECURE_DESERIALIZATION = "insecure_deserialization"
    SSRF = "ssrf"
    INSECURE_RANDOM = "insecure_random"
    PERMISSION_CHECK = "permission_check"
    TLS_VERIFICATION = "tls_verification"


class ReviewPriority(str, Enum):
    """Review priority for a security hotspot."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ReviewStatus(str, Enum):
    """Current review status of a hotspot."""
    TO_REVIEW = "to_review"
    REVIEWED_SAFE = "reviewed_safe"
    REVIEWED_FIXED = "reviewed_fixed"


class SecurityHotspot(BaseModel):
    """A detected security-sensitive code pattern requiring manual review."""
    file_path: str = Field(..., description="Path to the file containing the hotspot")
    line_number: int = Field(..., description="Line number of the hotspot")
    category: HotspotCategory = Field(..., description="Category of the hotspot")
    review_priority: ReviewPriority = Field(..., description="Priority for review")
    title: str = Field(..., description="Short title describing the hotspot")
    description: str = Field("", description="Detailed description of why this needs review")
    code_snippet: str = Field("", description="The code snippet flagged as a hotspot")
    review_guidance: str = Field("", description="Guidance on what to check during review")
    review_status: ReviewStatus = Field(ReviewStatus.TO_REVIEW, description="Current review status")
    owasp_category: Optional[str] = Field(None, description="OWASP Top 10 category if applicable")
    cwe_id: Optional[str] = Field(None, description="CWE identifier if applicable")

    class Config:
        use_enum_values = True


class HotspotConfig(BaseModel):
    """Configuration for hotspot detection scanning."""
    scan_path: Path = Field(default_factory=lambda: Path("."), description="Root path to scan")
    enabled_categories: List[HotspotCategory] = Field(
        default_factory=lambda: list(HotspotCategory),
        description="Hotspot categories to detect"
    )
    min_priority: ReviewPriority = Field(
        ReviewPriority.LOW,
        description="Minimum review priority to include in results"
    )
    exclude_patterns: List[str] = Field(
        default_factory=lambda: [
            "__pycache__",
            "node_modules",
            ".git",
            ".venv",
            "venv",
            "build",
            "dist",
        ],
        description="Glob patterns to exclude from scanning"
    )
    include_extensions: List[str] = Field(
        default_factory=lambda: [".py"],
        description="File extensions to include"
    )
    include_tests: bool = Field(True, description="Include test files in analysis")
    output_format: str = Field("text", description="Output format: text, json, markdown")
    verbose: bool = Field(False, description="Verbose output")

    class Config:
        use_enum_values = True


class HotspotReport(BaseModel):
    """Summary hotspot detection report across all scanned files."""
    total_hotspots: int = Field(0, description="Total number of hotspots detected")
    high_priority_count: int = Field(0, description="Number of HIGH priority hotspots")
    medium_priority_count: int = Field(0, description="Number of MEDIUM priority hotspots")
    low_priority_count: int = Field(0, description="Number of LOW priority hotspots")
    hotspots_by_category: Dict[str, int] = Field(
        default_factory=dict,
        description="Count of hotspots grouped by category"
    )
    hotspots: List[SecurityHotspot] = Field(
        default_factory=list,
        description="All detected hotspots"
    )

    # Metadata
    scan_path: str = Field("", description="Root path that was scanned")
    scan_duration_seconds: float = Field(0.0, description="Time taken for the scan")
    scanned_at: datetime = Field(default_factory=datetime.now, description="When scan was performed")

    class Config:
        use_enum_values = True

    def add_hotspot(self, hotspot: SecurityHotspot) -> None:
        """Add a hotspot to the report and update counters."""
        self.hotspots.append(hotspot)
        self.total_hotspots += 1

        priority: str = hotspot.review_priority.value if isinstance(hotspot.review_priority, ReviewPriority) else hotspot.review_priority

        if priority == ReviewPriority.HIGH.value:
            self.high_priority_count += 1
        elif priority == ReviewPriority.MEDIUM.value:
            self.medium_priority_count += 1
        else:
            self.low_priority_count += 1

        category: str = hotspot.category.value if isinstance(hotspot.category, HotspotCategory) else hotspot.category
        self.hotspots_by_category[category] = self.hotspots_by_category.get(category, 0) + 1
