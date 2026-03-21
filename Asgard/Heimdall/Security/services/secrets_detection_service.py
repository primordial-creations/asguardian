"""
Heimdall Secrets Detection Service

Service for detecting hardcoded secrets, API keys, passwords, and other sensitive
data in source code files.
"""

import time
from pathlib import Path
from typing import List, Optional

from Asgard.Heimdall.Security.models.security_models import (
    SecretFinding,
    SecretType,
    SecretsReport,
    SecurityScanConfig,
    SecuritySeverity,
)
from Asgard.Heimdall.Security.services._secret_patterns import (
    SecretPattern,
    DEFAULT_SECRET_PATTERNS,
)
from Asgard.Heimdall.Security.services._secrets_detection_helpers import (
    calculate_confidence,
    is_false_positive,
    sanitize_line,
    severity_meets_threshold,
    severity_order,
)
from Asgard.Heimdall.Security.utilities.security_utils import (
    calculate_entropy,
    extract_code_snippet,
    find_line_column,
    is_in_comment_or_docstring,
    is_example_or_placeholder,
    mask_secret,
    scan_directory_for_security,
)


class SecretsDetectionService:
    """
    Detects hardcoded secrets and sensitive data in source code.

    Supports detection of:
    - API keys (AWS, Azure, GCP, generic)
    - Passwords and credentials
    - Private keys and certificates
    - Database connection strings
    - OAuth/JWT tokens
    - Service-specific tokens (GitHub, Slack, Stripe, etc.)
    """

    def __init__(self, config: Optional[SecurityScanConfig] = None):
        """
        Initialize the secrets detection service.

        Args:
            config: Security scan configuration. Uses defaults if not provided.
        """
        self.config = config or SecurityScanConfig()
        self.patterns = list(DEFAULT_SECRET_PATTERNS)

        for name, pattern in self.config.custom_patterns.items():
            self.patterns.append(
                SecretPattern(
                    name=f"custom_{name}",
                    pattern=pattern,
                    secret_type=SecretType.GENERIC_SECRET,
                    severity=SecuritySeverity.HIGH,
                    description=f"Custom pattern: {name}",
                )
            )

    def scan(self, scan_path: Optional[Path] = None) -> SecretsReport:
        """
        Scan the specified path for hardcoded secrets.

        Args:
            scan_path: Root path to scan. Uses config path if not provided.

        Returns:
            SecretsReport containing all findings
        """
        path = scan_path or self.config.scan_path
        path = Path(path).resolve()

        if not path.exists():
            raise FileNotFoundError(f"Scan path does not exist: {path}")

        start_time = time.time()

        report = SecretsReport(
            scan_path=str(path),
            patterns_used=[p.name for p in self.patterns],
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

    def _scan_file(self, file_path: Path, root_path: Path) -> List[SecretFinding]:
        """
        Scan a single file for secrets.

        Args:
            file_path: Path to the file to scan
            root_path: Root path for relative path calculation

        Returns:
            List of secret findings in the file
        """
        findings: List[SecretFinding] = []

        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except (IOError, OSError):
            return findings

        lines = content.split("\n")
        file_ext = file_path.suffix.lower()

        for pattern in self.patterns:
            for match in pattern.pattern.finditer(content):
                matched_text = match.group(0)
                secret_value = match.group(1) if match.lastindex and match.lastindex >= 1 else matched_text

                line_number, column = find_line_column(content, match.start())

                if is_in_comment_or_docstring(content, lines, line_number, match.start(), file_ext):
                    continue

                context_start = max(0, match.start() - 200)
                context_end = min(len(content), match.end() + 100)
                context = content[context_start:context_end]

                if is_example_or_placeholder(secret_value, context):
                    continue

                if is_false_positive(secret_value, matched_text, content, match.start()):
                    continue

                entropy = None
                if pattern.min_entropy > 0:
                    entropy = calculate_entropy(secret_value)
                    if entropy < pattern.min_entropy:
                        continue

                line_content = lines[line_number - 1] if line_number <= len(lines) else ""

                finding = SecretFinding(
                    file_path=str(file_path.relative_to(root_path)),
                    line_number=line_number,
                    column_start=column,
                    column_end=column + len(matched_text),
                    secret_type=pattern.secret_type,
                    severity=pattern.severity,
                    pattern_name=pattern.name,
                    masked_value=mask_secret(secret_value),
                    line_content=sanitize_line(line_content, secret_value),
                    confidence=calculate_confidence(pattern, secret_value, entropy),
                    remediation=pattern.remediation or f"Remove hardcoded {pattern.description.lower()} from source code.",
                )

                findings.append(finding)

        return findings

    def add_pattern(self, pattern: SecretPattern) -> None:
        """
        Add a custom pattern to the detection list.

        Args:
            pattern: The pattern to add
        """
        self.patterns.append(pattern)

    def get_patterns(self) -> List[str]:
        """
        Get list of pattern names being used.

        Returns:
            List of pattern names
        """
        return [p.name for p in self.patterns]
