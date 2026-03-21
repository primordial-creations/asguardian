"""
Heimdall Security Utilities

Re-exports all security utility functions for backward compatibility.
"""

import math
from collections import Counter
from typing import List, Tuple

from Asgard.Heimdall.Security.utilities._scan_utils import (
    BINARY_EXTENSIONS,
    DEFAULT_EXCLUDE_DIRS,
    SECURITY_SCAN_EXTENSIONS,
    is_binary_file,
    is_excluded_path,
    read_file_lines,
    scan_directory_for_security,
)
from Asgard.Heimdall.Security.utilities._comment_utils import (
    is_example_or_placeholder,
    is_in_comment_or_docstring,
    is_inside_docstring,
    is_parameterized_sql,
)


def extract_code_snippet(
    lines: List[str],
    line_number: int,
    context_lines: int = 2
) -> str:
    """
    Extract a code snippet around a specific line.

    Args:
        lines: List of file lines
        line_number: Line number (1-indexed)
        context_lines: Number of context lines before and after

    Returns:
        Code snippet with context
    """
    if not lines or line_number < 1:
        return ""

    start_idx = max(0, line_number - 1 - context_lines)
    end_idx = min(len(lines), line_number + context_lines)

    snippet_lines = []
    for i in range(start_idx, end_idx):
        line_num = i + 1
        marker = ">>> " if line_num == line_number else "    "
        snippet_lines.append(f"{marker}{line_num}: {lines[i].rstrip()}")

    return "\n".join(snippet_lines)


def mask_secret(secret: str, visible_chars: int = 4) -> str:
    """
    Mask a secret value for safe display.

    Args:
        secret: The secret value to mask
        visible_chars: Number of characters to show at start and end

    Returns:
        Masked secret string
    """
    if len(secret) <= visible_chars * 2:
        return "*" * len(secret)

    return f"{secret[:visible_chars]}{'*' * (len(secret) - visible_chars * 2)}{secret[-visible_chars:]}"


def get_cwe_url(cwe_id: str) -> str:
    """
    Get the URL for a CWE entry.

    Args:
        cwe_id: CWE ID (e.g., "CWE-89")

    Returns:
        URL to the CWE entry
    """
    cwe_num = cwe_id.replace("CWE-", "").replace("cwe-", "")
    return f"https://cwe.mitre.org/data/definitions/{cwe_num}.html"


def get_owasp_url(category: str) -> str:
    """
    Get the URL for an OWASP category.

    Args:
        category: OWASP category identifier

    Returns:
        URL to the OWASP page
    """
    return f"https://owasp.org/Top10/A{category.zfill(2)}/"


def calculate_entropy(data: str) -> float:
    """
    Calculate the Shannon entropy of a string.

    Args:
        data: String to analyze

    Returns:
        Entropy value (bits per character)
    """
    if not data:
        return 0.0

    counter = Counter(data)
    length = len(data)
    entropy = 0.0

    for count in counter.values():
        probability = count / length
        if probability > 0:
            entropy -= probability * math.log2(probability)

    return entropy


def find_line_column(content: str, match_start: int) -> Tuple[int, int]:
    """
    Convert a character offset to line and column numbers.

    Args:
        content: Full file content
        match_start: Character offset of the match

    Returns:
        Tuple of (line_number, column_number), both 1-indexed
    """
    lines = content[:match_start].split("\n")
    line_number = len(lines)
    column_number = len(lines[-1]) + 1 if lines else 1
    return line_number, column_number


__all__ = [
    "SECURITY_SCAN_EXTENSIONS",
    "BINARY_EXTENSIONS",
    "DEFAULT_EXCLUDE_DIRS",
    "is_binary_file",
    "is_excluded_path",
    "scan_directory_for_security",
    "read_file_lines",
    "extract_code_snippet",
    "mask_secret",
    "get_cwe_url",
    "get_owasp_url",
    "calculate_entropy",
    "find_line_column",
    "is_inside_docstring",
    "is_in_comment_or_docstring",
    "is_example_or_placeholder",
    "is_parameterized_sql",
]
