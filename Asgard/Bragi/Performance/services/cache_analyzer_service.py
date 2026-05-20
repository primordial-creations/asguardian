"""Heimdall Cache Analyzer Service - static analysis of caching patterns in source code."""

import re
import time
from pathlib import Path
from typing import List, Optional, Set

from Asgard.Bragi.Performance.models.performance_models import (
    CacheFinding,
    CacheIssueType,
    CacheReport,
    PerformanceScanConfig,
    PerformanceSeverity,
)
from Asgard.Bragi.Performance.utilities.performance_utils import (
    extract_code_snippet,
    find_line_column,
    scan_directory_for_performance,
)


class CachePattern:
    """Defines a pattern for detecting caching issues."""

    def __init__(
        self,
        name: str,
        pattern: str,
        issue_type: CacheIssueType,
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
        self.file_types = file_types or {".py", ".js", ".ts"}


CACHE_PATTERNS: List[CachePattern] = [
    CachePattern(
        name="no_cache_decorator",
        pattern=r"""def\s+(?:get|fetch|load|compute|calculate)_\w+\s*\([^)]*\)\s*:""",
        issue_type=CacheIssueType.MISSING_CACHE,
        severity=PerformanceSeverity.LOW,
        description="Function with get/fetch/load/compute pattern may benefit from caching.",
        estimated_impact="Potentially repeated expensive operations",
        recommendation="Consider adding @lru_cache or external cache for frequently called functions.",
        file_types={".py"},
    ),
    CachePattern(
        name="cache_no_ttl",
        pattern=r"""(?:redis\.set|cache\.set|memcached\.set)\s*\([^)]+\)\s*$""",
        issue_type=CacheIssueType.STALE_CACHE,
        severity=PerformanceSeverity.MEDIUM,
        description="Cache set without TTL may serve stale data indefinitely.",
        estimated_impact="Stale data returned after source changes",
        recommendation="Always set a TTL appropriate for your data freshness requirements.",
    ),
    CachePattern(
        name="cache_get_simple",
        pattern=r"""(?:cache\.get|redis\.get|memcached\.get)\s*\(\s*["'][^"']{1,20}["']\s*\)""",
        issue_type=CacheIssueType.INEFFICIENT_KEY,
        severity=PerformanceSeverity.LOW,
        description="Simple cache key may lack version identifier.",
        estimated_impact="Difficult to invalidate cache on schema changes",
        recommendation="Include version prefix in cache keys (e.g., 'v1:user:123').",
    ),
    CachePattern(
        name="query_in_template",
        pattern=r"""(?:\{\{|\{%)[^}%]*(?:\.objects\.|\.query\(|\.filter\()""",
        issue_type=CacheIssueType.MISSING_CACHE,
        severity=PerformanceSeverity.HIGH,
        description="Database query in template - hard to cache and debug.",
        estimated_impact="Query executed on every render, N+1 issues hidden",
        recommendation="Move queries to view/controller, pass data to template.",
        file_types={".html", ".jinja", ".jinja2"},
    ),
    CachePattern(
        name="lru_cache_no_maxsize",
        pattern=r"""@lru_cache\s*\(\s*\)""",
        issue_type=CacheIssueType.OVER_CACHING,
        severity=PerformanceSeverity.MEDIUM,
        description="lru_cache without maxsize can grow unbounded.",
        estimated_impact="Memory grows with unique inputs",
        recommendation="Use @lru_cache(maxsize=N) to limit cache size.",
        file_types={".py"},
    ),
    CachePattern(
        name="localstorage_sync",
        pattern=r"""localStorage\.(?:getItem|setItem)""",
        issue_type=CacheIssueType.MISSING_CACHE,
        severity=PerformanceSeverity.LOW,
        description="localStorage is synchronous and blocks the main thread.",
        estimated_impact="UI blocking on read/write operations",
        recommendation="Consider IndexedDB for larger data, or batch localStorage access.",
        file_types={".js", ".ts", ".jsx", ".tsx"},
    ),
]


class CacheAnalyzerService:
    """
    Static analysis service for caching-related performance issues.

    Detects:
    - Missing caching opportunities
    - Cache configuration issues
    - Cache key problems
    - Cache stampede risks
    - Over-caching anti-patterns
    """

    def __init__(self, config: Optional[PerformanceScanConfig] = None):
        """
        Initialize the cache analyzer service.

        Args:
            config: Performance scan configuration. Uses defaults if not provided.
        """
        self.config = config or PerformanceScanConfig()
        self.patterns = list(CACHE_PATTERNS)

    def scan(self, scan_path: Optional[Path] = None) -> CacheReport:
        """
        Scan the specified path for caching performance issues.

        Args:
            scan_path: Root path to scan. Uses config path if not provided.

        Returns:
            CacheReport containing all findings
        """
        path = scan_path or self.config.scan_path
        path = Path(path).resolve()

        if not path.exists():
            raise FileNotFoundError(f"Scan path does not exist: {path}")

        start_time = time.time()

        report = CacheReport(
            scan_path=str(path),
        )

        cache_systems: Set[str] = set()

        for file_path in scan_directory_for_performance(
            path,
            exclude_patterns=self.config.exclude_patterns,
            include_extensions=self.config.include_extensions,
        ):
            report.total_files_scanned += 1

            detected = self._detect_cache_systems(file_path)
            cache_systems.update(detected)

            findings = self._scan_file(file_path, path)

            for finding in findings:
                if self._severity_meets_threshold(finding.severity):
                    report.add_finding(finding)

        report.cache_systems_detected = sorted(list(cache_systems))
        report.scan_duration_seconds = time.time() - start_time

        report.findings.sort(
            key=lambda f: (
                self._severity_order(f.severity),
                f.file_path,
                f.line_number,
            )
        )

        return report

    def _detect_cache_systems(self, file_path: Path) -> Set[str]:
        """Detect which caching systems are being used."""
        systems: Set[str] = set()

        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read(5000)

            if "import redis" in content or "from redis" in content:
                systems.add("Redis")
            if "memcache" in content.lower():
                systems.add("Memcached")
            if "@lru_cache" in content or "@cache" in content:
                systems.add("Python functools cache")
            if "from django.core.cache" in content:
                systems.add("Django Cache")
            if "Flask-Caching" in content or "flask_caching" in content:
                systems.add("Flask-Caching")
            if "localStorage" in content or "sessionStorage" in content:
                systems.add("Browser Storage")
            if "IndexedDB" in content or "indexedDB" in content:
                systems.add("IndexedDB")

        except (IOError, OSError):
            pass

        return systems

    def _scan_file(self, file_path: Path, root_path: Path) -> List[CacheFinding]:
        """
        Scan a single file for caching issues.

        Args:
            file_path: Path to the file to scan
            root_path: Root path for relative path calculation

        Returns:
            List of cache findings in the file
        """
        findings: List[CacheFinding] = []

        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except (IOError, OSError):
            return findings

        lines = content.split("\n")
        file_ext = file_path.suffix.lower()

        for pattern in self.patterns:
            if pattern.file_types and file_ext not in pattern.file_types:
                continue

            for match in pattern.pattern.finditer(content):
                line_number, column = find_line_column(content, match.start())

                if self._is_in_comment(lines, line_number):
                    continue

                code_snippet = extract_code_snippet(lines, line_number)

                finding = CacheFinding(
                    file_path=str(file_path.relative_to(root_path)),
                    line_number=line_number,
                    issue_type=pattern.issue_type,
                    severity=pattern.severity,
                    description=pattern.description,
                    cache_pattern=pattern.name,
                    estimated_impact=pattern.estimated_impact,
                    recommendation=pattern.recommendation,
                    code_snippet=code_snippet,
                )

                findings.append(finding)

        return findings

    def _is_in_comment(self, lines: List[str], line_number: int) -> bool:
        """Check if a line is inside a comment."""
        if line_number < 1 or line_number > len(lines):
            return False

        line = lines[line_number - 1].strip()

        if line.startswith("#") or line.startswith("//") or line.startswith("*"):
            return True

        return False

    def _severity_meets_threshold(self, severity: str) -> bool:
        """Check if a severity level meets the configured threshold."""
        severity_order = {
            PerformanceSeverity.INFO.value: 0,
            PerformanceSeverity.LOW.value: 1,
            PerformanceSeverity.MEDIUM.value: 2,
            PerformanceSeverity.HIGH.value: 3,
            PerformanceSeverity.CRITICAL.value: 4,
        }

        min_level = severity_order.get(self.config.min_severity, 1)
        finding_level = severity_order.get(severity, 1)

        return finding_level >= min_level

    def _severity_order(self, severity: str) -> int:
        """Get sort order for severity (critical first)."""
        order = {
            PerformanceSeverity.CRITICAL.value: 0,
            PerformanceSeverity.HIGH.value: 1,
            PerformanceSeverity.MEDIUM.value: 2,
            PerformanceSeverity.LOW.value: 3,
            PerformanceSeverity.INFO.value: 4,
        }
        return order.get(severity, 5)
