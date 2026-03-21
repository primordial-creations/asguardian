import ast
from typing import List, Tuple

from Asgard.Heimdall.Quality.models.documentation_models import (
    ClassDocumentation,
    FunctionDocumentation,
)


def count_lines(source: str) -> Tuple[int, int, int, int]:
    """
    Count total, code, comment, and blank lines in source text.

    Returns:
        Tuple of (total_lines, code_lines, comment_lines, blank_lines)
    """
    lines = source.splitlines()
    total_lines = len(lines)
    blank_lines = 0
    comment_lines = 0
    code_lines = 0
    in_multiline = False
    multiline_quote = ""

    for line in lines:
        stripped = line.strip()

        if not stripped:
            blank_lines += 1
            continue

        if in_multiline:
            comment_lines += 1
            if multiline_quote in stripped:
                count = stripped.count(multiline_quote)
                if count % 2 == 1:
                    in_multiline = False
                    multiline_quote = ""
            continue

        for quote in ('"""', "'''"):
            if quote in stripped:
                count = stripped.count(quote)
                if count % 2 == 1:
                    in_multiline = True
                    multiline_quote = quote
                comment_lines += 1
                break
        else:
            if stripped.startswith("#"):
                comment_lines += 1
            else:
                code_lines += 1

    return total_lines, code_lines, comment_lines, blank_lines


def analyze_function_node(node: ast.FunctionDef | ast.AsyncFunctionDef) -> FunctionDocumentation:
    """Analyze a function or method AST node for documentation."""
    docstring = ast.get_docstring(node)
    is_dunder = node.name.startswith("__") and node.name.endswith("__")
    is_private = node.name.startswith("_") and not is_dunder
    is_public = not is_private and not is_dunder

    docstring_lines = 0
    if docstring:
        docstring_lines = len(docstring.splitlines())

    return FunctionDocumentation(
        name=node.name,
        line_number=node.lineno,
        has_docstring=docstring is not None,
        is_public=is_public,
        docstring_lines=docstring_lines,
    )


def analyze_class_node(node: ast.ClassDef) -> ClassDocumentation:
    """Analyze a class AST node for documentation, including its methods."""
    docstring = ast.get_docstring(node)
    is_private = node.name.startswith("_")
    is_public = not is_private

    docstring_lines = 0
    if docstring:
        docstring_lines = len(docstring.splitlines())

    methods: List[FunctionDocumentation] = []
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            method_doc = analyze_function_node(child)
            methods.append(method_doc)

    return ClassDocumentation(
        name=node.name,
        line_number=node.lineno,
        has_docstring=docstring is not None,
        is_public=is_public,
        docstring_lines=docstring_lines,
        methods=methods,
    )


def extract_documentation(
    tree: ast.AST,
) -> Tuple[List[FunctionDocumentation], List[ClassDocumentation]]:
    """
    Extract function and class documentation status from an AST.

    Returns:
        Tuple of (top_level_functions, classes)
    """
    top_level_functions: List[FunctionDocumentation] = []
    classes: List[ClassDocumentation] = []

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            func_doc = analyze_function_node(node)
            top_level_functions.append(func_doc)
        elif isinstance(node, ast.ClassDef):
            class_doc = analyze_class_node(node)
            classes.append(class_doc)

    return top_level_functions, classes
