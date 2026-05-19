"""Ruby security and quality rules (regex-based)."""

import re
from typing import List
from Asgard.Heimdall.Quality.languages.ruby.models.ruby_models import (
    RubyFinding, RubyRuleCategory, RubySeverity,
)


def _finding(file_path, line_number, rule_id, category, severity, title, description, snippet="", fix=""):
    return RubyFinding(
        file_path=file_path, line_number=line_number, rule_id=rule_id,
        category=category, severity=severity, title=title,
        description=description, code_snippet=snippet.rstrip(), fix_suggestion=fix,
    )


def check_sql_injection(file_path: str, lines: List[str], enabled: bool = True) -> List[RubyFinding]:
    """ruby.sql-injection: string interpolation in ActiveRecord queries."""
    if not enabled:
        return []
    pattern = re.compile(r'(?:where|find_by_sql|execute)\s*\(["\'].*#\{|\bexecute\s*\(.*\+')
    return [
        _finding(file_path, i + 1, "ruby.sql-injection", RubyRuleCategory.SECURITY, RubySeverity.ERROR,
                 "SQL Injection via String Interpolation",
                 "Using string interpolation in ActiveRecord queries allows injection.",
                 line, "Use parameterised queries: where(\'name = ?\', name).")
        for i, line in enumerate(lines) if pattern.search(line)
    ]


def check_no_eval(file_path: str, lines: List[str], enabled: bool = True) -> List[RubyFinding]:
    """ruby.no-eval: use of eval()."""
    if not enabled:
        return []
    pattern = re.compile(r'\beval\s*\(')
    return [
        _finding(file_path, i + 1, "ruby.no-eval", RubyRuleCategory.SECURITY, RubySeverity.ERROR,
                 "Use of eval()",
                 "eval() executes arbitrary code and is a critical security risk.",
                 line, "Avoid eval(); use safe alternatives.")
        for i, line in enumerate(lines) if pattern.search(line)
    ]


def check_command_injection(file_path: str, lines: List[str], enabled: bool = True) -> List[RubyFinding]:
    """ruby.command-injection: backtick or system() with interpolation."""
    if not enabled:
        return []
    pattern = re.compile(r'`[^`]*#\{|\bsystem\s*\([^)]*#\{')
    return [
        _finding(file_path, i + 1, "ruby.command-injection", RubyRuleCategory.SECURITY, RubySeverity.ERROR,
                 "Command Injection",
                 "Shell command with interpolated user input allows injection.",
                 line, "Use Open3 with an array argument to avoid shell interpolation.")
        for i, line in enumerate(lines) if pattern.search(line)
    ]


def check_no_yaml_load(file_path: str, lines: List[str], enabled: bool = True) -> List[RubyFinding]:
    """ruby.no-yaml-load: YAML.load() allows arbitrary object deserialisation."""
    if not enabled:
        return []
    pattern = re.compile(r'YAML\.load\s*\(')
    return [
        _finding(file_path, i + 1, "ruby.no-yaml-load", RubyRuleCategory.SECURITY, RubySeverity.ERROR,
                 "Unsafe YAML.load()",
                 "YAML.load() can instantiate arbitrary Ruby objects.",
                 line, "Use YAML.safe_load() instead.")
        for i, line in enumerate(lines) if pattern.search(line)
    ]


def check_no_send(file_path: str, lines: List[str], enabled: bool = True) -> List[RubyFinding]:
    """ruby.no-send: send() with user input."""
    if not enabled:
        return []
    pattern = re.compile(r'\.send\s*\([^)]*(?:params|request|user_input)')
    return [
        _finding(file_path, i + 1, "ruby.no-send", RubyRuleCategory.SECURITY, RubySeverity.ERROR,
                 "Dynamic send() with User Input",
                 "send() with user-controlled method name can call arbitrary methods.",
                 line, "Whitelist allowed method names before calling send().")
        for i, line in enumerate(lines) if pattern.search(line)
    ]


def check_mass_assignment(file_path: str, lines: List[str], enabled: bool = True) -> List[RubyFinding]:
    """ruby.mass-assignment: update_attributes(params) without filtering."""
    if not enabled:
        return []
    pattern = re.compile(r'(?:update_attributes|update)\s*\(\s*params\s*\)')
    return [
        _finding(file_path, i + 1, "ruby.mass-assignment", RubyRuleCategory.SECURITY, RubySeverity.WARNING,
                 "Mass Assignment from params",
                 "Passing params directly allows attackers to set protected attributes.",
                 line, "Use strong parameters: params.require(:model).permit(:field1, :field2).")
        for i, line in enumerate(lines) if pattern.search(line)
    ]


def check_no_hardcoded_credentials(file_path: str, lines: List[str], enabled: bool = True) -> List[RubyFinding]:
    """ruby.no-hardcoded-credentials: hardcoded passwords/tokens."""
    if not enabled:
        return []
    pattern = re.compile(r'(?:password|secret|api_key|token)\s*=\s*["\'][^"\']{4,}["\']', re.IGNORECASE)
    return [
        _finding(file_path, i + 1, "ruby.no-hardcoded-credentials",
                 RubyRuleCategory.SECURITY, RubySeverity.ERROR,
                 "Hardcoded Credential",
                 "Credentials in source code are a security risk.",
                 line, "Use ENV[] or Rails credentials.")
        for i, line in enumerate(lines) if pattern.search(line)
    ]


def check_no_md5_sha1(file_path: str, lines: List[str], enabled: bool = True) -> List[RubyFinding]:
    """ruby.no-md5-sha1: MD5/SHA1 for password hashing."""
    if not enabled:
        return []
    pattern = re.compile(r'Digest::(?:MD5|SHA1)\.(?:hexdigest|digest)', re.IGNORECASE)
    return [
        _finding(file_path, i + 1, "ruby.no-md5-sha1", RubyRuleCategory.SECURITY, RubySeverity.ERROR,
                 "Weak Hash Algorithm for Passwords",
                 "MD5 and SHA1 are cryptographically broken for password hashing.",
                 line, "Use bcrypt via the bcrypt gem.")
        for i, line in enumerate(lines) if pattern.search(line)
    ]
