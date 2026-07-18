"""
Finding Fingerprints — stable identity for analysis findings.

Implements the fingerprint scheme from the Heimdall-09 / Bragi-06 plans:

    fingerprint = sha256(rule_id + normalized_file_path + ast_node_signature)

The AST node signature is a structural hash of the innermost enclosing
function/class (or the whole module) with all line/column information
excluded, so refactors that merely shift lines do not churn fingerprints.

Anchor quality (best available wins):
    - "ast":     Python source parsed; enclosing-node structural hash.
    - "snippet": whitespace-normalized snippet hash (interim fallback for
                 languages without AST anchoring yet).
    - "file":    rule + file only (weakest; used when nothing else exists).

No network access, no external services, no project-specific assumptions.
"""

import ast
import hashlib
from pathlib import PurePath
from typing import Optional


def normalize_path(file_path: str) -> str:
    """Normalize a file path for fingerprinting: POSIX separators, no leading './'."""
    path = PurePath(str(file_path).strip().replace("\\", "/")).as_posix()
    while path.startswith("./"):
        path = path[2:]
    return path


def normalize_snippet(snippet: str) -> str:
    """Collapse all whitespace so formatting changes do not churn fingerprints."""
    return " ".join(snippet.split())


def _enclosing_node_signature(source: str, line: int) -> Optional[str]:
    """
    Structural hash of the innermost function/class enclosing `line`,
    or of the whole module if the line sits at top level.

    Returns None when the source cannot be parsed as Python.
    """
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return None

    enclosing: ast.AST = tree
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            start = node.lineno
            end = getattr(node, "end_lineno", None) or start
            if start <= line <= end:
                # Prefer the innermost (smallest) enclosing scope
                if enclosing is tree:
                    enclosing = node
                else:
                    cur_start = getattr(enclosing, "lineno", 0)
                    cur_end = getattr(enclosing, "end_lineno", 10 ** 9)
                    if start >= cur_start and end <= cur_end:
                        enclosing = node

    # ast.dump with default settings excludes lineno/col_offset attributes,
    # giving a purely structural representation.
    structure = ast.dump(enclosing)
    return hashlib.sha256(structure.encode("utf-8")).hexdigest()


def compute_fingerprint(
    rule_id: str,
    file_path: str,
    *,
    source: Optional[str] = None,
    line: Optional[int] = None,
    snippet: Optional[str] = None,
) -> str:
    """
    Compute a stable fingerprint for a finding.

    Args:
        rule_id: Rule identifier (e.g. "SQLI", "complexity.max").
        file_path: Path of the file containing the finding.
        source: Full source text of the file (enables AST anchoring for Python).
        line: 1-based line number of the finding within `source`.
        snippet: Source snippet at the finding site (interim non-AST anchor).

    Returns:
        Hex sha256 fingerprint. Same finding after a pure line-shift refactor
        keeps the same fingerprint when AST or snippet anchoring is available.
    """
    return fingerprint_with_anchor(
        rule_id, file_path, source=source, line=line, snippet=snippet
    )[0]


def fingerprint_with_anchor(
    rule_id: str,
    file_path: str,
    *,
    source: Optional[str] = None,
    line: Optional[int] = None,
    snippet: Optional[str] = None,
) -> tuple:
    """
    Compute (fingerprint, anchor) where anchor is 'ast', 'snippet', or 'file'.
    """
    norm_path = normalize_path(file_path)

    signature = None
    anchor = "file"
    if source is not None and line is not None:
        signature = _enclosing_node_signature(source, line)
        if signature is not None:
            anchor = "ast"
    if signature is None and snippet:
        normalized = normalize_snippet(snippet)
        if normalized:
            signature = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
            anchor = "snippet"
    if signature is None:
        signature = ""
        anchor = "file"

    payload = "\x00".join([str(rule_id), norm_path, signature])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest(), anchor
