"""C++ security and quality rules (regex-based)."""

import re
from typing import List
from Asgard.Heimdall.Quality.languages.cpp.models.cpp_models import (
    CppFinding, CppRuleCategory, CppSeverity,
)


def _finding(file_path, line_number, rule_id, category, severity, title, description, snippet="", fix=""):
    return CppFinding(
        file_path=file_path, line_number=line_number, rule_id=rule_id,
        category=category, severity=severity, title=title,
        description=description, code_snippet=snippet.rstrip(), fix_suggestion=fix,
    )


def check_buffer_overflow(file_path: str, lines: List[str], enabled: bool = True) -> List[CppFinding]:
    """cpp.buffer-overflow: use of strcpy, gets, sprintf, strcat (unsafe C functions)."""
    if not enabled:
        return []
    pattern = re.compile(r'\b(?:strcpy|gets|sprintf|strcat)\s*\(')
    return [
        _finding(file_path, i + 1, "cpp.buffer-overflow", CppRuleCategory.SECURITY, CppSeverity.ERROR,
                 "Unsafe C String Function",
                 "Functions like strcpy, gets, sprintf, strcat do not perform bounds checking and can cause buffer overflows.",
                 line, "Use safe alternatives: strncpy, fgets, snprintf, strncat with explicit size limits.")
        for i, line in enumerate(lines) if pattern.search(line)
    ]


def check_format_string(file_path: str, lines: List[str], enabled: bool = True) -> List[CppFinding]:
    """cpp.format-string: printf(variable) pattern (no format string)."""
    if not enabled:
        return []
    pattern = re.compile(r'\bprintf\s*\(\s*[^")\n][^,)\n]*\)')
    return [
        _finding(file_path, i + 1, "cpp.format-string", CppRuleCategory.SECURITY, CppSeverity.ERROR,
                 "Format String Vulnerability",
                 "Passing a variable directly to printf without a format string allows format string attacks.",
                 line, 'Use printf("%s", msg) with an explicit format string.')
        for i, line in enumerate(lines) if pattern.search(line)
    ]


def check_integer_overflow(file_path: str, lines: List[str], enabled: bool = True) -> List[CppFinding]:
    """cpp.integer-overflow: signed integer arithmetic without bounds check (heuristic)."""
    if not enabled:
        return []
    pattern = re.compile(r'\bint\s+\w+\s*=\s*\w+\s*\*\s*\w+')
    return [
        _finding(file_path, i + 1, "cpp.integer-overflow", CppRuleCategory.CORRECTNESS, CppSeverity.WARNING,
                 "Potential Integer Overflow",
                 "Signed integer multiplication may overflow without bounds checking (heuristic detection).",
                 line, "Check operand ranges before multiplication or use a larger type with explicit cast.")
        for i, line in enumerate(lines) if pattern.search(line)
    ]


def check_memory_leak(file_path: str, lines: List[str], enabled: bool = True) -> List[CppFinding]:
    """cpp.memory-leak: new without corresponding delete in same scope (heuristic)."""
    if not enabled:
        return []
    pattern = re.compile(r'\bnew\s+[A-Z]\w*\s*[\(\[]')
    return [
        _finding(file_path, i + 1, "cpp.memory-leak", CppRuleCategory.QUALITY, CppSeverity.WARNING,
                 "Potential Memory Leak (Heuristic)",
                 "Heap allocation with 'new' detected; verify a corresponding 'delete' exists in all code paths.",
                 line, "Prefer smart pointers (std::unique_ptr, std::shared_ptr) over raw new/delete.")
        for i, line in enumerate(lines) if pattern.search(line)
    ]


def check_null_deref(file_path: str, lines: List[str], enabled: bool = True) -> List[CppFinding]:
    """cpp.null-deref: pointer dereference without null check (heuristic)."""
    if not enabled:
        return []
    findings = []
    assign_pattern = re.compile(r'\w+\s*=\s*\w+\s*\(')
    deref_pattern = re.compile(r'\w+\s*->')
    for i in range(1, len(lines)):
        if assign_pattern.search(lines[i - 1]) and deref_pattern.search(lines[i]):
            findings.append(_finding(
                file_path, i + 1, "cpp.null-deref", CppRuleCategory.CORRECTNESS, CppSeverity.WARNING,
                "Potential Null Pointer Dereference (Heuristic)",
                "Arrow dereference immediately after a function-call assignment without null check.",
                lines[i], "Check the pointer for null before dereferencing."
            ))
    return findings


def check_hardcoded_credentials(file_path: str, lines: List[str], enabled: bool = True) -> List[CppFinding]:
    """cpp.hardcoded-credentials: const char* password or string password assigned to string literal."""
    if not enabled:
        return []
    pattern = re.compile(r'(?:const\s+char\s*\*\s*|std::string\s+)(?:password|passwd|secret|api_?key|token)\s*=\s*"[^"]{1,}"', re.IGNORECASE)
    return [
        _finding(file_path, i + 1, "cpp.hardcoded-credentials", CppRuleCategory.SECURITY, CppSeverity.ERROR,
                 "Hardcoded Credential",
                 "Credentials stored directly in source code are a security risk.",
                 line, "Use environment variables or a secrets manager.")
        for i, line in enumerate(lines) if pattern.search(line)
    ]


def check_command_injection(file_path: str, lines: List[str], enabled: bool = True) -> List[CppFinding]:
    """cpp.command-injection: system( or popen( with variable."""
    if not enabled:
        return []
    pattern = re.compile(r'\b(?:system|popen)\s*\([^")\n]')
    return [
        _finding(file_path, i + 1, "cpp.command-injection", CppRuleCategory.SECURITY, CppSeverity.ERROR,
                 "Command Injection",
                 "Passing user-controlled data to system() or popen() allows arbitrary command execution.",
                 line, "Avoid system()/popen(); use execve() with a fixed argument array instead.")
        for i, line in enumerate(lines) if pattern.search(line)
    ]


def check_use_after_free(file_path: str, lines: List[str], enabled: bool = True) -> List[CppFinding]:
    """cpp.use-after-free: delete ptr followed by potential use of ptr."""
    if not enabled:
        return []
    pattern = re.compile(r'\bdelete\s+\w+')
    return [
        _finding(file_path, i + 1, "cpp.use-after-free", CppRuleCategory.SECURITY, CppSeverity.WARNING,
                 "Potential Use-After-Free (Review Required)",
                 "'delete' detected; verify the pointer is not accessed after deallocation.",
                 line, "Set the pointer to nullptr after delete and prefer smart pointers.")
        for i, line in enumerate(lines) if pattern.search(line)
    ]
