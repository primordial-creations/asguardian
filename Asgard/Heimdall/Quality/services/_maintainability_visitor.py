import ast
import math
import os
from typing import Dict, List, cast

from Asgard.Heimdall.Quality.models.maintainability_models import HalsteadMetrics


class MaintainabilityVisitor(ast.NodeVisitor):
    """
    AST visitor to extract maintainability metrics from Python code.

    Analyzes:
    - Function definitions and their complexity
    - Halstead operators and operands
    - Code structure and size
    - Documentation/comment coverage
    """

    def __init__(self, file_path: str, include_halstead: bool = True, include_comments: bool = True):
        self.file_path = file_path
        self.include_halstead = include_halstead
        self.include_comments = include_comments
        self.functions: List[Dict] = []
        self.file_lines = 0
        self.file_comments = 0
        self.code_lines = 0

        self.python_operators = {
            '+', '-', '*', '/', '//', '%', '**', '&', '|', '^', '~', '<<', '>>',
            '==', '!=', '<', '>', '<=', '>=', 'and', 'or', 'not', 'in', 'is',
            '=', '+=', '-=', '*=', '/=', '//=', '%=', '**=', '&=', '|=', '^=',
            '<<=', '>>=', 'if', 'else', 'elif', 'while', 'for', 'break', 'continue',
            'def', 'class', 'return', 'yield', 'import', 'from', 'as', 'try',
            'except', 'finally', 'raise', 'with', 'assert', 'del', 'pass'
        }

        if include_comments:
            self._count_file_comments()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Visit function definitions."""
        func_data = self._analyze_function(node)
        self.functions.append(func_data)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Visit async function definitions."""
        func_data = self._analyze_function(node)
        self.functions.append(func_data)
        self.generic_visit(node)

    def _analyze_function(self, node) -> Dict:
        """Analyze a single function for maintainability metrics."""
        complexity = self._calculate_complexity(node)

        loc = getattr(node, 'end_lineno', node.lineno) - node.lineno + 1

        halstead_volume = 0.0
        if self.include_halstead:
            halstead = self._calculate_halstead_metrics(node)
            halstead_volume = halstead.volume

        comment_percentage = 0.0
        if self.include_comments:
            comment_percentage = self._calculate_function_comments(node)

        return {
            'name': node.name,
            'line_number': node.lineno,
            'complexity': complexity,
            'loc': loc,
            'halstead_volume': halstead_volume,
            'comment_percentage': comment_percentage
        }

    def _calculate_complexity(self, node: ast.AST) -> int:
        """Calculate cyclomatic complexity for a node."""
        complexity = 1
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1
            elif isinstance(child, ast.comprehension):
                complexity += 1
            elif isinstance(child, (ast.IfExp,)):
                complexity += 1
        return complexity

    def _calculate_halstead_metrics(self, node: ast.AST) -> HalsteadMetrics:
        """Calculate Halstead complexity metrics for a node."""
        operators = set()
        operands = set()
        operator_count = 0
        operand_count = 0

        for child in ast.walk(node):
            if isinstance(child, ast.Name):
                operands.add(child.id)
                operand_count += 1
            elif isinstance(child, ast.Constant):
                operands.add(str(child.value))
                operand_count += 1

            elif isinstance(child, ast.BinOp):
                op_name = type(child.op).__name__.lower()
                operators.add(op_name)
                operator_count += 1
            elif isinstance(child, ast.UnaryOp):
                op_name = type(child.op).__name__.lower()
                operators.add(op_name)
                operator_count += 1
            elif isinstance(child, ast.BoolOp):
                op_name = type(child.op).__name__.lower()
                operators.add(op_name)
                operator_count += 1
            elif isinstance(child, ast.Compare):
                for op in child.ops:
                    op_name = type(op).__name__.lower()
                    operators.add(op_name)
                    operator_count += 1

            elif isinstance(child, (ast.If, ast.While, ast.For)):
                op_name = type(child).__name__.lower()
                operators.add(op_name)
                operator_count += 1
            elif isinstance(child, (ast.Return, ast.Yield)):
                op_name = type(child).__name__.lower()
                operators.add(op_name)
                operator_count += 1

        return HalsteadMetrics(
            n1=len(operators),
            n2=len(operands),
            N1=operator_count,
            N2=operand_count
        )

    def _calculate_function_comments(self, node) -> float:
        """Calculate comment percentage for a function."""
        docstring = ast.get_docstring(node)
        func_lines = getattr(node, 'end_lineno', node.lineno) - node.lineno + 1

        if docstring:
            docstring_lines = len(docstring.split('\n'))
            return cast(float, min((docstring_lines / max(func_lines, 1)) * 100, 100.0))

        return 0.0

    def _count_file_comments(self) -> None:
        """Count comments and lines in the entire file."""
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            self.file_lines = len(lines)
            comment_lines: float = 0
            code_lines = 0
            in_multiline = False

            for line in lines:
                stripped = line.strip()

                if not stripped:
                    continue

                if '"""' in line or "'''" in line:
                    quote = '"""' if '"""' in line else "'''"
                    count = line.count(quote)
                    if count == 1:
                        in_multiline = not in_multiline
                    comment_lines += 1
                    continue

                if in_multiline:
                    comment_lines += 1
                    continue

                if stripped.startswith('#'):
                    comment_lines += 1
                else:
                    code_lines += 1
                    if '#' in line:
                        comment_lines += 0.5

            self.file_comments = int(comment_lines)
            self.code_lines = code_lines
        except Exception:
            self.file_lines = 1
            self.file_comments = 0
            self.code_lines = 1

    def get_file_metrics(self) -> Dict:
        """Get file-level metrics."""
        if self.functions:
            avg_complexity = sum(f['complexity'] for f in self.functions) / len(self.functions)
        else:
            avg_complexity = 1

        halstead_volume = 50.0
        if self.include_halstead and self.functions:
            volumes = [f['halstead_volume'] for f in self.functions if f['halstead_volume'] > 0]
            if volumes:
                halstead_volume = sum(volumes) / len(volumes)

        comment_percentage = 0.0
        if self.include_comments and self.file_lines > 0:
            comment_percentage = (self.file_comments / self.file_lines) * 100

        return {
            'name': os.path.basename(self.file_path),
            'line_number': 1,
            'complexity': int(avg_complexity),
            'loc': self.code_lines or self.file_lines,
            'halstead_volume': halstead_volume,
            'comment_percentage': comment_percentage,
            'total_lines': self.file_lines,
            'comment_lines': self.file_comments,
        }
