import ast
from typing import List, Optional

from Asgard.Heimdall.Quality.models.lazy_import_models import (
    LazyImport,
    LazyImportSeverity,
    LazyImportType,
)


class LazyImportVisitor(ast.NodeVisitor):
    """
    AST visitor that detects imports not at module level.

    Walks the AST and identifies import statements that appear inside:
    - Functions (def)
    - Async functions (async def)
    - Class methods
    - Conditional blocks (if/elif/else)
    - Try/except blocks
    - Loops (for/while)
    - With blocks
    """

    def __init__(self, file_path: str, source_lines: List[str]):
        """
        Initialize the lazy import visitor.

        Args:
            file_path: Path to the file being analyzed
            source_lines: Source code lines for extracting import text
        """
        self.file_path = file_path
        self.source_lines = source_lines
        self.lazy_imports: List[LazyImport] = []
        self.current_function: Optional[str] = None
        self.current_class: Optional[str] = None
        self.context_stack: List[str] = []  # Track nested contexts

    def _get_import_statement(self, node: ast.stmt) -> str:
        """Extract the import statement text from source."""
        if node.lineno <= len(self.source_lines):
            line = self.source_lines[node.lineno - 1].strip()
            return line
        return ""

    def _determine_severity(self, import_type: LazyImportType) -> LazyImportSeverity:
        """Determine severity based on import type."""
        high_severity = {
            LazyImportType.FUNCTION,
            LazyImportType.METHOD,
        }
        medium_severity = {
            LazyImportType.CONDITIONAL,
            LazyImportType.TRY_EXCEPT,
        }

        if import_type in high_severity:
            return LazyImportSeverity.HIGH
        elif import_type in medium_severity:
            return LazyImportSeverity.MEDIUM
        return LazyImportSeverity.LOW

    def _get_context_description(self, import_type: LazyImportType) -> str:
        """Generate a human-readable context description."""
        descriptions = {
            LazyImportType.FUNCTION: "inside function",
            LazyImportType.METHOD: "inside class method",
            LazyImportType.CONDITIONAL: "inside conditional block (if/elif/else)",
            LazyImportType.TRY_EXCEPT: "inside try/except block",
            LazyImportType.LOOP: "inside loop (for/while)",
            LazyImportType.WITH_BLOCK: "inside with block",
        }
        base = descriptions.get(import_type, "in non-module-level scope")

        if self.current_class and self.current_function:
            return f"{base} '{self.current_class}.{self.current_function}'"
        elif self.current_function:
            return f"{base} '{self.current_function}'"
        return base

    def _record_lazy_import(self, node: ast.stmt, import_type: LazyImportType) -> None:
        """Record a lazy import violation."""
        import_stmt = self._get_import_statement(node)
        severity = self._determine_severity(import_type)

        self.lazy_imports.append(LazyImport(
            file_path=self.file_path,
            line_number=node.lineno,
            import_statement=import_stmt,
            import_type=import_type,
            severity=severity,
            containing_function=self.current_function,
            containing_class=self.current_class,
            context_description=self._get_context_description(import_type),
        ))

    def _check_import_node(self, node: ast.stmt) -> None:
        """Check if an import node is in a non-module-level context."""
        if not self.context_stack:
            # Module level import - this is fine
            return

        # Determine import type based on context
        current_context = self.context_stack[-1]

        if current_context == "method":
            import_type = LazyImportType.METHOD
        elif current_context == "function":
            import_type = LazyImportType.FUNCTION
        elif current_context == "conditional":
            import_type = LazyImportType.CONDITIONAL
        elif current_context == "try_except":
            import_type = LazyImportType.TRY_EXCEPT
        elif current_context == "loop":
            import_type = LazyImportType.LOOP
        elif current_context == "with_block":
            import_type = LazyImportType.WITH_BLOCK
        else:
            import_type = LazyImportType.FUNCTION

        self._record_lazy_import(node, import_type)

    def visit_Import(self, node: ast.Import) -> None:
        """Handle 'import X' statements."""
        self._check_import_node(node)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Handle 'from X import Y' statements."""
        self._check_import_node(node)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Visit class definition to track class context."""
        old_class = self.current_class
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = old_class

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Visit function definition to track function context."""
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Visit async function definition to track function context."""
        self._visit_function(node)

    def _visit_function(self, node) -> None:
        """Common handler for function and async function definitions."""
        old_function = self.current_function
        self.current_function = node.name

        # Determine if this is a method or function
        context = "method" if self.current_class else "function"
        self.context_stack.append(context)

        self.generic_visit(node)

        self.context_stack.pop()
        self.current_function = old_function

    def _is_type_checking_block(self, node: ast.If) -> bool:
        """Check if this is an 'if TYPE_CHECKING:' block."""
        # Check for `if TYPE_CHECKING:`
        if isinstance(node.test, ast.Name) and node.test.id == "TYPE_CHECKING":
            return True
        # Check for `if typing.TYPE_CHECKING:`
        if isinstance(node.test, ast.Attribute):
            if node.test.attr == "TYPE_CHECKING":
                return True
        return False

    def visit_If(self, node: ast.If) -> None:
        """Visit if statement to track conditional context."""
        # Allow imports inside TYPE_CHECKING blocks (valid pattern for type hints)
        if self._is_type_checking_block(node):
            return  # Skip processing this block entirely

        self.context_stack.append("conditional")
        self.generic_visit(node)
        self.context_stack.pop()

    def visit_Try(self, node: ast.Try) -> None:
        """Visit try statement to track try/except context."""
        self.context_stack.append("try_except")
        self.generic_visit(node)
        self.context_stack.pop()

    def visit_For(self, node: ast.For) -> None:
        """Visit for loop to track loop context."""
        self.context_stack.append("loop")
        self.generic_visit(node)
        self.context_stack.pop()

    def visit_While(self, node: ast.While) -> None:
        """Visit while loop to track loop context."""
        self.context_stack.append("loop")
        self.generic_visit(node)
        self.context_stack.pop()

    def visit_With(self, node: ast.With) -> None:
        """Visit with statement to track with block context."""
        self.context_stack.append("with_block")
        self.generic_visit(node)
        self.context_stack.pop()

    def visit_AsyncWith(self, node: ast.AsyncWith) -> None:
        """Visit async with statement to track with block context."""
        self.context_stack.append("with_block")
        self.generic_visit(node)
        self.context_stack.pop()

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        """Visit async for loop to track loop context."""
        self.context_stack.append("loop")
        self.generic_visit(node)
        self.context_stack.pop()
