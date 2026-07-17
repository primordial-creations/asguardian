"""
Heimdall Cryptographic Validation Service - Helper Functions

Standalone helper functions for false-positive filtering, severity
comparison, and secure cryptographic recommendations.
"""

import ast
import re
from pathlib import Path
from typing import List

from Asgard.Heimdall.Security.models.security_models import SecuritySeverity


def is_usedforsecurity_false(
    file_path: Path,
    content: str,
    match_start: int,
    match_text: str,
) -> bool:
    """Plan 07.4: honor Python's ``hashlib.md5(..., usedforsecurity=False)``
    / ``hashlib.new("md5", ..., usedforsecurity=False)`` kwarg -- the
    stdlib's own escape hatch for non-cryptographic uses (checksums, cache
    keys, dedup) of a "weak" hash. When present, the call is explicitly
    declaring it is NOT relying on the algorithm's security properties, so
    the finding should be suppressed rather than reported as a crypto
    weakness.

    This only applies to Python files (the kwarg is Python-specific); for
    other languages this always returns False (no suppression), matching
    prior behaviour. Detection is line-local AST parsing of just the
    matched call expression when possible, falling back to a regex check
    on the surrounding text if the file doesn't parse as a whole (e.g. the
    match sits inside an f-string or a non-Python-looking snippet).

    Two adversarial-review fixes (BLOCKER-2 / BLOCKER-3) are load-bearing
    here:

    * BLOCKER-2 -- when the AST parse *succeeds*, its verdict is
      authoritative and we return immediately (True or False). We only
      fall through to the textual regex fallback when ``ast.parse`` itself
      raised ``SyntaxError`` (the window was truncated mid-expression).
      Previously, a successful parse that found no matching kwarg still
      fell through to the regex fallback, which matches inside comments --
      e.g. ``hashlib.md5(password)  # usedforsecurity=False`` was wrongly
      suppressed even though there is no such kwarg in the actual code.
    * BLOCKER-3 -- the AST path only honors ``usedforsecurity=False`` when
      it is a keyword on the SPECIFIC call whose span contains
      ``match_start`` -- not any ``ast.Call`` anywhere in the 300-char
      window. Previously ``hashlib.md5(pw).hexdigest()`` followed by
      ``other_call(y, usedforsecurity=False)`` on the next line was wrongly
      suppressed because the walk found the kwarg on the unrelated call.
    """
    if file_path.suffix.lower() != ".py":
        return False

    line_start = content.rfind("\n", 0, match_start) + 1
    # Look a little past the matched call for the closing paren/kwarg,
    # since `usedforsecurity=False` can appear after other args.
    window_end = min(len(content), match_start + 300)
    window = content[line_start:window_end]
    rel_offset = match_start - line_start

    def _offset_to_linecol(text: str, offset: int):
        line = text.count("\n", 0, offset) + 1
        col = offset - (text.rfind("\n", 0, offset) + 1)
        return line, col

    target_line, target_col = _offset_to_linecol(window, rel_offset)

    try:
        tree = ast.parse(window)
    except SyntaxError:
        # A window starting mid-block (e.g. an indented line) often fails
        # to parse purely due to leading indentation; retry with the
        # leading whitespace stripped, adjusting the target position to
        # match so BLOCKER-3's span containment check still lines up.
        lstripped = window.lstrip()
        stripped_len = len(window) - len(lstripped)
        try:
            tree = ast.parse(lstripped)
            adj_line, adj_col = _offset_to_linecol(lstripped, max(0, rel_offset - stripped_len))
            target_line, target_col = adj_line, adj_col
        except SyntaxError:
            tree = None

    if tree is not None:
        # AST parse succeeded: its verdict is authoritative (BLOCKER-2).
        # Find the specific Call node whose span contains the matched
        # text's position, and only inspect ITS keywords (BLOCKER-3).
        best: "ast.Call | None" = None
        best_span = None
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            end_lineno = getattr(node, "end_lineno", None)
            end_col = getattr(node, "end_col_offset", None)
            if end_lineno is None or end_col is None:
                continue
            start = (node.lineno, node.col_offset)
            end = (end_lineno, end_col)
            target = (target_line, target_col)
            if not (start <= target <= end):
                continue
            # Prefer the smallest (most specific / innermost) enclosing
            # call span -- e.g. `hashlib.md5(x).hexdigest()` should match
            # the `hashlib.md5(x)` call, not the outer `.hexdigest()` call.
            span = (end_lineno, end_col, node.lineno, -node.col_offset)
            if best is None or span < best_span:
                best = node
                best_span = span
        if best is not None:
            for kw in best.keywords:
                if kw.arg == "usedforsecurity" and isinstance(kw.value, ast.Constant) \
                        and kw.value.value is False:
                    return True
        return False

    # Fallback: the AST parse of a truncated window failed (the call's
    # closing paren may be past `window_end`, or it sits inside a larger
    # expression) -- a bounded textual check on the same window is a
    # reasonable, documented approximation for that case. Comments must be
    # stripped first so `# usedforsecurity=False` never counts (BLOCKER-2).
    code_only_lines = []
    for line in window.splitlines():
        code_only_lines.append(re.sub(r"#.*$", "", line))
    code_only = "\n".join(code_only_lines)
    return bool(re.search(r"usedforsecurity\s*=\s*False", code_only))


