"""
Heimdall Security Utilities

Helper functions for security scanning and analysis.
"""

import fnmatch
import math
import mimetypes
import re
from collections import Counter
from pathlib import Path
from typing import Generator, List, Optional, Set, Tuple


SECURITY_SCAN_EXTENSIONS: Set[str] = {
    ".py",
    ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs",
    ".java", ".kt", ".kts",
    ".go",
    ".rb",
    ".php",
    ".cs",
    ".c", ".h", ".cpp", ".hpp",
    ".rs",
    ".swift",
    ".sh", ".bash", ".zsh", ".ps1",
    ".sql",
    ".yaml", ".yml",
    ".json",
    ".xml",
    ".env",
    ".config",
    ".conf",
    ".ini",
    ".properties",
}

BINARY_EXTENSIONS: Set[str] = {
    ".exe", ".dll", ".so", ".dylib",
    ".pyc", ".pyo", ".class",
    ".o", ".obj", ".a", ".lib",
    ".zip", ".tar", ".gz", ".bz2", ".7z", ".rar",
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".svg",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx",
    ".mp3", ".mp4", ".wav", ".avi", ".mov",
    ".woff", ".woff2", ".ttf", ".eot",
    ".db", ".sqlite", ".sqlite3",
}

DEFAULT_EXCLUDE_DIRS: Set[str] = {
    "__pycache__",
    "node_modules",
    ".git",
    ".svn",
    ".hg",
    ".venv",
    "venv",
    "env",
    ".env",
    "build",
    "dist",
    ".next",
    "out",
    "coverage",
    ".pytest_cache",
    ".mypy_cache",
    ".tox",
    "eggs",
    ".eggs",
    ".cache",
    ".idea",
    ".vscode",
    "vendor",
    "target",
    "bin",
    "obj",
    ".gradle",
}


def is_binary_file(file_path: Path) -> bool:
    """
    Check if a file is likely binary.

    Args:
        file_path: Path to the file

    Returns:
        True if the file appears to be binary
    """
    ext = file_path.suffix.lower()
    if ext in BINARY_EXTENSIONS:
        return True

    mime_type, _ = mimetypes.guess_type(str(file_path))
    if mime_type:
        if not mime_type.startswith("text/") and not mime_type.startswith("application/json"):
            if "xml" not in mime_type and "javascript" not in mime_type:
                return True

    return False


def is_excluded_path(path: Path, exclude_patterns: List[str]) -> bool:
    """
    Check if a path should be excluded from scanning.

    Args:
        path: Path to check
        exclude_patterns: List of glob patterns to exclude

    Returns:
        True if the path should be excluded
    """
    path_str = str(path)
    path_name = path.name
    # Normalize path separators for cross-platform matching
    path_str_normalized = path_str.replace("\\", "/")

    if path_name.startswith("."):
        if path_name not in {".env", ".config", ".htaccess"}:
            return True

    for pattern in exclude_patterns:
        # Normalize pattern separators too
        pattern_normalized = pattern.replace("\\", "/")
        if fnmatch.fnmatch(path_name, pattern):
            return True
        if fnmatch.fnmatch(path_str_normalized, f"*/{pattern_normalized}/*"):
            return True
        if fnmatch.fnmatch(path_str_normalized, f"*/{pattern_normalized}"):
            return True
        # Also check if pattern appears anywhere in the path
        if pattern_normalized in path_str_normalized:
            return True

    if path.is_dir() and path_name in DEFAULT_EXCLUDE_DIRS:
        return True

    return False


def scan_directory_for_security(
    root_path: Path,
    exclude_patterns: Optional[List[str]] = None,
    include_extensions: Optional[List[str]] = None,
) -> Generator[Path, None, None]:
    """
    Recursively scan a directory for files to analyze for security issues.

    Args:
        root_path: Root directory to scan
        exclude_patterns: Additional patterns to exclude
        include_extensions: File extensions to include (None = use defaults)

    Yields:
        Paths to files that should be scanned
    """
    if exclude_patterns is None:
        exclude_patterns = []

    all_exclusions = list(DEFAULT_EXCLUDE_DIRS) + exclude_patterns

    if include_extensions:
        valid_extensions = {e if e.startswith(".") else f".{e}" for e in include_extensions}
    else:
        valid_extensions = SECURITY_SCAN_EXTENSIONS

    def _scan_recursive(current_path: Path) -> Generator[Path, None, None]:
        try:
            for entry in current_path.iterdir():
                if is_excluded_path(entry, all_exclusions):
                    continue

                if entry.is_dir():
                    yield from _scan_recursive(entry)
                elif entry.is_file():
                    ext = entry.suffix.lower()
                    if ext in valid_extensions and not is_binary_file(entry):
                        yield entry
                    elif entry.name in {".env", ".htaccess", "Dockerfile"}:
                        yield entry

        except PermissionError:
            pass

    yield from _scan_recursive(root_path)


