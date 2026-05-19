"""JavaScript security rules (regex-based)."""

import re
from typing import List

from Asgard.Heimdall.Quality.languages.javascript.models.js_models import (
    JSFinding,
    JSRuleCategory,
    JSSeverity,
)


def _make_finding(
    file_path: str,
    line_number: int,
    rule_id: str,
    category: JSRuleCategory,
    severity: JSSeverity,
    title: str,
    description: str,
    code_snippet: str = "",
    fix_suggestion: str = "",
) -> JSFinding:
    return JSFinding(
        file_path=file_path,
        line_number=line_number,
        column=0,
        rule_id=rule_id,
        category=category,
        severity=severity,
        title=title,
        description=description,
        code_snippet=code_snippet.rstrip(),
        fix_suggestion=fix_suggestion,
    )


def check_sql_injection(file_path: str, lines: List[str], enabled: bool = True) -> List[JSFinding]:
    """js.sql-injection: template literal or string concat in db query."""
    if not enabled:
        return []
    pattern = re.compile(r'db\.query\s*\(\s*(?:`[^`]*\$\{|"[^"]*"\s*\+|\'[^\']*\'\s*\+)')
    return [
        _make_finding(
            file_path, i + 1, "js.sql-injection",
            JSRuleCategory.SECURITY, JSSeverity.ERROR,
            "SQL Injection via String Concatenation or Template Literal",
            "Building SQL queries with string concatenation or template literals is vulnerable to injection.",
            line, "Use parameterised queries with placeholders."
        )
        for i, line in enumerate(lines) if pattern.search(line)
    ]


def check_hardcoded_credentials(file_path: str, lines: List[str], enabled: bool = True) -> List[JSFinding]:
    """js.hardcoded-credentials: const password or apiKey assigned to a string literal."""
    if not enabled:
        return []
    pattern = re.compile(r'(?:const|let|var)\s+(?:password|passwd|apiKey|api_key|secret|token)\s*=\s*["\'][^"\']{4,}["\']', re.IGNORECASE)
    return [
        _make_finding(
            file_path, i + 1, "js.hardcoded-credentials",
            JSRuleCategory.SECURITY, JSSeverity.ERROR,
            "Hardcoded Credential",
            "Credentials in source code are a security risk.",
            line, "Use environment variables (process.env.SECRET) instead."
        )
        for i, line in enumerate(lines) if pattern.search(line)
    ]


def check_command_injection(file_path: str, lines: List[str], enabled: bool = True) -> List[JSFinding]:
    """js.command-injection: exec or execSync with template literal containing variable."""
    if not enabled:
        return []
    pattern = re.compile(r'(?:exec|execSync)\s*\(\s*`[^`]*\$\{')
    return [
        _make_finding(
            file_path, i + 1, "js.command-injection",
            JSRuleCategory.SECURITY, JSSeverity.ERROR,
            "Command Injection via Template Literal",
            "Passing user-controlled data to exec/execSync allows arbitrary command execution.",
            line, "Use execFile with an argument array, never shell interpolation."
        )
        for i, line in enumerate(lines) if pattern.search(line)
    ]


def check_xss(file_path: str, lines: List[str], enabled: bool = True) -> List[JSFinding]:
    """js.xss: innerHTML or document.write with variable."""
    if not enabled:
        return []
    pattern = re.compile(r'(?:\.innerHTML\s*=\s*(?!["\'`])|document\.write\s*\(\s*(?!["\']))')
    return [
        _make_finding(
            file_path, i + 1, "js.xss",
            JSRuleCategory.SECURITY, JSSeverity.ERROR,
            "Cross-Site Scripting (XSS) via innerHTML or document.write",
            "Writing unsanitised data to innerHTML or document.write enables XSS attacks.",
            line, "Use textContent instead of innerHTML, or sanitise input with DOMPurify."
        )
        for i, line in enumerate(lines) if pattern.search(line)
    ]


def check_path_traversal(file_path: str, lines: List[str], enabled: bool = True) -> List[JSFinding]:
    """js.path-traversal: fs.readFile or fs.readFileSync with req. variable."""
    if not enabled:
        return []
    pattern = re.compile(r'fs\.(?:readFile|readFileSync)\s*\([^)]*req\.')
    return [
        _make_finding(
            file_path, i + 1, "js.path-traversal",
            JSRuleCategory.SECURITY, JSSeverity.ERROR,
            "Path Traversal via User-Controlled File Path",
            "Using request parameters directly in file-read calls allows path traversal.",
            line, "Validate and sanitise the path; use path.resolve() and check it stays within the expected root."
        )
        for i, line in enumerate(lines) if pattern.search(line)
    ]


def check_weak_crypto(file_path: str, lines: List[str], enabled: bool = True) -> List[JSFinding]:
    """js.weak-crypto: crypto.createHash with md5 or sha1."""
    if not enabled:
        return []
    pattern = re.compile(r"crypto\.createHash\s*\(\s*['\"](?:md5|sha1)['\"]", re.IGNORECASE)
    return [
        _make_finding(
            file_path, i + 1, "js.weak-crypto",
            JSRuleCategory.SECURITY, JSSeverity.ERROR,
            "Weak Cryptographic Hash Algorithm",
            "MD5 and SHA1 are cryptographically broken and should not be used for security purposes.",
            line, "Use crypto.createHash('sha256') or stronger, or bcrypt for passwords."
        )
        for i, line in enumerate(lines) if pattern.search(line)
    ]


def check_no_prototype_pollution(file_path: str, lines: List[str], enabled: bool = True) -> List[JSFinding]:
    """js.no-prototype-pollution: __proto__ assignment."""
    if not enabled:
        return []
    pattern = re.compile(r'__proto__\s*=')
    return [
        _make_finding(
            file_path, i + 1, "js.no-prototype-pollution",
            JSRuleCategory.SECURITY, JSSeverity.ERROR,
            "Prototype Pollution via __proto__ Assignment",
            "Assigning to __proto__ can pollute the prototype chain and cause security vulnerabilities.",
            line, "Use Object.create(null) for safe property maps and avoid __proto__ assignments."
        )
        for i, line in enumerate(lines) if pattern.search(line)
    ]


_SECURITY_RULES = [
    check_sql_injection,
    check_hardcoded_credentials,
    check_command_injection,
    check_xss,
    check_path_traversal,
    check_weak_crypto,
    check_no_prototype_pollution,
]
