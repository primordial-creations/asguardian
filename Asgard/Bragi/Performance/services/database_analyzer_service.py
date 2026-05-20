"""
Heimdall Database Analyzer Service

Service for static analysis of database-related performance issues
in source code, particularly ORM anti-patterns.
"""

import re
import time
from pathlib import Path
from typing import List, Optional, Set

from Asgard.Bragi.Performance.models.performance_models import (
    DatabaseFinding,
    DatabaseIssueType,
    DatabaseReport,
    PerformanceScanConfig,
    PerformanceSeverity,
)
from Asgard.Bragi.Performance.utilities.performance_utils import (
    extract_code_snippet,
    find_line_column,
    scan_directory_for_performance,
)


class DatabasePattern:
    """Defines a pattern for detecting database performance issues."""

    def __init__(
        self,
        name: str,
        pattern: str,
        issue_type: DatabaseIssueType,
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
        self.file_types = file_types or {".py"}


DATABASE_PATTERNS: List[DatabasePattern] = [
    DatabasePattern(
        name="objects_all_no_filter",
        pattern=r"""\.objects\.all\(\)\s*$""",
        issue_type=DatabaseIssueType.FULL_TABLE_SCAN,
        severity=PerformanceSeverity.MEDIUM,
        description="Fetching all objects without filtering may load entire table.",
        estimated_impact="Memory and time proportional to table size",
        recommendation="Add filters, limits, or use pagination.",
    ),
    DatabasePattern(
        name="cursor_execute",
        pattern=r"""cursor\.execute\s*\(""",
        issue_type=DatabaseIssueType.N_PLUS_ONE,
        severity=PerformanceSeverity.MEDIUM,
        description="Raw SQL cursor execute - check if inside loop.",
        estimated_impact="Potential N+1 if in loop",
        recommendation="Use batch queries or parameterized bulk operations.",
    ),
    DatabasePattern(
        name="like_leading_wildcard",
        pattern=r"""LIKE\s*['\"]%""",
        issue_type=DatabaseIssueType.FULL_TABLE_SCAN,
        severity=PerformanceSeverity.MEDIUM,
        description="LIKE with leading wildcard cannot use index.",
        estimated_impact="Full table scan required",
        recommendation="Use full-text search, trigram indexes, or reverse the pattern.",
    ),
    DatabasePattern(
        name="select_star",
        pattern=r"""SELECT\s+\*\s+FROM""",
        issue_type=DatabaseIssueType.FULL_TABLE_SCAN,
        severity=PerformanceSeverity.LOW,
        description="Selecting all columns when only some may be needed.",
        estimated_impact="Extra data transferred and processed",
        recommendation="Select only required columns.",
    ),
    DatabasePattern(
        name="distinct_keyword",
        pattern=r"""DISTINCT\s+""",
        issue_type=DatabaseIssueType.MISSING_INDEX,
        severity=PerformanceSeverity.LOW,
        description="DISTINCT may require sorting if not indexed.",
        estimated_impact="Full sort of result set",
        recommendation="Ensure columns have appropriate indexes or use GROUP BY.",
    ),
    DatabasePattern(
        name="django_bulk_create",
        pattern=r"""\.save\(\)\s*$""",
        issue_type=DatabaseIssueType.EXCESSIVE_QUERIES,
        severity=PerformanceSeverity.LOW,
        description="Individual save() - consider bulk_create for batch inserts.",
        estimated_impact="One query per object",
        recommendation="Use bulk_create() for multiple objects.",
    ),
]


class DatabaseAnalyzerService:
    """
    Static analysis service for database-related performance issues.

    Detects:
    - N+1 query problems
    - Missing eager loading
    - Full table scans
    - Inefficient query patterns
    - Bulk operation opportunities
    """

    def __init__(self, config: Optional[PerformanceScanConfig] = None):
        """
        Initialize the database analyzer service.

        Args:
            config: Performance scan configuration. Uses defaults if not provided.
        """
        self.config = config or PerformanceScanConfig()
        self.patterns = list(DATABASE_PATTERNS)

    def scan(self, scan_path: Optional[Path] = None) -> DatabaseReport:
        """
        Scan the specified path for database performance issues.

        Args:
            scan_path: Root path to scan. Uses config path if not provided.

        Returns:
            DatabaseReport containing all findings
        """
        path = scan_path or self.config.scan_path
        path = Path(path).resolve()

        if not path.exists():
            raise FileNotFoundError(f"Scan path does not exist: {path}")

        start_time = time.time()

        report = DatabaseReport(
            scan_path=str(path),
        )

        orm_detected = None

        for file_path in scan_directory_for_performance(
            path,
            exclude_patterns=self.config.exclude_patterns,
            include_extensions=self.config.include_extensions,
        ):
            report.total_files_scanned += 1

            if not orm_detected:
                orm_detected = self._detect_orm(file_path)

            findings = self._scan_file(file_path, path)

            for finding in findings:
                if self._severity_meets_threshold(finding.severity):
                    report.add_finding(finding)

        report.orm_detected = orm_detected
        report.scan_duration_seconds = time.time() - start_time

        report.findings.sort(
            key=lambda f: (
                self._severity_order(f.severity),
                f.file_path,
                f.line_number,
            )
        )

        return report

    def _detect_orm(self, file_path: Path) -> Optional[str]:
        """Detect which ORM framework is being used."""
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read(5000)

            if "from django" in content or "django.db" in content:
                return "Django ORM"
            elif "from sqlalchemy" in content or "sqlalchemy" in content:
                return "SQLAlchemy"
            elif "from peewee" in content:
                return "Peewee"
            elif "from tortoise" in content:
                return "Tortoise ORM"
            elif "from prisma" in content:
                return "Prisma"
        except (IOError, OSError):
            pass

        return None

    def _scan_file(self, file_path: Path, root_path: Path) -> List[DatabaseFinding]:
        """
        Scan a single file for database issues.

        Args:
            file_path: Path to the file to scan
            root_path: Root path for relative path calculation

        Returns:
            List of database findings in the file
        """
        findings: List[DatabaseFinding] = []

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

                finding = DatabaseFinding(
                    file_path=str(file_path.relative_to(root_path)),
                    line_number=line_number,
                    issue_type=pattern.issue_type,
                    severity=pattern.severity,
                    description=pattern.description,
                    query_pattern=pattern.name,
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
