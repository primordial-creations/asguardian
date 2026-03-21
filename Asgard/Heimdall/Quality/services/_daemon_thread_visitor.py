import ast
from collections import defaultdict
from typing import Dict, List, Optional, Set

from Asgard.Heimdall.Quality.models.daemon_thread_models import (
    DaemonThreadIssue,
    DaemonThreadIssueType,
    DaemonThreadSeverity,
)


def _is_thread_call(call_node: ast.Call) -> bool:
    """Check if a Call node is a threading.Thread() or Thread() instantiation."""
    func = call_node.func
    return (
        (isinstance(func, ast.Name) and func.id == "Thread")
        or (isinstance(func, ast.Attribute) and func.attr == "Thread")
    )


def _is_daemon_thread_call(call_node: ast.Call) -> bool:
    """Check if Thread() call has daemon=True keyword argument."""
    if not _is_thread_call(call_node):
        return False
    for kw in call_node.keywords:
        if kw.arg == "daemon":
            # Check for True literal
            if isinstance(kw.value, ast.Constant) and kw.value.value is True:
                return True
            # Check for ast.NameConstant True (older Python)
            if isinstance(kw.value, ast.Name) and kw.value.id == "True":
                return True
    return False


def _is_event_call(call_node: ast.Call) -> bool:
    """Check if Call node is threading.Event() or Event() instantiation."""
    func = call_node.func
    return (
        (isinstance(func, ast.Name) and func.id == "Event")
        or (isinstance(func, ast.Attribute) and func.attr == "Event")
    )


def _get_method_name(call_node: ast.Call) -> Optional[str]:
    """Get the method name from a method call (e.g. 'start', 'join', 'set', 'wait')."""
    if isinstance(call_node.func, ast.Attribute):
        return call_node.func.attr
    return None


def _get_call_receiver_name(call_node: ast.Call) -> Optional[str]:
    """Get the variable name the method is called on."""
    if isinstance(call_node.func, ast.Attribute):
        if isinstance(call_node.func.value, ast.Name):
            return call_node.func.value.id
        elif (
            isinstance(call_node.func.value, ast.Attribute)
            and isinstance(call_node.func.value.value, ast.Name)
            and call_node.func.value.value.id == "self"
        ):
            return f"self.{call_node.func.value.attr}"
    return None


def _is_stored_on_self(assign_node: ast.Assign) -> bool:
    """Check if the assignment target is a self.attr (stored on instance)."""
    for target in assign_node.targets:
        if (
            isinstance(target, ast.Attribute)
            and isinstance(target.value, ast.Name)
            and target.value.id == "self"
        ):
            return True
    return False


def _get_local_var_name(assign_node: ast.Assign) -> Optional[str]:
    """Get the local variable name from an assignment if target is a plain Name."""
    for target in assign_node.targets:
        if isinstance(target, ast.Name):
            return target.id
    return None


class DaemonThreadInfo:
    """Holds information about a daemon thread found in code."""

    def __init__(self, var_name: str, line_number: int, stored_on_self: bool):
        self.var_name = var_name
        self.line_number = line_number
        self.stored_on_self = stored_on_self


