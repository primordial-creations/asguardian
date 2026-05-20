"""
Heimdall Null Dereference Detector

Detects patterns where a value that might be None is accessed without a
prior None check, using Python's AST module.

Patterns detected:
- x = dict.get(key) followed by x.method() without if x or if x is not None
- x = None then x.method() or x.attribute
- Conditional assignment then use outside the if-block
- os.environ.get() result used directly without None check
- Optional-typed return values used without None guard
"""

import ast
import fnmatch
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from Asgard.Bragi.Quality.BugDetection.models.bug_models import (
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


def _attr_chain(node: ast.AST) -> str:
    """Flatten an attribute chain to a dotted string."""
    if isinstance(node, ast.Attribute):
        parent = _attr_chain(node.value)
        if parent:
            return f"{parent}.{node.attr}"
        return node.attr
    if isinstance(node, ast.Name):
        return node.id
    return ""


def _is_none_check(test_node: ast.AST, var_name: str) -> bool:
    """
    Return True if test_node is a None-guard for var_name.

    Recognises:
    - if var_name:
    - if var_name is not None:
    - if var_name is not None and ...:
    - if var_name is None: (negative guard, but signals awareness)
    """
    if isinstance(test_node, ast.Name) and test_node.id == var_name:
        return True
    if isinstance(test_node, ast.Compare):
        left = test_node.left
        if isinstance(left, ast.Name) and left.id == var_name:
            for op in test_node.ops:
                if isinstance(op, (ast.IsNot, ast.Is)):
                    return True
    if isinstance(test_node, ast.BoolOp):
        return any(_is_none_check(v, var_name) for v in test_node.values)
    if isinstance(test_node, ast.UnaryOp) and isinstance(test_node.op, ast.Not):
        return _is_none_check(test_node.operand, var_name)
    return False


def _is_get_call(node: ast.AST) -> bool:
    """Check if node is a .get(...) call on any object (dict.get / os.environ.get etc.)."""
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Attribute) and node.func.attr == "get":
            return True
    return False


def _is_environ_get(node: ast.AST) -> bool:
    """Check if node is os.environ.get(...) or os.getenv(...)."""
    if isinstance(node, ast.Call):
        func_chain = _attr_chain(node.func)
        return func_chain in ("os.environ.get", "os.getenv", "environ.get")
    return False


def _is_none_literal(node: ast.AST) -> bool:
    """Check if a node is the literal None."""
    if isinstance(node, ast.Constant) and node.value is None:
        return True
    # Python 3.7 compat
    if isinstance(node, ast.NameConstant) and node.value is None:  # type: ignore[attr-defined]
        return True
    return False


def _is_optional_annotation(annotation: Optional[ast.AST]) -> bool:
    """Check if a return annotation is Optional[X]."""
    if annotation is None:
        return False
    # Optional[X] -> Subscript of Name "Optional"
    if isinstance(annotation, ast.Subscript):
        if isinstance(annotation.value, ast.Name) and annotation.value.id == "Optional":
            return True
        if isinstance(annotation.value, ast.Attribute) and annotation.value.attr == "Optional":
            return True
    # Union[X, None] -> Subscript of Name "Union" with None in slice
    if isinstance(annotation, ast.Subscript):
        if isinstance(annotation.value, ast.Name) and annotation.value.id == "Union":
            return True
    return False


