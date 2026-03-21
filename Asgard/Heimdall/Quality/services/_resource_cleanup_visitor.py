import ast
from typing import Dict, List, Optional, Set, cast

from Asgard.Heimdall.Quality.models.resource_cleanup_models import (
    ResourceCleanupSeverity,
    ResourceCleanupType,
    ResourceCleanupViolation,
)


# Connection-like calls that should use context managers
CONNECTION_CALLS = {
    ("socket", "socket"),       # socket.socket()
    ("subprocess", "Popen"),    # subprocess.Popen()
    ("ssl", "wrap_socket"),     # ssl.wrap_socket()
    ("ssl", "SSLContext"),      # ssl.SSLContext()
}

# Single-name connection calls (from direct imports)
CONNECTION_NAMES = {
    "Popen",
}


def _is_open_call(node: ast.Call) -> bool:
    """Return True if this Call node is a call to open()."""
    if isinstance(node.func, ast.Name):
        return node.func.id == "open"
    if isinstance(node.func, ast.Attribute):
        # builtins.open or io.open
        return node.func.attr == "open"
    return False


def _is_connection_call(node: ast.Call) -> bool:
    """Return True if this Call is a known connection-type constructor."""
    if isinstance(node.func, ast.Attribute):
        if isinstance(node.func.value, ast.Name):
            pair = (node.func.value.id, node.func.attr)
            if pair in CONNECTION_CALLS:
                return True
    if isinstance(node.func, ast.Name):
        if node.func.id in CONNECTION_NAMES:
            return True
    return False


def _get_call_repr(node: ast.Call) -> str:
    """Get a readable representation of a call expression."""
    if isinstance(node.func, ast.Name):
        return f"{node.func.id}()"
    if isinstance(node.func, ast.Attribute):
        if isinstance(node.func.value, ast.Name):
            return f"{node.func.value.id}.{node.func.attr}()"
        return f"...{node.func.attr}()"
    return "unknown_call()"


def _get_variable_name(node: ast.Attribute) -> Optional[str]:
    """Extract variable name from an attribute access (e.g., 'obj' from obj.append)."""
    if isinstance(node.value, ast.Name):
        return node.value.id
    return None


