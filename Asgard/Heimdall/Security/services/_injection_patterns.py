"""
Heimdall Injection Detection Patterns

Pattern definitions for SQL, XSS, command injection, and path traversal detection.
"""

import re
from typing import List, Optional, Set

from Asgard.Heimdall.Security.models.security_models import (
    SecuritySeverity,
    VulnerabilityType,
)


class InjectionPattern:
    """Defines a pattern for detecting injection vulnerabilities."""

    def __init__(
        self,
        name: str,
        pattern: str,
        vuln_type: VulnerabilityType,
        severity: SecuritySeverity,
        title: str,
        description: str,
        cwe_id: str,
        owasp_category: str,
        remediation: str,
        file_types: Optional[Set[str]] = None,
        confidence: float = 0.7,
    ):
        self.name = name
        self.pattern = re.compile(pattern, re.IGNORECASE | re.MULTILINE)
        self.vuln_type = vuln_type
        self.severity = severity
        self.title = title
        self.description = description
        self.cwe_id = cwe_id
        self.owasp_category = owasp_category
        self.remediation = remediation
        self.file_types = file_types or {".py", ".js", ".ts", ".java", ".php", ".rb", ".go"}
        self.confidence = confidence


SQL_INJECTION_PATTERNS: List[InjectionPattern] = [
    InjectionPattern(
        name="sql_string_format",
        pattern=r"""(?:execute|query|cursor\.execute|raw|rawsql|RawSQL)\s*\(\s*[f"'].*(?:\{|\%s|\%\().*["']\s*(?:%|\.format)""",
        vuln_type=VulnerabilityType.SQL_INJECTION,
        severity=SecuritySeverity.CRITICAL,
        title="SQL Injection via String Formatting",
        description="User input is directly interpolated into SQL query using string formatting.",
        cwe_id="CWE-89",
        owasp_category="A03:2021",
        remediation="Use parameterized queries or prepared statements. Never concatenate user input into SQL.",
        confidence=0.85,
    ),
    InjectionPattern(
        name="sql_string_concat",
        pattern=r"""(?:SELECT|INSERT|UPDATE|DELETE|FROM|WHERE|AND|OR)\s*.*['"]\s*\+\s*(?:request|input|params|data|user)""",
        vuln_type=VulnerabilityType.SQL_INJECTION,
        severity=SecuritySeverity.CRITICAL,
        title="SQL Injection via String Concatenation",
        description="User input is concatenated into SQL query string.",
        cwe_id="CWE-89",
        owasp_category="A03:2021",
        remediation="Use parameterized queries with placeholders (?, :param, or $1).",
        confidence=0.8,
    ),
    InjectionPattern(
        name="sql_fstring",
        pattern=r"""(?:execute|query|cursor\.execute)\s*\(\s*f['"]{1,3}.*(?:SELECT|INSERT|UPDATE|DELETE).*\{.*\}""",
        vuln_type=VulnerabilityType.SQL_INJECTION,
        severity=SecuritySeverity.CRITICAL,
        title="SQL Injection via f-string",
        description="Variables are interpolated into SQL using Python f-strings.",
        cwe_id="CWE-89",
        owasp_category="A03:2021",
        remediation="Use parameterized queries instead of f-strings for SQL.",
        file_types={".py"},
        confidence=0.9,
    ),
    InjectionPattern(
        name="sql_percent_format",
        pattern=r"""(?:execute|query|cursor\.execute)\s*\([^)]*["'].*(?:SELECT|INSERT|UPDATE|DELETE).*%[sd].*["']\s*%\s*""",
        vuln_type=VulnerabilityType.SQL_INJECTION,
        severity=SecuritySeverity.CRITICAL,
        title="SQL Injection via Percent Formatting",
        description="SQL query uses percent-style string formatting with user input.",
        cwe_id="CWE-89",
        owasp_category="A03:2021",
        remediation="Replace % formatting with parameterized queries.",
        file_types={".py"},
        confidence=0.85,
    ),
    InjectionPattern(
        name="django_raw_sql",
        pattern=r"""(?:\.raw|\.extra)\s*\([^)]*(?:\{|%|\.format)""",
        vuln_type=VulnerabilityType.SQL_INJECTION,
        severity=SecuritySeverity.HIGH,
        title="Django Raw SQL with User Input",
        description="Django raw() or extra() with potentially unsafe interpolation.",
        cwe_id="CWE-89",
        owasp_category="A03:2021",
        remediation="Use Django ORM methods or pass parameters separately to raw().",
        file_types={".py"},
        confidence=0.75,
    ),
    InjectionPattern(
        name="sqlalchemy_text_format",
        pattern=r"""text\s*\(\s*f?['"]{1,3}.*(?:SELECT|INSERT|UPDATE|DELETE).*(?:\{|%|\.format)""",
        vuln_type=VulnerabilityType.SQL_INJECTION,
        severity=SecuritySeverity.CRITICAL,
        title="SQLAlchemy text() with String Formatting",
        description="SQLAlchemy text() with potentially unsafe string interpolation.",
        cwe_id="CWE-89",
        owasp_category="A03:2021",
        remediation="Use SQLAlchemy bindparams or pass parameters to execute().",
        file_types={".py"},
        confidence=0.85,
    ),
]

