"""
Heimdall Architecture AST Utilities - Class and Method Inspection

Functions for extracting class structure, methods, bases, decorators,
abstract methods, and related structural information from AST nodes.
"""

import ast
from typing import List, Set


def extract_classes(source: str) -> List[ast.ClassDef]:
    """
    Extract all class definitions from source code.

    Args:
        source: Python source code

    Returns:
        List of class definition AST nodes
    """
    try:
        tree = ast.parse(source)
        return [node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
    except SyntaxError:
        return []


def get_class_methods(
    class_node: ast.ClassDef,
) -> List[ast.FunctionDef | ast.AsyncFunctionDef]:
    """
    Get all method definitions from a class.

    Args:
        class_node: Class definition AST node

    Returns:
        List of method definitions
    """
    return [
        node for node in class_node.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]


def get_public_methods(class_node: ast.ClassDef) -> List[ast.FunctionDef | ast.AsyncFunctionDef]:
    """
    Get public methods (not starting with _) from a class.

    Args:
        class_node: Class definition AST node

    Returns:
        List of public method definitions
    """
    methods = get_class_methods(class_node)
    return [m for m in methods if not m.name.startswith("_")]


def get_private_methods(class_node: ast.ClassDef) -> List[ast.FunctionDef | ast.AsyncFunctionDef]:
    """
    Get private methods (starting with _) from a class.

    Args:
        class_node: Class definition AST node

    Returns:
        List of private method definitions
    """
    methods = get_class_methods(class_node)
    return [m for m in methods if m.name.startswith("_") and not m.name.startswith("__")]


def get_class_bases(class_node: ast.ClassDef) -> List[str]:
    """
    Get base class names from a class definition.

    Args:
        class_node: Class definition AST node

    Returns:
        List of base class names
    """
    bases = []
    for base in class_node.bases:
        if isinstance(base, ast.Name):
            bases.append(base.id)
        elif isinstance(base, ast.Attribute):
            parts = []
            node: ast.expr = base
            while isinstance(node, ast.Attribute):
                parts.append(node.attr)
                node = node.value
            if isinstance(node, ast.Name):
                parts.append(node.id)
            bases.append(".".join(reversed(parts)))
    return bases


def get_abstract_methods(class_node: ast.ClassDef) -> List[str]:
    """
    Get names of abstract methods in a class.

    Args:
        class_node: Class definition AST node

    Returns:
        List of abstract method names
    """
    abstract_methods = []

    for method in get_class_methods(class_node):
        for decorator in method.decorator_list:
            if isinstance(decorator, ast.Name) and decorator.id in ("abstractmethod", "abstractproperty"):
                abstract_methods.append(method.name)
                break
            elif isinstance(decorator, ast.Attribute) and decorator.attr in ("abstractmethod", "abstractproperty"):
                abstract_methods.append(method.name)
                break

    return abstract_methods


def is_abstract_class(class_node: ast.ClassDef) -> bool:
    """
    Check if a class is an abstract class.

    Args:
        class_node: Class definition AST node

    Returns:
        True if class is abstract
    """
    for base in class_node.bases:
        if isinstance(base, ast.Name) and base.id in ("ABC", "ABCMeta"):
            return True
        elif isinstance(base, ast.Attribute) and base.attr in ("ABC", "ABCMeta"):
            return True

    for keyword in class_node.keywords:
        if keyword.arg == "metaclass":
            if isinstance(keyword.value, ast.Name) and keyword.value.id == "ABCMeta":
                return True
            elif isinstance(keyword.value, ast.Attribute) and keyword.value.attr == "ABCMeta":
                return True

    return len(get_abstract_methods(class_node)) > 0


def get_class_decorators(class_node: ast.ClassDef) -> List[str]:
    """
    Get decorator names from a class.

    Args:
        class_node: Class definition AST node

    Returns:
        List of decorator names
    """
    decorators = []

    for dec in class_node.decorator_list:
        if isinstance(dec, ast.Name):
            decorators.append(dec.id)
        elif isinstance(dec, ast.Attribute):
            decorators.append(dec.attr)
        elif isinstance(dec, ast.Call):
            if isinstance(dec.func, ast.Name):
                decorators.append(dec.func.id)
            elif isinstance(dec.func, ast.Attribute):
                decorators.append(dec.func.attr)

    return decorators


def get_constructor_params(class_node: ast.ClassDef) -> List[str]:
    """
    Get parameter names from __init__ method.

    Args:
        class_node: Class definition AST node

    Returns:
        List of parameter names (excluding self)
    """
    for method in get_class_methods(class_node):
        if method.name == "__init__":
            params = []
            for arg in method.args.args:
                if arg.arg != "self":
                    params.append(arg.arg)
            return params
    return []


def count_class_lines(class_node: ast.ClassDef) -> int:
    """
    Count the number of lines in a class.

    Args:
        class_node: Class definition AST node

    Returns:
        Number of lines
    """
    if hasattr(class_node, "end_lineno") and class_node.end_lineno:
        return class_node.end_lineno - class_node.lineno + 1
    return 0


def get_class_attributes(class_node: ast.ClassDef) -> Set[str]:
    """
    Get all instance attributes accessed via self.

    Args:
        class_node: Class definition AST node

    Returns:
        Set of attribute names
    """
    attributes: Set[str] = set()

    for node in ast.walk(class_node):
        if isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name) and node.value.id == "self":
                attributes.add(node.attr)

    method_names = {m.name for m in get_class_methods(class_node)}
    return attributes - method_names
