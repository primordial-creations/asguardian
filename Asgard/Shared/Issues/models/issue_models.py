"""
Heimdall Issue Lifecycle Models

Pydantic models for persistent issue tracking across multiple analysis runs.
Issues are identified by a stable UUID and track their lifecycle status,
assignment, git blame attribution, and comments.
"""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class IssueStatus(str, Enum):
    """Lifecycle status of a tracked issue."""
    OPEN = "open"
    CONFIRMED = "confirmed"
    RESOLVED = "resolved"
    CLOSED = "closed"
    FALSE_POSITIVE = "false_positive"
    WONT_FIX = "wont_fix"


class IssueSeverity(str, Enum):
    """Severity levels for tracked issues."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class IssueType(str, Enum):
    """Categories of tracked issues."""
    BUG = "bug"
    VULNERABILITY = "vulnerability"
    CODE_SMELL = "code_smell"
    SECURITY_HOTSPOT = "security_hotspot"


class TrackedIssue(BaseModel):
    """
    A persistent tracked issue identified across analysis runs.

    Issues are keyed by (project_path, rule_id, file_path, approximate_line)
    and assigned a stable UUID that remains constant across subsequent scans.
    """
    issue_id: str = Field(..., description="Stable UUID identifying this issue across scans")
    rule_id: str = Field(..., description="Rule identifier that produced this issue")
    issue_type: IssueType = Field(..., description="Category of the issue")
    file_path: str = Field(..., description="Absolute path to the file containing the issue")
    line_number: int = Field(..., description="Line number where the issue occurs")
    severity: IssueSeverity = Field(..., description="Severity level")
    title: str = Field(..., description="Short title describing the issue")
    description: str = Field(..., description="Detailed description of the issue")
    status: IssueStatus = Field(IssueStatus.OPEN, description="Current lifecycle status")
    first_detected: datetime = Field(..., description="When this issue was first detected")
    last_seen: datetime = Field(..., description="When this issue was last seen in a scan")
    resolved_at: Optional[datetime] = Field(None, description="When the issue was resolved")
    false_positive_reason: Optional[str] = Field(None, description="Reason if marked as false positive")
    assigned_to: Optional[str] = Field(None, description="Developer assigned to this issue")
    git_blame_author: Optional[str] = Field(None, description="Git blame author for the line")
    git_blame_commit: Optional[str] = Field(None, description="Git commit hash from git blame")
    tags: List[str] = Field(default_factory=list, description="User-defined tags for the issue")
    comments: List[str] = Field(default_factory=list, description="Comments added to the issue")
    scan_count: int = Field(1, description="Number of scans in which this issue has been detected")

    class Config:
        use_enum_values = True


class IssueFilter(BaseModel):
    """Filter criteria for querying tracked issues."""
    status: Optional[List[IssueStatus]] = Field(None, description="Filter by status values")
    severity: Optional[List[IssueSeverity]] = Field(None, description="Filter by severity values")
    issue_type: Optional[List[IssueType]] = Field(None, description="Filter by issue type values")
    file_path_contains: Optional[str] = Field(
        None,
        description="Filter to issues whose file_path contains this string"
    )
    assigned_to: Optional[str] = Field(None, description="Filter to issues assigned to this person")
    rule_id: Optional[str] = Field(None, description="Filter to issues from this rule")

    class Config:
        use_enum_values = True


class IssuesSummary(BaseModel):
    """Aggregated summary of tracked issues for a project."""
    total_open: int = Field(0, description="Total number of open issues")
    total_confirmed: int = Field(0, description="Total number of confirmed issues")
    total_false_positives: int = Field(0, description="Total number of false positive issues")
    total_wont_fix: int = Field(0, description="Total number of issues marked as wont_fix")
    total_resolved: int = Field(0, description="Total number of resolved issues")
    open_by_severity: Dict[str, int] = Field(
        default_factory=dict,
        description="Count of open issues grouped by severity"
    )
    open_by_type: Dict[str, int] = Field(
        default_factory=dict,
        description="Count of open issues grouped by issue type"
    )
    oldest_open_issue: Optional[datetime] = Field(
        None,
        description="Timestamp of the oldest currently open issue"
    )
    project_path: str = Field(..., description="Project path this summary is for")
    generated_at: datetime = Field(
        default_factory=datetime.now,
        description="When this summary was generated"
    )

    class Config:
        use_enum_values = True