XSS_PATTERNS: List[InjectionPattern] = [
    InjectionPattern(
        name="xss_innerhtml",
        pattern=r"""\.innerHTML\s*=\s*(?:(?!['"`]<).)*(?:request|params|input|data|user|query)""",
        vuln_type=VulnerabilityType.XSS,
        severity=SecuritySeverity.HIGH,
        title="XSS via innerHTML",
        description="User input is assigned to innerHTML without sanitization.",
        cwe_id="CWE-79",
        owasp_category="A03:2021",
        remediation="Use textContent instead of innerHTML, or sanitize with DOMPurify.",
        file_types={".js", ".jsx", ".ts", ".tsx"},
        confidence=0.8,
    ),
    InjectionPattern(
        name="xss_document_write",
        pattern=r"""document\.write\s*\([^)]*(?:request|params|input|data|user|query|location|url)""",
        vuln_type=VulnerabilityType.XSS,
        severity=SecuritySeverity.HIGH,
        title="XSS via document.write",
        description="User input passed to document.write without sanitization.",
        cwe_id="CWE-79",
        owasp_category="A03:2021",
        remediation="Avoid document.write. Use DOM methods and sanitize input.",
        file_types={".js", ".jsx", ".ts", ".tsx", ".html"},
        confidence=0.85,
    ),
    InjectionPattern(
        name="xss_eval",
        pattern=r"""eval\s*\([^)]*(?:request|params|input|data|user|query|location)""",
        vuln_type=VulnerabilityType.XSS,
        severity=SecuritySeverity.CRITICAL,
        title="Code Injection via eval",
        description="User input passed to eval() function.",
        cwe_id="CWE-95",
        owasp_category="A03:2021",
        remediation="Never use eval with user input. Use JSON.parse for data parsing.",
        file_types={".js", ".jsx", ".ts", ".tsx"},
        confidence=0.9,
    ),
    InjectionPattern(
        name="xss_dangerously_set",
        pattern=r"""dangerouslySetInnerHTML\s*=\s*\{\s*\{\s*__html\s*:\s*(?!['"`]<)""",
        vuln_type=VulnerabilityType.XSS,
        severity=SecuritySeverity.HIGH,
        title="React dangerouslySetInnerHTML with Dynamic Content",
        description="React dangerouslySetInnerHTML used with potentially unsanitized content.",
        cwe_id="CWE-79",
        owasp_category="A03:2021",
        remediation="Sanitize content with DOMPurify before using dangerouslySetInnerHTML.",
        file_types={".js", ".jsx", ".ts", ".tsx"},
        confidence=0.75,
    ),
    InjectionPattern(
        name="xss_template_unescaped",
        pattern=r"""\{\{\{\s*.*(?:request|params|input|data|user|body)\.""",
        vuln_type=VulnerabilityType.XSS,
        severity=SecuritySeverity.HIGH,
        title="Unescaped Template Variable",
        description="Template uses unescaped variable that may contain user input.",
        cwe_id="CWE-79",
        owasp_category="A03:2021",
        remediation="Use escaped template syntax or sanitize user input.",
        file_types={".html", ".hbs", ".handlebars", ".mustache"},
        confidence=0.7,
    ),
    InjectionPattern(
        name="xss_jinja_safe",
        pattern=r"""\{\{.*\|\s*safe\s*\}\}""",
        vuln_type=VulnerabilityType.XSS,
        severity=SecuritySeverity.MEDIUM,
        title="Jinja2 safe Filter Usage",
        description="Jinja2 safe filter bypasses HTML escaping - ensure content is sanitized.",
        cwe_id="CWE-79",
        owasp_category="A03:2021",
        remediation="Only use |safe with content that is already sanitized or trusted.",
        file_types={".html", ".jinja", ".jinja2"},
        confidence=0.6,
    ),
    InjectionPattern(
        name="xss_jquery_html",
        pattern=r"""\$\([^)]+\)\.html\s*\([^)]*(?:request|params|input|data|user|query)""",
        vuln_type=VulnerabilityType.XSS,
        severity=SecuritySeverity.HIGH,
        title="XSS via jQuery .html()",
        description="User input passed to jQuery .html() method.",
        cwe_id="CWE-79",
        owasp_category="A03:2021",
        remediation="Use .text() for text content, or sanitize HTML before using .html().",
        file_types={".js", ".jsx", ".ts", ".tsx"},
        confidence=0.8,
    ),
]

