"""
Heimdall Access Control Analyzer Service

Service for detecting RBAC/ABAC patterns and access control issues.
"""

import re
import time
from pathlib import Path
from typing import List, Optional, Pattern

from Asgard.Heimdall.Security.Access.models.access_models import (
    AccessConfig,
    AccessFinding,
    AccessFindingType,
    AccessReport,
)
from Asgard.Heimdall.Security.models.security_models import SecuritySeverity
from Asgard.Heimdall.Security.utilities.security_utils import (
    extract_code_snippet,
    find_line_column,
    scan_directory_for_security,
)


class ControlPattern:
    """Defines a pattern for detecting access control issues."""

    def __init__(
        self,
        name: str,
        pattern: str,
        finding_type: AccessFindingType,
        severity: SecuritySeverity,
        title: str,
        description: str,
        cwe_id: str,
        remediation: str,
        confidence: float = 0.7,
    ):
        self.name = name
        self.pattern = re.compile(pattern, re.IGNORECASE | re.MULTILINE)
        self.finding_type = finding_type
        self.severity = severity
        self.title = title
        self.description = description
        self.cwe_id = cwe_id
        self.remediation = remediation
        self.confidence = confidence


CONTROL_PATTERNS: List[ControlPattern] = [
    ControlPattern(
        name="hardcoded_admin_bypass",
        pattern=r"""if\s+(?:username|user|name)\s*[=!]=\s*['"](admin|root|superuser|administrator)['"]""",
        finding_type=AccessFindingType.HARDCODED_ROLE_BYPASS,
        severity=SecuritySeverity.CRITICAL,
        title="Hardcoded Admin Bypass",
        description="Access control bypassed by checking for hardcoded admin username.",
        cwe_id="CWE-798",
        remediation="Use proper role-based access control instead of hardcoded username checks.",
        confidence=0.9,
    ),
    ControlPattern(
        name="wildcard_permission",
        pattern=r"""(?:permission|role|access)\s*[=!]=\s*['"]\*['"]""",
        finding_type=AccessFindingType.WILDCARD_PERMISSION,
        severity=SecuritySeverity.HIGH,
        title="Wildcard Permission Assignment",
        description="Wildcard (*) permission grants unrestricted access.",
        cwe_id="CWE-732",
        remediation="Use specific, least-privilege permissions instead of wildcards.",
        confidence=0.85,
    ),
    ControlPattern(
        name="overly_permissive_role_check",
        pattern=r"""if\s+.*role\s+in\s+\[.*admin.*user.*guest.*\]""",
        finding_type=AccessFindingType.OVERLY_PERMISSIVE,
        severity=SecuritySeverity.MEDIUM,
        title="Overly Permissive Role Check",
        description="Role check allows too many roles including low-privilege roles.",
        cwe_id="CWE-732",
        remediation="Restrict access to only the necessary roles for the operation.",
        confidence=0.7,
    ),
    ControlPattern(
        name="default_allow_pattern",
        pattern=r"""(?:allowed|authorized|permitted)\s*=\s*True\s*(?:#.*default|$)""",
        finding_type=AccessFindingType.DEFAULT_ALLOW,
        severity=SecuritySeverity.HIGH,
        title="Default Allow Access Pattern",
        description="Access is allowed by default, which violates the principle of least privilege.",
        cwe_id="CWE-276",
        remediation="Default to deny access and explicitly grant permissions.",
        confidence=0.75,
    ),
    ControlPattern(
        name="insecure_admin_check",
        pattern=r"""if\s+(?:is_admin|isAdmin|admin)\s*:\s*(?:return\s+True|pass)""",
        finding_type=AccessFindingType.INSECURE_ADMIN_CHECK,
        severity=SecuritySeverity.MEDIUM,
        title="Insecure Admin Check Pattern",
        description="Simple boolean admin check without proper validation.",
        cwe_id="CWE-285",
        remediation="Implement proper role-based access control with validated permissions.",
        confidence=0.65,
    ),
    ControlPattern(
        name="direct_object_reference",
        pattern=r"""(?:get|fetch|load|find).*\(\s*(?:request|params|args)\.(?:id|user_id|object_id)""",
        finding_type=AccessFindingType.DIRECT_OBJECT_REFERENCE,
        severity=SecuritySeverity.HIGH,
        title="Insecure Direct Object Reference",
        description="Object accessed directly using user-supplied ID without ownership verification.",
        cwe_id="CWE-639",
        # Plan 07.6: BOLA/IDOR is a data-provenance/business-logic question
        # SAST structurally cannot prove -- ship as an advisory (Possible
        # confidence bucket per plan 04), not a high-trust finding, and
        # point at the real control (contract-driven fuzzing).
        remediation=(
            "Verify that the current user has permission to access the "
            "requested resource. Note: static analysis cannot prove BOLA/IDOR "
            "exploitability -- pair this advisory with contract-driven "
            "fuzzing (e.g. Schemathesis) against the live API."
        ),
        confidence=0.4,
    ),
    ControlPattern(
        name="missing_ownership_check",
        pattern=r"""@(?:app\.route|router\.(?:get|post|put|delete))\s*\([^)]*(?:user|account|profile)[^)]*\)[\s\S]{0,500}def\s+\w+[^:]+:[\s\S]{0,200}(?:return|yield)(?![\s\S]{0,100}(?:\.user_id|\.owner|\.created_by))""",
        finding_type=AccessFindingType.MISSING_OWNERSHIP_CHECK,
        severity=SecuritySeverity.HIGH,
        title="Missing Resource Ownership Check",
        description="User resource accessed without verifying ownership.",
        cwe_id="CWE-639",
        remediation=(
            "Add ownership verification before returning user-specific "
            "resources. Note: static analysis cannot prove BOLA/IDOR "
            "exploitability -- pair this advisory with contract-driven "
            "fuzzing (e.g. Schemathesis) against the live API."
        ),
        confidence=0.35,
    ),
    ControlPattern(
        name="privilege_escalation_role_change",
        pattern=r"""(?:user|account)\.(?:role|permission|level)\s*=\s*(?:request|params|args|data)""",
        finding_type=AccessFindingType.PRIVILEGE_ESCALATION,
        severity=SecuritySeverity.CRITICAL,
        title="Potential Privilege Escalation",
        description="User role or permission set directly from user input.",
        cwe_id="CWE-269",
        remediation="Never allow users to set their own roles. Use admin-only endpoints for role changes.",
        confidence=0.85,
    ),
]


