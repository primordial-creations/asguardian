"""Java security and quality rules (regex-based)."""

import re
from typing import List
from Asgard.Bragi.Quality.languages.java.models.java_models import (
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
    # Direct concatenation in execute calls
    inline = re.compile(r'(?:executeQuery|executeUpdate|execute|prepareStatement)\s*\(\s*"[^"]*"\s*\+')
    # String query = "SELECT ... " + variable  (build-then-execute pattern)
    build = re.compile(r'(?:String\s+\w*[Qq]uery\w*|String\s+\w*[Ss]ql\w*|String\s+\w*[Ss]tmt\w*)\s*=\s*"[^"]*"\s*\+')
    findings = []
    for i, line in enumerate(lines):
        if inline.search(line) or build.search(line):
            findings.append(_finding(
                file_path, i + 1, "java.sql-injection", JavaRuleCategory.SECURITY, JavaSeverity.ERROR,
                "SQL Injection via String Concatenation",
                "Building SQL with string concatenation is vulnerable to injection.",
                line, "Use PreparedStatement with parameterised queries."))
    return findings


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


def check_command_injection(file_path: str, lines: List[str], enabled: bool = True) -> List[JavaFinding]:
    """java.command-injection: Runtime.getRuntime().exec( with variable concatenation."""
    if not enabled:
        return []
    pattern = re.compile(r'Runtime\.getRuntime\s*\(\s*\)\.exec\s*\([^)]*\+')
    return [
        _finding(file_path, i + 1, "java.command-injection", JavaRuleCategory.SECURITY, JavaSeverity.ERROR,
                 "Command Injection",
                 "Passing user-controlled data to Runtime.exec() allows arbitrary command execution.",
                 line, "Use ProcessBuilder with a String[] argument array; never concatenate user input.")
        for i, line in enumerate(lines) if pattern.search(line)
    ]


def check_xss(file_path: str, lines: List[str], enabled: bool = True) -> List[JavaFinding]:
    """java.xss: writing unescaped request data to the response."""
    if not enabled:
        return []
    # Direct write of request param
    direct = re.compile(r'(?:response\.getWriter|getWriter\s*\(\s*\))\s*.*print\w*\s*\([^)]*(?:request\.getParameter|req\.getParameter|getParameter)')
    # ResponseBody/ModelAttribute returning user input (Spring MVC)
    spring = re.compile(r'return\s+(?:request\.getParameter|req\.getParameter|params\.get)\s*\(')
    # setAttribute with raw request param
    attr = re.compile(r'setAttribute\s*\([^)]*(?:request\.getParameter|req\.getParameter)')
    findings = []
    for i, line in enumerate(lines):
        if direct.search(line) or spring.search(line) or attr.search(line):
            findings.append(_finding(
                file_path, i + 1, "java.xss", JavaRuleCategory.SECURITY, JavaSeverity.ERROR,
                "Cross-Site Scripting (XSS)",
                "Writing unescaped request parameters to the response enables XSS.",
                line, "Escape output with OWASP Java Encoder or use a template engine that auto-escapes."))
    return findings


def check_weak_crypto(file_path: str, lines: List[str], enabled: bool = True) -> List[JavaFinding]:
    """java.weak-crypto: MessageDigest.getInstance with MD5 or SHA-1."""
    if not enabled:
        return []
    pattern = re.compile(r'MessageDigest\.getInstance\s*\(\s*"(?:MD5|SHA-1)"', re.IGNORECASE)
    return [
        _finding(file_path, i + 1, "java.weak-crypto", JavaRuleCategory.SECURITY, JavaSeverity.ERROR,
                 "Weak Cryptographic Hash Algorithm",
                 "MD5 and SHA-1 are cryptographically broken.",
                 line, "Use SHA-256 or stronger: MessageDigest.getInstance(\"SHA-256\").")
        for i, line in enumerate(lines) if pattern.search(line)
    ]


def check_path_traversal(file_path: str, lines: List[str], enabled: bool = True) -> List[JavaFinding]:
    """java.path-traversal: new File( with request parameter concatenation."""
    if not enabled:
        return []
    pattern = re.compile(r'new\s+File\s*\([^)]*(?:request\.getParameter|req\.getParameter|getParam)')
    return [
        _finding(file_path, i + 1, "java.path-traversal", JavaRuleCategory.SECURITY, JavaSeverity.ERROR,
                 "Path Traversal via User-Controlled File Path",
                 "Using request parameters directly in new File() allows path traversal.",
                 line, "Validate the path and use Path.normalize(); ensure it stays within the expected root.")
        for i, line in enumerate(lines) if pattern.search(line)
    ]


def check_no_script_engine_eval(file_path: str, lines: List[str], enabled: bool = True) -> List[JavaFinding]:
    """java.no-eval: ScriptEngine eval() executes arbitrary code."""
    if not enabled:
        return []
    pattern = re.compile(r'\beval\s*\(')
    # Only flag if ScriptEngine is referenced nearby — simple heuristic: flag eval( in any line
    # that also contains script engine context, or flag broadly
    return [
        _finding(file_path, i + 1, "java.no-eval", JavaRuleCategory.SECURITY, JavaSeverity.ERROR,
                 "ScriptEngine eval() Executes Arbitrary Code",
                 "Calling eval() on a ScriptEngine with user-controlled input allows code injection.",
                 line, "Avoid dynamic script evaluation; use a safe expression library instead.")
        for i, line in enumerate(lines) if pattern.search(line) and "engine" in line.lower()
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
