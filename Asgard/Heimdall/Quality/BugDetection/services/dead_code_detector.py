"""
Heimdall Dead Code Detector

Detects code that is defined but never used within the same file:
1. Private methods (`_method`) in a class that are never called via `self._method(...)`  (MEDIUM)
2. Module-level private variables (`_VAR = ...`) never referenced anywhere in the file   (LOW)

Note: Dynamic dispatch via `getattr`, `__getattr__`, or external callers cannot be
statically detected. Results should be treated as candidates for review, not certainties.
"""

import ast
from pathlib import Path
from typing import Dict, List, Optional, Set

from Asgard.Heimdall.Quality.BugDetection.models.bug_models import (
    BugCategory,
    BugDetectionConfig,
    BugFinding,
    BugSeverity,
)


def _snippet(lines: List[str], n: int) -> str:
    idx = n - 1
    return lines[idx].strip() if 0 <= idx < len(lines) else ""


def _collect_self_attr_references(class_node: ast.ClassDef) -> Set[str]:
    """
    Collect every attribute name accessed as `self.X` within the class body.
    This covers both `self.method()` calls and `self.attr` reads.
    """
    refs: Set[str] = set()
    for node in ast.walk(class_node):
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "self"
        ):
            refs.add(node.attr)
    return refs


def _is_private_non_dunder(name: str) -> bool:
    """Return True for single-underscore private names (not dunder)."""
    return (
        name.startswith("_")
        and not name.startswith("__")
        and not name.endswith("__")
    )


class DeadCodeDetector:
    """
    Detects unused private methods and module-level private variables.

    Uses conservative heuristics — only flags names that are clearly never
    referenced within the same compilation unit (file or class body).
    """

    def __init__(self, config: Optional[BugDetectionConfig] = None) -> None:
        self.config = config or BugDetectionConfig()

    def analyze_file(self, file_path: Path, lines: List[str]) -> List[BugFinding]:
        """Analyse a single Python source file for dead code."""
        source = "\n".join(lines)
        fp = str(file_path)
        try:
            tree = ast.parse(source, filename=fp)
        except SyntaxError:
            return []

        findings: List[BugFinding] = []
        findings.extend(self._detect_unused_private_methods(tree, fp, lines))
        findings.extend(self._detect_unused_module_vars(tree, fp, lines))
        return findings

    # ── 1. Unused private methods in classes ──────────────────────────────────

    def _detect_unused_private_methods(
        self, tree: ast.AST, fp: str, lines: List[str]
    ) -> List[BugFinding]:
        findings: List[BugFinding] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue

            # Collect private method definitions (single-underscore, not dunder)
            private_methods: Dict[str, int] = {}  # name -> line number
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if _is_private_non_dunder(item.name):
                        private_methods[item.name] = item.lineno

            if not private_methods:
                continue

            # Collect every self.X attribute reference in the class (covers calls + reads)
            referenced = _collect_self_attr_references(node)

            for method_name, lineno in private_methods.items():
                if method_name not in referenced:
                    findings.append(BugFinding(
                        file_path=fp,
                        line_number=lineno,
                        category=BugCategory.DEAD_CODE,
                        severity=BugSeverity.MEDIUM,
                        title=f"Unused Private Method `{method_name}` in `{node.name}`",
                        description=(
                            f"Line {lineno}: Method `{method_name}` in class `{node.name}` "
                            "is declared private (single-underscore prefix) but is never "
                            "referenced via `self.{name}` anywhere in the class body."
                        ).replace("{name}", method_name),
                        code_snippet=_snippet(lines, lineno),
                        fix_suggestion=(
                            f"Remove `{method_name}` if it is no longer needed. "
                            "If it is called dynamically (e.g. via `getattr`), add a comment "
                            "explaining this to suppress the warning."
                        ),
                    ))
        return findings

    # ── 2. Unused module-level private variables ──────────────────────────────

    def _detect_unused_module_vars(
        self, tree: ast.AST, fp: str, lines: List[str]
    ) -> List[BugFinding]:
        """
        Detect module-level private variables (_VAR = ...) that are never
        read anywhere in the same file.
        """
        findings: List[BugFinding] = []

        # Collect module-level private variable assignments
        private_vars: Dict[str, int] = {}  # name -> line number
        for stmt in tree.body:
            if isinstance(stmt, ast.Assign):
                for target in stmt.targets:
                    if isinstance(target, ast.Name) and _is_private_non_dunder(target.id):
                        private_vars[target.id] = stmt.lineno
            elif isinstance(stmt, ast.AnnAssign):
                if (
                    isinstance(stmt.target, ast.Name)
                    and _is_private_non_dunder(stmt.target.id)
                    and stmt.value is not None
                ):
                    private_vars[stmt.target.id] = stmt.lineno

        if not private_vars:
            return findings

        # Collect every Name(Load) reference in the entire file
        all_reads: Set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                all_reads.add(node.id)

        for var_name, lineno in private_vars.items():
            if var_name not in all_reads:
                findings.append(BugFinding(
                    file_path=fp,
                    line_number=lineno,
                    category=BugCategory.DEAD_CODE,
                    severity=BugSeverity.LOW,
                    title=f"Unused Module-Level Private Variable `{var_name}`",
                    description=(
                        f"Line {lineno}: Module-level variable `{var_name}` is assigned "
                        "but never referenced (read) anywhere in this file."
                    ),
                    code_snippet=_snippet(lines, lineno),
                    fix_suggestion=(
                        f"Remove `{var_name}` if it is no longer needed, "
                        "or rename it without the underscore prefix if it is part of the "
                        "module's public interface."
                    ),
                ))
        return findings
