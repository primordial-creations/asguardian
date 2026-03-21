"""
Heimdall TLS Cipher Validator Service

Service for detecting weak cipher suites in TLS/SSL configurations.
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
from Asgard.Heimdall.Security.TLS.services._cipher_patterns import (
    CIPHER_PATTERNS,
    CipherPattern,
)
from Asgard.Heimdall.Security.TLS.utilities.ssl_utils import (
    find_cipher_suite_usage,
    is_weak_cipher,
)
from Asgard.Heimdall.Security.models.security_models import SecuritySeverity
from Asgard.Heimdall.Security.utilities.security_utils import (
    extract_code_snippet,
    find_line_column,
    scan_directory_for_security,
)


class CipherValidator:
    """
    Validates cipher suite usage for security issues.

    Detects:
    - DES/3DES cipher usage
    - RC4/RC2 cipher usage
    - NULL/EXPORT ciphers
    - Anonymous cipher suites
    - Weak DH parameters
    """

    def __init__(self, config: Optional[TLSConfig] = None):
        """
        Initialize the cipher validator.

        Args:
            config: TLS configuration. Uses defaults if not provided.
        """
        self.config = config or TLSConfig()
        self.patterns = CIPHER_PATTERNS

    def scan(self, scan_path: Optional[Path] = None) -> TLSReport:
        """
        Scan the specified path for weak cipher suite usage.

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
            include_extensions=[".py", ".js", ".ts", ".yaml", ".yml", ".json", ".conf"],
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
        Scan a single file for weak cipher usage.

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
                    finding_type=TLSFindingType.WEAK_CIPHER,
                    severity=pattern.severity,
                    title=pattern.title,
                    description=pattern.description,
                    code_snippet=code_snippet,
                    cipher_suite=pattern.cipher_name,
                    cwe_id=pattern.cwe_id,
                    confidence=pattern.confidence,
                    remediation=pattern.remediation,
                    references=[
                        f"https://cwe.mitre.org/data/definitions/{pattern.cwe_id.replace('CWE-', '')}.html",
                        "https://wiki.mozilla.org/Security/Server_Side_TLS",
                    ],
                )

                findings.append(finding)

        cipher_usage_findings = self._check_cipher_usage(content, lines, file_path, root_path)
        findings.extend(cipher_usage_findings)

        return findings

    def _check_cipher_usage(
        self,
        content: str,
        lines: List[str],
        file_path: Path,
        root_path: Path,
    ) -> List[TLSFinding]:
        """
        Check for weak ciphers in cipher suite specifications.

        Args:
            content: File content
            lines: File lines
            file_path: Path to file
            root_path: Root path

        Returns:
            List of findings for weak cipher usage
        """
        findings = []

        cipher_usages = find_cipher_suite_usage(content)

        for line_number, cipher_string, context in cipher_usages:
            weak, weak_ciphers = is_weak_cipher(cipher_string)

            if weak:
                code_snippet = extract_code_snippet(lines, line_number)

                finding = TLSFinding(
                    file_path=str(file_path.relative_to(root_path)),
                    line_number=line_number,
                    finding_type=TLSFindingType.WEAK_CIPHER,
                    severity=SecuritySeverity.HIGH,
                    title="Weak Cipher Suites in Configuration",
                    description=f"Cipher configuration includes weak ciphers: {', '.join(weak_ciphers)}",
                    code_snippet=code_snippet,
                    cipher_suite=", ".join(weak_ciphers),
                    cwe_id="CWE-327",
                    confidence=0.85,
                    remediation=(
                        "Remove weak ciphers from the cipher suite configuration. "
                        "Use only: ECDHE+AESGCM:DHE+AESGCM:ECDHE+CHACHA20:DHE+CHACHA20"
                    ),
                    references=[
                        "https://cwe.mitre.org/data/definitions/327.html",
                        "https://wiki.mozilla.org/Security/Server_Side_TLS",
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
