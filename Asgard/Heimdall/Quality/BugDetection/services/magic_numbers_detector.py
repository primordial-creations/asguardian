"""
Heimdall Magic Numbers Detector

Detects hard-coded numeric literals used directly in expressions instead of
named constants, which reduces readability and makes maintenance harder.

What is flagged:
- Integer or float literals other than {-1, 0, 1, 2, 100} used in:
    * Arithmetic binary operations  (BinOp)
    * Comparisons                   (Compare)
    * Return statements             (Return)
    * Slice indices when non-trivial

What is NOT flagged:
- Constants in named assignments (UPPER_CASE = 42)
- 0, 1, -1, 2, 100 (universal idioms)
- Boolean values True/False (not numeric in this context)
- Type annotations / default parameter values
"""

import ast
from pathlib import Path
from typing import List, Optional, Set

from Asgard.Heimdall.Quality.BugDetection.models.bug_models import (
    BugCategory,
    BugDetectionConfig,
    BugFinding,
    BugSeverity,
)

# Numeric values that are universally idiomatic and should not be flagged
_EXEMPT_INTS: Set[int] = {-1, 0, 1, 2, 100}
_EXEMPT_FLOATS: Set[float] = {-1.0, 0.0, 0.5, 1.0, 2.0, 100.0}


def _snippet(lines: List[str], n: int) -> str:
    idx = n - 1
    return lines[idx].strip() if 0 <= idx < len(lines) else ""


def _is_magic(node: ast.Constant) -> bool:
    """Return True if the constant is a magic number worth flagging."""
    if isinstance(node.value, bool):
        return False
    if isinstance(node.value, int) and node.value not in _EXEMPT_INTS:
        return True
    if isinstance(node.value, float) and node.value not in _EXEMPT_FLOATS:
        return True
    return False


def _suggest_name(value: object) -> str:
    """Generate a placeholder constant name suggestion."""
    if isinstance(value, int):
        if value > 0:
            return "MAX_VALUE"
        return "MIN_VALUE"
    if isinstance(value, float):
        return "THRESHOLD"
    return "CONSTANT"


class MagicNumbersDetector:
    """
    Detects magic numeric literals used inline in code.

    Only reports numbers that appear inside expressions (operations, comparisons,
    return values). Assignments to UPPER_CASE names are treated as named constants
    and are exempt from flagging.
    """

    def __init__(self, config: Optional[BugDetectionConfig] = None) -> None:
        self.config = config or BugDetectionConfig()

    def analyze_file(self, file_path: Path, lines: List[str]) -> List[BugFinding]:
        """Analyse a single Python source file for magic numbers."""
        source = "\n".join(lines)
        fp = str(file_path)
        try:
            tree = ast.parse(source, filename=fp)
        except SyntaxError:
            return []

        # Collect object ids of constants that appear as direct RHS values in
        # UPPER_CASE = <constant> assignments — these are named constants, not magic.
        named_constant_ids: Set[int] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if (
                        isinstance(target, ast.Name)
                        and target.id.isupper()
                        and isinstance(node.value, ast.Constant)
                    ):
                        named_constant_ids.add(id(node.value))
            elif isinstance(node, ast.AnnAssign):
                if (
                    isinstance(node.target, ast.Name)
                    and node.target.id.isupper()
                    and node.value is not None
                    and isinstance(node.value, ast.Constant)
                ):
                    named_constant_ids.add(id(node.value))

        findings: List[BugFinding] = []
        reported_lines: Set[int] = set()

        for node in ast.walk(tree):
            found: Optional[ast.Constant] = None
            context = ""

            if isinstance(node, ast.BinOp):
                # Flag the non-trivial operand (prefer right operand for clarity)
                for operand in (node.left, node.right):
                    if (
                        isinstance(operand, ast.Constant)
                        and _is_magic(operand)
                        and id(operand) not in named_constant_ids
                    ):
                        found = operand
                        context = "arithmetic operation"
                        break

            elif isinstance(node, ast.Compare):
                for comp in node.comparators:
                    if (
                        isinstance(comp, ast.Constant)
                        and _is_magic(comp)
                        and id(comp) not in named_constant_ids
                    ):
                        found = comp
                        context = "comparison"
                        break

            elif isinstance(node, ast.Return):
                if (
                    node.value is not None
                    and isinstance(node.value, ast.Constant)
                    and _is_magic(node.value)
                    and id(node.value) not in named_constant_ids
                ):
                    found = node.value
                    context = "return value"

            if found is not None and found.lineno not in reported_lines:
                reported_lines.add(found.lineno)
                suggested = _suggest_name(found.value)
                findings.append(BugFinding(
                    file_path=fp,
                    line_number=found.lineno,
                    category=BugCategory.MAGIC_NUMBER,
                    severity=BugSeverity.LOW,
                    title=f"Magic Number `{found.value}` in {context.title()}",
                    description=(
                        f"Line {found.lineno}: The literal `{found.value}` appears directly "
                        f"in a {context}. Magic numbers reduce readability and make future "
                        "maintenance harder — if the value needs to change, every occurrence "
                        "must be found and updated individually."
                    ),
                    code_snippet=_snippet(lines, found.lineno),
                    fix_suggestion=(
                        f"Extract to a named constant at the top of the module or class: "
                        f"`{suggested} = {found.value}` and reference `{suggested}` by name."
                    ),
                ))

        return findings
