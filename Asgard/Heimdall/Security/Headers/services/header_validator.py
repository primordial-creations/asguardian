"""
Heimdall Header Validator Service

Service for detecting missing security headers in code.
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
from Asgard.Heimdall.Security.Headers.services._header_patterns import (
    HEADER_PATTERNS,
    HeaderPattern,
)
from Asgard.Heimdall.Security.models.security_models import SecuritySeverity
from Asgard.Heimdall.Security.utilities.security_utils import (
    extract_code_snippet,
    find_line_column,
    scan_directory_for_security,
)


class HeaderValidator:
    """
    Validates security header configurations in code.

    Detects:
    - Missing security headers
    - Weak header configurations
    - Insecure cookie settings
    """

    def __init__(self, config: Optional[HeaderConfig] = None):
        """
        Initialize the header validator.

        Args:
            config: Header configuration. Uses defaults if not provided.
        """
        self.config = config or HeaderConfig()
        self.patterns = HEADER_PATTERNS

    def scan(self, scan_path: Optional[Path] = None) -> HeaderReport:
        """
        Scan the specified path for security header issues.

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
        Scan a single file for header security issues.

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
                    header_name=pattern.header_name,
                    cwe_id=pattern.cwe_id,
                    confidence=pattern.confidence,
                    remediation=pattern.remediation,
                    references=[
                        f"https://cwe.mitre.org/data/definitions/{pattern.cwe_id.replace('CWE-', '')}.html",
                    ],
                )

                findings.append(finding)

        missing_header_findings = self._check_missing_headers(content, lines, file_path, root_path)
        findings.extend(missing_header_findings)

        return findings

    def _check_missing_headers(
        self,
        content: str,
        lines: List[str],
        file_path: Path,
        root_path: Path,
    ) -> List[HeaderFinding]:
        """
        Check for missing security headers in files that configure security headers.

        Args:
            content: File content
            lines: File lines
            file_path: Path to file
            root_path: Root path

        Returns:
            List of findings for missing headers
        """
        findings: List[HeaderFinding] = []

        security_header_patterns = [
            r'Content-Security-Policy',
            r'X-Frame-Options',
            r'X-Content-Type-Options',
            r'Strict-Transport-Security',
            r'X-XSS-Protection',
            r'Referrer-Policy',
            r'add_middleware.*Security',
            r'SecurityMiddleware',
            r'helmet',
            r'secure_headers',
            r'add_header\s+(?:Content-Security-Policy|X-Frame-Options|X-Content-Type|Strict-Transport)',
            r'Header\s+(?:set|always)\s+(?:Content-Security-Policy|X-Frame-Options)',
        ]

        has_security_header_config = any(
            re.search(p, content, re.IGNORECASE) for p in security_header_patterns
        )

        if not has_security_header_config:
            return findings

        security_headers = [
            ("Content-Security-Policy", HeaderFindingType.MISSING_CSP, SecuritySeverity.HIGH),
            ("X-Frame-Options", HeaderFindingType.MISSING_X_FRAME, SecuritySeverity.MEDIUM),
            ("X-Content-Type-Options", HeaderFindingType.MISSING_X_CONTENT_TYPE, SecuritySeverity.MEDIUM),
            ("Strict-Transport-Security", HeaderFindingType.MISSING_HSTS, SecuritySeverity.MEDIUM),
            ("Referrer-Policy", HeaderFindingType.MISSING_REFERRER_POLICY, SecuritySeverity.LOW),
        ]

        for header_name, finding_type, severity in security_headers:
            if header_name.lower() not in content.lower():
                if self.config.check_csp and header_name == "Content-Security-Policy":
                    findings.append(self._create_missing_header_finding(
                        header_name, finding_type, severity, file_path, root_path
                    ))
                elif self.config.check_frame_options and header_name == "X-Frame-Options":
                    findings.append(self._create_missing_header_finding(
                        header_name, finding_type, severity, file_path, root_path
                    ))
                elif self.config.check_content_type and header_name == "X-Content-Type-Options":
                    findings.append(self._create_missing_header_finding(
                        header_name, finding_type, severity, file_path, root_path
                    ))
                elif self.config.check_hsts and header_name == "Strict-Transport-Security":
                    findings.append(self._create_missing_header_finding(
                        header_name, finding_type, severity, file_path, root_path
                    ))

        return findings

    def _create_missing_header_finding(self, header_name: str, finding_type: HeaderFindingType,
                                        severity: SecuritySeverity, file_path: Path,
                                        root_path: Path) -> HeaderFinding:
        """Create a finding for a missing security header."""
        remediation_map = {
            "Content-Security-Policy": "Add Content-Security-Policy header with appropriate directives.",
            "X-Frame-Options": "Add X-Frame-Options: DENY or X-Frame-Options: SAMEORIGIN.",
            "X-Content-Type-Options": "Add X-Content-Type-Options: nosniff.",
            "Strict-Transport-Security": "Add Strict-Transport-Security: max-age=31536000; includeSubDomains.",
            "Referrer-Policy": "Add Referrer-Policy: strict-origin-when-cross-origin.",
        }

        cwe_map = {
            "Content-Security-Policy": "CWE-693",
            "X-Frame-Options": "CWE-1021",
            "X-Content-Type-Options": "CWE-16",
            "Strict-Transport-Security": "CWE-319",
            "Referrer-Policy": "CWE-200",
        }

        return HeaderFinding(
            file_path=str(file_path.relative_to(root_path)),
            line_number=1,
            finding_type=finding_type,
            severity=severity,
            title=f"Missing {header_name} Header",
            description=f"Response configuration found but {header_name} header is not set.",
            header_name=header_name,
            cwe_id=cwe_map.get(header_name, "CWE-693"),
            confidence=0.6,
            remediation=remediation_map.get(header_name, f"Add the {header_name} security header."),
            references=[
                f"https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/{header_name}",
            ],
        )

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
