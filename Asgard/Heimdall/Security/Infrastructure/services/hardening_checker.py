"""
Heimdall Hardening Checker Service

Service for checking infrastructure hardening best practices.
"""

import re
import time
from pathlib import Path
from typing import List, Optional

from Asgard.Heimdall.Security.Infrastructure.models.infra_models import (
    InfraConfig,
    InfraFinding,
    InfraFindingType,
    InfraReport,
)
from Asgard.Heimdall.Security.Infrastructure.services._hardening_patterns import (
    HARDENING_PATTERNS,
    HardeningPattern,
)
from Asgard.Heimdall.Security.models.security_models import SecuritySeverity
from Asgard.Heimdall.Security.utilities.security_utils import (
    extract_code_snippet,
    find_line_column,
    scan_directory_for_security,
)


class HardeningChecker:
    """
    Checks infrastructure for hardening best practices.

    Detects:
    - Exposed debug/admin endpoints
    - World-writable file permissions
    - Insecure transport settings
    - Docker security misconfigurations
    - Web server security issues
    """

    def __init__(self, config: Optional[InfraConfig] = None):
        """
        Initialize the hardening checker.

        Args:
            config: Infrastructure configuration. Uses defaults if not provided.
        """
        self.config = config or InfraConfig()
        self.patterns = HARDENING_PATTERNS

    def scan(self, scan_path: Optional[Path] = None) -> InfraReport:
        """
        Scan the specified path for hardening issues.

        Args:
            scan_path: Root path to scan. Uses config path if not provided.

        Returns:
            InfraReport containing all findings
        """
        path = scan_path or self.config.scan_path
        path = Path(path).resolve()

        if not path.exists():
            raise FileNotFoundError(f"Scan path does not exist: {path}")

        start_time = time.time()

        report = InfraReport(scan_path=str(path))

        for file_path in scan_directory_for_security(
            path,
            exclude_patterns=self.config.exclude_patterns,
        ):
            report.total_files_scanned += 1

            if self._is_config_file(file_path):
                report.total_config_files += 1

            findings = self._scan_file(file_path, path)

            for finding in findings:
                if self._severity_meets_threshold(finding.severity):
                    report.add_finding(finding)

        findings_from_routes = self._check_debug_endpoints(path, report)
        for finding in findings_from_routes:
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

    def _scan_file(self, file_path: Path, root_path: Path) -> List[InfraFinding]:
        """
        Scan a single file for hardening issues.

        Args:
            file_path: Path to the file to scan
            root_path: Root path for relative path calculation

        Returns:
            List of infrastructure findings in the file
        """
        findings: List[InfraFinding] = []

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

                finding = InfraFinding(
                    file_path=str(file_path.relative_to(root_path)),
                    line_number=line_number,
                    column_start=column,
                    column_end=column + len(match.group(0)),
                    finding_type=pattern.finding_type,
                    severity=pattern.severity,
                    title=pattern.title,
                    description=pattern.description,
                    code_snippet=code_snippet,
                    cwe_id=pattern.cwe_id,
                    confidence=pattern.confidence,
                    remediation=pattern.remediation,
                    references=[
                        f"https://cwe.mitre.org/data/definitions/{pattern.cwe_id.replace('CWE-', '')}.html",
                    ],
                )

                findings.append(finding)

        return findings

    def _check_debug_endpoints(self, root_path: Path, report: InfraReport) -> List[InfraFinding]:
        """
        Check for known debug endpoints in route definitions.

        Args:
            root_path: Root path to scan
            report: Current report for file tracking

        Returns:
            List of findings for exposed debug endpoints
        """
        findings: List[InfraFinding] = []

        debug_endpoints = self.config.debug_endpoints

        for file_path in scan_directory_for_security(
            root_path,
            exclude_patterns=self.config.exclude_patterns,
        ):
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
            except (IOError, OSError):
                continue

            lines = content.split("\n")

            for endpoint in debug_endpoints:
                pattern = re.compile(
                    rf"""['"](?:{re.escape(endpoint)})['"]""",
                    re.IGNORECASE
                )

                for match in pattern.finditer(content):
                    line_number, column = find_line_column(content, match.start())

                    if self._is_in_comment(lines, line_number):
                        continue

                    context_line = lines[line_number - 1] if line_number <= len(lines) else ""
                    if "route" in context_line.lower() or "path" in context_line.lower() or "@" in context_line:
                        code_snippet = extract_code_snippet(lines, line_number)

                        finding = InfraFinding(
                            file_path=str(file_path.relative_to(root_path)),
                            line_number=line_number,
                            column_start=column,
                            column_end=column + len(match.group(0)),
                            finding_type=InfraFindingType.EXPOSED_DEBUG_ENDPOINT,
                            severity=SecuritySeverity.HIGH,
                            title=f"Exposed Debug Endpoint: {endpoint}",
                            description=f"Debug endpoint '{endpoint}' is exposed. Debug endpoints can leak sensitive information and should not be accessible in production.",
                            code_snippet=code_snippet,
                            cwe_id="CWE-489",
                            confidence=0.85,
                            remediation="Remove or restrict access to debug endpoints in production. Use authentication and IP whitelisting.",
                            references=[
                                "https://cwe.mitre.org/data/definitions/489.html",
                            ],
                        )

                        findings.append(finding)

        return findings

    def _is_config_file(self, file_path: Path) -> bool:
        """Check if a file is a configuration file."""
        return file_path.name in self.config.config_files

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
