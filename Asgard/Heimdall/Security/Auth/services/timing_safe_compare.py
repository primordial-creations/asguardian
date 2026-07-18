"""
Non-constant-time secret comparison detector (plan 07.6 "present-but-weak").

Flags `==`/`!=` comparisons where an operand is a secret-shaped identifier
(password/token/secret/signature/hmac/digest/api_key/csrf hash) instead of
`hmac.compare_digest`/`secrets.compare_digest`. Python-only AST check --
other languages keep whatever regex floor already exists elsewhere and are
not touched here (documented scope limit).

FP-bias: precision-first per plan 07 cross-cutting guidance (this family is
listed alongside TLS/MD5/TOCTOU as precision-biased, not recall-biased).
The identifier lexicon is deliberately narrow; a secret compared under an
unrecognized variable name is a documented false negative rather than a
guess.
"""

import ast
from pathlib import Path
from typing import List, Optional

from Asgard.Heimdall.Security.Auth.models.auth_models import (
    AuthConfig,
    AuthFinding,
    AuthFindingType,
    AuthReport,
)
from Asgard.Heimdall.Security.models.security_models import SecuritySeverity
from Asgard.Heimdall.Security.normalization.impact_matrix import normalize_finding
from Asgard.Heimdall.Security.utilities.security_utils import (
    extract_code_snippet,
    scan_directory_for_security,
)

_SECRET_LEXICON = (
    "password", "passwd", "secret", "token", "signature", "sig",
    "hmac", "digest", "api_key", "apikey", "csrf", "auth_key",
    "session_key", "private_key",
)

_SEVERITY_FOR_NORMALIZED = {
    "critical": SecuritySeverity.CRITICAL,
    "high": SecuritySeverity.HIGH,
    "medium": SecuritySeverity.MEDIUM,
    "low": SecuritySeverity.LOW,
}


def _name_of(node: ast.AST) -> Optional[str]:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Subscript):
        return _name_of(node.value)
    return None


def _looks_like_secret(node: ast.AST) -> bool:
    name = _name_of(node)
    if not name:
        return False
    lowered = name.lower()
    return any(term in lowered for term in _SECRET_LEXICON)


def _is_trivial_literal(node: ast.AST) -> bool:
    """Comparisons against None/bool/empty-string are existence checks, not
    secret-value comparisons -- excluding them cuts an FP class."""
    if isinstance(node, ast.Constant):
        return node.value is None or node.value == "" or isinstance(node.value, bool)
    return False


class _TimingUnsafeCompareVisitor(ast.NodeVisitor):
    def __init__(self):
        self.hits: List[ast.Compare] = []

    def visit_Compare(self, node: ast.Compare) -> None:
        ops = node.ops
        if len(ops) == 1 and isinstance(ops[0], (ast.Eq, ast.NotEq)):
            left, right = node.left, node.comparators[0]
            if not (_is_trivial_literal(left) or _is_trivial_literal(right)):
                if _looks_like_secret(left) or _looks_like_secret(right):
                    self.hits.append(node)
        self.generic_visit(node)


class TimingSafeCompareChecker:
    """Scans Python source for non-constant-time secret comparisons."""

    def scan(self, scan_path: Optional[Path] = None, config: Optional[AuthConfig] = None) -> AuthReport:
        cfg = config or AuthConfig()
        path = Path(scan_path or cfg.scan_path).resolve()
        report = AuthReport(scan_path=str(path))

        for file_path in scan_directory_for_security(
            path, exclude_patterns=cfg.exclude_patterns, include_extensions=[".py"],
        ):
            report.total_files_scanned += 1
            report.findings.extend(self._scan_file(file_path, path))

        report.total_issues = len(report.findings)
        report.high_issues = sum(1 for f in report.findings if f.severity == SecuritySeverity.HIGH.value)
        report.medium_issues = sum(1 for f in report.findings if f.severity == SecuritySeverity.MEDIUM.value)
        return report

    def _scan_file(self, file_path: Path, root_path: Path) -> List[AuthFinding]:
        findings: List[AuthFinding] = []
        try:
            source = file_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return findings

        try:
            tree = ast.parse(source, filename=str(file_path))
        except SyntaxError:
            return findings

        visitor = _TimingUnsafeCompareVisitor()
        visitor.visit(tree)
        if not visitor.hits:
            return findings

        lines = source.split("\n")
        try:
            rel = str(file_path.relative_to(root_path))
        except ValueError:
            rel = str(file_path)

        normalized = normalize_finding(
            "auth.timing_unsafe_compare", confidence=0.7, fallback_severity="medium",
        )
        severity = _SEVERITY_FOR_NORMALIZED.get(normalized.severity, SecuritySeverity.MEDIUM)

        for node in visitor.hits:
            line_number = getattr(node, "lineno", 1)
            findings.append(AuthFinding(
                file_path=rel,
                line_number=line_number,
                column_start=getattr(node, "col_offset", 0),
                finding_type=AuthFindingType.TIMING_UNSAFE_COMPARE,
                severity=severity,
                title="Non-Constant-Time Secret Comparison",
                description=(
                    "A secret-shaped value (password/token/signature/hmac/"
                    "digest/api_key/csrf) is compared with a Python `==`/`!=` "
                    "operator, which short-circuits on the first differing "
                    "byte and can leak timing information to an attacker."
                ),
                code_snippet=extract_code_snippet(lines, line_number),
                cwe_id="CWE-208",
                confidence=normalized.confidence,
                mechanism_id="auth.timing_unsafe_compare",
                remediation=(
                    "Use hmac.compare_digest(a, b) (or secrets.compare_digest) "
                    "for constant-time comparison of secrets, MACs, and tokens."
                ),
                references=[
                    "https://cwe.mitre.org/data/definitions/208.html",
                    "https://docs.python.org/3/library/hmac.html#hmac.compare_digest",
                ],
            ))

        return findings