class DaemonThreadVisitor(ast.NodeVisitor):
    """
    AST visitor that detects daemon thread lifecycle issues.

    Analyzes function/method bodies for:
    - Daemon threads stored in local variables only (reference may be lost)
    - Daemon threads with no join() call in the same scope
    - Event.wait() patterns with only daemon thread callers for .set()
    """

    def __init__(self, file_path: str, source_lines: List[str]):
        """
        Initialize the daemon thread visitor.

        Args:
            file_path: Path to the file being analyzed
            source_lines: Source code lines for context
        """
        self.file_path = file_path
        self.source_lines = source_lines
        self.issues: List[DaemonThreadIssue] = []
        self.current_class: Optional[str] = None
        self.current_method: Optional[str] = None

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Track class context."""
        old_class = self.current_class
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = old_class

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Analyze function/method for daemon thread issues."""
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Analyze async function for daemon thread issues."""
        self._visit_function(node)

    def _visit_function(self, node) -> None:
        """Common handler for function and async function analysis."""
        old_method = self.current_method
        self.current_method = node.name
        self._analyze_scope(node.body)
        self.generic_visit(node)
        self.current_method = old_method

    def _analyze_scope(self, body: List[ast.stmt]) -> None:
        """
        Analyze a scope (function body) for daemon thread lifecycle issues.

        Collects all daemon thread assignments, then checks:
        1. Whether each is stored in a local var only (MEDIUM)
        2. Whether each has a .join() call in scope (LOW if missing)
        3. Whether Event objects are waited on by non-daemon code (MEDIUM)
        """
        # Track daemon thread info: var_name -> DaemonThreadInfo
        daemon_threads: Dict[str, DaemonThreadInfo] = {}

        # Track all join() calls in scope: set of var names joined
        joined_vars: Set[str] = set()

        # Track event variables
        event_vars: Set[str] = set()
        event_waited: Set[str] = set()

        # Collect daemon threads and joined vars
        for stmt in ast.walk(ast.Module(body=body, type_ignores=[])):
            if isinstance(stmt, ast.Assign):
                if isinstance(stmt.value, ast.Call):
                    if _is_daemon_thread_call(stmt.value):
                        stored_on_self = _is_stored_on_self(stmt)
                        local_name = _get_local_var_name(stmt)
                        var_name = local_name if not stored_on_self else None
                        if stored_on_self:
                            # self.t = Thread(daemon=True) - get attr name
                            for target in stmt.targets:
                                if (
                                    isinstance(target, ast.Attribute)
                                    and isinstance(target.value, ast.Name)
                                    and target.value.id == "self"
                                ):
                                    var_name = f"self.{target.attr}"
                        if var_name:
                            daemon_threads[var_name] = DaemonThreadInfo(
                                var_name=var_name,
                                line_number=stmt.lineno,
                                stored_on_self=stored_on_self,
                            )

                    elif _is_event_call(stmt.value):
                        local_name = _get_local_var_name(stmt)
                        if local_name:
                            event_vars.add(local_name)
                        for target in stmt.targets:
                            if (
                                isinstance(target, ast.Attribute)
                                and isinstance(target.value, ast.Name)
                                and target.value.id == "self"
                            ):
                                event_vars.add(f"self.{target.attr}")

            elif isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
                call = stmt.value
                method = _get_method_name(call)
                receiver = _get_call_receiver_name(call)
                if method == "join" and receiver:
                    joined_vars.add(receiver)
                elif method == "wait" and receiver:
                    event_waited.add(receiver)

        # Generate issues for daemon threads
        for var_name, info in daemon_threads.items():
            # Issue 1: stored in local variable only (MEDIUM)
            if not info.stored_on_self:
                self.issues.append(DaemonThreadIssue(
                    file_path=self.file_path,
                    line_number=info.line_number,
                    class_name=self.current_class,
                    method_name=self.current_method,
                    issue_type=DaemonThreadIssueType.LOCAL_VAR_ONLY,
                    severity=DaemonThreadSeverity.MEDIUM,
                    description=(
                        f"Daemon thread '{var_name}' is stored only in a local variable. "
                        f"The reference may be lost when the function returns, making it "
                        f"impossible to join or monitor the thread."
                    ),
                    thread_variable=var_name,
                    remediation=(
                        f"Store the daemon thread as an instance attribute (e.g., 'self._thread = {var_name}') "
                        f"to maintain a reference for monitoring and graceful shutdown."
                    ),
                ))

            # Issue 2: no join() call found in scope (LOW)
            if var_name not in joined_vars:
                self.issues.append(DaemonThreadIssue(
                    file_path=self.file_path,
                    line_number=info.line_number,
                    class_name=self.current_class,
                    method_name=self.current_method,
                    issue_type=DaemonThreadIssueType.NO_JOIN,
                    severity=DaemonThreadSeverity.LOW,
                    description=(
                        f"Daemon thread '{var_name}' has no join() call in scope. "
                        f"The thread will be silently killed when the main thread exits. "
                        f"Errors or incomplete work in the daemon thread may go undetected."
                    ),
                    thread_variable=var_name,
                    remediation=(
                        f"Add a health check mechanism or call '{var_name}.join(timeout=...)' "
                        f"with a timeout to detect if the daemon thread has terminated unexpectedly."
                    ),
                ))

        # Issue 3: Event.wait() where only daemon threads could call .set()
        # Heuristic: if we see Event.wait() in non-daemon code and daemon threads exist in scope
        if event_waited and daemon_threads:
            for event_var in event_waited:
                self.issues.append(DaemonThreadIssue(
                    file_path=self.file_path,
                    line_number=0,
                    class_name=self.current_class,
                    method_name=self.current_method,
                    issue_type=DaemonThreadIssueType.EVENT_SET_BY_DAEMON,
                    severity=DaemonThreadSeverity.MEDIUM,
                    description=(
                        f"Event '{event_var}' is waited on in a scope that also contains daemon "
                        f"threads. If only daemon threads call '{event_var}.set()', the wait "
                        f"may never complete if the daemon is killed before setting the event."
                    ),
                    thread_variable=event_var,
                    remediation=(
                        f"Ensure non-daemon code is responsible for calling '{event_var}.set()', "
                        f"or use Event.wait(timeout=...) to prevent indefinite blocking."
                    ),
                ))
