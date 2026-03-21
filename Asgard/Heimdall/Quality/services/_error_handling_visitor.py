import ast
from typing import List, Optional, Set, cast

from Asgard.Heimdall.Quality.models.error_handling_models import (
    ErrorHandlingSeverity,
    ErrorHandlingType,
    ErrorHandlingViolation,
)


EXTERNAL_CALL_PATTERNS: Set[tuple] = {
    ("requests", "get"), ("requests", "post"), ("requests", "put"),
    ("requests", "delete"), ("requests", "patch"), ("requests", "head"),
    ("requests", "options"), ("requests", "request"),
    ("urllib", "urlopen"), ("urllib.request", "urlopen"),
    ("subprocess", "run"), ("subprocess", "call"), ("subprocess", "check_call"),
    ("subprocess", "check_output"), ("subprocess", "Popen"),
    ("aiohttp", "get"), ("aiohttp", "post"), ("aiohttp", "request"),
    ("httpx", "get"), ("httpx", "post"), ("httpx", "put"),
    ("httpx", "delete"), ("httpx", "request"),
}

EXTERNAL_MODULES: Set[str] = {"requests", "urllib", "subprocess", "aiohttp", "httpx"}

EXTERNAL_SESSION_METHODS: Set[str] = {
    "get", "post", "put", "delete", "patch", "head", "options", "request",
    "execute", "run", "call",
}


def _is_external_call(node: ast.Call) -> bool:
    """Return True if this call is to a known external API."""
    if not isinstance(node.func, ast.Attribute):
        return False

    attr = node.func.attr
    if isinstance(node.func.value, ast.Name):
        module = node.func.value.id
        if module in EXTERNAL_MODULES:
            return True
        if (module, attr) in EXTERNAL_CALL_PATTERNS:
            return True

    return False


def _get_call_repr(node: ast.Call) -> str:
    """Get a readable representation of a call expression."""
    if isinstance(node.func, ast.Attribute):
        if isinstance(node.func.value, ast.Name):
            return f"{node.func.value.id}.{node.func.attr}()"
        return f"...{node.func.attr}()"
    if isinstance(node.func, ast.Name):
        return f"{node.func.id}()"
    return "unknown_call()"


def _function_has_top_level_try_except(func_node: ast.AST) -> bool:
    """
    Return True if the function body has a try/except as its outermost statement.

    We look at the direct body of the function (not nested functions).
    A try/except at the top level of the function body is considered
    adequate exception handling.
    """
    body = getattr(func_node, 'body', [])
    for stmt in body:
        if isinstance(stmt, (ast.Try,)):
            if getattr(stmt, 'handlers', []):
                return True
    return False


def _node_is_inside_try_except(node: ast.AST, func_body: List[ast.stmt]) -> bool:
    """
    Return True if the given node is inside any try/except in the function body.

    Uses a simple walk of the function body to check if node's line is
    covered by a try block with at least one handler.
    """
    node_line = getattr(node, 'lineno', -1)
    if node_line < 0:
        return False

    for stmt in ast.walk(ast.Module(body=func_body, type_ignores=[])):
        if not isinstance(stmt, ast.Try):
            continue
        if not getattr(stmt, 'handlers', []):
            continue
        try_start = getattr(stmt, 'lineno', -1)
        if stmt.handlers:
            try_end = getattr(stmt.handlers[0], 'lineno', try_start + 9999)
        else:
            try_end = try_start + 9999

        if try_start <= node_line < try_end:
            return True

    return False


class ThreadTargetCollector(ast.NodeVisitor):
    """
    First-pass visitor that collects all function names referenced as
    threading.Thread(target=...) targets.
    """

    def __init__(self):
        self.thread_targets: Set[str] = set()

    def visit_Call(self, node: ast.Call) -> None:
        """Detect threading.Thread(target=func_name) patterns."""
        is_thread_call = False

        if isinstance(node.func, ast.Attribute):
            if node.func.attr == "Thread":
                if isinstance(node.func.value, ast.Name) and node.func.value.id == "threading":
                    is_thread_call = True
        elif isinstance(node.func, ast.Name):
            if node.func.id == "Thread":
                is_thread_call = True

        if is_thread_call:
            for kw in node.keywords:
                if kw.arg == "target":
                    if isinstance(kw.value, ast.Name):
                        self.thread_targets.add(kw.value.id)
                    elif isinstance(kw.value, ast.Attribute):
                        self.thread_targets.add(kw.value.attr)

        self.generic_visit(node)


