"""Sensitive data and PII exposure scanner."""

import ast
import os
import re
from pathlib import Path
from typing import List

from Asgard.Heimdall.Security.SensitiveData.models.sensitive_data_models import (
    SensitiveDataFinding,
    SensitiveDataScanConfig,
    SensitiveDataScanReport,
    SensitiveDataSeverity,
)
from Asgard.Heimdall.Security.SensitiveData.services._pii_log_sink_analysis import (
    scan_django_debug_true,
    scan_pii_log_sinks,
)
from Asgard.Heimdall.Security.context.test_context import is_test_context
from Asgard.Heimdall.Security.normalization.priority import confidence_bucket

_SENSITIVE_PATTERNS: dict = {
    "credentials": [
        (r"(?:password|passwd|pwd|pass)\s*(?:=|:)\s*['\"`]([^'\"`\s]{4,})['\"`]", "CRITICAL", "hardcoded_password", "Hardcoded password", "Use environment variables or secrets manager"),
        (r"(?:api[_-]?key|apikey)\s*(?:=|:)\s*['\"`]([A-Za-z0-9_-]{16,})['\"`]", "CRITICAL", "api_key", "Hardcoded API key", "Store in environment variables"),
        (r"(?:secret[_-]?key|secretkey)\s*(?:=|:)\s*['\"`]([^'\"`\s]{8,})['\"`]", "CRITICAL", "secret_key", "Hardcoded secret key", "Use secrets management"),
        (r"(?:auth[_-]?token|access[_-]?token)\s*(?:=|:)\s*['\"`]([A-Za-z0-9_.-]{20,})['\"`]", "CRITICAL", "auth_token", "Hardcoded auth token", "Never hardcode tokens"),
    ],
    "pii": [
        (r"\b\d{3}-\d{2}-\d{4}\b", "CRITICAL", "ssn", "Social Security Number pattern", "Remove or encrypt SSN data"),
        (r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12})\b", "CRITICAL", "credit_card", "Credit card number pattern", "Never store credit card numbers in code"),
        (r"\b[A-Z]{2}\d{6,9}\b", "HIGH", "passport", "Passport number pattern", "Remove or encrypt passport data"),
    ],
    "private_keys": [
        (r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----", "CRITICAL", "private_key", "Private key in code", "Store keys securely, never in code"),
        (r"-----BEGIN PGP PRIVATE KEY BLOCK-----", "CRITICAL", "pgp_private_key", "PGP private key in code", "Use secure key storage"),
    ],
    "cloud_credentials": [
        (r"AKIA[0-9A-Z]{16}", "CRITICAL", "aws_access_key", "AWS access key", "Rotate immediately and use IAM roles"),
        (r"(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{36,}", "CRITICAL", "github_token", "GitHub personal access token", "Revoke and use GitHub Actions secrets"),
        (r"sk_live_[0-9a-zA-Z]{24,}", "CRITICAL", "stripe_live_key", "Stripe live key", "Remove and rotate immediately"),
    ],
    "database": [
        (r"(?:mysql|postgresql|postgres|mongodb|redis)://[^'\"\s@]+:[^'\"\s@]+@", "CRITICAL", "db_connection_string", "Database connection string with credentials", "Use environment variables for connection strings"),
    ],
    "tokens": [
        (r"Bearer\s+[A-Za-z0-9_.-]{20,}", "HIGH", "bearer_token_hardcoded", "Bearer token hardcoded", "Use runtime token management"),
        (r"eyJ[A-Za-z0-9_-]{20,}\.eyJ[A-Za-z0-9_-]{20,}\.", "HIGH", "jwt_hardcoded", "Hardcoded JWT token", "Generate tokens at runtime"),
    ],
}


def _mask(value: str) -> str:
    if len(value) <= 4:
        return "****"
    return value[:2] + "*" * (len(value) - 4) + value[-2:]


