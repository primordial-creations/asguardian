import ast
from typing import Dict, List, Optional, cast

from Asgard.Heimdall.Quality.models.blocking_async_models import (
    BlockingAsyncSeverity,
    BlockingCall,
    BlockingCallType,
)


_BLOCKING_REMEDIATION: Dict[str, str] = {
    "time_sleep": (
        "Replace time.sleep() with 'await asyncio.sleep()' to yield "
        "control back to the event loop."
    ),
    "requests_http": (
        "Replace the requests library with an async HTTP client such as "
        "aiohttp or httpx (with async transport) inside async functions."
    ),
    "open_file_io": (
        "Replace open() with 'async with aiofiles.open()' to perform "
        "non-blocking file I/O. Install aiofiles via pip."
    ),
    "subprocess_call": (
        "Replace subprocess calls with 'await asyncio.create_subprocess_exec()' "
        "or 'await asyncio.create_subprocess_shell()' for non-blocking execution."
    ),
    "urllib_call": (
        "Replace urllib.request.urlopen() with an async HTTP client such as "
        "aiohttp or httpx (with async transport) inside async functions."
    ),
}

_CONTEXT_DESCRIPTIONS: Dict[str, str] = {
    "time_sleep": "time.sleep() blocks the event loop",
    "requests_http": "requests library performs blocking HTTP I/O",
    "open_file_io": "open() performs blocking file I/O",
    "subprocess_call": "subprocess call blocks the event loop",
    "urllib_call": "urllib.request.urlopen() performs blocking HTTP I/O",
}

_REQUESTS_HTTP_METHODS = frozenset(
    ("get", "post", "put", "delete", "patch", "head", "options", "request")
)

_SUBPROCESS_BLOCKING_FUNCS = frozenset(
    ("run", "call", "check_output", "check_call", "Popen")
)


class BlockingAsyncVisitor(ast.NodeVisitor):
    """
    AST visitor that detects blocking calls inside async functions.

    Uses a context stack to track whether the current node is inside an
    async function definition. Only flags blocking calls when the innermost
    enclosing function is an async def.

    Sync functions nested inside async functions are correctly excluded:
    the context stack records the most recent function type, so a sync
    inner function suppresses detection until its scope ends.
    """

    def __init__(self, file_path: str, source_lines: List[str]):
        """
        Initialize the blocking async visitor.

        Args:
            file_path: Path to the file being analyzed
            source_lines: Source code lines for extracting call text
        """
        self.file_path = file_path
        self.source_lines = source_lines
        self.violations: List[BlockingCall] = []
        self.context_stack: List[bool] = []  # True = async function, False = sync function
        self.current_function: Optional[str] = None
        self.current_class: Optional[str] = None

    def _in_async_context(self) -> bool:
        """Return True if the innermost enclosing function is async."""
        return bool(self.context_stack) and self.context_stack[-1]

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Visit class definition to track class context."""
        old_class = self.current_class
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = old_class

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Visit sync function - push False onto context stack."""
        old_function = self.current_function
        self.current_function = node.name
        self.context_stack.append(False)
        self.generic_visit(node)
        self.context_stack.pop()
        self.current_function = old_function

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Visit async function - push True onto context stack."""
        old_function = self.current_function
        self.current_function = node.name
        self.context_stack.append(True)
        self.generic_visit(node)
        self.context_stack.pop()
        self.current_function = old_function

    def visit_Call(self, node: ast.Call) -> None:
        """Visit a function call - check for blocking patterns if in async context."""
        if self._in_async_context():
            blocking_type = self._detect_blocking_call(node)
            if blocking_type:
                self._record_violation(node, blocking_type)
        self.generic_visit(node)

    def _detect_blocking_call(self, node: ast.Call) -> Optional[str]:
        """
        Determine if a Call node represents a blocking operation.

        Returns the BlockingCallType string value, or None if not blocking.
        """
        func = node.func

        if isinstance(func, ast.Name):
            if func.id == "open":
                return cast(str, BlockingCallType.OPEN_FILE_IO.value)

        if not isinstance(func, ast.Attribute):
            return None

        attr = func.attr
        value = func.value

        if isinstance(value, ast.Name):
            module = value.id

            if module == "time" and attr == "sleep":
                return cast(str, BlockingCallType.TIME_SLEEP.value)

            if module == "requests" and attr in _REQUESTS_HTTP_METHODS:
                return cast(str, BlockingCallType.REQUESTS_HTTP.value)

            if module == "subprocess" and attr in _SUBPROCESS_BLOCKING_FUNCS:
                return cast(str, BlockingCallType.SUBPROCESS_CALL.value)

            if module == "request" and attr == "urlopen":
                return cast(str, BlockingCallType.URLLIB_CALL.value)

        if isinstance(value, ast.Attribute):
            inner = value.value
            if isinstance(inner, ast.Name):
                if inner.id == "urllib" and value.attr == "request" and attr == "urlopen":
                    return cast(str, BlockingCallType.URLLIB_CALL.value)

        return None

    def _get_call_expression(self, node: ast.Call) -> str:
        """Extract the source line containing the blocking call."""
        if node.lineno <= len(self.source_lines):
            return self.source_lines[node.lineno - 1].strip()
        return ""

    def _get_context_description(self, blocking_type_val: str) -> str:
        """Build a human-readable context description for the blocking call."""
        base = _CONTEXT_DESCRIPTIONS.get(blocking_type_val, "blocking call in async function")
        if self.current_class and self.current_function:
            return f"{base} in async '{self.current_class}.{self.current_function}'"
        elif self.current_function:
            return f"{base} in async '{self.current_function}'"
        return base

    def _record_violation(self, node: ast.Call, blocking_type_val: str) -> None:
        """Record a blocking call violation."""
        call_expr = self._get_call_expression(node)
        context = self._get_context_description(blocking_type_val)
        remediation = _BLOCKING_REMEDIATION.get(
            blocking_type_val, "Use async-safe alternatives instead of blocking calls."
        )

        self.violations.append(BlockingCall(
            file_path=self.file_path,
            line_number=node.lineno,
            call_expression=call_expr,
            blocking_type=BlockingCallType(blocking_type_val),
            severity=BlockingAsyncSeverity.HIGH,
            containing_function=self.current_function,
            containing_class=self.current_class,
            context_description=context,
            remediation=remediation,
        ))
