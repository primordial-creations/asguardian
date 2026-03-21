"""
Heimdall CSP Analyzer Service

Service for analyzing Content-Security-Policy configurations.
"""

import time
from pathlib import Path
from typing import List, Optional

from Asgard.Heimdall.Security.Headers.models.header_models import (
    HeaderConfig,
    HeaderFinding,
    HeaderReport,
)
from Asgard.Heimdall.Security.Headers.services._csp_checks import (
    analyze_csp,
    check_inline_patterns,
)
from Asgard.Heimdall.Security.Headers.utilities.csp_parser import (
    ParsedCSP,
    extract_csp_from_code,
    parse_csp,
)
from Asgard.Heimdall.Security.models.security_models import SecuritySeverity
from Asgard.Heimdall.Security.utilities.security_utils import (
    extract_code_snippet,
    find_line_column,
    scan_directory_for_security,
)


class CSPAnalyzer:
    """
    Analyzes Content-Security-Policy configurations.

    Detects:
    - unsafe-inline usage
    - unsafe-eval usage
    - Wildcard sources
    - Missing directives
    - Weak CSP configurations
    """

    def __init__(self, config: Optional[HeaderConfig] = None):
        """
        Initialize the CSP analyzer.

        Args:
            config: Header configuration. Uses defaults if not provided.
        """
        self.config = config or HeaderConfig()

    def scan(self, scan_path: Optional[Path] = None) -> HeaderReport:
        """
        Scan the specified path for CSP security issues.

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
            include_extensions=[".py", ".js", ".ts", ".conf", ".yaml", ".yml", ".json", ".html"],
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
        Scan a single file for CSP issues.

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

        csp_occurrences = extract_csp_from_code(content)

        for line_number, csp_value in csp_occurrences:
            parsed_csp = parse_csp(csp_value)
            csp_findings = analyze_csp(
                parsed_csp,
                line_number,
                csp_value,
                lines,
                file_path,
                root_path,
                self.config.required_csp_directives,
            )
            findings.extend(csp_findings)

        inline_findings = check_inline_patterns(
            content, lines, file_path, root_path, self._is_in_comment
        )
        findings.extend(inline_findings)

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

    def analyze_csp_string(self, csp_string: str) -> List[str]:
        """
        Analyze a CSP string and return issues.

        Args:
            csp_string: The CSP header value

        Returns:
            List of issue descriptions
        """
        parsed = parse_csp(csp_string)
        issues = []

        for directive_name, unsafe_value in parsed.unsafe_directives:
            issues.append(f"{directive_name} contains {unsafe_value}")

        for missing in parsed.missing_recommended_directives:
            issues.append(f"Missing recommended directive: {missing}")

        return issues
