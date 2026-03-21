"""
Heimdall Security Comment Detection Utilities

Helpers for detecting comments, docstrings, and placeholder values.
"""

import re
from typing import List


def is_inside_docstring(content: str, match_start: int, file_ext: str = ".py") -> bool:
    """
    Check if a character position is inside a docstring or multi-line comment.

    Args:
        content: Full file content
        match_start: Character offset to check
        file_ext: File extension for language-specific handling

    Returns:
        True if the position is inside a docstring or multi-line comment
    """
    if file_ext in {".py"}:
        docstring_pattern = re.compile(
            r'(?P<triple>\'\'\'|\"\"\")'
            r'.*?'
            r'(?P=triple)',
            re.DOTALL
        )

        for match in docstring_pattern.finditer(content):
            if match.start() <= match_start < match.end():
                return True

    elif file_ext in {".js", ".jsx", ".ts", ".tsx", ".java", ".go", ".c", ".cpp", ".cs"}:
        comment_pattern = re.compile(
            r'/\*.*?\*/',
            re.DOTALL
        )

        for match in comment_pattern.finditer(content):
            if match.start() <= match_start < match.end():
                return True

    return False


def is_in_comment_or_docstring(
    content: str,
    lines: List[str],
    line_number: int,
    match_start: int,
    file_ext: str = ".py"
) -> bool:
    """
    Comprehensive check if a match is in a comment or docstring.

    Args:
        content: Full file content
        lines: File content as list of lines
        line_number: Line number of the match (1-indexed)
        match_start: Character offset of the match
        file_ext: File extension for language detection

    Returns:
        True if the match is inside a comment or docstring
    """
    if line_number < 1 or line_number > len(lines):
        return False

    line = lines[line_number - 1].strip()

    if file_ext == ".py":
        if line.startswith("#"):
            return True
    elif file_ext in {".js", ".jsx", ".ts", ".tsx", ".java", ".go", ".c", ".cpp", ".cs", ".swift", ".kt"}:
        if line.startswith("//") or line.startswith("*"):
            return True
    elif file_ext == ".sql":
        if line.startswith("--"):
            return True
    elif file_ext in {".sh", ".bash", ".zsh", ".yaml", ".yml"}:
        if line.startswith("#"):
            return True

    if is_inside_docstring(content, match_start, file_ext):
        return True

    return False


def is_example_or_placeholder(text: str, context: str = "") -> bool:
    """
    Check if text appears to be an example or placeholder value.

    Args:
        text: The text to check (e.g., the secret value)
        context: Surrounding context (e.g., 100 chars before/after)

    Returns:
        True if the text appears to be a placeholder/example
    """
    lower_text = text.lower()
    lower_context = context.lower()

    placeholder_patterns = [
        r"^your[_-]?\w+$",
        r"^my[_-]?\w+$",
        r"^\w*example\w*$",
        r"^\w*sample\w*$",
        r"^\w*placeholder\w*$",
        r"^\w*changeme\w*$",
        r"^\w*xxx+\w*$",
        r"^\w*test\w*$",
        r"^\w*demo\w*$",
        r"^\w*dummy\w*$",
        r"^\*+$",
        r"^\.{3,}$",
        r"^\[.*\]$",
        r"^<.*>$",
    ]

    for pattern in placeholder_patterns:
        if re.match(pattern, lower_text, re.IGNORECASE):
            return True

    doc_indicators = [
        "example:", "example usage", "for example",
        "usage:", "usage example",
        ">>> ",
        "e.g.", "e.g.,", "i.e.",
        "sample code", "sample usage",
        "how to use", "getting started",
        "replace with", "substitute with",
        "your actual", "your real",
    ]

    for indicator in doc_indicators:
        if indicator in lower_context:
            return True

    return False


def is_parameterized_sql(matched_text: str, context: str) -> bool:
    """
    Check if SQL appears to use parameterized queries (safe pattern).

    Args:
        matched_text: The matched SQL-like text
        context: Surrounding code context

    Returns:
        True if the SQL appears to be properly parameterized
    """
    safe_patterns = [
        r'execute\s*\([^)]+["\'],\s*[\(\[\{]',
        r'text\s*\([^)]+\)\s*,\s*\{',
        r':\w+',
        r'\)\s*,\s*\{[^}]+\}',
        r'\)\s*,\s*\[[^\]]+\]',
        r'\)\s*,\s*\([^)]+\)',
    ]

    for pattern in safe_patterns:
        if re.search(pattern, context, re.IGNORECASE | re.DOTALL):
            return True

    return False
