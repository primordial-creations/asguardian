import ast
from typing import Dict, List, Optional, Set, Tuple, cast

from Asgard.Heimdall.Quality.models.future_leak_models import (
    FutureLeak,
    FutureLeakSeverity,
    FutureLeakType,
)


_REMEDIATION: Dict[str, str] = {
    "asyncio_task": (
        "Await the task or store a reference and await it later. "
        "Use asyncio.gather() or asyncio.shield() to manage task lifecycle."
    ),
    "executor_submit": (
        "Call .result(), .exception(), or .wait() on the returned future "
        "to check completion and handle exceptions."
    ),
    "concurrent_future": (
        "Call .result(), .exception(), or .cancel() on the future "
        "to manage its lifecycle and handle exceptions."
    ),
    "thread_not_joined": (
        "Call .join() on the thread after .start() to wait for it to complete "
        "and ensure proper resource cleanup."
    ),
}

_CONTEXT_DESCRIPTIONS: Dict[str, str] = {
    "asyncio_task": "asyncio task created but never awaited",
    "executor_submit": "executor future created but .result()/.exception()/.wait() never called",
    "concurrent_future": "concurrent.futures.Future created but never resolved",
    "thread_not_joined": "Thread started with .start() but .join() never called",
}


def _walk_without_nested_functions(node: ast.AST):
    """
    Walk AST nodes without descending into nested function or class definitions.

    This prevents cross-scope contamination when scanning a function body
    for future assignments and resolutions.
    """
    yield node
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        yield from _walk_without_nested_functions(child)


def _get_dotted_call_name(node: ast.Call) -> Optional[str]:
    """
    Extract the dotted name from a Call node's func attribute.

    Examples:
        asyncio.create_task(...)   -> 'asyncio.create_task'
        executor.submit(...)       -> 'executor.submit'
        self.pool.submit(...)      -> 'self.pool.submit'
    """
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        value = func.value
        if isinstance(value, ast.Name):
            return f"{value.id}.{func.attr}"
        if isinstance(value, ast.Attribute):
            inner = value.value
            if isinstance(inner, ast.Name):
                return f"{inner.id}.{value.attr}.{func.attr}"
    return None


def _detect_future_creation(node: ast.expr) -> Optional[str]:
    """
    Determine if an expression is a future-creating call.

    Returns the FutureLeakType string value, or None if not a future creator.
    """
    if not isinstance(node, ast.Call):
        return None

    name = _get_dotted_call_name(node)
    if name is None:
        return None

    if name in ("asyncio.create_task", "asyncio.ensure_future"):
        return cast(str, FutureLeakType.ASYNCIO_TASK.value)

    if name.endswith(".submit"):
        return cast(str, FutureLeakType.EXECUTOR_SUBMIT.value)

    if name == "concurrent.futures.Future":
        return cast(str, FutureLeakType.CONCURRENT_FUTURE.value)

    return None


def _detect_thread_creation(node: ast.expr) -> bool:
    """Check if an expression is a threading.Thread constructor call."""
    if not isinstance(node, ast.Call):
        return False
    name = _get_dotted_call_name(node)
    return name in ("threading.Thread", "Thread")


def _build_context_description(
    leak_type_val: str,
    current_class: Optional[str],
    current_function: Optional[str],
) -> str:
    """Build a human-readable context description for a leak."""
    base = _CONTEXT_DESCRIPTIONS.get(leak_type_val, "future/thread leak detected")
    if current_class and current_function:
        return f"{base} in '{current_class}.{current_function}'"
    elif current_function:
        return f"{base} in '{current_function}'"
    return base


