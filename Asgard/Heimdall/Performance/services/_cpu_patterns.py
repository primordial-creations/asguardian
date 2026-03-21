"""
Heimdall CPU Profiler Service - Pattern Definitions

CpuPattern class and the list of CPU performance patterns for use
in static CPU analysis.
"""

import re
from typing import List, Optional, Set

from Asgard.Heimdall.Performance.models.performance_models import (
    CpuIssueType,
    PerformanceSeverity,
)


class CpuPattern:
    """Defines a pattern for detecting CPU performance issues."""

    def __init__(
        self,
        name: str,
        pattern: str,
        issue_type: CpuIssueType,
        severity: PerformanceSeverity,
        description: str,
        estimated_impact: str,
        recommendation: str,
        file_types: Optional[Set[str]] = None,
    ):
        self.name = name
        self.pattern = re.compile(pattern, re.IGNORECASE | re.MULTILINE)
        self.issue_type = issue_type
        self.severity = severity
        self.description = description
        self.estimated_impact = estimated_impact
        self.recommendation = recommendation
        self.file_types = file_types or {".py", ".js", ".ts", ".java"}


CPU_PATTERNS: List[CpuPattern] = [
    CpuPattern(
        name="synchronous_sleep",
        pattern=r"""time\.sleep\s*\(""",
        issue_type=CpuIssueType.BLOCKING_OPERATION,
        severity=PerformanceSeverity.MEDIUM,
        description="Synchronous sleep blocks the thread.",
        estimated_impact="Thread blocked for sleep duration",
        recommendation="Use asyncio.sleep() in async code, or consider non-blocking alternatives.",
        file_types={".py"},
    ),
    CpuPattern(
        name="synchronous_http",
        pattern=r"""requests\.(?:get|post|put|delete|patch)\s*\(""",
        issue_type=CpuIssueType.SYNCHRONOUS_IO,
        severity=PerformanceSeverity.MEDIUM,
        description="Synchronous HTTP request blocks execution.",
        estimated_impact="Thread blocked during network I/O",
        recommendation="Use aiohttp, httpx with async, or run in thread pool.",
        file_types={".py"},
    ),
    CpuPattern(
        name="regex_greedy_star",
        pattern=r"""re\.(?:match|search|findall|sub)\s*\([^)]*\.\*[^)]*\.\*""",
        issue_type=CpuIssueType.HIGH_COMPLEXITY,
        severity=PerformanceSeverity.HIGH,
        description="Regex with multiple greedy wildcards may cause backtracking.",
        estimated_impact="Exponential time on certain inputs",
        recommendation="Use non-greedy quantifiers or rewrite pattern.",
        file_types={".py"},
    ),
    CpuPattern(
        name="list_in_literal",
        pattern=r"""if\s+\w+\s+in\s+\[[^\]]+\]""",
        issue_type=CpuIssueType.INEFFICIENT_LOOP,
        severity=PerformanceSeverity.LOW,
        description="Using 'in' operator with literal list has O(n) lookup.",
        estimated_impact="Linear search on each check",
        recommendation="Use a set literal instead: {item1, item2} for O(1) lookup.",
        file_types={".py"},
    ),
    CpuPattern(
        name="for_loop_len_call",
        pattern=r"""for\s+\w+\s+in\s+range\s*\(\s*len\s*\(""",
        issue_type=CpuIssueType.INEFFICIENT_LOOP,
        severity=PerformanceSeverity.LOW,
        description="Using range(len()) is unpythonic.",
        estimated_impact="Less readable, potential off-by-one errors",
        recommendation="Use enumerate() or iterate directly over the collection.",
        file_types={".py"},
    ),
    CpuPattern(
        name="js_nested_for",
        pattern=r"""for\s*\([^)]+\)\s*\{[^}]*for\s*\(""",
        issue_type=CpuIssueType.HIGH_COMPLEXITY,
        severity=PerformanceSeverity.MEDIUM,
        description="Nested loops detected in JavaScript.",
        estimated_impact="O(n^2) or higher complexity",
        recommendation="Consider using Map/Set for lookups, or Array methods.",
        file_types={".js", ".ts", ".jsx", ".tsx"},
    ),
    CpuPattern(
        name="document_query_loop",
        pattern=r"""(?:forEach|\.map)\s*\([^)]*document\.querySelector""",
        issue_type=CpuIssueType.INEFFICIENT_LOOP,
        severity=PerformanceSeverity.MEDIUM,
        description="DOM query inside loop causes repeated DOM traversal.",
        estimated_impact="O(n * DOM size) for n iterations",
        recommendation="Cache DOM references before the loop.",
        file_types={".js", ".ts", ".jsx", ".tsx"},
    ),
]
