"""
Heimdall Injection Detection Service

Service for detecting injection vulnerabilities including SQL injection,
XSS (Cross-Site Scripting), command injection, and other injection patterns.
"""

import time
from pathlib import Path
from typing import List, Optional

from Asgard.Heimdall.Security.models.security_models import (
    SecurityScanConfig,
    SecuritySeverity,
    VulnerabilityFinding,
    VulnerabilityReport,
    VulnerabilityType,
)
from Asgard.Heimdall.Security.utilities.security_utils import (
    extract_code_snippet,
    find_line_column,
    is_in_comment_or_docstring,
    is_parameterized_sql,
    scan_directory_for_security,
)
from Asgard.Heimdall.Security.services._injection_patterns import (
    InjectionPattern,
    SQL_INJECTION_PATTERNS,
    XSS_PATTERNS,
    COMMAND_INJECTION_PATTERNS,
    PATH_TRAVERSAL_PATTERNS,
)


class InjectionDetectionService:
    """
    Detects injection vulnerabilities in source code.

    Supports detection of:
    - SQL Injection
    - Cross-Site Scripting (XSS)
    - Command Injection
    - Path Traversal
    - Code Injection
    """

    def __init__(self, config: Optional[SecurityScanConfig] = None):
        """
        Initialize the injection detection service.

        Args:
            config: Security scan configuration. Uses defaults if not provided.
        """
        self.config = config or SecurityScanConfig()
        self.patterns: List[InjectionPattern] = (
            SQL_INJECTION_PATTERNS +
            XSS_PATTERNS +
            COMMAND_INJECTION_PATTERNS +
            PATH_TRAVERSAL_PATTERNS
        )

    def scan(self, scan_path: Optional[Path] = None) -> VulnerabilityReport:
        """
        Scan the specified path for injection vulnerabilities.

        Args:
            scan_path: Root path to scan. Uses config path if not provided.

        Returns:
            VulnerabilityReport containing all findings
        """
        path = scan_path or self.config.scan_path
        path = Path(path).resolve()

        if not path.exists():
            raise FileNotFoundError(f"Scan path does not exist: {path}")

        start_time = time.time()

        report = VulnerabilityReport(
            scan_path=str(path),
        )

        for file_path in scan_directory_for_security(
            path,
            exclude_patterns=self.config.exclude_patterns,
            include_extensions=self.config.include_extensions,
        ):
            if str(file_path) in self.config.ignore_paths:
                continue

            report.total_files_scanned += 1
            findings = self._scan_file(file_path, path)

            for finding in findings:
                if self._severity_meets_threshold(finding.severity):
                    report.add_finding(finding)

        report.scan_duration_seconds = time.time() - start_time

        report.findings.sort(
            key=lambda f: (
                self._severity_order(f.severity),
                f.file_path,
                f.line_number,
            )
        )

        return report

    def _scan_file(self, file_path: Path, root_path: Path) -> List[VulnerabilityFinding]:
        """
        Scan a single file for injection vulnerabilities.

        Args:
            file_path: Path to the file to scan
            root_path: Root path for relative path calculation

        Returns:
            List of vulnerability findings in the file
        """
        findings: List[VulnerabilityFinding] = []

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

                if is_in_comment_or_docstring(content, lines, line_number, match.start(), file_ext):
                    continue

                if pattern.vuln_type == VulnerabilityType.SQL_INJECTION:
                    context_start = max(0, match.start() - 50)
                    context_end = min(len(content), match.end() + 200)
                    context = content[context_start:context_end]

                    if is_parameterized_sql(match.group(0), context):
                        continue

                code_snippet = extract_code_snippet(lines, line_number)

                finding = VulnerabilityFinding(
                    file_path=str(file_path.relative_to(root_path)),
                    line_number=line_number,
                    column_start=column,
                    column_end=column + len(match.group(0)),
                    vulnerability_type=pattern.vuln_type,
                    severity=pattern.severity,
                    title=pattern.title,
                    description=pattern.description,
                    code_snippet=code_snippet,
                    cwe_id=pattern.cwe_id,
                    owasp_category=pattern.owasp_category,
                    confidence=pattern.confidence,
                    remediation=pattern.remediation,
                    references=[
                        f"https://cwe.mitre.org/data/definitions/{pattern.cwe_id.replace('CWE-', '')}.html",
                        f"https://owasp.org/Top10/{pattern.owasp_category}/",
                    ],
                )

                findings.append(finding)

        return findings

    def _is_in_comment(self, lines: List[str], line_number: int) -> bool:
        """
        Check if a line is inside a comment.

        Args:
            lines: List of file lines
            line_number: Line number to check (1-indexed)

        Returns:
            True if the line is a comment
        """
        if line_number < 1 or line_number > len(lines):
            return False

        line = lines[line_number - 1].strip()

        if line.startswith("#") or line.startswith("//") or line.startswith("*"):
            return True

        if line.startswith("'''") or line.startswith('"""'):
            return True

        return False

    def _severity_meets_threshold(self, severity: str) -> bool:
        """Check if a severity level meets the configured threshold."""
        severity_order = {
            SecuritySeverity.INFO.value: 0,
            SecuritySeverity.LOW.value: 1,
            SecuritySeverity.MEDIUM.value: 2,
            SecuritySeverity.HIGH.value: 3,
            SecuritySeverity.CRITICAL.value: 4,
        }

        min_level = severity_order.get(self.config.min_severity, 1)
        finding_level = severity_order.get(severity, 1)

        return finding_level >= min_level

    def _severity_order(self, severity: str) -> int:
        """Get sort order for severity (critical first)."""
        order = {
            SecuritySeverity.CRITICAL.value: 0,
            SecuritySeverity.HIGH.value: 1,
            SecuritySeverity.MEDIUM.value: 2,
            SecuritySeverity.LOW.value: 3,
            SecuritySeverity.INFO.value: 4,
        }
        return order.get(severity, 5)

    def scan_for_sql_injection(self, scan_path: Optional[Path] = None) -> VulnerabilityReport:
        """
        Scan specifically for SQL injection vulnerabilities.

        Args:
            scan_path: Root path to scan

        Returns:
            VulnerabilityReport with SQL injection findings only
        """
        original_patterns = self.patterns
        self.patterns = SQL_INJECTION_PATTERNS

        try:
            report = self.scan(scan_path)
        finally:
            self.patterns = original_patterns

        return report

    def scan_for_xss(self, scan_path: Optional[Path] = None) -> VulnerabilityReport:
        """
        Scan specifically for XSS vulnerabilities.

        Args:
            scan_path: Root path to scan

        Returns:
            VulnerabilityReport with XSS findings only
        """
        original_patterns = self.patterns
        self.patterns = XSS_PATTERNS

        try:
            report = self.scan(scan_path)
        finally:
            self.patterns = original_patterns

        return report

    def scan_for_command_injection(self, scan_path: Optional[Path] = None) -> VulnerabilityReport:
        """
        Scan specifically for command injection vulnerabilities.

        Args:
            scan_path: Root path to scan

        Returns:
            VulnerabilityReport with command injection findings only
        """
        original_patterns = self.patterns
        self.patterns = COMMAND_INJECTION_PATTERNS + PATH_TRAVERSAL_PATTERNS

        try:
            report = self.scan(scan_path)
        finally:
            self.patterns = original_patterns

        return report