class SensitiveDataScanner:
    """Scans source code for exposed sensitive data and PII."""

    def __init__(self) -> None:
        self._compiled: dict = {}
        for dtype, patterns in _SENSITIVE_PATTERNS.items():
            self._compiled[dtype] = [
                (re.compile(p, re.IGNORECASE), sev, ptype, desc, rec)
                for p, sev, ptype, desc, rec in patterns
            ]

    def scan(self, config: SensitiveDataScanConfig) -> SensitiveDataScanReport:
        findings: List[SensitiveDataFinding] = []
        files_scanned = 0
        target = config.scan_path
        skip = set(config.skip_dirs)

        if target.is_file():
            findings = self._scan_file(target)
            files_scanned = 1
        else:
            for root, dirs, files in os.walk(target):
                dirs[:] = [d for d in dirs if d not in skip]
                for name in files:
                    fp = Path(root) / name
                    ff = self._scan_file(fp)
                    if ff:
                        findings.extend(ff)
                        files_scanned += 1

        by_severity: dict = {}
        by_data_type: dict = {}
        for f in findings:
            by_severity[f.severity.value] = by_severity.get(f.severity.value, 0) + 1
            by_data_type[f.data_type] = by_data_type.get(f.data_type, 0) + 1

        return SensitiveDataScanReport(
            scan_path=str(config.scan_path),
            total_findings=len(findings),
            files_scanned=files_scanned,
            findings=findings,
            by_severity=by_severity,
            by_data_type=by_data_type,
        )

    def _scan_file(self, file_path: Path) -> List[SensitiveDataFinding]:
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return []

        lines = content.splitlines()
        in_test_context = is_test_context(str(file_path))

        findings: List[SensitiveDataFinding] = []
        for line_num, line in enumerate(lines, 1):
            for dtype, patterns in self._compiled.items():
                for regex, sev, ptype, desc, rec in patterns:
                    m = regex.search(line)
                    if m:
                        captured = m.group(1) if m.lastindex else m.group(0)
                        confidence = 0.4 if in_test_context else 0.75
                        findings.append(SensitiveDataFinding(
                            file_path=str(file_path),
                            line_number=line_num,
                            severity=SensitiveDataSeverity(sev),
                            data_type=dtype,
                            pattern_type=ptype,
                            masked_value=_mask(captured),
                            description=desc,
                            recommendation=rec,
                            mechanism_id=f"sensitive_data.{dtype}.{ptype}",
                            confidence=confidence,
                            confidence_bucket=confidence_bucket(confidence),
                            compliance_tags=self._compliance_tags(dtype, ptype),
                        ))
                        break

        if file_path.suffix == ".py":
            findings.extend(self._scan_pii_log_sinks(file_path, content, lines, in_test_context))

        return findings

    def _scan_pii_log_sinks(
        self, file_path: Path, content: str, lines: List[str], in_test_context: bool,
    ) -> List[SensitiveDataFinding]:
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return []

        findings: List[SensitiveDataFinding] = []

        for pii_finding in scan_pii_log_sinks(tree, lines):
            severity = pii_finding.severity
            confidence = pii_finding.confidence
            is_hotspot = pii_finding.is_hotspot
            if in_test_context:
                # Plan 07.11/08: PII-to-log findings are downgraded, not
                # suppressed, in test code -- test fixtures can still leak
                # real-shaped data into CI logs.
                confidence = min(confidence, 0.25)
                is_hotspot = True
                severity = "LOW"
            findings.append(SensitiveDataFinding(
                file_path=str(file_path),
                line_number=pii_finding.line_number,
                severity=SensitiveDataSeverity(severity if severity in ("CRITICAL", "HIGH", "MEDIUM", "LOW") else "LOW"),
                data_type="pii_log_sink",
                pattern_type=pii_finding.lexicon_term,
                masked_value=_mask(pii_finding.identifier),
                description=pii_finding.description,
                recommendation=pii_finding.recommendation,
                mechanism_id=pii_finding.mechanism_id,
                confidence=confidence,
                confidence_bucket=confidence_bucket(confidence),
                compliance_tags=pii_finding.compliance_tags,
                is_hotspot=is_hotspot,
            ))

        for debug_finding in scan_django_debug_true(tree, lines):
            findings.append(SensitiveDataFinding(
                file_path=str(file_path),
                line_number=debug_finding.line_number,
                severity=SensitiveDataSeverity.HIGH,
                data_type="django_debug",
                pattern_type=debug_finding.lexicon_term,
                masked_value="",
                description=debug_finding.description,
                recommendation=debug_finding.recommendation,
                mechanism_id=debug_finding.mechanism_id,
                confidence=debug_finding.confidence,
                confidence_bucket=confidence_bucket(debug_finding.confidence),
                compliance_tags=debug_finding.compliance_tags,
                is_hotspot=False,
            ))

        return findings

    @staticmethod
    def _compliance_tags(dtype: str, ptype: str) -> List[str]:
        if dtype == "pii":
            return ["GDPR"]
        if ptype in ("credit_card",):
            return ["PCI-DSS"]
        if dtype in ("credentials", "cloud_credentials", "tokens", "database", "private_keys"):
            return []
        return []