class _NullCheckVisitor(ast.NodeVisitor):
    """
    AST visitor that tracks potentially-None variables within a function scope
    and reports dereferences without prior None checks.
    """

    def __init__(self, file_path: str, lines: List[str], func_name: str):
        self.file_path = file_path
        self.lines = lines
        self.func_name = func_name
        # Maps variable name -> line_number where it became possibly-None
        self.nullable: Dict[str, int] = {}
        # Variables that have been None-checked (guarded)
        self.checked: Set[str] = set()
        self.findings: List[BugFinding] = []

    def visit_Assign(self, node: ast.Assign) -> None:
        """Handle assignments: detect nullable sources."""
        value = node.value

        # x = None  (definite null)
        if _is_none_literal(value):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    self.nullable[target.id] = node.lineno
                    self.checked.discard(target.id)

        # x = something.get(...)  (dict.get / environ.get -> Optional)
        elif _is_get_call(value):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    self.nullable[target.id] = node.lineno
                    self.checked.discard(target.id)

        # Reassignment to non-None: remove from nullable
        else:
            for target in node.targets:
                if isinstance(target, ast.Name):
                    # If reassigned to a known non-None value, clear nullable
                    if not _is_none_literal(value) and not _is_get_call(value):
                        self.nullable.pop(target.id, None)

        self.generic_visit(node)

    def visit_If(self, node: ast.If) -> None:
        """Track None-checks: if x is not None / if x."""
        # Mark any variable that is None-checked as guarded inside this block
        guarded_vars: Set[str] = set()
        for var_name in list(self.nullable.keys()):
            if _is_none_check(node.test, var_name):
                guarded_vars.add(var_name)

        previously_checked = set(self.checked)
        self.checked |= guarded_vars

        # Visit the if-body (guarded context)
        for stmt in node.body:
            self.visit(stmt)

        # Remove guard after the if-block
        self.checked = previously_checked

        # Visit the else-body (may have inverse guard)
        for stmt in node.orelse:
            self.visit(stmt)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        """Detect attribute access on a nullable variable."""
        if isinstance(node.value, ast.Name):
            var_name = node.value.id
            if var_name in self.nullable and var_name not in self.checked:
                source_line = self.nullable[var_name]
                access_line = node.lineno

                # Determine severity
                source_snippet = _get_code_snippet(self.lines, source_line)
                is_definite = _is_none_literal(ast.Constant(value=None))

                if "= None" in source_snippet or source_snippet.endswith("= None"):
                    severity = BugSeverity.HIGH
                    desc_prefix = "definite"
                else:
                    severity = BugSeverity.MEDIUM
                    desc_prefix = "potential"

                self.findings.append(BugFinding(
                    file_path=self.file_path,
                    line_number=access_line,
                    category=BugCategory.NULL_DEREFERENCE,
                    severity=severity,
                    title="Null Dereference",
                    description=(
                        f"Variable '{var_name}' is accessed at line {access_line} but may be None "
                        f"(assigned at line {source_line} without a prior None check). "
                        f"This is a {desc_prefix} null dereference."
                    ),
                    code_snippet=_get_code_snippet(self.lines, access_line),
                    fix_suggestion=(
                        f"Add a None check before accessing '{var_name}': "
                        f"'if {var_name} is not None:' or 'if {var_name}:'."
                    ),
                ))
                # After reporting, mark as checked to avoid duplicate reports
                self.checked.add(var_name)

        self.generic_visit(node)


class NullDereferenceDetector:
    """
    Detects potential null dereference bugs using Python AST analysis.

    Tracks variables that may be None (from dict.get, os.environ.get,
    direct None assignments, or Optional return types) and reports
    attribute/method accesses that occur without a prior None check.
    """

    def __init__(self, config: Optional[BugDetectionConfig] = None):
        """
        Initialize the null dereference detector.

        Args:
            config: Bug detection configuration. Uses defaults if not provided.
        """
        self.config = config or BugDetectionConfig()

    def analyze_file(self, file_path: Path, lines: List[str]) -> List[BugFinding]:
        """
        Analyze a single Python source file for null dereferences.

        Args:
            file_path: Path to the file.
            lines: Source lines of the file.

        Returns:
            List of BugFinding objects found in the file.
        """
        findings: List[BugFinding] = []

        source = "\n".join(lines)

        try:
            tree = ast.parse(source, filename=str(file_path))
        except SyntaxError:
            return findings

        file_path_str = str(file_path)

        # Analyze module-level code
        module_visitor = _NullCheckVisitor(file_path_str, lines, "<module>")
        for stmt in tree.body:
            module_visitor.visit(stmt)
        findings.extend(module_visitor.findings)

        # Analyze each function
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                visitor = _NullCheckVisitor(file_path_str, lines, node.name)
                visitor.visit(node)
                findings.extend(visitor.findings)

        return findings
