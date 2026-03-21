"""
Heimdall Unreachable Code Detector

Detects code that can never execute using Python's AST module.

Patterns detected:
1. Code after return/break/continue/raise in the same block
2. Always-false conditions (if False:, if 0:, if None:, literal comparisons)
3. Always-true conditions (if True:, if 1:) — flags dead else-branches
4. Duplicate elif conditions (same condition as a preceding if/elif)
"""

import ast
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from Asgard.Heimdall.Quality.BugDetection.models.bug_models import (
    BugCategory,
    BugDetectionConfig,
    BugFinding,
    BugSeverity,
)


def _get_code_snippet(lines: List[str], line_number: int) -> str:
    """Return the source line at line_number (1-indexed), stripped."""
    idx = line_number - 1
    if 0 <= idx < len(lines):
        return lines[idx].strip()
    return ""


def _is_always_false(node: ast.AST) -> bool:
    """Check if a condition node always evaluates to False."""
    # Constant False
    if isinstance(node, ast.Constant):
        return not bool(node.value) and node.value is not True
    # NameConstant False (Python 3.7 compat)
    if hasattr(ast, "NameConstant") and isinstance(node, ast.NameConstant):  # type: ignore[attr-defined]
        return not bool(node.value) and node.value is not True
    # Literal string comparison like "" == "foo"
    if isinstance(node, ast.Compare):
        if isinstance(node.left, ast.Constant) and isinstance(node.left.value, str):
            for comparator in node.comparators:
                if isinstance(comparator, ast.Constant) and isinstance(comparator.value, str):
                    if node.left.value != comparator.value and len(node.ops) == 1 and isinstance(node.ops[0], ast.Eq):
                        return True
                    if node.left.value == comparator.value and len(node.ops) == 1 and isinstance(node.ops[0], ast.NotEq):
                        return True
    return False


def _is_always_true(node: ast.AST) -> bool:
    """Check if a condition node always evaluates to True (but not while True)."""
    if isinstance(node, ast.Constant):
        return bool(node.value) and node.value is not False
    if hasattr(ast, "NameConstant") and isinstance(node, ast.NameConstant):  # type: ignore[attr-defined]
        return bool(node.value) and node.value is not False
    return False


def _is_terminator(node: ast.AST) -> bool:
    """Check if a statement is a block terminator (return/break/continue/raise)."""
    return isinstance(node, (ast.Return, ast.Break, ast.Continue, ast.Raise))


def _condition_repr(node: ast.AST) -> Optional[str]:
    """
    Return a hashable string representation of a condition for duplicate detection.
    Returns None if the condition is too complex to compare.
    """
    if isinstance(node, ast.Constant):
        return repr(node.value)
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Compare):
        left = _condition_repr(node.left)
        ops = [type(op).__name__ for op in node.ops]
        comparators = [_condition_repr(c) for c in node.comparators]
        if left and all(c is not None for c in comparators):
            return f"{left} {ops} {comparators}"
    if isinstance(node, ast.BoolOp):
        values = [_condition_repr(v) for v in node.values]
        if all(v is not None for v in values):
            op_name = type(node.op).__name__
            return f"{op_name}({', '.join(values)})"  # type: ignore[arg-type]
    return None