def _scan_function_body_for_leaks(
    func_node: ast.AST,
    file_path: str,
    current_function: Optional[str],
    current_class: Optional[str],
) -> List[FutureLeak]:
    """
    Scan a single function body for future and thread leaks.

    Uses _walk_without_nested_functions to restrict the scan to this
    function's own scope, preventing cross-scope contamination.

    Returns a list of detected FutureLeak objects.
    """
    leaks: List[FutureLeak] = []

    # future_vars: var_name -> (line_no, leak_type_string)
    future_vars: Dict[str, Tuple[int, str]] = {}

    # thread_vars: var_name -> line_no (created threads)
    thread_vars: Dict[str, int] = {}

    # started_threads: var names that had .start() called
    started_threads: Set[str] = set()

    # resolved: var names that were awaited, .result()/.join() called on
    resolved: Set[str] = set()

    for child in _walk_without_nested_functions(func_node):
        # Detect future/thread assignments
        if isinstance(child, ast.Assign):
            rhs = child.value
            leak_type_val = _detect_future_creation(rhs)
            if leak_type_val:
                for target in child.targets:
                    if isinstance(target, ast.Name):
                        future_vars[target.id] = (child.lineno, leak_type_val)
            elif _detect_thread_creation(rhs):
                for target in child.targets:
                    if isinstance(target, ast.Name):
                        thread_vars[target.id] = child.lineno

        # Detect await expressions: await task_var or await task_var.something()
        elif isinstance(child, ast.Await):
            awaited = child.value
            if isinstance(awaited, ast.Name):
                resolved.add(awaited.id)
            elif isinstance(awaited, ast.Call):
                if isinstance(awaited.func, ast.Attribute) and isinstance(awaited.func.value, ast.Name):
                    resolved.add(awaited.func.value.id)

        # Detect .result(), .exception(), .wait(), .cancel(), .join(), .start() method calls
        elif isinstance(child, ast.Call):
            if isinstance(child.func, ast.Attribute):
                attr = child.func.attr
                obj = child.func.value
                if isinstance(obj, ast.Name):
                    if attr in ("result", "exception", "wait", "cancel", "join"):
                        resolved.add(obj.id)
                    elif attr == "start":
                        started_threads.add(obj.id)

    # Report unresolved futures
    for var_name, (line_no, leak_type_val) in future_vars.items():
        if var_name not in resolved:
            context = _build_context_description(leak_type_val, current_class, current_function)
            leaks.append(FutureLeak(
                file_path=file_path,
                line_number=line_no,
                variable_name=var_name,
                leak_type=FutureLeakType(leak_type_val),
                severity=FutureLeakSeverity.MEDIUM,
                containing_function=current_function,
                containing_class=current_class,
                context_description=context,
                remediation=_REMEDIATION.get(leak_type_val, "Ensure the future is properly resolved."),
            ))

    # Report threads that were started but never joined
    for var_name, line_no in thread_vars.items():
        if var_name in started_threads and var_name not in resolved:
            context = _build_context_description(
                FutureLeakType.THREAD_NOT_JOINED.value, current_class, current_function
            )
            leaks.append(FutureLeak(
                file_path=file_path,
                line_number=line_no,
                variable_name=var_name,
                leak_type=FutureLeakType.THREAD_NOT_JOINED,
                severity=FutureLeakSeverity.MEDIUM,
                containing_function=current_function,
                containing_class=current_class,
                context_description=context,
                remediation=_REMEDIATION["thread_not_joined"],
            ))

    return leaks


class FutureLeakVisitor(ast.NodeVisitor):
    """
    AST visitor that detects future and thread leaks.

    For each function definition encountered, scans its body (without
    descending into nested functions) to find futures, tasks, and threads
    that are never properly resolved, awaited, or joined.
    """

    def __init__(self, file_path: str, source_lines: List[str]):
        """
        Initialize the future leak visitor.

        Args:
            file_path: Path to the file being analyzed
            source_lines: Source code lines (unused but kept for API consistency)
        """
        self.file_path = file_path
        self.source_lines = source_lines
        self.leaks: List[FutureLeak] = []
        self.current_function: Optional[str] = None
        self.current_class: Optional[str] = None

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Visit class definition to track class context."""
        old_class = self.current_class
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = old_class

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Visit sync function definition."""
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Visit async function definition."""
        self._visit_function(node)

    def _visit_function(self, node) -> None:
        """Common handler for function and async function definitions."""
        old_function = self.current_function
        self.current_function = node.name

        leaks = _scan_function_body_for_leaks(
            node,
            self.file_path,
            self.current_function,
            self.current_class,
        )
        self.leaks.extend(leaks)

        # Continue traversal to handle nested functions
        self.generic_visit(node)
        self.current_function = old_function
