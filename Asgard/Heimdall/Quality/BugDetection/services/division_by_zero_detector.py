"""
Heimdall Division by Zero Detector

Detects division operations that will always raise ZeroDivisionError:
1. Literal zero as divisor: x / 0, x // 0, x % 0  (CRITICAL)
2. Variable that was assigned 0 and used as divisor without reassignment (HIGH)

Uses a scoped visitor so each function body is analysed independently,
preventing false positives from variables in unrelated scopes.
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


def _is_zero(node: ast.AST) -> bool:
    """Return True if node is the numeric literal 0 (int or float)."""
    return (
        isinstance(node, ast.Constant)
        and isinstance(node.value, (int, float))
        and not isinstance(node.value, bool)
        and node.value == 0
    )


class _ZeroDivVisitor(ast.NodeVisitor):
    """
    AST visitor that tracks zero-assigned variables within a scope and
    reports division/modulo operations where the divisor is provably zero.
    """

    def __init__(self, file_path_str: str, lines: List[str]) -> None:
        self.fp = file_path_str
        self.lines = lines
        self.findings: List[BugFinding] = []
        # var_name -> line_number where it was assigned 0
        self.zero_vars: Dict[str, int] = {}

    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            if isinstance(target, ast.Name):
                if _is_zero(node.value):
                    self.zero_vars[target.id] = node.lineno
                else:
                    self.zero_vars.pop(target.id, None)
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        # Any augmented assignment (+=, *=, etc.) means the value may no longer be zero.
        if isinstance(node.target, ast.Name):
            self.zero_vars.pop(node.target.id, None)
        self.generic_visit(node)

    def visit_BinOp(self, node: ast.BinOp) -> None:
        if isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod)):
            right = node.right

            # Case 1: literal 0 as divisor
            if _is_zero(right):
                op_sym = {ast.Div: "/", ast.FloorDiv: "//", ast.Mod: "%"}[type(node.op)]
                self.findings.append(BugFinding(
                    file_path=self.fp,
                    line_number=node.lineno,
                    category=BugCategory.DIVISION_BY_ZERO,
                    severity=BugSeverity.CRITICAL,
                    title=f"Division by Literal Zero (`{op_sym} 0`)",
                    description=(
                        f"Line {node.lineno}: Division by the literal value 0 using `{op_sym}`. "
                        "This will unconditionally raise ZeroDivisionError at runtime."
                    ),
                    code_snippet=_snippet(self.lines, node.lineno),
                    fix_suggestion=(
                        "Remove the division or guard with a non-zero check: "
                        "`if divisor != 0: result = x / divisor`"
                    ),
                ))

            # Case 2: variable provably zero (assigned 0 and not reassigned)
            elif isinstance(right, ast.Name) and right.id in self.zero_vars:
                assign_line = self.zero_vars[right.id]
                self.findings.append(BugFinding(
                    file_path=self.fp,
                    line_number=node.lineno,
                    category=BugCategory.DIVISION_BY_ZERO,
                    severity=BugSeverity.HIGH,
                    title=f"Division by Zero-Assigned Variable `{right.id}`",
                    description=(
                        f"Line {node.lineno}: Variable `{right.id}` was assigned 0 at "
                        f"line {assign_line} and is used as a divisor without reassignment. "
                        "This will raise ZeroDivisionError."
                    ),
                    code_snippet=_snippet(self.lines, node.lineno),
                    fix_suggestion=(
                        f"Add a zero check before dividing: "
                        f"`if {right.id} != 0: ...` or assign a non-zero value first."
                    ),
                ))

        self.generic_visit(node)


class DivisionByZeroDetector:
    """
    Detects division by zero patterns using Python AST analysis.

    Analyses both module-level code and individual function scopes to find
    literal zero divisors and variables that are provably zero at the point of division.
    """

    def __init__(self, config: Optional[BugDetectionConfig] = None) -> None:
        self.config = config or BugDetectionConfig()

    def analyze_file(self, file_path: Path, lines: List[str]) -> List[BugFinding]:
        """Analyse a single Python source file for division-by-zero bugs."""
        source = "\n".join(lines)
        fp = str(file_path)
        try:
            tree = ast.parse(source, filename=fp)
        except SyntaxError:
            return []

        all_findings: List[BugFinding] = []

        # Module-level scope
        module_visitor = _ZeroDivVisitor(fp, lines)
        for stmt in tree.body:
            module_visitor.visit(stmt)
        all_findings.extend(module_visitor.findings)

        # Each function scope independently
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                fn_visitor = _ZeroDivVisitor(fp, lines)
                fn_visitor.visit(node)
                all_findings.extend(fn_visitor.findings)

        # Deduplicate by (file, line, category)
        seen: Set[tuple] = set()
        unique: List[BugFinding] = []
        for f in all_findings:
            key = (f.file_path, f.line_number, f.category)
            if key not in seen:
                seen.add(key)
                unique.append(f)
        return unique
