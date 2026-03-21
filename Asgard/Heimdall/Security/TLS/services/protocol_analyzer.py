"""
Heimdall TLS Protocol Analyzer Service

Service for detecting deprecated TLS/SSL protocol versions.
"""

import time
from pathlib import Path
from typing import List, Optional

from Asgard.Heimdall.Security.TLS.models.tls_models import (
    TLSConfig,
    TLSFinding,
    TLSFindingType,
    TLSReport,
)
from Asgard.Heimdall.Security.TLS.services._protocol_patterns import (
    PROTOCOL_PATTERNS,
    ProtocolPattern,
)
from Asgard.Heimdall.Security.TLS.utilities.ssl_utils import (
    find_tls_version_usage,
    is_deprecated_protocol,
)
from Asgard.Heimdall.Security.models.security_models import SecuritySeverity
from Asgard.Heimdall.Security.utilities.security_utils import (
    extract_code_snippet,
    find_line_column,
    scan_directory_for_security,
)


class ProtocolAnalyzer:
    """
    Analyzes TLS/SSL protocol usage for security issues.

    Detects:
    - SSLv2/SSLv3 usage
    - TLS 1.0/1.1 usage
    - Deprecated protocol configurations
    """

    def __init__(self, config: Optional[TLSConfig] = None):
        """
        Initialize the protocol analyzer.

        Args:
            config: TLS configuration. Uses defaults if not provided.
        """
        self.config = config or TLSConfig()
        self.patterns = PROTOCOL_PATTERNS

    def scan(self, scan_path: Optional[Path] = None) -> TLSReport:
        """
        Scan the specified path for deprecated TLS/SSL protocol usage.

        Args:
            scan_path: Root path to scan. Uses config path if not provided.

        Returns:
            TLSReport containing all findings
        """
        path = scan_path or self.config.scan_path
        path = Path(path).resolve()

        if not path.exists():
            raise FileNotFoundError(f"Scan path does not exist: {path}")

        start_time = time.time()

        report = TLSReport(scan_path=str(path))

        for file_path in scan_directory_for_security(
            path,
            exclude_patterns=self.config.exclude_patterns,
            include_extensions=[".py", ".js", ".ts"],
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

    def _scan_file(self, file_path: Path, root_path: Path) -> List[TLSFinding]:
        """
        Scan a single file for deprecated protocol usage.

        Args:
            file_path: Path to the file to scan
            root_path: Root path for relative path calculation

        Returns:
            List of TLS findings in the file
        """
        findings: List[TLSFinding] = []

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

                finding = TLSFinding(
                    file_path=str(file_path.relative_to(root_path)),
                    line_number=line_number,
                    column_start=column,
                    column_end=column + len(match.group(0)),
                    finding_type=TLSFindingType.DEPRECATED_TLS_VERSION,
                    severity=pattern.severity,
                    title=pattern.title,
                    description=pattern.description,
                    code_snippet=code_snippet,
                    protocol_version=pattern.protocol_version,
                    cwe_id=pattern.cwe_id,
                    confidence=pattern.confidence,
                    remediation=pattern.remediation,
                    references=[
                        f"https://cwe.mitre.org/data/definitions/{pattern.cwe_id.replace('CWE-', '')}.html",
                        "https://tools.ietf.org/html/rfc8996",
                    ],
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
