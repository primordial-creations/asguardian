"""Go security and quality rules (regex-based)."""

import re
from typing import List
from Asgard.Heimdall.Quality.languages.go.models.go_models import (
    GoFinding, GoRuleCategory, GoSeverity,
)


def _finding(file_path, line_number, rule_id, category, severity, title, description, snippet="", fix=""):
    return GoFinding(
        file_path=file_path, line_number=line_number, rule_id=rule_id,
        category=category, severity=severity, title=title,
        description=description, code_snippet=snippet.rstrip(), fix_suggestion=fix,
    )


def check_error_not_checked(file_path: str, lines: List[str], enabled: bool = True) -> List[GoFinding]:
    """go.error-not-checked: _ used to discard error return."""
    if not enabled:
        return []
    pattern = re.compile(r'\b_\s*,?\s*=\s*\w+\.(?:Open|Read|Write|Close|Exec|Query|Scan|Decode)')
    return [
        _finding(file_path, i + 1, "go.error-not-checked", GoRuleCategory.CORRECTNESS, GoSeverity.WARNING,
                 "Error Return Ignored",
                 "Discarding errors with _ can hide failures.",
                 line, "Always check returned errors.")
        for i, line in enumerate(lines) if pattern.search(line)
    ]


def check_no_panic(file_path: str, lines: List[str], enabled: bool = True) -> List[GoFinding]:
    """go.no-panic: use of panic() in non-test code."""
    if not enabled:
        return []
    pattern = re.compile(r'\bpanic\s*\(')
    return [
        _finding(file_path, i + 1, "go.no-panic", GoRuleCategory.QUALITY, GoSeverity.WARNING,
                 "Use of panic()",
                 "panic() crashes the entire program; prefer returning an error.",
                 line, "Return an error value instead.")
        for i, line in enumerate(lines) if pattern.search(line)
    ]


def check_sql_injection(file_path: str, lines: List[str], enabled: bool = True) -> List[GoFinding]:
    """go.sql-injection: fmt.Sprintf used in db queries."""
    if not enabled:
        return []
    pattern = re.compile(r'db\.(?:Query|Exec|QueryRow)\s*\(\s*fmt\.Sprintf')
    return [
        _finding(file_path, i + 1, "go.sql-injection", GoRuleCategory.SECURITY, GoSeverity.ERROR,
                 "SQL Injection via fmt.Sprintf",
                 "Building SQL with fmt.Sprintf is vulnerable to injection.",
                 line, "Use parameterised queries with ? placeholders.")
        for i, line in enumerate(lines) if pattern.search(line)
    ]


def check_no_defer_in_loop(file_path: str, lines: List[str], enabled: bool = True) -> List[GoFinding]:
    """go.no-defer-in-loop: defer inside a for loop."""
    if not enabled:
        return []
    findings = []
    in_loop = False
    for i, line in enumerate(lines):
        if re.search(r'\bfor\b', line):
            in_loop = True
        if in_loop and re.search(r'\bdefer\b', line):
            findings.append(_finding(file_path, i + 1, "go.no-defer-in-loop",
                GoRuleCategory.QUALITY, GoSeverity.WARNING,
                "defer Inside for Loop",
                "defer runs at function return, not loop iteration end — resources accumulate.",
                line, "Call the deferred function explicitly or use a closure."))
        if re.match(r'^\s*}\s*$', line):
            in_loop = False
    return findings


def check_no_hardcoded_credentials(file_path: str, lines: List[str], enabled: bool = True) -> List[GoFinding]:
    """go.no-hardcoded-credentials: hardcoded passwords/tokens."""
    if not enabled:
        return []
    pattern = re.compile(r'(?:password|passwd|secret|apiKey|token)\s*:?=\s*"[^"]{4,}"', re.IGNORECASE)
    return [
        _finding(file_path, i + 1, "go.no-hardcoded-credentials",
                 GoRuleCategory.SECURITY, GoSeverity.ERROR,
                 "Hardcoded Credential",
                 "Credentials in source code are a security risk.",
                 line, "Use os.Getenv() or a secrets manager.")
        for i, line in enumerate(lines) if pattern.search(line)
    ]


def check_no_unbuffered_channel(file_path: str, lines: List[str], enabled: bool = True) -> List[GoFinding]:
    """go.no-unbuffered-channel: make(chan Type) without buffer."""
    if not enabled:
        return []
    pattern = re.compile(r'make\s*\(\s*chan\s+\w+\s*\)')
    return [
        _finding(file_path, i + 1, "go.no-unbuffered-channel", GoRuleCategory.PERFORMANCE, GoSeverity.INFO,
                 "Unbuffered Channel",
                 "Unbuffered channels block sender until receiver is ready.",
                 line, "Consider a buffered channel make(chan Type, size) if appropriate.")
        for i, line in enumerate(lines) if pattern.search(line)
    ]


def check_no_global_mutex(file_path: str, lines: List[str], enabled: bool = True) -> List[GoFinding]:
    """go.no-global-mutex: package-level sync.Mutex variable."""
    if not enabled:
        return []
    pattern = re.compile(r'^var\s+\w+\s+sync\.(?:Mutex|RWMutex)')
    return [
        _finding(file_path, i + 1, "go.no-global-mutex", GoRuleCategory.QUALITY, GoSeverity.WARNING,
                 "Global Mutex",
                 "Package-level mutexes create hidden coupling and are hard to test.",
                 line, "Embed the mutex in a struct instead.")
        for i, line in enumerate(lines) if pattern.search(line)
    ]


def check_context_not_propagated(file_path: str, lines: List[str], enabled: bool = True) -> List[GoFinding]:
    """go.context-not-propagated: context.Background() inside a function that has ctx."""
    if not enabled:
        return []
    pattern = re.compile(r'context\.(?:Background|TODO)\s*\(\s*\)')
    return [
        _finding(file_path, i + 1, "go.context-not-propagated", GoRuleCategory.QUALITY, GoSeverity.WARNING,
                 "context.Background() in Non-Root Function",
                 "Using context.Background() discards deadline/cancellation from the caller.",
                 line, "Pass the caller's ctx down instead.")
        for i, line in enumerate(lines) if pattern.search(line)
    ]
