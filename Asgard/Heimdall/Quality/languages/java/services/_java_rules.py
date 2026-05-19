"""Java security and quality rules (regex-based)."""

import re
from typing import List
from Asgard.Heimdall.Quality.languages.java.models.java_models import (
    JavaFinding, JavaRuleCategory, JavaSeverity,
)


def _finding(file_path, line_number, rule_id, category, severity, title, description, snippet="", fix=""):
    return JavaFinding(
        file_path=file_path, line_number=line_number, rule_id=rule_id,
        category=category, severity=severity, title=title,
        description=description, code_snippet=snippet.rstrip(), fix_suggestion=fix,
    )


def check_sql_injection(file_path: str, lines: List[str], enabled: bool = True) -> List[JavaFinding]:
    """java.sql-injection: string concatenation in SQL queries."""
    if not enabled:
        return []
    pattern = re.compile(r'(?:executeQuery|executeUpdate|execute|prepareStatement)\s*\(\s*"[^"]*"\s*\+')
    return [
        _finding(file_path, i + 1, "java.sql-injection", JavaRuleCategory.SECURITY, JavaSeverity.ERROR,
                 "SQL Injection via String Concatenation",
                 "Building SQL with string concatenation is vulnerable to injection.",
                 line, "Use PreparedStatement with parameterised queries.")
        for i, line in enumerate(lines) if pattern.search(line)
    ]


def check_no_system_exit(file_path: str, lines: List[str], enabled: bool = True) -> List[JavaFinding]:
    """java.no-system-exit: System.exit() outside main."""
    if not enabled:
        return []
    pattern = re.compile(r'\bSystem\.exit\s*\(')
    return [
        _finding(file_path, i + 1, "java.no-system-exit", JavaRuleCategory.QUALITY, JavaSeverity.WARNING,
                 "Use of System.exit()",
                 "System.exit() makes code untestable and can leave resources unclosed.",
                 line, "Throw an exception or use a return code instead.")
        for i, line in enumerate(lines) if pattern.search(line)
    ]


def check_no_print_stacktrace(file_path: str, lines: List[str], enabled: bool = True) -> List[JavaFinding]:
    """java.no-print-stacktrace: e.printStackTrace() instead of logging."""
    if not enabled:
        return []
    pattern = re.compile(r'\.printStackTrace\s*\(')
    return [
        _finding(file_path, i + 1, "java.no-print-stacktrace", JavaRuleCategory.QUALITY, JavaSeverity.WARNING,
                 "Use of printStackTrace()",
                 "printStackTrace() writes to stderr — use a logger instead.",
                 line, "Replace with logger.error(\"message\", e).")
        for i, line in enumerate(lines) if pattern.search(line)
    ]


def check_empty_catch(file_path: str, lines: List[str], enabled: bool = True) -> List[JavaFinding]:
    """java.empty-catch: empty catch blocks."""
    if not enabled:
        return []
    findings = []
    for i in range(len(lines) - 1):
        if re.search(r'catch\s*\([^)]+\)\s*\{', lines[i]) and re.match(r'\s*\}\s*$', lines[i + 1]):
            findings.append(_finding(file_path, i + 1, "java.empty-catch",
                JavaRuleCategory.QUALITY, JavaSeverity.ERROR,
                "Empty Catch Block", "Silently swallowing exceptions hides bugs.",
                lines[i], "Log the exception or rethrow."))
    return findings


def check_string_equals(file_path: str, lines: List[str], enabled: bool = True) -> List[JavaFinding]:
    """java.string-equals: == used to compare strings."""
    if not enabled:
        return []
    pattern = re.compile(r'(?:String|str)\s+\w+.*==\s*"|\".*==\s*(?:String|str)')
    return [
        _finding(file_path, i + 1, "java.string-equals", JavaRuleCategory.CORRECTNESS, JavaSeverity.ERROR,
                 "String Compared with ==",
                 "== compares references, not string content.",
                 line, "Use .equals() or Objects.equals().")
        for i, line in enumerate(lines) if pattern.search(line)
    ]


def check_no_hardcoded_credentials(file_path: str, lines: List[str], enabled: bool = True) -> List[JavaFinding]:
    """java.no-hardcoded-credentials: hardcoded passwords/tokens."""
    if not enabled:
        return []
    pattern = re.compile(r'(?:password|passwd|secret|api_?key|token)\s*=\s*"[^"]{4,}"', re.IGNORECASE)
    return [
        _finding(file_path, i + 1, "java.no-hardcoded-credentials",
                 JavaRuleCategory.SECURITY, JavaSeverity.ERROR,
                 "Hardcoded Credential",
                 "Credentials in source code are a security risk.",
                 line, "Use environment variables or a secrets manager.")
        for i, line in enumerate(lines) if pattern.search(line)
    ]


def check_no_raw_types(file_path: str, lines: List[str], enabled: bool = True) -> List[JavaFinding]:
    """java.no-raw-types: raw generic types."""
    if not enabled:
        return []
    pattern = re.compile(r'\b(?:List|Map|Set|Collection|Iterator)\s+\w+\s*[=;,)]')
    return [
        _finding(file_path, i + 1, "java.no-raw-types", JavaRuleCategory.QUALITY, JavaSeverity.WARNING,
                 "Raw Generic Type",
                 "Raw types bypass generic type safety.",
                 line, "Add type parameters, e.g. List<String>.")
        for i, line in enumerate(lines) if pattern.search(line)
    ]


def check_no_object_finalize(file_path: str, lines: List[str], enabled: bool = True) -> List[JavaFinding]:
    """java.no-object-finalize: calling finalize() directly."""
    if not enabled:
        return []
    pattern = re.compile(r'\.finalize\s*\(')
    return [
        _finding(file_path, i + 1, "java.no-object-finalize", JavaRuleCategory.QUALITY, JavaSeverity.WARNING,
                 "Direct call to finalize()",
                 "finalize() is deprecated and unreliable.",
                 line, "Use try-with-resources or explicit close().")
        for i, line in enumerate(lines) if pattern.search(line)
    ]
