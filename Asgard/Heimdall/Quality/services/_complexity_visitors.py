import ast


class CyclomaticComplexityVisitor(ast.NodeVisitor):
    """
    AST visitor that calculates cyclomatic complexity for Python functions.

    Cyclomatic complexity counts decision points:
    - if/elif statements
    - for/while loops
    - try/except blocks
    - boolean operators (and/or)
    - comprehensions
    - ternary expressions
    """

    def __init__(self):
        self.complexity = 1  # Base complexity

    def visit_If(self, node: ast.If) -> None:
        """Count if statements."""
        self.complexity += 1
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        """Count for loops."""
        self.complexity += 1
        self.generic_visit(node)

    def visit_While(self, node: ast.While) -> None:
        """Count while loops."""
        self.complexity += 1
        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        """Count except handlers."""
        self.complexity += 1
        self.generic_visit(node)

    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        """Count boolean operators (and/or add paths)."""
        self.complexity += len(node.values) - 1
        self.generic_visit(node)

    def visit_comprehension(self, node: ast.comprehension) -> None:
        """Count comprehension loops."""
        self.complexity += 1
        self.complexity += len(node.ifs)
        self.generic_visit(node)

    def visit_IfExp(self, node: ast.IfExp) -> None:
        """Count ternary expressions."""
        self.complexity += 1
        self.generic_visit(node)

    def visit_Assert(self, node: ast.Assert) -> None:
        """Count assert statements as decision points."""
        self.complexity += 1
        self.generic_visit(node)

    def visit_Match(self, node: ast.Match) -> None:
        """Count match statement cases (Python 3.10+)."""
        self.complexity += len(node.cases)
        self.generic_visit(node)


class CognitiveComplexityVisitor(ast.NodeVisitor):
    """
    AST visitor that calculates cognitive complexity for Python functions.

    Cognitive complexity differs from cyclomatic by:
    - Incrementing for nesting (nested structures are harder to understand)
    - Not counting structures that don't break linear flow
    - Penalizing recursion and breaks in control flow

    Based on SonarSource's cognitive complexity methodology.
    """

    def __init__(self):
        self.complexity = 0
        self.nesting_level = 0
        self._in_boolean_sequence = False

    def _increment(self, base: int = 1) -> None:
        """Add to complexity with nesting penalty."""
        self.complexity += base + self.nesting_level

    def _increment_nesting(self) -> None:
        """Increase nesting level."""
        self.nesting_level += 1

    def _decrement_nesting(self) -> None:
        """Decrease nesting level."""
        self.nesting_level = max(0, self.nesting_level - 1)

    def visit_If(self, node: ast.If) -> None:
        """Count if statements with nesting penalty."""
        self._increment()
        self._increment_nesting()
        for child in node.body:
            self.visit(child)
        self._decrement_nesting()

        for child in node.orelse:
            if isinstance(child, ast.If):
                self._increment(1)
                self._increment_nesting()
                for subchild in child.body:
                    self.visit(subchild)
                self._decrement_nesting()
                for subchild in child.orelse:
                    if isinstance(subchild, ast.If):
                        continue
                    self.visit(subchild)
            else:
                self.visit(child)

    def visit_For(self, node: ast.For) -> None:
        """Count for loops with nesting penalty."""
        self._increment()
        self._increment_nesting()
        for child in node.body:
            self.visit(child)
        self._decrement_nesting()
        for child in node.orelse:
            self.visit(child)

    def visit_While(self, node: ast.While) -> None:
        """Count while loops with nesting penalty."""
        self._increment()
        self._increment_nesting()
        for child in node.body:
            self.visit(child)
        self._decrement_nesting()
        for child in node.orelse:
            self.visit(child)

    def visit_Try(self, node: ast.Try) -> None:
        """Count try blocks with nesting penalty."""
        self._increment_nesting()
        for child in node.body:
            self.visit(child)
        self._decrement_nesting()

        for handler in node.handlers:
            self._increment()
            self._increment_nesting()
            for child in handler.body:
                self.visit(child)
            self._decrement_nesting()

        for child in node.finalbody:
            self.visit(child)

    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        """
        Count boolean operator sequences.

        Only the first in a sequence adds complexity.
        Mixing and/or adds complexity.
        """
        if not self._in_boolean_sequence:
            self._increment(1)
            self._in_boolean_sequence = True

        self.generic_visit(node)
        self._in_boolean_sequence = False

    def visit_Break(self, node: ast.Break) -> None:
        """Break statements add complexity (interrupts flow)."""
        self._increment(1)

    def visit_Continue(self, node: ast.Continue) -> None:
        """Continue statements add complexity (interrupts flow)."""
        self._increment(1)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        """Lambda adds nesting but not base complexity."""
        self._increment_nesting()
        self.generic_visit(node)
        self._decrement_nesting()

    def visit_ListComp(self, node: ast.ListComp) -> None:
        """List comprehensions add complexity."""
        self._increment()
        self._increment_nesting()
        self.generic_visit(node)
        self._decrement_nesting()

    def visit_DictComp(self, node: ast.DictComp) -> None:
        """Dict comprehensions add complexity."""
        self._increment()
        self._increment_nesting()
        self.generic_visit(node)
        self._decrement_nesting()

    def visit_SetComp(self, node: ast.SetComp) -> None:
        """Set comprehensions add complexity."""
        self._increment()
        self._increment_nesting()
        self.generic_visit(node)
        self._decrement_nesting()

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:
        """Generator expressions add complexity."""
        self._increment()
        self._increment_nesting()
        self.generic_visit(node)
        self._decrement_nesting()

    def visit_IfExp(self, node: ast.IfExp) -> None:
        """Ternary expressions add complexity."""
        self._increment()
        self.generic_visit(node)

    def visit_Match(self, node: ast.Match) -> None:
        """Match statements (Python 3.10+)."""
        self._increment()
        self._increment_nesting()
        for case in node.cases:
            self._increment(1)
            for child in case.body:
                self.visit(child)
        self._decrement_nesting()
