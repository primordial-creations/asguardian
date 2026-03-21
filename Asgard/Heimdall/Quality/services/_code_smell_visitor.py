import ast
from collections import defaultdict
from typing import Dict, List, Optional

from Asgard.Heimdall.Quality.models.smell_models import (
    CodeSmell,
    SmellCategory,
    SmellSeverity,
    SmellThresholds,
)


class SmellVisitor(ast.NodeVisitor):
    """
    AST visitor to detect code smells.

    Walks the AST and identifies various code smell patterns including:
    - Large Class (too many methods or lines)
    - Long Method (too many lines or statements)
    - Long Parameter List
    - Dead Code (pass-only methods)
    - Complex Conditional (too many boolean operators)
    - Feature Envy (tracks method calls to other objects)
    """

    def __init__(
        self,
        file_path: str,
        thresholds: SmellThresholds,
        categories: List[str],
    ):
        """
        Initialize the smell visitor.

        Args:
            file_path: Path to the file being analyzed
            thresholds: Thresholds for smell detection
            categories: List of enabled smell categories
        """
        self.file_path = file_path
        self.thresholds = thresholds
        self.categories = categories
        self.smells: List[CodeSmell] = []
        self.current_class: Optional[str] = None
        self.class_methods: Dict[str, List[str]] = defaultdict(list)
        self.method_calls: Dict[str, List[str]] = defaultdict(list)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """
        Visit class definition to detect class-level smells.

        Detects:
        - Large Class (too many methods)
        - Large Class (too many lines)
        """
        old_class = self.current_class
        self.current_class = node.name

        if SmellCategory.BLOATERS.value in self.categories:
            class_lines = node.end_lineno - node.lineno if hasattr(node, "end_lineno") and node.end_lineno is not None else 0
            methods = [n for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]

            if len(methods) > self.thresholds.large_class_methods:
                self.smells.append(
                    CodeSmell(
                        name="Large Class",
                        category=SmellCategory.BLOATERS,
                        severity=SmellSeverity.HIGH,
                        file_path=self.file_path,
                        line_number=node.lineno,
                        description=f"Class has {len(methods)} methods (threshold: {self.thresholds.large_class_methods})",
                        evidence=f"Class '{node.name}' has too many methods",
                        remediation="Consider splitting into smaller, focused classes using Single Responsibility Principle",
                        confidence=0.9,
                    )
                )

            if class_lines > self.thresholds.large_class_lines:
                self.smells.append(
                    CodeSmell(
                        name="Large Class",
                        category=SmellCategory.BLOATERS,
                        severity=SmellSeverity.MEDIUM,
                        file_path=self.file_path,
                        line_number=node.lineno,
                        description=f"Class has {class_lines} lines (threshold: {self.thresholds.large_class_lines})",
                        evidence=f"Class '{node.name}' is too long",
                        remediation="Break down into smaller classes with focused responsibilities",
                        confidence=0.8,
                    )
                )

        self.generic_visit(node)
        self.current_class = old_class

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """
        Visit function definition to detect method-level smells.

        Detects:
        - Long Method (too many lines)
        - Long Method (too many statements)
        - Long Parameter List
        - Dead Code (pass-only methods)
        """
        self._analyze_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Visit async function definition to detect method-level smells."""
        self._analyze_function(node)

    def _analyze_function(self, node) -> None:
        """Analyze a function or async function for smells."""
        if self.current_class:
            self.class_methods[self.current_class].append(node.name)

        if SmellCategory.BLOATERS.value in self.categories:
            method_lines = node.end_lineno - node.lineno if hasattr(node, "end_lineno") else 0
            statements = len([n for n in ast.walk(node) if isinstance(n, ast.stmt)])

            if method_lines > self.thresholds.long_method_lines:
                self.smells.append(
                    CodeSmell(
                        name="Long Method",
                        category=SmellCategory.BLOATERS,
                        severity=SmellSeverity.MEDIUM,
                        file_path=self.file_path,
                        line_number=node.lineno,
                        description=f"Method has {method_lines} lines (threshold: {self.thresholds.long_method_lines})",
                        evidence=f"Method '{node.name}' is too long",
                        remediation="Extract smaller methods or simplify logic using Extract Method refactoring",
                        confidence=0.9,
                    )
                )

            if statements > self.thresholds.long_method_statements:
                self.smells.append(
                    CodeSmell(
                        name="Long Method",
                        category=SmellCategory.BLOATERS,
                        severity=SmellSeverity.MEDIUM,
                        file_path=self.file_path,
                        line_number=node.lineno,
                        description=f"Method has {statements} statements (threshold: {self.thresholds.long_method_statements})",
                        evidence=f"Method '{node.name}' has too many statements",
                        remediation="Break down into smaller methods with single responsibilities",
                        confidence=0.8,
                    )
                )

        if SmellCategory.BLOATERS.value in self.categories:
            param_count = len(node.args.args)
            if self.current_class and param_count > 0:
                first_arg = node.args.args[0].arg if node.args.args else ""
                if first_arg == "self" or first_arg == "cls":
                    param_count -= 1

            if param_count > self.thresholds.long_parameter_list:
                self.smells.append(
                    CodeSmell(
                        name="Long Parameter List",
                        category=SmellCategory.BLOATERS,
                        severity=SmellSeverity.MEDIUM,
                        file_path=self.file_path,
                        line_number=node.lineno,
                        description=f"Method has {param_count} parameters (threshold: {self.thresholds.long_parameter_list})",
                        evidence=f"Method '{node.name}' has too many parameters",
                        remediation="Use parameter object pattern, introduce a config class, or use builder pattern",
                        confidence=0.9,
                    )
                )

        if SmellCategory.DISPENSABLES.value in self.categories:
            has_return = any(isinstance(n, ast.Return) and n.value is not None for n in ast.walk(node))
            has_assignments = any(isinstance(n, ast.Assign) for n in ast.walk(node))
            has_calls = any(isinstance(n, ast.Call) for n in ast.walk(node))
            has_yield = any(isinstance(n, (ast.Yield, ast.YieldFrom)) for n in ast.walk(node))
            has_raise = any(isinstance(n, ast.Raise) for n in ast.walk(node))

            if not has_return and not has_assignments and not has_calls and not has_yield and not has_raise:
                if len(node.body) == 1:
                    body_item = node.body[0]
                    if isinstance(body_item, ast.Pass):
                        self.smells.append(
                            CodeSmell(
                                name="Dead Code",
                                category=SmellCategory.DISPENSABLES,
                                severity=SmellSeverity.LOW,
                                file_path=self.file_path,
                                line_number=node.lineno,
                                description="Method contains only pass statement",
                                evidence=f"Method '{node.name}' appears to be dead code",
                                remediation="Remove unused method or implement functionality",
                                confidence=0.7,
                            )
                        )
                    elif isinstance(body_item, ast.Expr) and isinstance(body_item.value, ast.Constant):
                        self.smells.append(
                            CodeSmell(
                                name="Dead Code",
                                category=SmellCategory.DISPENSABLES,
                                severity=SmellSeverity.LOW,
                                file_path=self.file_path,
                                line_number=node.lineno,
                                description="Method contains only a docstring with no implementation",
                                evidence=f"Method '{node.name}' appears to be a stub",
                                remediation="Remove unused method or implement functionality",
                                confidence=0.6,
                            )
                        )

        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        """
        Visit function calls to detect coupling smells.

        Tracks method calls for Feature Envy detection.
        """
        if SmellCategory.COUPLERS.value in self.categories:
            if isinstance(node.func, ast.Attribute):
                if isinstance(node.func.value, ast.Name):
                    object_name = node.func.value.id
                    method_name = node.func.attr
                    self.method_calls[object_name].append(method_name)

        self.generic_visit(node)

    def visit_If(self, node: ast.If) -> None:
        """
        Visit if statements to detect complex conditionals.

        Detects conditionals with too many boolean operators.
        """
        if SmellCategory.BLOATERS.value in self.categories:
            condition_complexity = self._count_boolean_operators(node.test)
            if condition_complexity > self.thresholds.complex_conditional_operators:
                self.smells.append(
                    CodeSmell(
                        name="Complex Conditional",
                        category=SmellCategory.BLOATERS,
                        severity=SmellSeverity.LOW,
                        file_path=self.file_path,
                        line_number=node.lineno,
                        description=f"Complex conditional with {condition_complexity} boolean operators (threshold: {self.thresholds.complex_conditional_operators})",
                        evidence="Boolean expression is too complex to understand easily",
                        remediation="Extract condition into well-named method using Extract Method refactoring",
                        confidence=0.6,
                    )
                )

        self.generic_visit(node)

    def visit_While(self, node: ast.While) -> None:
        """Visit while statements to detect complex conditionals."""
        if SmellCategory.BLOATERS.value in self.categories:
            condition_complexity = self._count_boolean_operators(node.test)
            if condition_complexity > self.thresholds.complex_conditional_operators:
                self.smells.append(
                    CodeSmell(
                        name="Complex Conditional",
                        category=SmellCategory.BLOATERS,
                        severity=SmellSeverity.LOW,
                        file_path=self.file_path,
                        line_number=node.lineno,
                        description=f"Complex while condition with {condition_complexity} boolean operators",
                        evidence="While condition is too complex to understand easily",
                        remediation="Extract condition into well-named method",
                        confidence=0.6,
                    )
                )

        self.generic_visit(node)

    def _count_boolean_operators(self, node: ast.AST) -> int:
        """Count boolean operators in an expression."""
        count = 0
        for child in ast.walk(node):
            if isinstance(child, ast.BoolOp):
                count += len(child.values) - 1
            elif isinstance(child, ast.UnaryOp) and isinstance(child.op, ast.Not):
                count += 1
        return count

    def get_feature_envy_smells(self) -> List[CodeSmell]:
        """
        Analyze collected method calls to detect Feature Envy.

        Feature Envy occurs when a method uses methods/properties of another
        object more than its own class.

        Returns:
            List of Feature Envy code smells
        """
        smells: List[CodeSmell] = []
        if SmellCategory.COUPLERS.value not in self.categories:
            return smells

        for object_name, calls in self.method_calls.items():
            if object_name in ("self", "cls", "super"):
                continue

            if len(calls) > self.thresholds.feature_envy_calls:
                smells.append(
                    CodeSmell(
                        name="Feature Envy",
                        category=SmellCategory.COUPLERS,
                        severity=SmellSeverity.MEDIUM,
                        file_path=self.file_path,
                        line_number=1,
                        description=f"Excessive calls to '{object_name}' ({len(calls)} calls)",
                        evidence=f"Methods called: {', '.join(list(set(calls))[:5])}{'...' if len(set(calls)) > 5 else ''}",
                        remediation="Consider moving logic to the class being used, or use delegation",
                        confidence=0.7,
                    )
                )

        return smells
