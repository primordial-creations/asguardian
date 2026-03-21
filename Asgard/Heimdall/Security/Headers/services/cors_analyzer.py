"""
Heimdall CORS Analyzer Service

Service for analyzing CORS configuration security.
"""

import re
import time
from pathlib import Path
from typing import List, Optional

from Asgard.Heimdall.Security.Headers.models.header_models import (
    HeaderConfig,
    HeaderFinding,
    HeaderFindingType,
    HeaderReport,
)
from Asgard.Heimdall.Security.Headers.services._cors_patterns import (
    CORS_PATTERNS,
    CORSPattern,
)
from Asgard.Heimdall.Security.models.security_models import SecuritySeverity
from Asgard.Heimdall.Security.utilities.security_utils import (
    extract_code_snippet,
    find_line_column,
    scan_directory_for_security,
)


class CORSAnalyzer:
    """
    Analyzes CORS configurations for security issues.

    Detects:
    - Wildcard origin allowance
    - Credentials with wildcard
    - Origin reflection without validation
    - Overly permissive methods/headers
    """

    def __init__(self, config: Optional[HeaderConfig] = None):
        """
        Initialize the CORS analyzer.

        Args:
            config: Header configuration. Uses defaults if not provided.
        """
        self.config = config or HeaderConfig()
        self.patterns = CORS_PATTERNS

    def scan(self, scan_path: Optional[Path] = None) -> HeaderReport:
        """
        Scan the specified path for CORS security issues.

        Args:
            scan_path: Root path to scan. Uses config path if not provided.

        Returns:
            HeaderReport containing all findings
        """
        path = scan_path or self.config.scan_path
        path = Path(path).resolve()

        if not path.exists():
            raise FileNotFoundError(f"Scan path does not exist: {path}")

        start_time = time.time()

        report = HeaderReport(scan_path=str(path))

        for file_path in scan_directory_for_security(
            path,
            exclude_patterns=self.config.exclude_patterns,
            include_extensions=[".py", ".js", ".ts", ".conf", ".yaml", ".yml", ".json"],
        ):
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

    def _scan_file(self, file_path: Path, root_path: Path) -> List[HeaderFinding]:
        """
        Scan a single file for CORS security issues.

        Args:
            file_path: Path to the file to scan
            root_path: Root path for relative path calculation

        Returns:
            List of header findings in the file
        """
        findings: List[HeaderFinding] = []

        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except (IOError, OSError):
            return findings

        lines = content.split("\n")

        for pattern in self.patterns:
            for match in pattern.pattern.finditer(content):
                line_number, column = find_line_column(content, match.start())

                if self._is_in_comment(lines, line_number):
                    continue

                code_snippet = extract_code_snippet(lines, line_number)

                finding = HeaderFinding(
                    file_path=str(file_path.relative_to(root_path)),
                    line_number=line_number,
                    column_start=column,
                    column_end=column + len(match.group(0)),
                    finding_type=pattern.finding_type,
                    severity=pattern.severity,
                    title=pattern.title,
                    description=pattern.description,
                    code_snippet=code_snippet,
                    header_name="Access-Control-Allow-Origin",
                    cwe_id=pattern.cwe_id,
                    confidence=pattern.confidence,
                    remediation=pattern.remediation,
                    references=[
                        f"https://cwe.mitre.org/data/definitions/{pattern.cwe_id.replace('CWE-', '')}.html",
                        "https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS",
                    ],
                )

                findings.append(finding)

        vary_findings = self._check_missing_vary(content, lines, file_path, root_path)
        findings.extend(vary_findings)

        return findings

    def _check_missing_vary(
        self,
        content: str,
        lines: List[str],
        file_path: Path,
        root_path: Path,
    ) -> List[HeaderFinding]:
        """
        Check for missing Vary header when CORS is used.

        Args:
            content: File content
            lines: File lines
            file_path: Path to file
            root_path: Root path

        Returns:
            List of findings for missing Vary header
        """
        findings = []

        cors_pattern = re.compile(
            r"""Access-Control-Allow-Origin""",
            re.IGNORECASE
        )

        if cors_pattern.search(content):
            vary_pattern = re.compile(r"""Vary['":\s]+Origin""", re.IGNORECASE)

            if not vary_pattern.search(content):
                match = cors_pattern.search(content)
                if match:
                    line_number, column = find_line_column(content, match.start())
                    code_snippet = extract_code_snippet(lines, line_number)

                    findings.append(HeaderFinding(
                        file_path=str(file_path.relative_to(root_path)),
                        line_number=line_number,
                        finding_type=HeaderFindingType.CORS_MISSING_VARY,
                        severity=SecuritySeverity.LOW,
                        title="CORS Missing Vary Header",
                        description="When using CORS, the Vary: Origin header should be set to prevent cache poisoning.",
                        code_snippet=code_snippet,
                        header_name="Vary",
                        cwe_id="CWE-525",
                        confidence=0.6,
                        remediation="Add 'Vary: Origin' header when Access-Control-Allow-Origin is dynamic.",
                        references=[
                            "https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS",
                        ],
                    ))

        return findings

    def _is_in_comment(self, lines: List[str], line_number: int) -> bool:
        """Check if a line is inside a comment."""
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
