import ast
from typing import List, Optional

from Asgard.Heimdall.Quality.models.typing_models import (
    AnnotationSeverity,
    AnnotationStatus,
    FunctionAnnotation,
    TypingConfig,
)


class TypingVisitor(ast.NodeVisitor):
    """
    AST visitor that analyzes type annotation coverage.

    Walks the AST and collects information about function/method
    type annotations, including parameters and return types.
    """

    def __init__(
        self,
        file_path: str,
        config: TypingConfig,
    ):
        """
        Initialize the typing visitor.

        Args:
            file_path: Path to the file being analyzed
            config: Configuration for typing analysis
        """
        self.file_path = file_path
        self.config = config
        self.functions: List[FunctionAnnotation] = []
        self.current_class: Optional[str] = None

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Visit class definition to track class context."""
        old_class = self.current_class
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = old_class

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Visit function definition to analyze annotations."""
        self._analyze_function(node, is_async=False)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Visit async function definition to analyze annotations."""
        self._analyze_function(node, is_async=True)
        self.generic_visit(node)

    def _analyze_function(self, node, is_async: bool) -> None:
        """Analyze a function/method for type annotations."""
        func_name = node.name
        is_method = self.current_class is not None
        is_private = func_name.startswith("_") and not func_name.startswith("__")
        is_dunder = func_name.startswith("__") and func_name.endswith("__")

        if self.config.exclude_private and is_private:
            return
        if self.config.exclude_dunder and is_dunder:
            return

        args = node.args
        all_params = []

        for arg in args.posonlyargs:
            all_params.append((arg.arg, arg.annotation))
        for arg in args.args:
            all_params.append((arg.arg, arg.annotation))
        for arg in args.kwonlyargs:
            all_params.append((arg.arg, arg.annotation))
        if args.vararg:
            all_params.append((f"*{args.vararg.arg}", args.vararg.annotation))
        if args.kwarg:
            all_params.append((f"**{args.kwarg.arg}", args.kwarg.annotation))

        if self.config.exclude_self_cls and is_method:
            all_params = [(name, ann) for name, ann in all_params if name not in ("self", "cls")]

        total_params = len(all_params)
        annotated_params = sum(1 for _, ann in all_params if ann is not None)
        missing_params = [name for name, ann in all_params if ann is None]

        has_return = node.returns is not None

        if total_params == 0:
            if has_return or not self.config.require_return_type:
                status = AnnotationStatus.FULLY_ANNOTATED
            else:
                status = AnnotationStatus.NOT_ANNOTATED
        elif annotated_params == total_params and (has_return or not self.config.require_return_type):
            status = AnnotationStatus.FULLY_ANNOTATED
        elif annotated_params > 0 or has_return:
            status = AnnotationStatus.PARTIALLY_ANNOTATED
        else:
            status = AnnotationStatus.NOT_ANNOTATED

        if is_dunder or is_private:
            severity = AnnotationSeverity.LOW
        elif is_method and self.current_class:
            severity = AnnotationSeverity.MEDIUM
        else:
            severity = AnnotationSeverity.HIGH

        self.functions.append(FunctionAnnotation(
            file_path=self.file_path,
            line_number=node.lineno,
            function_name=func_name,
            class_name=self.current_class,
            is_async=is_async,
            is_method=is_method,
            is_private=is_private,
            is_dunder=is_dunder,
            status=status,
            severity=severity,
            total_parameters=total_params,
            annotated_parameters=annotated_params,
            has_return_annotation=has_return,
            missing_parameter_names=missing_params,
        ))