def read_file_lines(file_path: Path) -> List[str]:
    """
    Read a file and return its lines.

    Args:
        file_path: Path to the file

    Returns:
        List of lines in the file
    """
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.readlines()
    except (IOError, OSError):
        return []


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
    Higher entropy indicates more randomness (potential secret).

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


def is_inside_docstring(content: str, match_start: int, file_ext: str = ".py") -> bool:
    """
    Check if a character position is inside a docstring or multi-line comment.

    This function properly handles:
    - Python triple-quoted strings (''' and \""")
    - JavaScript/TypeScript multi-line comments (/* */)
    - JSDoc comments (/** */)
    - String literals vs actual docstrings

    Args:
        content: Full file content
        match_start: Character offset to check
        file_ext: File extension for language-specific handling

    Returns:
        True if the position is inside a docstring or multi-line comment
    """
    if file_ext in {".py"}:
        # Find all Python docstring regions (triple-quoted strings)
        docstring_pattern = re.compile(
            r'(?P<triple>\'\'\'|\"\"\")'  # Opening delimiter
            r'.*?'                         # Content (non-greedy)
            r'(?P=triple)',               # Matching closing delimiter
            re.DOTALL
        )

        for match in docstring_pattern.finditer(content):
            if match.start() <= match_start < match.end():
                return True

    elif file_ext in {".js", ".jsx", ".ts", ".tsx", ".java", ".go", ".c", ".cpp", ".cs"}:
        # Find all multi-line comments /* */ including JSDoc /** */
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

    Checks for:
    - Single-line comments (#, //, --)
    - Multi-line docstrings (''' or \""")
    - Multi-line comments (/* */)
    - Lines starting with * (inside block comments)

    Args:
        content: Full file content
        lines: File content as list of lines
        line_number: Line number of the match (1-indexed)
        match_start: Character offset of the match
        file_ext: File extension for language detection

    Returns:
        True if the match is inside a comment or docstring
    """
    # First check single-line comments
    if line_number < 1 or line_number > len(lines):
        return False

    line = lines[line_number - 1].strip()

    # Single-line comment patterns by language
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

    # Check multi-line docstrings/comments
    if is_inside_docstring(content, match_start, file_ext):
        return True

    return False


def is_example_or_placeholder(text: str, context: str = "") -> bool:
    """
    Check if text appears to be an example or placeholder value.

    This helps filter out:
    - Documentation examples (password="mypassword")
    - Placeholder values (password="your_password_here")
    - Template variables (password="${PASSWORD}")

    Args:
        text: The text to check (e.g., the secret value)
        context: Surrounding context (e.g., 100 chars before/after)

    Returns:
        True if the text appears to be a placeholder/example
    """
    lower_text = text.lower()
    lower_context = context.lower()

    # Common placeholder/example patterns in the value itself
    placeholder_patterns = [
        r"^your[_-]?\w+$",           # your_password, your_key
        r"^my[_-]?\w+$",             # mypassword, my_key
        r"^\w*example\w*$",          # example, myexample
        r"^\w*sample\w*$",           # sample, mysample
        r"^\w*placeholder\w*$",      # placeholder
        r"^\w*changeme\w*$",         # changeme
        r"^\w*xxx+\w*$",             # xxx, xxxx
        r"^\w*test\w*$",             # test, testpassword
        r"^\w*demo\w*$",             # demo
        r"^\w*dummy\w*$",            # dummy
        r"^\*+$",                    # ****
        r"^\.{3,}$",                 # ...
        r"^\[.*\]$",                 # [PASSWORD]
        r"^<.*>$",                   # <password>
    ]

    for pattern in placeholder_patterns:
        if re.match(pattern, lower_text, re.IGNORECASE):
            return True

    # Check if context suggests it's documentation/example
    doc_indicators = [
        "example:", "example usage", "for example",
        "usage:", "usage example",
        ">>> ",  # Python doctest
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

    Parameterized queries pass values separately from the query string,
    which is the secure way to prevent SQL injection.

    Args:
        matched_text: The matched SQL-like text
        context: Surrounding code context

    Returns:
        True if the SQL appears to be properly parameterized
    """
    # Patterns indicating parameterized queries (SAFE):
    # - cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    # - cursor.execute("SELECT * FROM users WHERE id = ?", [user_id])
    # - conn.execute(text("..."), {"param": value})

    # Check if there's a tuple/list/dict passed as second argument
    safe_patterns = [
        # Python DB-API style: execute(query, (params,)) or execute(query, [params])
        r'execute\s*\([^)]+["\'],\s*[\(\[\{]',
        # SQLAlchemy bindparam style: text("..."), {"key": value}
        r'text\s*\([^)]+\)\s*,\s*\{',
        # Named parameters with :param style
        r':\w+',
        # The context has params passed separately
        r'\)\s*,\s*\{[^}]+\}',
        r'\)\s*,\s*\[[^\]]+\]',
        r'\)\s*,\s*\([^)]+\)',
    ]

    for pattern in safe_patterns:
        if re.search(pattern, context, re.IGNORECASE | re.DOTALL):
            return True

    return False
