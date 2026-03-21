import ast
from typing import Dict, List, Optional

from Asgard.Heimdall.Quality.models.datetime_models import (
    DatetimeConfig,
    DatetimeIssueType,
    DatetimeSeverity,
    DatetimeViolation,
    DATETIME_REMEDIATIONS,
)


class DatetimeVisitor(ast.NodeVisitor):
    """
    AST visitor that detects problematic datetime usage.

    Walks the AST and identifies:
    - datetime.utcnow() calls (deprecated in Python 3.12+)
    - datetime.now() calls without timezone argument
    - datetime.today() calls (returns naive datetime)
    - datetime.utcfromtimestamp() calls (deprecated)
    """

    def __init__(
        self,
        file_path: str,
        source_lines: List[str],
        config: DatetimeConfig,
    ):
        """
        Initialize the datetime visitor.

        Args:
            file_path: Path to the file being analyzed
            source_lines: Source code lines for extracting context
            config: Configuration for what to check
        """
        self.file_path = file_path
        self.source_lines = source_lines
        self.config = config
        self.violations: List[DatetimeViolation] = []
        self.current_function: Optional[str] = None
        self.current_class: Optional[str] = None
        self._datetime_aliases: set = set()
        self._datetime_module_aliases: Dict[str, str] = {}

    def _get_code_snippet(self, line_number: int) -> str:
        """Extract code at the line."""
        if line_number <= len(self.source_lines):
            return self.source_lines[line_number - 1].strip()
        return ""

    def _determine_severity(self, issue_type: DatetimeIssueType) -> DatetimeSeverity:
        """Determine severity based on issue type."""
        if issue_type in (DatetimeIssueType.UTCNOW, DatetimeIssueType.UTCFROMTIMESTAMP):
            return DatetimeSeverity.HIGH
        return DatetimeSeverity.MEDIUM

    def _record_violation(
        self,
        node: ast.expr,
        issue_type: DatetimeIssueType,
    ) -> None:
        """Record a datetime violation."""
        self.violations.append(DatetimeViolation(
            file_path=self.file_path,
            line_number=node.lineno,
            column=node.col_offset,
            code_snippet=self._get_code_snippet(node.lineno),
            issue_type=issue_type,
            severity=self._determine_severity(issue_type),
            remediation=DATETIME_REMEDIATIONS.get(issue_type, "Use timezone-aware datetime"),
            containing_function=self.current_function,
            containing_class=self.current_class,
        ))

    def visit_Import(self, node: ast.Import) -> None:
        """Track import datetime statements."""
        for alias in node.names:
            if alias.name == "datetime":
                actual_name = alias.asname if alias.asname else alias.name
                self._datetime_module_aliases[actual_name] = "datetime"
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Track from datetime import datetime statements."""
        if node.module == "datetime":
            for alias in node.names:
                if alias.name == "datetime":
                    actual_name = alias.asname if alias.asname else alias.name
                    self._datetime_aliases.add(actual_name)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Visit class definition to track class context."""
        old_class = self.current_class
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = old_class

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Visit function definition to track function context."""
        old_function = self.current_function
        self.current_function = node.name
        self.generic_visit(node)
        self.current_function = old_function

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Visit async function definition to track function context."""
        old_function = self.current_function
        self.current_function = node.name
        self.generic_visit(node)
        self.current_function = old_function

    def visit_Call(self, node: ast.Call) -> None:
        """Visit function calls to detect datetime issues."""
        self._check_datetime_call(node)
        self.generic_visit(node)

    def _check_datetime_call(self, node: ast.Call) -> None:
        """Check if this is a problematic datetime call."""
        if isinstance(node.func, ast.Attribute):
            attr_name = node.func.attr

            if self._is_datetime_class_call(node.func):
                self._check_datetime_method(node, attr_name)

    def _is_datetime_class_call(self, func: ast.Attribute) -> bool:
        """Check if this is a call on the datetime class."""
        if isinstance(func.value, ast.Name):
            name = func.value.id
            if name in self._datetime_aliases:
                return True
            if name in self._datetime_module_aliases:
                return False

        if isinstance(func.value, ast.Attribute):
            if isinstance(func.value.value, ast.Name):
                module_name = func.value.value.id
                class_name = func.value.attr
                if module_name in self._datetime_module_aliases and class_name == "datetime":
                    return True
                if module_name == "datetime" and class_name == "datetime":
                    return True

        return False

    def _check_datetime_method(self, node: ast.Call, method_name: str) -> None:
        """Check specific datetime method calls."""
        if method_name == "utcnow" and self.config.check_utcnow:
            self._record_violation(node, DatetimeIssueType.UTCNOW)

        elif method_name == "utcfromtimestamp" and self.config.check_utcnow:
            self._record_violation(node, DatetimeIssueType.UTCFROMTIMESTAMP)

        elif method_name == "now" and self.config.check_now_no_tz:
            if not self._has_timezone_arg(node):
                self._record_violation(node, DatetimeIssueType.NOW_NO_TZ)

        elif method_name == "today" and self.config.check_today_no_tz:
            self._record_violation(node, DatetimeIssueType.TODAY_NO_TZ)

    def _has_timezone_arg(self, node: ast.Call) -> bool:
        """Check if a now() call has a timezone argument."""
        if node.args:
            return True

        for keyword in node.keywords:
            if keyword.arg == "tz":
                return True

        return False
