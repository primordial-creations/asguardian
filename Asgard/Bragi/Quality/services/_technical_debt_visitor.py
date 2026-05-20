import ast
from typing import List, Tuple


class ComplexityVisitor(ast.NodeVisitor):
    """
    AST visitor to analyze complexity metrics for debt calculation.

    Detects:
    - High complexity functions (cyclomatic complexity > 15)
    - Long methods (> 50 lines)
    """

    def __init__(self, complexity_threshold: int = 15, length_threshold: int = 50):
        self.complex_functions: List[Tuple[str, int, int]] = []  # (name, complexity, line)
        self.long_methods: List[Tuple[str, int, int]] = []  # (name, length, line)
        self.complexity_threshold = complexity_threshold
        self.length_threshold = length_threshold

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Visit function definitions."""
        self._analyze_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Visit async function definitions."""
        self._analyze_function(node)

    def _analyze_function(self, node) -> None:
        """Analyze function for complexity and length."""
        complexity = self._calculate_complexity(node)
        if complexity > self.complexity_threshold:
            self.complex_functions.append((node.name, complexity, node.lineno))

        method_length = getattr(node, "end_lineno", node.lineno) - node.lineno
        if method_length > self.length_threshold:
            self.long_methods.append((node.name, method_length, node.lineno))

        self.generic_visit(node)

    def _calculate_complexity(self, node: ast.AST) -> int:
        """Calculate cyclomatic complexity."""
        complexity = 1
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1
        return complexity
