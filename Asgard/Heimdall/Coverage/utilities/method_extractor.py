"""
Heimdall Method Extractor Utilities

Utility functions for extracting method information from Python code.
"""

import ast
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from Asgard.Heimdall.Coverage.models.coverage_models import MethodInfo, MethodType


def extract_methods(source: str, file_path: str = "<string>") -> List[MethodInfo]:
    """
    Extract all methods and functions from source code.

    Args:
        source: Python source code
        file_path: Path to the file (for reporting)

    Returns:
        List of MethodInfo objects
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    methods = []

    # Extract module-level functions
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and not isinstance(
            getattr(node, "parent", None), ast.ClassDef
        ):
            # Check if this is a top-level function
            if _is_top_level(tree, node):
                methods.append(_create_method_info(node, None, file_path))

    # Extract class methods
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    methods.append(_create_method_info(item, node.name, file_path))

    return methods


def _is_top_level(tree: ast.Module, func: ast.FunctionDef) -> bool:
    """Check if a function is at module level."""
    for node in tree.body:
        if node is func:
            return True
    return False


def _create_method_info(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    class_name: Optional[str],
    file_path: str
) -> MethodInfo:
    """Create a MethodInfo object from an AST node."""
    method_type = _get_method_type(node)
    complexity = get_method_complexity(node)
    branch_count = get_branch_count(node)
    param_count = len(node.args.args) - (1 if class_name else 0)  # Exclude self

    docstring = None
    if node.body and isinstance(node.body[0], ast.Expr):
        if isinstance(node.body[0].value, ast.Constant):
            if isinstance(node.body[0].value.value, str):
                docstring = node.body[0].value.value

    return MethodInfo(
        name=node.name,
        class_name=class_name,
        file_path=file_path,
        line_number=node.lineno,
        method_type=method_type,
        complexity=complexity,
        has_branches=branch_count > 0,
        branch_count=branch_count,
        parameter_count=param_count,
        is_async=isinstance(node, ast.AsyncFunctionDef),
        docstring=docstring,
    )


def _get_method_type(node: ast.FunctionDef | ast.AsyncFunctionDef) -> MethodType:
    """Determine the type of method."""
    name = node.name

    # Check decorators
    for decorator in node.decorator_list:
        if isinstance(decorator, ast.Name):
            if decorator.id == "property":
                return MethodType.PROPERTY
            elif decorator.id == "classmethod":
                return MethodType.CLASSMETHOD
            elif decorator.id == "staticmethod":
                return MethodType.STATICMETHOD

    # Check name patterns
    if name.startswith("__") and name.endswith("__"):
        return MethodType.DUNDER
    elif name.startswith("_"):
        return MethodType.PRIVATE
    else:
        return MethodType.PUBLIC


def extract_classes_with_methods(
    source: str,
    file_path: str = "<string>"
) -> Dict[str, List[MethodInfo]]:
    """
    Extract classes and their methods from source code.

    Args:
        source: Python source code
        file_path: Path to the file

    Returns:
        Dict mapping class names to their methods
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}

    classes = {}

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            methods = []
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    methods.append(_create_method_info(item, node.name, file_path))
            classes[node.name] = methods

    return classes


def get_method_complexity(node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """
    Calculate cyclomatic complexity of a method.

    Args:
        node: Function definition AST node

    Returns:
        Complexity score (1 is minimum)
    """
    complexity = 1  # Base complexity

    for child in ast.walk(node):
        # Decision points
        if isinstance(child, (ast.If, ast.While, ast.For)):
            complexity += 1
        elif isinstance(child, ast.ExceptHandler):
            complexity += 1
        elif isinstance(child, ast.BoolOp):
            # and/or add branches
            complexity += len(child.values) - 1
        elif isinstance(child, ast.comprehension):
            # List/dict/set comprehensions
            complexity += 1
            if child.ifs:
                complexity += len(child.ifs)
        elif isinstance(child, ast.IfExp):
            # Ternary operator
            complexity += 1
        elif isinstance(child, ast.Assert):
            complexity += 1

    return complexity


def get_branch_count(node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """
    Count the number of branches in a method.

    Args:
        node: Function definition AST node

    Returns:
        Number of branches
    """
    branches = 0

    for child in ast.walk(node):
        if isinstance(child, ast.If):
            branches += 1
            if child.orelse:
                # Count elif/else
                if isinstance(child.orelse[0], ast.If):
                    branches += 1
                else:
                    branches += 1  # else branch
        elif isinstance(child, ast.While):
            branches += 1
        elif isinstance(child, ast.For):
            branches += 1
            if child.orelse:
                branches += 1
        elif isinstance(child, ast.Try):
            branches += len(child.handlers)
            if child.orelse:
                branches += 1
            if child.finalbody:
                branches += 1

    return branches


def find_test_methods(
    source: str,
    file_path: str = "<string>"
) -> List[MethodInfo]:
    """
    Find test methods in source code.

    Args:
        source: Python source code
        file_path: Path to the file

    Returns:
        List of test method MethodInfo objects
    """
    methods = extract_methods(source, file_path)

    test_methods = [
        m for m in methods
        if m.name.startswith("test_") or m.name.startswith("test")
    ]

    return test_methods


def find_tested_methods(
    test_source: str,
    target_class: Optional[str] = None
) -> List[str]:
    """
    Find method names that are likely being tested.

    Args:
        test_source: Test file source code
        target_class: Optional class to focus on

    Returns:
        List of method names being tested
    """
    try:
        tree = ast.parse(test_source)
    except SyntaxError:
        return []

    tested = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            # Method calls
            if isinstance(node.func, ast.Attribute):
                tested.add(node.func.attr)

    return list(tested)


def get_test_coverage_map(
    source_methods: List[MethodInfo],
    test_methods: List[MethodInfo]
) -> Dict[str, bool]:
    """
    Create a mapping of source methods to their coverage status.

    Args:
        source_methods: Methods from source code
        test_methods: Methods from test code

    Returns:
        Dict mapping method names to coverage status
    """
    coverage = {}

    test_names = {m.name for m in test_methods}

    for method in source_methods:
        # Check if a test exists for this method
        possible_test_names = [
            f"test_{method.name}",
            f"test_{method.full_name.replace('.', '_')}",
        ]

        is_covered = any(name in test_names for name in possible_test_names)
        coverage[method.full_name] = is_covered

    return coverage
