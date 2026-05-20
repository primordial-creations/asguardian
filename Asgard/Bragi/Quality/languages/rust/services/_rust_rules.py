"""Rust security and quality rules (regex-based)."""

import re
from typing import List
from Asgard.Bragi.Quality.languages.rust.models.rust_models import (
    RustFinding, RustRuleCategory, RustSeverity,
)


def _finding(file_path, line_number, rule_id, category, severity, title, description, snippet="", fix=""):
    return RustFinding(
        file_path=file_path, line_number=line_number, rule_id=rule_id,
        category=category, severity=severity, title=title,
        description=description, code_snippet=snippet.rstrip(), fix_suggestion=fix,
    )


def check_unsafe_block(file_path: str, lines: List[str], enabled: bool = True) -> List[RustFinding]:
    """rust.unsafe-block: unsafe { or unsafe fn."""
    if not enabled:
        return []
    pattern = re.compile(r'\bunsafe\s*(?:\{|fn\b)')
    return [
        _finding(file_path, i + 1, "rust.unsafe-block", RustRuleCategory.SECURITY, RustSeverity.WARNING,
                 "Unsafe Block or Function",
                 "Unsafe code bypasses Rust's memory safety guarantees; review carefully.",
                 line, "Minimise unsafe surface; document invariants and consider a safe abstraction.")
        for i, line in enumerate(lines) if pattern.search(line)
    ]


def check_unwrap_in_production(file_path: str, lines: List[str], enabled: bool = True) -> List[RustFinding]:
    """rust.unwrap-in-production: .unwrap() or .expect( — panic risk."""
    if not enabled:
        return []
    pattern = re.compile(r'\.unwrap\s*\(\s*\)|\.expect\s*\(')
    return [
        _finding(file_path, i + 1, "rust.unwrap-in-production", RustRuleCategory.QUALITY, RustSeverity.WARNING,
                 "Panic Risk: unwrap/expect",
                 ".unwrap() and .expect() panic on None/Err and should be avoided in production paths.",
                 line, "Use ? operator, if let, or match to handle errors gracefully.")
        for i, line in enumerate(lines) if pattern.search(line)
    ]


def check_transmute(file_path: str, lines: List[str], enabled: bool = True) -> List[RustFinding]:
    """rust.transmute: mem::transmute or std::mem::transmute."""
    if not enabled:
        return []
    pattern = re.compile(r'(?:std::)?mem::transmute\b')
    return [
        _finding(file_path, i + 1, "rust.transmute", RustRuleCategory.SECURITY, RustSeverity.ERROR,
                 "Dangerous mem::transmute",
                 "transmute reinterprets bits between types with no safety checks; undefined behaviour is trivial to trigger.",
                 line, "Use safe conversion traits (From/Into, TryFrom/TryInto) or bytemuck crate instead.")
        for i, line in enumerate(lines) if pattern.search(line)
    ]


def check_raw_pointer_deref(file_path: str, lines: List[str], enabled: bool = True) -> List[RustFinding]:
    """rust.raw-pointer-deref: *mut or *const type declarations (heuristic)."""
    if not enabled:
        return []
    pattern = re.compile(r'\*(?:mut|const)\s+\w')
    return [
        _finding(file_path, i + 1, "rust.raw-pointer-deref", RustRuleCategory.SECURITY, RustSeverity.WARNING,
                 "Raw Pointer Usage",
                 "Raw pointer declarations bypass Rust's borrow checker; dereferences must be in unsafe blocks.",
                 line, "Prefer references, Box, or other safe pointer types over raw pointers.")
        for i, line in enumerate(lines) if pattern.search(line)
    ]


def check_command_injection(file_path: str, lines: List[str], enabled: bool = True) -> List[RustFinding]:
    """rust.command-injection: Command::new( with variable."""
    if not enabled:
        return []
    pattern = re.compile(r'Command::new\s*\(\s*[^"&)\n]')
    return [
        _finding(file_path, i + 1, "rust.command-injection", RustRuleCategory.SECURITY, RustSeverity.ERROR,
                 "Command Injection",
                 "Passing a variable to Command::new() without sanitisation allows arbitrary command execution.",
                 line, 'Use a hardcoded command string and pass user input only as validated .arg() arguments.')
        for i, line in enumerate(lines) if pattern.search(line)
    ]


def check_hardcoded_credentials(file_path: str, lines: List[str], enabled: bool = True) -> List[RustFinding]:
    """rust.hardcoded-credentials: let password, let secret, or let api_key assigned to string literal."""
    if not enabled:
        return []
    pattern = re.compile(r'\blet\s+(?:mut\s+)?(?:password|passwd|secret|api_?key|token)\s*[=:].*"[^"]{1,}"', re.IGNORECASE)
    return [
        _finding(file_path, i + 1, "rust.hardcoded-credentials", RustRuleCategory.SECURITY, RustSeverity.ERROR,
                 "Hardcoded Credential",
                 "Credentials stored directly in source code are a security risk.",
                 line, "Read credentials from environment variables or a secrets manager at runtime.")
        for i, line in enumerate(lines) if pattern.search(line)
    ]


def check_integer_overflow(file_path: str, lines: List[str], enabled: bool = True) -> List[RustFinding]:
    """rust.integer-overflow: as u8 or as i8 cast from larger type (truncation risk)."""
    if not enabled:
        return []
    pattern = re.compile(r'\bas\s+[ui](?:8|16)\b')
    return [
        _finding(file_path, i + 1, "rust.integer-overflow", RustRuleCategory.CORRECTNESS, RustSeverity.WARNING,
                 "Potential Integer Truncation",
                 "Casting to a smaller integer type with 'as' silently truncates in debug and release builds.",
                 line, "Use TryFrom/TryInto to get an error on out-of-range values instead of silent truncation.")
        for i, line in enumerate(lines) if pattern.search(line)
    ]


def check_path_traversal(file_path: str, lines: List[str], enabled: bool = True) -> List[RustFinding]:
    """rust.path-traversal: File::open( or fs::read( with variable that isn't a literal."""
    if not enabled:
        return []
    pattern = re.compile(r'(?:File::open|fs::read(?:_to_string)?)\s*\(\s*[^"&)\n]')
    return [
        _finding(file_path, i + 1, "rust.path-traversal", RustRuleCategory.SECURITY, RustSeverity.ERROR,
                 "Path Traversal",
                 "Opening a file path derived from user input without validation allows path traversal attacks.",
                 line, "Canonicalise the path and verify it is within the expected root directory.")
        for i, line in enumerate(lines) if pattern.search(line)
    ]
