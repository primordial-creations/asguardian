"""
Heimdall JWT Validator Service

Service for detecting JWT implementation security issues.
"""

import re
import time
from pathlib import Path
from typing import List, Optional

from Asgard.Heimdall.Security.Auth.models.auth_models import (
    AuthConfig,
    AuthFinding,
    AuthFindingType,
    AuthReport,
)
from Asgard.Heimdall.Security.Auth.services._jwt_patterns import (
    ENUM_VALUE_PATTERNS,
    INTENTIONAL_NO_VERIFY_PATTERNS,
    JWT_PATTERNS,
    JWTPattern,
)
from Asgard.Heimdall.Security.Auth.utilities.token_utils import (
    extract_algorithm_from_jwt_call,
    find_token_expiration,
)
from Asgard.Heimdall.Security.models.security_models import SecuritySeverity
from Asgard.Heimdall.Security.utilities.security_utils import (
    extract_code_snippet,
    find_line_column,
    is_in_comment_or_docstring,
    scan_directory_for_security,
)


class JWTValidator:
    """
    Validates JWT implementation security.

    Detects:
    - Weak or 'none' algorithms
    - Missing token expiration
    - Hardcoded secrets
    - Disabled signature verification
    """

    def __init__(self, config: Optional[AuthConfig] = None):
        """
        Initialize the JWT validator.

        Args:
            config: Auth configuration. Uses defaults if not provided.
        """
        self.config = config or AuthConfig()
        self.patterns = JWT_PATTERNS

    def scan(self, scan_path: Optional[Path] = None) -> AuthReport:
        """
        Scan the specified path for JWT security issues.

        Args:
            scan_path: Root path to scan. Uses config path if not provided.

        Returns:
            AuthReport containing all findings
        """
        path = scan_path or self.config.scan_path
        path = Path(path).resolve()

        if not path.exists():
            raise FileNotFoundError(f"Scan path does not exist: {path}")

        start_time = time.time()

        report = AuthReport(scan_path=str(path))

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

    def _scan_file(self, file_path: Path, root_path: Path) -> List[AuthFinding]:
        """
        Scan a single file for JWT security issues.

        Args:
            file_path: Path to the file to scan
            root_path: Root path for relative path calculation

        Returns:
            List of auth findings in the file
        """
        findings: List[AuthFinding] = []

        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except (IOError, OSError):
            return findings

        lines = content.split("\n")
        file_ext = file_path.suffix.lower()

        for pattern in self.patterns:
            for match in pattern.pattern.finditer(content):
                line_number, column = find_line_column(content, match.start())

                if is_in_comment_or_docstring(content, lines, line_number, match.start(), file_ext):
                    continue

                if self._is_enum_value(match.group(0)):
                    continue

                if pattern.name == "jwt_decode_no_verify":
                    if self._is_intentional_no_verify(content, match.start(), lines, line_number):
                        continue

                code_snippet = extract_code_snippet(lines, line_number)

                finding = AuthFinding(
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

        expiration_findings = self._check_token_expiration(content, lines, file_path, root_path)
        findings.extend(expiration_findings)

        return findings

    def _check_token_expiration(
        self,
        content: str,
        lines: List[str],
        file_path: Path,
        root_path: Path,
    ) -> List[AuthFinding]:
        """
        Check for missing token expiration.

        Args:
            content: File content
            lines: File lines
            file_path: Path to file
            root_path: Root path

        Returns:
            List of findings for missing expiration
        """
        findings = []

        exp_results = find_token_expiration(content)

        for line_number, has_exp, context in exp_results:
            if not has_exp:
                code_snippet = extract_code_snippet(lines, line_number)

                finding = AuthFinding(
                    file_path=str(file_path.relative_to(root_path)),
                    line_number=line_number,
                    finding_type=AuthFindingType.MISSING_TOKEN_EXPIRATION,
                    severity=SecuritySeverity.HIGH,
                    title="JWT Missing Expiration Claim",
                    description="JWT token is created without an expiration (exp) claim.",
                    code_snippet=code_snippet,
                    cwe_id="CWE-613",
                    confidence=0.7,
                    remediation=(
                        "Add an 'exp' claim to JWT tokens. Use a reasonable expiration time "
                        "(e.g., 15 minutes for access tokens, 7 days for refresh tokens)."
                    ),
                    references=[
                        "https://cwe.mitre.org/data/definitions/613.html",
                    ],
                )

                findings.append(finding)

        return findings

    def _is_enum_value(self, matched_text: str) -> bool:
        """Check if matched text is an enum value definition, not a real credential."""
        if "=" in matched_text:
            value_part = matched_text.split("=", 1)[1].strip().strip("'\"")
            for pattern in ENUM_VALUE_PATTERNS:
                if re.match(pattern, value_part, re.IGNORECASE):
                    return True
        return False

    def _is_intentional_no_verify(
        self,
        content: str,
        match_start: int,
        lines: List[str],
        line_number: int
    ) -> bool:
        """
        Check if JWT verification disabled is intentional/legitimate.

        Args:
            content: Full file content
            match_start: Start position of the match
            lines: File content as lines
            line_number: Line number of the match

        Returns:
            True if the unverified decode appears intentional
        """
        context_start = max(0, match_start - 500)
        context_end = min(len(content), match_start + 200)
        context = content[context_start:context_end]

        for pattern in INTENTIONAL_NO_VERIFY_PATTERNS:
            if re.search(pattern, context, re.IGNORECASE):
                return True

        before_match = content[max(0, match_start - 300):match_start]
        after_match = content[match_start:min(len(content), match_start + 300)]

        if "try:" in before_match and "except" in after_match:
            return True

        for i in range(line_number - 1, max(0, line_number - 30), -1):
            if i < len(lines):
                line = lines[i].strip()
                if line.startswith("def "):
                    docstring_check = "\n".join(lines[i:min(len(lines), i + 10)])
                    if "WARNING" in docstring_check or "Never trust" in docstring_check:
                        return True
                    if any(pattern in line.lower() for pattern in ["without_verification", "unverified", "inspect", "debug", "peek"]):
                        return True
                    break

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
