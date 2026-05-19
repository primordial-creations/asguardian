"""C# security and quality rules (regex-based)."""

import re
from typing import List
from Asgard.Heimdall.Quality.languages.csharp.models.csharp_models import (
    CsharpFinding, CsharpRuleCategory, CsharpSeverity,
)


def _finding(file_path, line_number, rule_id, category, severity, title, description, snippet="", fix=""):
    return CsharpFinding(
        file_path=file_path, line_number=line_number, rule_id=rule_id,
        category=category, severity=severity, title=title,
        description=description, code_snippet=snippet.rstrip(), fix_suggestion=fix,
    )


def check_sql_injection(file_path: str, lines: List[str], enabled: bool = True) -> List[CsharpFinding]:
    """csharp.sql-injection: string concat in SQL queries."""
    if not enabled:
        return []
    # new SqlCommand("..." + var)
    cmd_inline = re.compile(r'new\s+SqlCommand\s*\(\s*"[^"]*"\s*\+')
    # string sql/query = "SELECT..." + var  (build-then-execute pattern)
    build = re.compile(r'string\s+\w*(?:sql|query|cmd|command)\w*\s*=\s*"[^"]*(?:SELECT|INSERT|UPDATE|DELETE|WHERE)[^"]*"\s*\+', re.IGNORECASE)
    findings = []
    for i, line in enumerate(lines):
        if cmd_inline.search(line) or build.search(line):
            findings.append(_finding(
                file_path, i + 1, "csharp.sql-injection", CsharpRuleCategory.SECURITY, CsharpSeverity.ERROR,
                "SQL Injection via String Concatenation",
                "Building SQL with string concatenation is vulnerable to injection.",
                line, "Use SqlParameter with parameterised queries."))
    return findings


def check_no_hardcoded_credentials(file_path: str, lines: List[str], enabled: bool = True) -> List[CsharpFinding]:
    """csharp.no-hardcoded-credentials: hardcoded passwords/connection strings."""
    if not enabled:
        return []
    pattern = re.compile(r'(?:password|Password|secret|ApiKey)\s*=\s*"[^"]{4,}"')
    return [
        _finding(file_path, i + 1, "csharp.no-hardcoded-credentials",
                 CsharpRuleCategory.SECURITY, CsharpSeverity.ERROR,
                 "Hardcoded Credential",
                 "Credentials in source code are a security risk.",
                 line, "Use appsettings.json with Secret Manager or Azure Key Vault.")
        for i, line in enumerate(lines) if pattern.search(line)
    ]


def check_no_empty_catch(file_path: str, lines: List[str], enabled: bool = True) -> List[CsharpFinding]:
    """csharp.no-empty-catch: empty catch blocks."""
    if not enabled:
        return []
    findings = []
    for i in range(len(lines) - 1):
        if re.search(r'catch\s*(?:\([^)]*\))?\s*\{', lines[i]) and re.match(r'\s*\}\s*$', lines[i + 1]):
            findings.append(_finding(file_path, i + 1, "csharp.no-empty-catch",
                CsharpRuleCategory.QUALITY, CsharpSeverity.ERROR,
                "Empty Catch Block", "Silent exception swallowing hides bugs.",
                lines[i], "Log or rethrow the exception."))
    return findings


def check_xss(file_path: str, lines: List[str], enabled: bool = True) -> List[CsharpFinding]:
    """csharp.xss: unencoded output in Response.Write."""
    if not enabled:
        return []
    pattern = re.compile(r'Response\.Write\s*\([^)]*(?:Request|query|user)', re.IGNORECASE)
    return [
        _finding(file_path, i + 1, "csharp.xss", CsharpRuleCategory.SECURITY, CsharpSeverity.ERROR,
                 "Cross-Site Scripting (XSS)",
                 "Writing user input directly to the response enables XSS.",
                 line, "Use HttpUtility.HtmlEncode() or Razor @-syntax.")
        for i, line in enumerate(lines) if pattern.search(line)
    ]


def check_no_weak_crypto(file_path: str, lines: List[str], enabled: bool = True) -> List[CsharpFinding]:
    """csharp.no-weak-crypto: MD5/SHA1 usage."""
    if not enabled:
        return []
    pattern = re.compile(r'new\s+(?:MD5CryptoServiceProvider|SHA1CryptoServiceProvider|HMACMD5|HMACSHA1)\s*\(')
    return [
        _finding(file_path, i + 1, "csharp.no-weak-crypto", CsharpRuleCategory.SECURITY, CsharpSeverity.ERROR,
                 "Weak Cryptographic Algorithm",
                 "MD5 and SHA1 are cryptographically broken.",
                 line, "Use SHA256Managed or better.")
        for i, line in enumerate(lines) if pattern.search(line)
    ]


