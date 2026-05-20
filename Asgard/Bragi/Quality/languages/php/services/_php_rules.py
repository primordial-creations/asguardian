"""PHP security and quality rules (regex-based)."""

import re
from typing import List
from Asgard.Bragi.Quality.languages.php.models.php_models import (
    PhpFinding, PhpRuleCategory, PhpSeverity,
)


def _finding(file_path, line_number, rule_id, category, severity, title, description, snippet="", fix=""):
    return PhpFinding(
        file_path=file_path, line_number=line_number, rule_id=rule_id,
        category=category, severity=severity, title=title,
        description=description, code_snippet=snippet.rstrip(), fix_suggestion=fix,
    )


def check_sql_injection(file_path: str, lines: List[str], enabled: bool = True) -> List[PhpFinding]:
    """php.sql-injection: unparameterised queries with user input."""
    if not enabled:
        return []
    # User input directly in query call
    direct = re.compile(r'(?:mysql_query|mysqli_query|->query)\s*\([^)]*\$_(?:GET|POST|REQUEST|COOKIE)')
    # $query/$sql built with string concat from user input: $query = "..." . $_GET
    build = re.compile(r'\$(?:query|sql|qry)\s*=\s*["\'].*["\']\s*\.\s*\$_(?:GET|POST|REQUEST|COOKIE)')
    # $query built with interpolation: $query = "...{$_GET['id']}..."
    interp = re.compile(r'\$(?:query|sql|qry)\s*=\s*"[^"]*\$_(?:GET|POST|REQUEST|COOKIE)')
    # $query with any PHP variable interpolated in SQL context (two-hop: $id = $_GET; $query = "...$id...")
    var_interp = re.compile(r"\$(?:query|sql|qry)\s*=\s*\"[^\"]*(?:SELECT|INSERT|UPDATE|DELETE|WHERE)[^\"]*'\$\w+", re.IGNORECASE)
    findings = []
    for i, line in enumerate(lines):
        if direct.search(line) or build.search(line) or interp.search(line) or var_interp.search(line):
            findings.append(_finding(
                file_path, i + 1, "php.sql-injection", PhpRuleCategory.SECURITY, PhpSeverity.ERROR,
                "SQL Injection",
                "Building SQL queries with user input allows injection attacks.",
                line, "Use PDO prepared statements with bound parameters."))
    return findings


def check_xss(file_path: str, lines: List[str], enabled: bool = True) -> List[PhpFinding]:
    """php.xss: unescaped output of user input."""
    if not enabled:
        return []
    # Direct echo of superglobal
    direct = re.compile(r'echo\s+\$_(?:GET|POST|REQUEST|COOKIE)')
    # HTML string concat with superglobal: $html .= '...' . $_GET['x']
    concat = re.compile(r'(?:\$html|\$output|\$page\[)\s*\.?=.*\.\s*\$_(?:GET|POST|REQUEST|COOKIE)')
    findings = []
    for i, line in enumerate(lines):
        if direct.search(line) or concat.search(line):
            findings.append(_finding(
                file_path, i + 1, "php.xss", PhpRuleCategory.SECURITY, PhpSeverity.ERROR,
                "Cross-Site Scripting (XSS)",
                "Echoing user input without escaping allows XSS.",
                line, "Use htmlspecialchars($val, ENT_QUOTES, 'UTF-8')."))
    return findings


def check_no_eval(file_path: str, lines: List[str], enabled: bool = True) -> List[PhpFinding]:
    """php.no-eval: use of eval()."""
    if not enabled:
        return []
    pattern = re.compile(r'\beval\s*\(')
    return [
        _finding(file_path, i + 1, "php.no-eval", PhpRuleCategory.SECURITY, PhpSeverity.ERROR,
                 "Use of eval()",
                 "eval() executes arbitrary PHP code.",
                 line, "Avoid eval(); refactor to avoid dynamic code execution.")
        for i, line in enumerate(lines) if pattern.search(line)
    ]


