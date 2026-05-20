"""
Heimdall Performance Utilities - AST analysis helpers.

Standalone functions for Python AST-based performance analysis:
function extraction, loop detection, and complexity calculation.
"""

import ast
from typing import Dict, List


def calculate_complexity(source_code: str) -> Dict[str, int]:
    """
    Calculate cyclomatic complexity for functions in Python code.

    Args:
        source_code: Python source code

    Returns:
        Dictionary mapping function names to complexity scores
    """
    complexity_scores: Dict[str, int] = {}

    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return complexity_scores

    class ComplexityVisitor(ast.NodeVisitor):
        def __init__(self):
            self.current_function = None
            self.complexity = 1

        def visit_FunctionDef(self, node):
            old_function = self.current_function
            old_complexity = self.complexity

            self.current_function = node.name
            self.complexity = 1

            self.generic_visit(node)

            complexity_scores[self.current_function] = self.complexity

            self.current_function = old_function
            self.complexity = old_complexity

        def visit_AsyncFunctionDef(self, node):
            self.visit_FunctionDef(node)

        def visit_If(self, node):
            if self.current_function:
                self.complexity += 1
            self.generic_visit(node)

        def visit_For(self, node):
            if self.current_function:
                self.complexity += 1
            self.generic_visit(node)

        def visit_While(self, node):
            if self.current_function:
                self.complexity += 1
            self.generic_visit(node)

        def visit_ExceptHandler(self, node):
            if self.current_function:
                self.complexity += 1
            self.generic_visit(node)

        def visit_BoolOp(self, node):
            if self.current_function:
                self.complexity += len(node.values) - 1
            self.generic_visit(node)

        def visit_comprehension(self, node):
            if self.current_function:
                self.complexity += 1
            self.generic_visit(node)

        def visit_Assert(self, node):
            if self.current_function:
                self.complexity += 1
            self.generic_visit(node)

    visitor = ComplexityVisitor()
    visitor.visit(tree)

    return complexity_scores


def _get_decorator_name(decorator: ast.expr) -> str:
    """Extract the name of a decorator."""
    if isinstance(decorator, ast.Name):
        return decorator.id
    elif isinstance(decorator, ast.Attribute):
        return decorator.attr
    elif isinstance(decorator, ast.Call):
        if isinstance(decorator.func, ast.Name):
            return decorator.func.id
        elif isinstance(decorator.func, ast.Attribute):
            return decorator.func.attr
    return "unknown"


def extract_function_info(source_code: str) -> List[Dict]:
    """
    Extract information about functions in Python code.

    Args:
        source_code: Python source code

    Returns:
        List of dictionaries with function information
    """
    functions: List[Dict] = []

    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return functions

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            func_info = {
                "name": node.name,
                "line_start": node.lineno,
                "line_end": node.end_lineno if hasattr(node, "end_lineno") else node.lineno,
                "is_async": isinstance(node, ast.AsyncFunctionDef),
                "num_args": len(node.args.args),
                "has_return": any(isinstance(child, ast.Return) for child in ast.walk(node)),
                "decorators": [_get_decorator_name(d) for d in node.decorator_list],
            }
            functions.append(func_info)

    return functions


def _is_nested_loop(tree: ast.AST, target_node: ast.AST) -> bool:
    """Check if a loop is nested inside another loop."""
    class NestingChecker(ast.NodeVisitor):
        def __init__(self):
            self.found = False
            self.in_loop = False

        def visit_For(self, node):
            if node is target_node:
                self.found = self.in_loop
                return

            old_in_loop = self.in_loop
            self.in_loop = True
            self.generic_visit(node)
            self.in_loop = old_in_loop

        def visit_While(self, node):
            if node is target_node:
                self.found = self.in_loop
                return

            old_in_loop = self.in_loop
            self.in_loop = True
            self.generic_visit(node)
            self.in_loop = old_in_loop

    checker = NestingChecker()
    checker.visit(tree)
    return checker.found


def find_loops(source_code: str) -> List[Dict]:
    """
    Find all loops in Python code.

    Args:
        source_code: Python source code

    Returns:
        List of dictionaries with loop information
    """
    loops: List[Dict] = []

    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return loops

    for node in ast.walk(tree):
        if isinstance(node, ast.For):
            loop_info = {
                "type": "for",
                "line_number": node.lineno,
                "is_nested": _is_nested_loop(tree, node),
                "has_break": any(isinstance(child, ast.Break) for child in ast.walk(node)),
                "has_continue": any(isinstance(child, ast.Continue) for child in ast.walk(node)),
            }
            loops.append(loop_info)

        elif isinstance(node, ast.While):
            loop_info = {
                "type": "while",
                "line_number": node.lineno,
                "is_nested": _is_nested_loop(tree, node),
                "has_break": any(isinstance(child, ast.Break) for child in ast.walk(node)),
                "has_continue": any(isinstance(child, ast.Continue) for child in ast.walk(node)),
            }
            loops.append(loop_info)

        elif isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            loop_info = {
                "type": "comprehension",
                "line_number": node.lineno,
                "is_nested": len(node.generators) > 1,
            }
            loops.append(loop_info)

    return loops