def check_path_traversal(file_path: str, lines: List[str], enabled: bool = True) -> List[CsharpFinding]:
    """csharp.path-traversal: File operations with user-controlled paths."""
    if not enabled:
        return []
    pattern = re.compile(r'File\.(?:ReadAllText|ReadAllBytes|Open|Create)\s*\([^)]*(?:Request|query|user)', re.IGNORECASE)
    return [
        _finding(file_path, i + 1, "csharp.path-traversal", CsharpRuleCategory.SECURITY, CsharpSeverity.ERROR,
                 "Path Traversal",
                 "File access with user-supplied path allows directory traversal.",
                 line, "Use Path.GetFullPath() and validate against a base directory.")
        for i, line in enumerate(lines) if pattern.search(line)
    ]


def check_command_injection(file_path: str, lines: List[str], enabled: bool = True) -> List[CsharpFinding]:
    """csharp.command-injection: Process.Start with user-controlled args."""
    if not enabled:
        return []
    pattern = re.compile(r'Process\.Start\s*\([^)]*(?:Request|query|user)', re.IGNORECASE)
    return [
        _finding(file_path, i + 1, "csharp.command-injection", CsharpRuleCategory.SECURITY, CsharpSeverity.ERROR,
                 "Command Injection",
                 "Process.Start() with user input allows arbitrary command execution.",
                 line, "Validate and whitelist allowed commands; never use shell: true.")
        for i, line in enumerate(lines) if pattern.search(line)
    ]


def check_unsafe_deserialization(file_path: str, lines: List[str], enabled: bool = True) -> List[CsharpFinding]:
    """csharp.unsafe-deserialization: BinaryFormatter/NetDataContractSerializer/LosFormatter/ObjectStateFormatter usage."""
    if not enabled:
        return []
    pattern = re.compile(r'\b(?:BinaryFormatter|NetDataContractSerializer|LosFormatter|ObjectStateFormatter)\s*\(')
    return [
        _finding(file_path, i + 1, "csharp.unsafe-deserialization",
                 CsharpRuleCategory.SECURITY, CsharpSeverity.ERROR,
                 "Unsafe Deserialization",
                 "BinaryFormatter and related serializers are vulnerable to remote code execution attacks.",
                 line, "Use System.Text.Json or Newtonsoft.Json with TypeNameHandling.None.")
        for i, line in enumerate(lines) if pattern.search(line)
    ]


def check_unsafe_reflection(file_path: str, lines: List[str], enabled: bool = True) -> List[CsharpFinding]:
    """csharp.unsafe-reflection: Assembly.Load or Activator.CreateInstance with variable (not string literal)."""
    if not enabled:
        return []
    pattern = re.compile(r'(?:Assembly\.Load\s*\([^")\n]|Activator\.CreateInstance\s*\([^")\n])')
    return [
        _finding(file_path, i + 1, "csharp.unsafe-reflection",
                 CsharpRuleCategory.SECURITY, CsharpSeverity.ERROR,
                 "Unsafe Reflection",
                 "Loading assemblies or creating instances from variable input allows arbitrary code execution.",
                 line, "Validate and whitelist allowed type names before using reflection.")
        for i, line in enumerate(lines) if pattern.search(line)
    ]


def check_no_debug_code(file_path: str, lines: List[str], enabled: bool = True) -> List[CsharpFinding]:
    """csharp.no-debug-code: Console.WriteLine/Debug.Print in production code."""
    if not enabled:
        return []
    pattern = re.compile(r'\b(?:Console\.Write(?:Line)?|Debug\.Print|System\.Diagnostics\.Debug\.Write)\s*\(')
    return [
        _finding(file_path, i + 1, "csharp.no-debug-code", CsharpRuleCategory.QUALITY, CsharpSeverity.INFO,
                 "Debug Output in Production Code",
                 "Console/Debug output should be replaced with structured logging.",
                 line, "Use ILogger<T> with Microsoft.Extensions.Logging.")
        for i, line in enumerate(lines) if pattern.search(line)
    ]