class ResourceCleanupVisitor(ast.NodeVisitor):
    """
    AST visitor that detects resource cleanup violations.

    Walks the AST and identifies:
    - open() and connection calls outside 'with' blocks
    - Collections appended/extended without being cleared in the same scope
    """

    def __init__(self, file_path: str, source_lines: List[str]):
        """
        Initialize the resource cleanup visitor.

        Args:
            file_path: Path to the file being analyzed
            source_lines: Source code lines for extracting code text
        """
        self.file_path = file_path
        self.source_lines = source_lines
        self.violations: List[ResourceCleanupViolation] = []
        self.current_function: Optional[str] = None
        self.current_class: Optional[str] = None
        # Stack tracks context types: "with", "function", "method", "class"
        self.context_stack: List[str] = []

    def _get_code_snippet(self, node: ast.AST) -> str:
        """Extract the code snippet from source."""
        if hasattr(node, 'lineno') and node.lineno <= len(self.source_lines):
            return cast(str, self.source_lines[node.lineno - 1].strip())
        return ""

    def _in_with_block(self) -> bool:
        """Return True if currently inside a 'with' or 'async with' block."""
        return "with" in self.context_stack

    def _in_try_finally_with_close(self, node: ast.AST) -> bool:
        """Placeholder: detecting try/finally close() patterns requires deeper analysis."""
        return False

    def _record_violation(
        self,
        node: ast.AST,
        cleanup_type: ResourceCleanupType,
        resource_name: Optional[str],
        remediation: str,
        severity: ResourceCleanupSeverity = ResourceCleanupSeverity.MEDIUM,
    ) -> None:
        """Record a resource cleanup violation."""
        code_snippet = self._get_code_snippet(node)

        context_parts = []
        if self.current_class:
            context_parts.append(f"class {self.current_class}")
        if self.current_function:
            context_parts.append(f"function {self.current_function}")
        context = f"in {', '.join(context_parts)}" if context_parts else "at module level"

        type_labels = {
            ResourceCleanupType.FILE_OPEN_NO_WITH: "File opened outside 'with' block",
            ResourceCleanupType.CONNECTION_NO_WITH: "Connection opened outside 'with' block",
            ResourceCleanupType.COLLECTION_NO_CLEAR: "Collection grows unbounded without clear()",
        }
        context_description = f"{type_labels.get(cleanup_type, 'Resource leak')} {context}"

        self.violations.append(ResourceCleanupViolation(
            file_path=self.file_path,
            line_number=getattr(node, 'lineno', 0),
            column=getattr(node, 'col_offset', 0),
            code_snippet=code_snippet,
            resource_name=resource_name,
            cleanup_type=cleanup_type,
            severity=severity,
            containing_function=self.current_function,
            containing_class=self.current_class,
            context_description=context_description,
            remediation=remediation,
        ))

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Visit class definition to track class context."""
        old_class = self.current_class
        self.current_class = node.name
        self.context_stack.append("class")
        self.generic_visit(node)
        self.context_stack.pop()
        self.current_class = old_class

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Visit function definition."""
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Visit async function definition."""
        self._visit_function(node)

    def _visit_function(self, node) -> None:
        """Common handler for function and async function definitions."""
        old_function = self.current_function
        self.current_function = node.name
        context = "method" if self.current_class else "function"
        self.context_stack.append(context)

        # Analyze collection usage within this function body
        self._check_collection_usage(node)

        self.generic_visit(node)

        self.context_stack.pop()
        self.current_function = old_function

    def visit_With(self, node: ast.With) -> None:
        """Track 'with' block context."""
        self.context_stack.append("with")
        self.generic_visit(node)
        self.context_stack.pop()

    def visit_AsyncWith(self, node: ast.AsyncWith) -> None:
        """Track 'async with' block context."""
        self.context_stack.append("with")
        self.generic_visit(node)
        self.context_stack.pop()

    def visit_Call(self, node: ast.Call) -> None:
        """Visit call nodes to detect open() and connection calls outside with blocks."""
        if not self._in_with_block():
            if _is_open_call(node):
                self._record_violation(
                    node,
                    ResourceCleanupType.FILE_OPEN_NO_WITH,
                    resource_name="file",
                    remediation=(
                        "Use 'with open(...) as f:' to ensure the file is closed automatically."
                    ),
                    severity=ResourceCleanupSeverity.HIGH,
                )
            elif _is_connection_call(node):
                call_repr = _get_call_repr(node)
                self._record_violation(
                    node,
                    ResourceCleanupType.CONNECTION_NO_WITH,
                    resource_name=call_repr,
                    remediation=(
                        f"Use 'with {call_repr} as conn:' or call .close() in a finally block."
                    ),
                    severity=ResourceCleanupSeverity.HIGH,
                )

        self.generic_visit(node)

    def _check_collection_usage(self, func_node: ast.AST) -> None:
        """
        Analyze a function body for collections that are appended/extended
        but never cleared within that scope.
        """
        # Collect variable names that have append/extend called
        appended_vars: Dict[str, int] = {}  # varname -> first_line
        cleared_vars: Set[str] = set()

        for node in ast.walk(func_node):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Attribute):
                continue

            attr = node.func.attr
            var_name = _get_variable_name(node.func)
            if var_name is None:
                continue

            if attr in ("append", "extend"):
                if var_name not in appended_vars:
                    appended_vars[var_name] = getattr(node, 'lineno', 0)
            elif attr == "clear":
                cleared_vars.add(var_name)

        for var_name, first_line in appended_vars.items():
            if var_name not in cleared_vars:
                # Find the node at that line to record the violation
                self._record_collection_violation(func_node, var_name, first_line)

    def _record_collection_violation(
        self, func_node: ast.AST, var_name: str, first_line: int
    ) -> None:
        """Record a collection-no-clear violation."""
        code_snippet = ""
        if first_line and first_line <= len(self.source_lines):
            code_snippet = self.source_lines[first_line - 1].strip()

        context_parts = []
        if self.current_class:
            context_parts.append(f"class {self.current_class}")
        if self.current_function:
            context_parts.append(f"function {self.current_function}")
        context = f"in {', '.join(context_parts)}" if context_parts else "at module level"

        self.violations.append(ResourceCleanupViolation(
            file_path=self.file_path,
            line_number=first_line,
            column=0,
            code_snippet=code_snippet,
            resource_name=var_name,
            cleanup_type=ResourceCleanupType.COLLECTION_NO_CLEAR,
            severity=ResourceCleanupSeverity.MEDIUM,
            containing_function=self.current_function,
            containing_class=self.current_class,
            context_description=(
                f"Collection '{var_name}' is appended/extended but never cleared {context}"
            ),
            remediation=(
                f"Call '{var_name}.clear()' when the collection is no longer needed, "
                "or use a bounded data structure."
            ),
        ))
