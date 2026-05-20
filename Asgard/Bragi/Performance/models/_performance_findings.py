"""
Heimdall Performance Analysis Models - Issue Types and Findings

Enumerations for performance issue categories and Pydantic finding models
for memory, CPU, database, and cache performance issues.
"""

from enum import Enum

from pydantic import BaseModel, Field


class PerformanceSeverity(str, Enum):
    """Severity level for performance findings."""
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class MemoryIssueType(str, Enum):
    """Types of memory issues."""
    MEMORY_LEAK = "memory_leak"
    HIGH_ALLOCATION = "high_allocation"
    CIRCULAR_REFERENCE = "circular_reference"
    LARGE_OBJECT = "large_object"
    UNBOUNDED_GROWTH = "unbounded_growth"
    INEFFICIENT_STRUCTURE = "inefficient_structure"


class CpuIssueType(str, Enum):
    """Types of CPU performance issues."""
    HIGH_COMPLEXITY = "high_complexity"
    INEFFICIENT_LOOP = "inefficient_loop"
    BLOCKING_OPERATION = "blocking_operation"
    EXCESSIVE_RECURSION = "excessive_recursion"
    REDUNDANT_COMPUTATION = "redundant_computation"
    SYNCHRONOUS_IO = "synchronous_io"


class DatabaseIssueType(str, Enum):
    """Types of database performance issues."""
    N_PLUS_ONE = "n_plus_one"
    MISSING_INDEX = "missing_index"
    FULL_TABLE_SCAN = "full_table_scan"
    EXCESSIVE_QUERIES = "excessive_queries"
    UNOPTIMIZED_JOIN = "unoptimized_join"
    NO_PAGINATION = "no_pagination"
    EAGER_LOADING = "eager_loading"


class CacheIssueType(str, Enum):
    """Types of caching issues."""
    MISSING_CACHE = "missing_cache"
    CACHE_MISS = "cache_miss"
    STALE_CACHE = "stale_cache"
    INEFFICIENT_KEY = "inefficient_key"
    CACHE_STAMPEDE = "cache_stampede"
    OVER_CACHING = "over_caching"


class MemoryFinding(BaseModel):
    """A memory performance finding."""
    file_path: str = Field(..., description="Path to the file")
    line_number: int = Field(..., description="Line number of the issue")
    issue_type: MemoryIssueType = Field(..., description="Type of memory issue")
    severity: PerformanceSeverity = Field(..., description="Severity of the issue")
    description: str = Field(..., description="Description of the issue")
    code_pattern: str = Field("", description="The problematic code pattern")
    estimated_impact: str = Field("", description="Estimated memory impact")
    recommendation: str = Field(..., description="Suggested fix")
    code_snippet: str = Field("", description="Code snippet with context")

    class Config:
        use_enum_values = True


class CpuFinding(BaseModel):
    """A CPU performance finding."""
    file_path: str = Field(..., description="Path to the file")
    line_number: int = Field(..., description="Line number of the issue")
    function_name: str = Field("", description="Name of the function if applicable")
    issue_type: CpuIssueType = Field(..., description="Type of CPU issue")
    severity: PerformanceSeverity = Field(..., description="Severity of the issue")
    description: str = Field(..., description="Description of the issue")
    complexity_score: float | None = Field(None, description="Complexity score if calculated")
    estimated_impact: str = Field("", description="Estimated performance impact")
    recommendation: str = Field(..., description="Suggested fix")
    code_snippet: str = Field("", description="Code snippet with context")

    class Config:
        use_enum_values = True


class DatabaseFinding(BaseModel):
    """A database performance finding."""
    file_path: str = Field(..., description="Path to the file")
    line_number: int = Field(..., description="Line number of the issue")
    issue_type: DatabaseIssueType = Field(..., description="Type of database issue")
    severity: PerformanceSeverity = Field(..., description="Severity of the issue")
    description: str = Field(..., description="Description of the issue")
    query_pattern: str = Field("", description="The problematic query pattern")
    estimated_impact: str = Field("", description="Estimated performance impact")
    recommendation: str = Field(..., description="Suggested fix")
    code_snippet: str = Field("", description="Code snippet with context")

    class Config:
        use_enum_values = True


class CacheFinding(BaseModel):
    """A caching performance finding."""
    file_path: str = Field(..., description="Path to the file")
    line_number: int = Field(..., description="Line number of the issue")
    issue_type: CacheIssueType = Field(..., description="Type of caching issue")
    severity: PerformanceSeverity = Field(..., description="Severity of the issue")
    description: str = Field(..., description="Description of the issue")
    cache_pattern: str = Field("", description="The caching pattern in use")
    estimated_impact: str = Field("", description="Estimated performance impact")
    recommendation: str = Field(..., description="Suggested improvement")
    code_snippet: str = Field("", description="Code snippet with context")

    class Config:
        use_enum_values = True
