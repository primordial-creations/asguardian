import ast
from typing import Dict, List, Optional

from Asgard.Heimdall.Quality.models.race_condition_models import (
    RaceConditionIssue,
    RaceConditionSeverity,
    RaceConditionType,
)
from Asgard.Heimdall.Quality.services._race_condition_helpers import (
    get_call_name,
    get_call_receiver_name,
    has_lock_enclosure,
    is_self_attr_assignment,
    is_self_attr_to_var,
    is_thread_call,
    self_attr_accessed_in_body,
)


class RaceConditionVisitor(ast.NodeVisitor):
    """
    AST visitor that detects race condition patterns.

    Analyzes method bodies for:
    - thread.start() before self reference is stored (unreliable join)
    - self.attr assignment after thread.start()
    - check-then-act patterns without lock protection
    """

    def __init__(self, file_path: str, source_lines: List[str]):
        """
        Initialize the race condition visitor.

        Args:
            file_path: Path to the file being analyzed
            source_lines: Source code lines for context
        """
        self.file_path = file_path
        self.source_lines = source_lines
        self.issues: List[RaceConditionIssue] = []
        self.current_class: Optional[str] = None
        self.current_method: Optional[str] = None

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Track class context."""
        old_class = self.current_class
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = old_class

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Analyze function/method body for race conditions."""
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Analyze async function body for race conditions."""
        self._visit_function(node)

    def _visit_function(self, node) -> None:
        """Common handler for function and async function analysis."""
        old_method = self.current_method
        self.current_method = node.name
        self._analyze_method_body(node.body)
        self.generic_visit(node)
        self.current_method = old_method

    def _analyze_method_body(self, body: List[ast.stmt]) -> None:
        """
        Analyze a method body for race conditions.

        Scans for:
        1. thread.start() before self._thread = thread (START_BEFORE_STORE)
        2. self.attr = value after thread.start() (ASSIGN_AFTER_START)
        3. if self.x: self.x.do() without lock (CHECK_THEN_ACT)
        """
        thread_vars: Dict[str, int] = {}
        thread_started: Dict[str, int] = {}

        for stmt in body:
            if isinstance(stmt, ast.Assign):
                for target in stmt.targets:
                    if isinstance(target, ast.Name) and isinstance(stmt.value, ast.Call):
                        if is_thread_call(stmt.value):
                            thread_vars[target.id] = stmt.lineno

        for i, stmt in enumerate(body):
            if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
                call = stmt.value
                method_name = get_call_name(call)
                receiver = get_call_receiver_name(call)

                if method_name == "start" and receiver and receiver in thread_vars:
                    thread_started[receiver] = stmt.lineno

                    remaining_stmts = body[i + 1:]
                    for later_stmt in remaining_stmts:
                        stored = is_self_attr_to_var(later_stmt)
                        if stored:
                            self_attr, var_name = stored
                            if var_name == receiver:
                                self.issues.append(RaceConditionIssue(
                                    file_path=self.file_path,
                                    line_number=stmt.lineno,
                                    class_name=self.current_class,
                                    method_name=self.current_method,
                                    race_type=RaceConditionType.START_BEFORE_STORE,
                                    severity=RaceConditionSeverity.HIGH,
                                    description=(
                                        f"Thread '{receiver}' is started at line {stmt.lineno} before "
                                        f"its reference is stored as 'self.{self_attr}' at line "
                                        f"{later_stmt.lineno}. Calling join() before the assignment "
                                        f"completes is unreliable."
                                    ),
                                    remediation=(
                                        f"Store the thread reference 'self.{self_attr} = {receiver}' "
                                        f"BEFORE calling '{receiver}.start()'."
                                    ),
                                ))

                        attr_name = is_self_attr_assignment(later_stmt)
                        if attr_name is not None:
                            stored_check = is_self_attr_to_var(later_stmt)
                            if not stored_check or stored_check[1] != receiver:
                                self.issues.append(RaceConditionIssue(
                                    file_path=self.file_path,
                                    line_number=later_stmt.lineno,
                                    class_name=self.current_class,
                                    method_name=self.current_method,
                                    race_type=RaceConditionType.ASSIGN_AFTER_START,
                                    severity=RaceConditionSeverity.HIGH,
                                    description=(
                                        f"'self.{attr_name}' is assigned at line {later_stmt.lineno} "
                                        f"after thread '{receiver}' was started at line {stmt.lineno}. "
                                        f"The thread may read a stale or missing value of this attribute."
                                    ),
                                    remediation=(
                                        f"Set 'self.{attr_name}' BEFORE calling '{receiver}.start()', "
                                        f"or use a threading.Lock() to synchronize access."
                                    ),
                                ))

            if isinstance(stmt, ast.If):
                self._check_check_then_act(stmt, body)

    def _check_check_then_act(self, if_node: ast.If, parent_body: List[ast.stmt]) -> None:
        """
        Detect check-then-act race on self attributes.

        Flags patterns like:
            if self.x:
                self.x.do_something()
        without a surrounding lock context.
        """
        test = if_node.test

        checked_attr: Optional[str] = None

        if (
            isinstance(test, ast.Attribute)
            and isinstance(test.value, ast.Name)
            and test.value.id == "self"
        ):
            checked_attr = test.attr

        elif isinstance(test, ast.Compare):
            left = test.left
            if (
                isinstance(left, ast.Attribute)
                and isinstance(left.value, ast.Name)
                and left.value.id == "self"
            ):
                checked_attr = left.attr

        if checked_attr is None:
            return

        if not self_attr_accessed_in_body(if_node.body, checked_attr):
            return

        if has_lock_enclosure(if_node, parent_body):
            return

        self.issues.append(RaceConditionIssue(
            file_path=self.file_path,
            line_number=if_node.lineno,
            class_name=self.current_class,
            method_name=self.current_method,
            race_type=RaceConditionType.CHECK_THEN_ACT,
            severity=RaceConditionSeverity.HIGH,
            description=(
                f"Check-then-act on 'self.{checked_attr}' at line {if_node.lineno} "
                f"without lock protection. Another thread may modify 'self.{checked_attr}' "
                f"between the check and the action."
            ),
            remediation=(
                f"Wrap the check and action in a 'with self._lock:' block to prevent "
                f"another thread from modifying 'self.{checked_attr}' between the check and act."
            ),
        ))