def is_in_test_context(
    file_path: Path,
    lines: List[str],
    line_number: int,
) -> bool:
    """
    Check if a finding is in a test context.

    Some weak crypto usage is acceptable in tests.

    Args:
        file_path: Path to the file
        lines: File content lines
        line_number: Line number of the finding

    Returns:
        True if the finding is in a test context
    """
    file_name = file_path.name.lower()
    if "test" in file_name or "_test" in file_name or "spec" in file_name:
        return False

    return False


def is_iv_nonce_false_positive(
    content: str,
    match_start: int,
    lines: List[str],
    line_number: int,
) -> bool:
    """
    Check if a static IV/nonce match is a false positive.

    Args:
        content: Full file content
        match_start: Start position of the match
        lines: File content as lines
        line_number: Line number of the match

    Returns:
        True if this appears to be a false positive
    """
    context_start = max(0, match_start - 200)
    context_end = min(len(content), match_start + 200)
    context = content[context_start:context_end]

    validation_patterns = [
        r"includes\s*\(",
        r"contains\s*\(",
        r"validate",
        r"check",
        r"verify",
        r"match\s*\(",
        r"test\s*\(",
        r"search\s*\(",
        r"indexOf\s*\(",
    ]

    for pattern in validation_patterns:
        if re.search(pattern, context, re.IGNORECASE):
            return True

    if re.search(r'\$\{[^}]+\}', context):
        return True

    if re.search(r'\{[a-z_][a-z_0-9]*\}', context, re.IGNORECASE):
        return True

    line = lines[line_number - 1] if line_number <= len(lines) else ""
    if re.search(r'(?:random|generate|create|crypto\.)', line, re.IGNORECASE):
        return True

    for i in range(line_number - 1, max(0, line_number - 20), -1):
        if i < len(lines):
            fn_line = lines[i].strip()
            if fn_line.startswith("def ") or fn_line.startswith("function ") or "=>" in fn_line:
                if re.search(r'generate|create|random', fn_line, re.IGNORECASE):
                    return True
                break

    return False


def severity_meets_threshold(severity: str, min_severity: str) -> bool:
    """Check if a severity level meets the configured threshold."""
    severity_order = {
        SecuritySeverity.INFO.value: 0,
        SecuritySeverity.LOW.value: 1,
        SecuritySeverity.MEDIUM.value: 2,
        SecuritySeverity.HIGH.value: 3,
        SecuritySeverity.CRITICAL.value: 4,
    }

    min_level = severity_order.get(min_severity, 1)
    finding_level = severity_order.get(severity, 1)

    return finding_level >= min_level


def severity_order(severity: str) -> int:
    """Get sort order for severity (critical first)."""
    order = {
        SecuritySeverity.CRITICAL.value: 0,
        SecuritySeverity.HIGH.value: 1,
        SecuritySeverity.MEDIUM.value: 2,
        SecuritySeverity.LOW.value: 3,
        SecuritySeverity.INFO.value: 4,
    }
    return order.get(severity, 5)


def get_secure_recommendations() -> dict:
    """
    Get recommendations for secure cryptographic implementations.

    Returns:
        Dictionary of recommendations by category
    """
    return {
        "hashing": {
            "general": "SHA-256 or SHA-3",
            "passwords": "Argon2id (preferred), bcrypt, or scrypt",
            "avoid": ["MD5", "SHA-1"],
        },
        "symmetric_encryption": {
            "recommended": "AES-256-GCM or ChaCha20-Poly1305",
            "key_size": "256 bits minimum",
            "mode": "GCM, CCM, or CBC with HMAC",
            "avoid": ["DES", "3DES", "ECB mode", "RC4"],
        },
        "asymmetric_encryption": {
            "rsa": "RSA-2048 minimum, RSA-4096 preferred",
            "ecc": "P-256, P-384, or Ed25519",
            "avoid": ["RSA-1024 or smaller", "DSA"],
        },
        "random_numbers": {
            "python": "secrets module",
            "javascript": "crypto.randomBytes or crypto.getRandomValues",
            "java": "SecureRandom",
            "avoid": ["random module", "Math.random()"],
        },
        "tls": {
            "minimum_version": "TLS 1.2",
            "preferred_version": "TLS 1.3",
            "verify_certificates": True,
            "avoid": ["SSL 2.0", "SSL 3.0", "TLS 1.0", "TLS 1.1"],
        },
        "jwt": {
            "algorithms": ["RS256", "RS384", "RS512", "ES256", "ES384", "ES512"],
            "secret_size": "256 bits minimum for HS256",
            "avoid": ["none algorithm", "HS256 with weak secrets"],
        },
    }
