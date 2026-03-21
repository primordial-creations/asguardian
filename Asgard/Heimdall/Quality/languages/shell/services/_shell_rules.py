import re
from typing import List

from Asgard.Heimdall.Quality.languages.shell.models.shell_models import (
    ShellFinding,
    ShellRuleCategory,
    ShellSeverity,
)

_SHELL_SHEBANGS = (
    "#!/bin/bash",
    "#!/bin/sh",
    "#!/usr/bin/env bash",
)


def _make_finding(
    file_path: str,
    line_number: int,
    rule_id: str,
    category: ShellRuleCategory,
    severity: ShellSeverity,
    title: str,
    description: str,
    code_snippet: str = "",
    fix_suggestion: str = "",
) -> ShellFinding:
    """Construct a ShellFinding with consistent defaults."""
    return ShellFinding(
        file_path=file_path,
        line_number=line_number,
        rule_id=rule_id,
        category=category,
        severity=severity,
        title=title,
        description=description,
        code_snippet=code_snippet.rstrip(),
        fix_suggestion=fix_suggestion,
    )


def check_eval_injection(file_path: str, lines: List[str], enabled: bool) -> List[ShellFinding]:
    """shell.eval-injection: eval with a variable argument."""
    if not enabled:
        return []
    findings: List[ShellFinding] = []
    pattern = re.compile(r"\beval\s+\$")
    for idx, line in enumerate(lines, start=1):
        if pattern.search(line):
            findings.append(_make_finding(
                file_path=file_path,
                line_number=idx,
                rule_id="shell.eval-injection",
                category=ShellRuleCategory.SECURITY,
                severity=ShellSeverity.ERROR,
                title="eval with variable argument (code injection risk)",
                description="Using eval with a variable can execute arbitrary code if the variable is user-controlled.",
                code_snippet=line,
                fix_suggestion="Avoid eval. Refactor to use explicit commands or arrays.",
            ))
    return findings


def check_curl_insecure(file_path: str, lines: List[str], enabled: bool) -> List[ShellFinding]:
    """shell.curl-insecure: curl with -k or --insecure flag."""
    if not enabled:
        return []
    findings: List[ShellFinding] = []
    pattern = re.compile(r"curl\s+.*(-k\b|--insecure)")
    for idx, line in enumerate(lines, start=1):
        if pattern.search(line):
            findings.append(_make_finding(
                file_path=file_path,
                line_number=idx,
                rule_id="shell.curl-insecure",
                category=ShellRuleCategory.SECURITY,
                severity=ShellSeverity.WARNING,
                title="curl called with TLS verification disabled",
                description="Using -k or --insecure disables TLS certificate verification and is a security risk.",
                code_snippet=line,
                fix_suggestion="Remove the -k/--insecure flag and use a proper certificate bundle.",
            ))
    return findings


def check_wget_no_check(file_path: str, lines: List[str], enabled: bool) -> List[ShellFinding]:
    """shell.wget-no-check: wget with --no-check-certificate."""
    if not enabled:
        return []
    findings: List[ShellFinding] = []
    pattern = re.compile(r"wget\s+.*--no-check-certificate")
    for idx, line in enumerate(lines, start=1):
        if pattern.search(line):
            findings.append(_make_finding(
                file_path=file_path,
                line_number=idx,
                rule_id="shell.wget-no-check",
                category=ShellRuleCategory.SECURITY,
                severity=ShellSeverity.WARNING,
                title="wget called with certificate verification disabled",
                description="--no-check-certificate disables TLS certificate verification.",
                code_snippet=line,
                fix_suggestion="Remove --no-check-certificate and use a proper certificate bundle.",
            ))
    return findings


def check_hardcoded_secret(file_path: str, lines: List[str], enabled: bool) -> List[ShellFinding]:
    """shell.hardcoded-secret: credential variable assigned a literal string."""
    if not enabled:
        return []
    findings: List[ShellFinding] = []
    pattern = re.compile(
        r"(PASSWORD|PASSWD|SECRET|API_KEY|TOKEN)\s*=\s*['\"][^'\"]+['\"]\s*$",
        re.IGNORECASE,
    )
    for idx, line in enumerate(lines, start=1):
        if pattern.search(line):
            findings.append(_make_finding(
                file_path=file_path,
                line_number=idx,
                rule_id="shell.hardcoded-secret",
                category=ShellRuleCategory.SECURITY,
                severity=ShellSeverity.WARNING,
                title="Hardcoded credential or secret value",
                description=(
                    "A variable with a sensitive name is assigned a string literal. "
                    "Hardcoded secrets should never be stored in source code."
                ),
                code_snippet=line,
                fix_suggestion="Read secrets from environment variables or a secrets manager.",
            ))
    return findings


def check_sudo_usage(file_path: str, lines: List[str], enabled: bool) -> List[ShellFinding]:
    """shell.sudo-usage: use of sudo."""
    if not enabled:
        return []
    findings: List[ShellFinding] = []
    pattern = re.compile(r"\bsudo\s+")
    for idx, line in enumerate(lines, start=1):
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        if pattern.search(line):
            findings.append(_make_finding(
                file_path=file_path,
                line_number=idx,
                rule_id="shell.sudo-usage",
                category=ShellRuleCategory.SECURITY,
                severity=ShellSeverity.INFO,
                title="Use of sudo",
                description="sudo grants elevated privileges. Ensure this is intentional and necessary.",
                code_snippet=line,
                fix_suggestion="Document why elevated privileges are required or find an alternative.",
            ))
    return findings
