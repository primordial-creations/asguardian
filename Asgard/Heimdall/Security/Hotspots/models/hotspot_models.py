"""
Heimdall Security Hotspot Models

Pydantic models for security hotspot detection.

Hotspot discipline (plan 08 Part A, DEEPTHINK_10): a hotspot is
*syntactically flawless code whose safety depends on extrinsic context*
(intent, provenance, topology) — never a "failed finding". Reclassifying
weak taint findings as hotspots to inflate precision is forbidden: if the
scanner lacks proof, it emits a Finding via taint or stays silent.

Exactly six pattern families qualify. Review statuses are TO_REVIEW,
SAFE_IN_CONTEXT (mandatory justification, audit-logged) and FIXED — there
is deliberately NO "Acknowledged Risk" status: risk acceptance belongs in
a GRC/ticket system, not a scanner UI (discoverable-negligence liability).
"""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class HotspotCategory(str, Enum):
    """
    The six defensible hotspot families (DEEPTHINK_10 s5).

    Each is a question only a human with extrinsic context can answer:
      WEAK_HASHING            - md5/sha1: is this a security context? (business domain)
      STANDARD_PRNG           - random.*: security sink or simulation? (intent)
      DISABLED_TLS            - verify=False etc.: internal topology? (network)
      PERMISSIVE_BINDING      - 0.0.0.0 / CORS *: deployment surface? (topology)
      OPAQUE_DESERIALIZATION  - pickle/yaml.load on non-taint-proven data (provenance)
      HAZMAT_CRYPTO           - cryptography.hazmat.*: mathematically sound? (review)
    """
    WEAK_HASHING = "weak_hashing"
    STANDARD_PRNG = "standard_prng"
    DISABLED_TLS = "disabled_tls"
    PERMISSIVE_BINDING = "permissive_binding"
    OPAQUE_DESERIALIZATION = "opaque_deserialization"
    HAZMAT_CRYPTO = "hazmat_crypto"


class ReviewPriority(str, Enum):
    """Review priority for a security hotspot."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ReviewStatus(str, Enum):
    """
    Review status of a hotspot.

    SAFE_IN_CONTEXT requires mandatory justification text (enforced by
    ``review_hotspot``) and is persisted to the Shared/Issues audit log.
    There is no "acknowledged risk" status by design.
    """
    TO_REVIEW = "to_review"
    SAFE_IN_CONTEXT = "safe_in_context"
    FIXED = "fixed"


# Volume guard: above this many hotspots on one PR, collapse to a single
# summary comment (>5 is where bulk "Mark as Safe" malicious compliance
# begins — DEEPTHINK_10).
PR_HOTSPOT_CAP = 5


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
    justification: str = Field(
        "", description="Reviewer justification (mandatory for SAFE_IN_CONTEXT transitions)"
    )
    context_tag: str = Field(
        "production",
        description="Test-context tag from the context engine (plan 08 Part B)"
    )
    suppressed_by_context: bool = Field(
        False,
        description="True when the test-context severity matrix suppressed this hotspot"
    )
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
        default_factory=lambda: [".py", ".pyw", ".js", ".jsx", ".mjs", ".ts", ".tsx", ".java", ".go", ".rb", ".php", ".cs", ".rs"],
        description="File extensions to include"
    )
    include_tests: bool = Field(True, description="Include test files in analysis")
    test_context_enabled: bool = Field(
        True,
        description="Route hotspots through the test-context severity matrix (plan 08 Part B)"
    )
    include_test_context: bool = Field(
        False,
        description="Include context-suppressed hotspots in the report (--include-test-context)"
    )
    strict_scan_paths: List[str] = Field(
        default_factory=list,
        description="Regexes for paths where the test-context engine is bypassed entirely"
    )
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
    suppressed_by_context_count: int = Field(
        0, description="Hotspots suppressed by the test-context engine (retained, not scored)"
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
