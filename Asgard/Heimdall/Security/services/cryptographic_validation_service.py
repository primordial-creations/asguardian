"""
Heimdall Cryptographic Validation Service

Service for detecting insecure cryptographic implementations,
weak algorithms, and cryptographic anti-patterns.
"""

import time
from pathlib import Path
from typing import List, Optional

from Asgard.Heimdall.Security.models.security_models import (
    CryptoFinding,
    CryptoReport,
    SecurityScanConfig,
)
from Asgard.Heimdall.Security.services._crypto_patterns import (
    CryptoPattern,
    CRYPTO_PATTERNS,
)
from Asgard.Heimdall.Security.services._crypto_validation_helpers import (
    get_secure_recommendations,
    is_in_test_context,
    is_iv_nonce_false_positive,
    severity_meets_threshold,
    severity_order,
)
from Asgard.Heimdall.Security.utilities.security_utils import (
    extract_code_snippet,
    find_line_column,
    is_in_comment_or_docstring,
    scan_directory_for_security,
)


class CryptographicValidationService:
    """
    Validates cryptographic implementations in source code.

    Detects:
    - Weak hash algorithms (MD5, SHA-1)
    - Deprecated ciphers (DES, 3DES)
    - Insecure cipher modes (ECB)
    - Static IVs and hardcoded keys
    - Weak random number generators
    - Insufficient key sizes
    - Improper password hashing
    - SSL/TLS misconfigurations
    - JWT vulnerabilities
    """

    def __init__(self, config: Optional[SecurityScanConfig] = None):
        """
        Initialize the cryptographic validation service.

        Args:
            config: Security scan configuration. Uses defaults if not provided.
        """
        self.config = config or SecurityScanConfig()
        self.patterns = list(CRYPTO_PATTERNS)

    def scan(self, scan_path: Optional[Path] = None) -> CryptoReport:
        """
        Scan the specified path for cryptographic issues.

        Args:
            scan_path: Root path to scan. Uses config path if not provided.

        Returns:
            CryptoReport containing all findings
        """
        path = scan_path or self.config.scan_path
        path = Path(path).resolve()

        if not path.exists():
            raise FileNotFoundError(f"Scan path does not exist: {path}")

        start_time = time.time()

        report = CryptoReport(
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
                if severity_meets_threshold(finding.severity, self.config.min_severity):
                    report.add_finding(finding)

        report.scan_duration_seconds = time.time() - start_time

        report.findings.sort(
            key=lambda f: (
                severity_order(f.severity),
                f.file_path,
                f.line_number,
            )
        )

        return report

    def _scan_file(self, file_path: Path, root_path: Path) -> List[CryptoFinding]:
        """
        Scan a single file for cryptographic issues.

        Args:
            file_path: Path to the file to scan
            root_path: Root path for relative path calculation

        Returns:
            List of cryptographic findings in the file
        """
        findings: List[CryptoFinding] = []

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

                if is_in_test_context(file_path, lines, line_number):
                    continue

                if pattern.name == "static_iv":
                    if is_iv_nonce_false_positive(content, match.start(), lines, line_number):
                        continue

                code_snippet = extract_code_snippet(lines, line_number)

                finding = CryptoFinding(
                    file_path=str(file_path.relative_to(root_path)),
                    line_number=line_number,
                    issue_type=pattern.issue_type,
                    severity=pattern.severity,
                    algorithm=pattern.algorithm,
                    description=pattern.description,
                    recommendation=pattern.recommendation,
                    code_snippet=code_snippet,
                )

                findings.append(finding)

        return findings

    def add_pattern(self, pattern: CryptoPattern) -> None:
        """
        Add a custom pattern to the detection list.

        Args:
            pattern: The pattern to add
        """
        self.patterns.append(pattern)

    def get_secure_recommendations(self) -> dict:
        """
        Get recommendations for secure cryptographic implementations.

        Returns:
            Dictionary of recommendations by category
        """
        return get_secure_recommendations()
