"""
Heimdall CSP Check Helpers

Standalone check functions for CSP analysis.
"""

import re
from pathlib import Path
from typing import List, Tuple

from Asgard.Heimdall.Security.Headers.models.header_models import (
    HeaderFinding,
    HeaderFindingType,
)
from Asgard.Heimdall.Security.Headers.utilities.csp_parser import ParsedCSP
from Asgard.Heimdall.Security.models.security_models import SecuritySeverity
from Asgard.Heimdall.Security.utilities.security_utils import (
    extract_code_snippet,
    find_line_column,
)


def analyze_csp(
    csp: ParsedCSP,
    line_number: int,
    csp_value: str,
    lines: List[str],
    file_path: Path,
    root_path: Path,
    required_csp_directives: List[str],
) -> List[HeaderFinding]:
    """
    Analyze a parsed CSP for security issues.

    Args:
        csp: Parsed CSP object
        line_number: Line number where CSP was found
        csp_value: Raw CSP value
        lines: File lines
        file_path: Path to file
        root_path: Root path
        required_csp_directives: List of required directive names from config

    Returns:
        List of findings
    """
    findings = []
    code_snippet = extract_code_snippet(lines, line_number)

    for directive_name, directive in csp.directives.items():
        if directive.has_unsafe_inline:
            findings.append(HeaderFinding(
                file_path=str(file_path.relative_to(root_path)),
                line_number=line_number,
                finding_type=HeaderFindingType.CSP_UNSAFE_INLINE,
                severity=SecuritySeverity.HIGH,
                title=f"CSP {directive_name} Uses unsafe-inline",
                description=f"The {directive_name} directive allows 'unsafe-inline' which defeats CSP protection against XSS.",
                code_snippet=code_snippet,
                header_name="Content-Security-Policy",
                header_value=csp_value[:200] if len(csp_value) > 200 else csp_value,
                cwe_id="CWE-79",
                confidence=0.9,
                remediation=f"Remove 'unsafe-inline' from {directive_name}. Use nonces or hashes for inline scripts/styles.",
                references=[
                    "https://developer.mozilla.org/en-US/docs/Web/HTTP/CSP",
                    "https://cwe.mitre.org/data/definitions/79.html",
                ],
            ))

        if directive.has_unsafe_eval:
            findings.append(HeaderFinding(
                file_path=str(file_path.relative_to(root_path)),
                line_number=line_number,
                finding_type=HeaderFindingType.CSP_UNSAFE_EVAL,
                severity=SecuritySeverity.HIGH,
                title=f"CSP {directive_name} Uses unsafe-eval",
                description=f"The {directive_name} directive allows 'unsafe-eval' which permits eval() and similar methods.",
                code_snippet=code_snippet,
                header_name="Content-Security-Policy",
                header_value=csp_value[:200] if len(csp_value) > 200 else csp_value,
                cwe_id="CWE-95",
                confidence=0.9,
                remediation=f"Remove 'unsafe-eval' from {directive_name}. Refactor code to avoid eval(), Function(), and similar.",
                references=[
                    "https://developer.mozilla.org/en-US/docs/Web/HTTP/CSP",
                    "https://cwe.mitre.org/data/definitions/95.html",
                ],
            ))

        if directive.has_wildcard:
            findings.append(HeaderFinding(
                file_path=str(file_path.relative_to(root_path)),
                line_number=line_number,
                finding_type=HeaderFindingType.CSP_WILDCARD_SOURCE,
                severity=SecuritySeverity.MEDIUM,
                title=f"CSP {directive_name} Uses Wildcard Source",
                description=f"The {directive_name} directive uses wildcard (*) which allows loading from any origin.",
                code_snippet=code_snippet,
                header_name="Content-Security-Policy",
                header_value=csp_value[:200] if len(csp_value) > 200 else csp_value,
                cwe_id="CWE-693",
                confidence=0.85,
                remediation=f"Replace wildcard in {directive_name} with specific trusted origins.",
                references=[
                    "https://developer.mozilla.org/en-US/docs/Web/HTTP/CSP",
                ],
            ))

    for missing_directive in csp.missing_recommended_directives:
        if missing_directive in required_csp_directives:
            findings.append(HeaderFinding(
                file_path=str(file_path.relative_to(root_path)),
                line_number=line_number,
                finding_type=HeaderFindingType.CSP_MISSING_DIRECTIVE,
                severity=SecuritySeverity.MEDIUM,
                title=f"CSP Missing {missing_directive} Directive",
                description=f"The Content-Security-Policy is missing the recommended {missing_directive} directive.",
                code_snippet=code_snippet,
                header_name="Content-Security-Policy",
                header_value=csp_value[:200] if len(csp_value) > 200 else csp_value,
                cwe_id="CWE-693",
                confidence=0.7,
                remediation=f"Add the {missing_directive} directive to your CSP policy.",
                references=[
                    "https://developer.mozilla.org/en-US/docs/Web/HTTP/CSP",
                ],
            ))

    return findings


def check_inline_patterns(
    content: str,
    lines: List[str],
    file_path: Path,
    root_path: Path,
    is_in_comment_fn,
) -> List[HeaderFinding]:
    """
    Check for patterns that suggest CSP issues.

    Args:
        content: File content
        lines: File lines
        file_path: Path to file
        root_path: Root path
        is_in_comment_fn: Callable(lines, line_number) -> bool

    Returns:
        List of findings
    """
    findings = []

    weak_csp_patterns = [
        (r"default-src\s+['\"]?\*['\"]?", "default-src allows all sources"),
        (r"script-src\s+['\"]?\*['\"]?", "script-src allows all sources"),
        (r"Content-Security-Policy[^;]*['\"]?unsafe-inline['\"]?[^;]*script", "CSP allows inline scripts"),
    ]

    for pattern, issue_desc in weak_csp_patterns:
        for match in re.finditer(pattern, content, re.IGNORECASE):
            line_number, column = find_line_column(content, match.start())

            if is_in_comment_fn(lines, line_number):
                continue

            code_snippet = extract_code_snippet(lines, line_number)

            findings.append(HeaderFinding(
                file_path=str(file_path.relative_to(root_path)),
                line_number=line_number,
                column_start=column,
                column_end=column + len(match.group(0)),
                finding_type=HeaderFindingType.WEAK_CSP,
                severity=SecuritySeverity.HIGH,
                title="Weak Content-Security-Policy",
                description=f"Content-Security-Policy has a weak configuration: {issue_desc}.",
                code_snippet=code_snippet,
                header_name="Content-Security-Policy",
                cwe_id="CWE-693",
                confidence=0.8,
                remediation="Strengthen the CSP by using specific sources and removing unsafe directives.",
                references=[
                    "https://developer.mozilla.org/en-US/docs/Web/HTTP/CSP",
                    "https://csp-evaluator.withgoogle.com/",
                ],
            ))

    return findings