COMMAND_INJECTION_PATTERNS: List[InjectionPattern] = [
    InjectionPattern(
        name="cmd_os_system",
        pattern=r"""os\.system\s*\([^)]*(?:\{|%|\.format|\+\s*(?:request|input|params|data|user))""",
        vuln_type=VulnerabilityType.COMMAND_INJECTION,
        severity=SecuritySeverity.CRITICAL,
        title="Command Injection via os.system",
        description="User input passed to os.system without sanitization.",
        cwe_id="CWE-78",
        owasp_category="A03:2021",
        remediation="Use subprocess with shell=False and pass arguments as a list.",
        file_types={".py"},
        confidence=0.9,
    ),
    InjectionPattern(
        name="cmd_subprocess_shell",
        pattern=r"""subprocess\.(?:call|run|Popen)\s*\([^)]*shell\s*=\s*True[^)]*(?:\{|%|\.format|\+\s*(?:request|input|params|data|user))""",
        vuln_type=VulnerabilityType.COMMAND_INJECTION,
        severity=SecuritySeverity.CRITICAL,
        title="Command Injection via subprocess with shell=True",
        description="subprocess with shell=True and user input.",
        cwe_id="CWE-78",
        owasp_category="A03:2021",
        remediation="Use shell=False and pass command as a list of arguments.",
        file_types={".py"},
        confidence=0.9,
    ),
    InjectionPattern(
        name="cmd_exec",
        pattern=r"""(?:exec|eval)\s*\([^)]*(?:request|input|params|data|user|args)""",
        vuln_type=VulnerabilityType.COMMAND_INJECTION,
        severity=SecuritySeverity.CRITICAL,
        title="Code Execution via exec/eval",
        description="User input passed to exec() or eval() function.",
        cwe_id="CWE-95",
        owasp_category="A03:2021",
        remediation="Never use exec/eval with user input. Find safer alternatives.",
        file_types={".py"},
        confidence=0.85,
    ),
    InjectionPattern(
        name="cmd_shell_exec",
        pattern=r"""(?:shell_exec|system|passthru|exec|popen)\s*\([^)]*\$_(?:GET|POST|REQUEST)""",
        vuln_type=VulnerabilityType.COMMAND_INJECTION,
        severity=SecuritySeverity.CRITICAL,
        title="PHP Command Injection",
        description="User input from superglobals passed to shell execution function.",
        cwe_id="CWE-78",
        owasp_category="A03:2021",
        remediation="Use escapeshellarg() and escapeshellcmd() for any shell arguments.",
        file_types={".php"},
        confidence=0.9,
    ),
]

PATH_TRAVERSAL_PATTERNS: List[InjectionPattern] = [
    InjectionPattern(
        name="path_traversal_open",
        pattern=r"""open\s*\([^)]*(?:\{|%|\.format|\+)\s*[^)]*(?:request|input|params|data|user|filename|path)""",
        vuln_type=VulnerabilityType.PATH_TRAVERSAL,
        severity=SecuritySeverity.HIGH,
        title="Path Traversal via open()",
        description="User input used in file path without proper sanitization.",
        cwe_id="CWE-22",
        owasp_category="A01:2021",
        remediation="Validate and sanitize file paths. Use os.path.basename() and whitelist allowed directories.",
        file_types={".py"},
        confidence=0.75,
    ),
    InjectionPattern(
        name="path_traversal_send_file",
        pattern=r"""send_file\s*\([^)]*(?:\{|%|\.format|\+)\s*[^)]*(?:request|input|params|data|user|filename|path)""",
        vuln_type=VulnerabilityType.PATH_TRAVERSAL,
        severity=SecuritySeverity.HIGH,
        title="Path Traversal in File Download",
        description="User input used in send_file path without sanitization.",
        cwe_id="CWE-22",
        owasp_category="A01:2021",
        remediation="Validate paths against allowed directories. Never allow ../ in paths.",
        file_types={".py"},
        confidence=0.8,
    ),
]