class ErrorHandlingVisitor(ast.NodeVisitor):
    """
    AST visitor that detects missing error handling around external calls
    and thread target functions.
    """

    def __init__(
        self,
        file_path: str,
        source_lines: List[str],
        thread_targets: Set[str],
    ):
        """
        Initialize the error handling visitor.

        Args:
            file_path: Path to the file being analyzed
            source_lines: Source code lines for extracting code text
            thread_targets: Set of function names used as threading.Thread targets
        """
        self.file_path = file_path
        self.source_lines = source_lines
        self.thread_targets = thread_targets
        self.violations: List[ErrorHandlingViolation] = []
        self.current_function: Optional[str] = None
        self.current_class: Optional[str] = None
        self.in_try_except: int = 0
        self.is_async_function: bool = False

    def _get_code_snippet(self, node: ast.AST) -> str:
        """Extract the code snippet from source."""
        if hasattr(node, 'lineno') and node.lineno <= len(self.source_lines):
            return cast(str, self.source_lines[node.lineno - 1].strip())
        return ""

    def _record_violation(
        self,
        node: ast.AST,
        handling_type: ErrorHandlingType,
        severity: ErrorHandlingSeverity,
        function_name: Optional[str],
        call_expression: Optional[str],
        context_description: str,
        remediation: str,
    ) -> None:
        """Record an error handling violation."""
        code_snippet = self._get_code_snippet(node)

        self.violations.append(ErrorHandlingViolation(
            file_path=self.file_path,
            line_number=getattr(node, 'lineno', 0),
            column=getattr(node, 'col_offset', 0),
            code_snippet=code_snippet,
            function_name=function_name,
            call_expression=call_expression,
            handling_type=handling_type,
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
        self.generic_visit(node)
        self.current_class = old_class

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Visit function definition."""
        self._visit_function(node, is_async=False)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Visit async function definition."""
        self._visit_function(node, is_async=True)

    def _visit_function(self, node, is_async: bool) -> None:
        """Common handler for function and async function definitions."""
        old_function = self.current_function
        old_is_async = self.is_async_function
        self.current_function = node.name
        self.is_async_function = is_async

        if node.name in self.thread_targets:
            if not _function_has_top_level_try_except(node):
                context_parts = []
                if self.current_class:
                    context_parts.append(f"class {self.current_class}")
                context = f"in {', '.join(context_parts)}" if context_parts else "at module level"

                self._record_violation(
                    node,
                    handling_type=ErrorHandlingType.THREAD_TARGET_NO_EXCEPTION_HANDLING,
                    severity=ErrorHandlingSeverity.HIGH,
                    function_name=node.name,
                    call_expression=None,
                    context_description=(
                        f"Thread target function '{node.name}' has no top-level try/except {context}. "
                        "Unhandled exceptions in threads terminate silently."
                    ),
                    remediation=(
                        f"Wrap the body of '{node.name}' in a try/except block to catch and handle "
                        "all exceptions, preventing silent thread failure."
                    ),
                )

        self.generic_visit(node)

        self.current_function = old_function
        self.is_async_function = old_is_async

    def visit_Try(self, node: ast.Try) -> None:
        """Track entry into try/except blocks."""
        if node.handlers:
            self.in_try_except += 1
            self.generic_visit(node)
            self.in_try_except -= 1
        else:
            self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        """Detect external calls not inside try/except."""
        if self.in_try_except == 0 and _is_external_call(node):
            call_repr = _get_call_repr(node)
            context_parts = []
            if self.current_class:
                context_parts.append(f"class {self.current_class}")
            if self.current_function:
                context_parts.append(f"function {self.current_function}")
            context = f"in {', '.join(context_parts)}" if context_parts else "at module level"

            if self.is_async_function:
                handling_type = ErrorHandlingType.ASYNC_EXTERNAL_NO_HANDLING
                description = (
                    f"Async external call '{call_repr}' not protected by try/except {context}"
                )
            else:
                handling_type = ErrorHandlingType.UNPROTECTED_EXTERNAL_CALL
                description = (
                    f"External call '{call_repr}' not protected by try/except {context}"
                )

            self._record_violation(
                node,
                handling_type=handling_type,
                severity=ErrorHandlingSeverity.MEDIUM,
                function_name=self.current_function,
                call_expression=call_repr,
                context_description=description,
                remediation=(
                    f"Wrap '{call_repr}' in a try/except block to handle network errors, "
                    "timeouts, and other potential exceptions."
                ),
            )

        self.generic_visit(node)