class UnreachableCodeDetector:
    """
    Detects unreachable code patterns using Python AST analysis.

    Detects:
    - Code after return/break/continue/raise in the same block
    - Always-false conditions (if False:, if 0:, if None:)
    - Always-true conditions (if True:, if 1:) flagging dead else branches
    - Duplicate elif conditions
    """

    def __init__(self, config: Optional[BugDetectionConfig] = None):
        """
        Initialize the unreachable code detector.

        Args:
            config: Bug detection configuration. Uses defaults if not provided.
        """
        self.config = config or BugDetectionConfig()

    def analyze_file(self, file_path: Path, lines: List[str]) -> List[BugFinding]:
        """
        Analyze a single Python source file for unreachable code.

        Args:
            file_path: Path to the file.
            lines: Source lines of the file.

        Returns:
            List of BugFinding objects found in the file.
        """
        findings: List[BugFinding] = []
        source = "\n".join(lines)
        file_path_str = str(file_path)

        try:
            tree = ast.parse(source, filename=file_path_str)
        except SyntaxError:
            return findings

        findings.extend(self._analyze_stmt_list(tree.body, lines, file_path_str))

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                findings.extend(self._analyze_function(node, lines, file_path_str))
            elif isinstance(node, ast.ClassDef):
                findings.extend(self._analyze_stmt_list(node.body, lines, file_path_str))

        return findings

    def _analyze_function(
        self,
        func_node: ast.FunctionDef | ast.AsyncFunctionDef,
        lines: List[str],
        file_path_str: str,
    ) -> List[BugFinding]:
        """Analyze a function body for unreachable code."""
        findings = self._analyze_stmt_list(func_node.body, lines, file_path_str)
        for stmt in ast.walk(func_node):
            if isinstance(stmt, (ast.For, ast.While, ast.With, ast.Try)):
                if hasattr(stmt, "body"):
                    findings.extend(self._analyze_stmt_list(stmt.body, lines, file_path_str))
                if hasattr(stmt, "orelse") and stmt.orelse:
                    findings.extend(self._analyze_stmt_list(stmt.orelse, lines, file_path_str))
        return findings

    def _analyze_stmt_list(
        self,
        stmts: List[ast.stmt],
        lines: List[str],
        file_path_str: str,
    ) -> List[BugFinding]:
        """
        Analyze a list of statements for unreachable code patterns.

        Args:
            stmts: List of AST statement nodes.
            lines: Source lines for snippet extraction.
            file_path_str: File path string for findings.

        Returns:
            List of BugFinding objects.
        """
        findings: List[BugFinding] = []

        # 1. Check for code after a block terminator
        for i, stmt in enumerate(stmts):
            if _is_terminator(stmt) and i + 1 < len(stmts):
                next_stmt = stmts[i + 1]
                # Skip if the next statement is just a docstring constant (common pattern)
                is_docstring = (
                    isinstance(next_stmt, ast.Expr)
                    and isinstance(next_stmt.value, ast.Constant)
                    and isinstance(next_stmt.value.value, str)
                )
                if not is_docstring:
                    term_type = type(stmt).__name__.lower()
                    findings.append(BugFinding(
                        file_path=file_path_str,
                        line_number=next_stmt.lineno,
                        category=BugCategory.UNREACHABLE_CODE,
                        severity=BugSeverity.MEDIUM,
                        title="Unreachable Code After Block Terminator",
                        description=(
                            f"Code at line {next_stmt.lineno} can never execute because "
                            f"the preceding '{term_type}' statement at line {stmt.lineno} "
                            f"always transfers control away from this block."
                        ),
                        code_snippet=_get_code_snippet(lines, next_stmt.lineno),
                        fix_suggestion=(
                            f"Remove the unreachable code following the '{term_type}' statement, "
                            "or move it before the terminating statement."
                        ),
                    ))

        # 2. Check for always-false / always-true conditions and duplicate elif
        seen_conditions: List[str] = []

        for stmt in stmts:
            if not isinstance(stmt, ast.If):
                seen_conditions.clear()
                continue

            # Check always-false
            if _is_always_false(stmt.test):
                findings.append(BugFinding(
                    file_path=file_path_str,
                    line_number=stmt.lineno,
                    category=BugCategory.ALWAYS_FALSE,
                    severity=BugSeverity.MEDIUM,
                    title="Always-False Condition",
                    description=(
                        f"The condition at line {stmt.lineno} always evaluates to False. "
                        "The body of this if-block can never execute."
                    ),
                    code_snippet=_get_code_snippet(lines, stmt.lineno),
                    fix_suggestion=(
                        "Remove the dead if-block, or fix the condition logic."
                    ),
                ))

            # Check always-true
            elif _is_always_true(stmt.test):
                # while True is intentional - skip while loops
                if stmt.orelse:
                    findings.append(BugFinding(
                        file_path=file_path_str,
                        line_number=stmt.lineno,
                        category=BugCategory.ALWAYS_TRUE,
                        severity=BugSeverity.LOW,
                        title="Always-True Condition with Dead Else Branch",
                        description=(
                            f"The condition at line {stmt.lineno} always evaluates to True. "
                            "The else branch of this if-statement can never execute."
                        ),
                        code_snippet=_get_code_snippet(lines, stmt.lineno),
                        fix_suggestion=(
                            "Remove the dead else branch, or fix the condition logic."
                        ),
                    ))

            # Check for duplicate elif conditions
            cond_repr = _condition_repr(stmt.test)
            if cond_repr is not None and cond_repr in seen_conditions:
                findings.append(BugFinding(
                    file_path=file_path_str,
                    line_number=stmt.lineno,
                    category=BugCategory.UNREACHABLE_CODE,
                    severity=BugSeverity.MEDIUM,
                    title="Duplicate Condition in If/Elif Chain",
                    description=(
                        f"The condition at line {stmt.lineno} duplicates a preceding "
                        f"condition in the same if/elif chain. This branch can never execute "
                        f"because the earlier branch with the same condition already handled it."
                    ),
                    code_snippet=_get_code_snippet(lines, stmt.lineno),
                    fix_suggestion=(
                        "Remove the duplicate condition or fix the logic to use a different condition."
                    ),
                ))
            elif cond_repr is not None:
                seen_conditions.append(cond_repr)

            # Recurse into elif chains (orelse contains the next If node in a chain)
            if stmt.orelse:
                findings.extend(self._analyze_stmt_list(stmt.orelse, lines, file_path_str))

        return findings