class ControlAnalyzer:
    """
    Analyzes code for RBAC/ABAC access control patterns and issues.

    Detects:
    - Hardcoded role bypasses
    - Wildcard permissions
    - Overly permissive role checks
    - Default allow patterns
    - Privilege escalation paths
    """

    def __init__(self, config: Optional[AccessConfig] = None):
        """
        Initialize the control analyzer.

        Args:
            config: Access control configuration. Uses defaults if not provided.
        """
        self.config = config or AccessConfig()
        self.patterns = CONTROL_PATTERNS

    def scan(self, scan_path: Optional[Path] = None) -> AccessReport:
        """
        Scan the specified path for access control issues.

        Args:
            scan_path: Root path to scan. Uses config path if not provided.

        Returns:
            AccessReport containing all findings
        """
        path = scan_path or self.config.scan_path
        path = Path(path).resolve()

        if not path.exists():
            raise FileNotFoundError(f"Scan path does not exist: {path}")

        start_time = time.time()

        report = AccessReport(scan_path=str(path))

        for file_path in scan_directory_for_security(
            path,
            exclude_patterns=self.config.exclude_patterns,
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

    def _scan_file(self, file_path: Path, root_path: Path) -> List[AccessFinding]:
        """
        Scan a single file for access control issues.

        Args:
            file_path: Path to the file to scan
            root_path: Root path for relative path calculation

        Returns:
            List of access control findings in the file
        """
        findings: List[AccessFinding] = []

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

                finding = AccessFinding(
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