def check_file_inclusion(file_path: str, lines: List[str], enabled: bool = True) -> List[PhpFinding]:
    """php.file-inclusion: include/require with user input."""
    if not enabled:
        return []
    pattern = re.compile(r'(?:include|require)(?:_once)?\s*\(?\s*\$_(?:GET|POST|REQUEST)')
    return [
        _finding(file_path, i + 1, "php.file-inclusion", PhpRuleCategory.SECURITY, PhpSeverity.ERROR,
                 "Remote/Local File Inclusion",
                 "Including files from user input allows path traversal and RFI.",
                 line, "Whitelist allowed filenames; never include user-supplied paths.")
        for i, line in enumerate(lines) if pattern.search(line)
    ]


def check_command_injection(file_path: str, lines: List[str], enabled: bool = True) -> List[PhpFinding]:
    """php.command-injection: system/exec with user input."""
    if not enabled:
        return []
    # Direct superglobal in call
    direct = re.compile(r'(?:system|exec|passthru|shell_exec|popen)\s*\([^)]*\$_(?:GET|POST|REQUEST)')
    # String concat with variable: shell_exec('cmd ' . $var)
    concat = re.compile(r'(?:system|exec|passthru|shell_exec|popen)\s*\([^)]*\'\s*\.\s*\$\w+')
    findings = []
    for i, line in enumerate(lines):
        if direct.search(line) or concat.search(line):
            findings.append(_finding(
                file_path, i + 1, "php.command-injection", PhpRuleCategory.SECURITY, PhpSeverity.ERROR,
                "Command Injection",
                "Running shell commands with user input allows arbitrary command execution.",
                line, "Use escapeshellarg() and escapeshellcmd(), or avoid shell calls entirely."))
    return findings


def check_no_md5_password(file_path: str, lines: List[str], enabled: bool = True) -> List[PhpFinding]:
    """php.no-md5-password: md5() for password hashing."""
    if not enabled:
        return []
    pattern = re.compile(r'\bmd5\s*\(')
    return [
        _finding(file_path, i + 1, "php.no-md5-password", PhpRuleCategory.SECURITY, PhpSeverity.ERROR,
                 "Weak Password Hash (MD5)",
                 "MD5 is cryptographically broken for password storage.",
                 line, "Use password_hash($pass, PASSWORD_BCRYPT).")
        for i, line in enumerate(lines) if pattern.search(line)
    ]


def check_no_extract(file_path: str, lines: List[str], enabled: bool = True) -> List[PhpFinding]:
    """php.no-extract: extract() on user input."""
    if not enabled:
        return []
    pattern = re.compile(r'extract\s*\(\s*\$_(?:GET|POST|REQUEST)')
    return [
        _finding(file_path, i + 1, "php.no-extract", PhpRuleCategory.SECURITY, PhpSeverity.ERROR,
                 "extract() on User Input",
                 "extract() on user input can overwrite arbitrary variables.",
                 line, "Never extract user-supplied data; access $_POST keys explicitly.")
        for i, line in enumerate(lines) if pattern.search(line)
    ]


def check_path_traversal(file_path: str, lines: List[str], enabled: bool = True) -> List[PhpFinding]:
    """php.path-traversal: file_get_contents or fopen with $_GET input."""
    if not enabled:
        return []
    pattern = re.compile(r'(?:file_get_contents|fopen)\s*\([^)]*\$_(?:GET|POST|REQUEST)')
    return [
        _finding(file_path, i + 1, "php.path-traversal", PhpRuleCategory.SECURITY, PhpSeverity.ERROR,
                 "Path Traversal via User-Controlled File Path",
                 "Using $_GET or $_POST directly in file functions allows path traversal.",
                 line, "Validate and sanitise the file path; use realpath() and check it stays within the expected root.")
        for i, line in enumerate(lines) if pattern.search(line)
    ]


def check_no_hardcoded_credentials(file_path: str, lines: List[str], enabled: bool = True) -> List[PhpFinding]:
    """php.no-hardcoded-credentials: hardcoded passwords."""
    if not enabled:
        return []
    pattern = re.compile(r'(?:password|passwd|secret|api_key)\s*=\s*["\'][^"\']{4,}["\']', re.IGNORECASE)
    return [
        _finding(file_path, i + 1, "php.no-hardcoded-credentials",
                 PhpRuleCategory.SECURITY, PhpSeverity.ERROR,
                 "Hardcoded Credential",
                 "Credentials in source code are a security risk.",
                 line, "Use environment variables via getenv().")
        for i, line in enumerate(lines) if pattern.search(line)
    ]
