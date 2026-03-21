"""
Heimdall OOP Class Utilities - Standalone Functions

Functions that wrap the visitor classes and provide convenient access
to class, method, and import information.
"""

import ast
from pathlib import Path
from typing import Dict, List, Set, Tuple

from Asgard.Heimdall.OOP.utilities._class_visitors import (
    ClassExtractor,
    ClassInfo,
    ImportExtractor,
    MethodAnalyzer,
    MethodInfo,
)


def extract_classes_from_source(source: str) -> List[ClassInfo]:
    """
    Extract class information from Python source code.

    Args:
        source: Python source code string

    Returns:
        List of ClassInfo objects
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    extractor = ClassExtractor()
    extractor.visit(tree)
    return extractor.classes


def extract_classes_from_file(file_path: Path) -> List[ClassInfo]:
    """
    Extract class information from a Python file.

    Args:
        file_path: Path to Python file

    Returns:
        List of ClassInfo objects
    """
    try:
        source = file_path.read_text(encoding="utf-8", errors="ignore")
        return extract_classes_from_source(source)
    except (IOError, OSError):
        return []


def get_class_methods(class_info: ClassInfo) -> List[MethodInfo]:
    """
    Get detailed method information for a class.

    Args:
        class_info: ClassInfo object

    Returns:
        List of MethodInfo objects
    """
    methods = []

    for name, node in class_info.method_nodes.items():
        analyzer = MethodAnalyzer()
        analyzer.visit(node)

        params = []
        for arg in node.args.args:
            if arg.arg != "self":
                params.append(arg.arg)

        method_info = MethodInfo(
            name=name,
            line_number=node.lineno,
            end_line=node.end_lineno or node.lineno,
            parameters=params,
            called_methods=analyzer.called_methods,
            accessed_attributes=analyzer.accessed_attributes,
            complexity=analyzer.complexity,
        )
        methods.append(method_info)

    return methods


def get_class_attributes(class_info: ClassInfo) -> Set[str]:
    """
    Get all attributes (class and instance) for a class.

    Args:
        class_info: ClassInfo object

    Returns:
        Set of attribute names
    """
    return class_info.attributes.copy()


def get_method_calls(method_node: ast.FunctionDef) -> Tuple[Set[str], Set[str]]:
    """
    Get method calls from a method.

    Args:
        method_node: AST node for the method

    Returns:
        Tuple of (self_calls, external_calls)
    """
    analyzer = MethodAnalyzer()
    analyzer.visit(method_node)
    return analyzer.called_methods, analyzer.external_calls


def get_attribute_accesses(method_node: ast.FunctionDef) -> Set[str]:
    """
    Get attribute accesses from a method.

    Args:
        method_node: AST node for the method

    Returns:
        Set of accessed attribute names
    """
    analyzer = MethodAnalyzer()
    analyzer.visit(method_node)
    return analyzer.accessed_attributes


def get_imports_from_source(source: str) -> Tuple[Set[str], Dict[str, Set[str]]]:
    """
    Extract import information from source code.

    Args:
        source: Python source code

    Returns:
        Tuple of (imports, from_imports)
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set(), {}

    extractor = ImportExtractor()
    extractor.visit(tree)
    return extractor.imports, extractor.from_imports


def get_imports_from_file(file_path: Path) -> Tuple[Set[str], Dict[str, Set[str]]]:
    """
    Extract import information from a file.

    Args:
        file_path: Path to Python file

    Returns:
        Tuple of (imports, from_imports)
    """
    try:
        source = file_path.read_text(encoding="utf-8", errors="ignore")
        return get_imports_from_source(source)
    except (IOError, OSError):
        return set(), {}


def find_class_usages(source: str, class_name: str) -> List[int]:
    """
    Find line numbers where a class is used.

    Args:
        source: Python source code
        class_name: Name of the class to find

    Returns:
        List of line numbers where class is referenced
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    usages = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == class_name:
            usages.append(node.lineno)
        elif isinstance(node, ast.Attribute) and node.attr == class_name:
            usages.append(node.lineno)

    return sorted(set(usages))
