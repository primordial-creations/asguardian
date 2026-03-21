"""
Heimdall Architecture AST Utilities - Method and Import Inspection

Functions for extracting method calls, attributes, imports, and type hints.
"""

import ast
from typing import Dict, Set, Tuple


def get_method_calls(method_node: ast.FunctionDef) -> Set[str]:
    """
    Extract all method calls from a method body.

    Args:
        method_node: Method definition AST node

    Returns:
        Set of called method names
    """
    calls: Set[str] = set()

    for node in ast.walk(method_node):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                calls.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                calls.add(node.func.attr)

    return calls


def get_self_method_calls(method_node: ast.FunctionDef) -> Set[str]:
    """
    Extract method calls on self from a method body.

    Args:
        method_node: Method definition AST node

    Returns:
        Set of self method call names
    """
    calls: Set[str] = set()

    for node in ast.walk(method_node):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                if isinstance(node.func.value, ast.Name) and node.func.value.id == "self":
                    calls.add(node.func.attr)

    return calls


def get_method_attributes(method_node: ast.FunctionDef) -> Set[str]:
    """
    Get attributes accessed via self in a method.

    Args:
        method_node: Method definition AST node

    Returns:
        Set of attribute names
    """
    attributes: Set[str] = set()

    for node in ast.walk(method_node):
        if isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name) and node.value.id == "self":
                attributes.add(node.attr)

    return attributes


def get_imports(source: str) -> Tuple[Set[str], Dict[str, Set[str]]]:
    """
    Extract import statements from source code.

    Args:
        source: Python source code

    Returns:
        Tuple of (direct imports, from imports)
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set(), {}

    imports: Set[str] = set()
    from_imports: Dict[str, Set[str]] = {}

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module not in from_imports:
                from_imports[module] = set()
            for alias in node.names:
                from_imports[module].add(alias.name)

    return imports, from_imports


def get_type_hints(method_node: ast.FunctionDef) -> Dict[str, str]:
    """
    Extract type hints from a method.

    Args:
        method_node: Method definition AST node

    Returns:
        Dict mapping parameter names to type hints
    """
    hints: Dict[str, str] = {}

    for arg in method_node.args.args:
        if arg.annotation:
            hints[arg.arg] = ast.unparse(arg.annotation) if hasattr(ast, "unparse") else str(arg.annotation)

    if method_node.returns:
        hints["return"] = ast.unparse(method_node.returns) if hasattr(ast, "unparse") else str(method_node.returns)

    return hints
