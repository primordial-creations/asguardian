"""
Heimdall Coupling Analyzer - AST Visitor

CouplingVisitor: detects coupling between classes.
"""

import ast
from typing import Set


class CouplingVisitor(ast.NodeVisitor):
    """AST visitor that detects coupling between classes."""

    def __init__(self, class_name: str, all_class_names: Set[str], imported_names: Set[str]):
        self.class_name = class_name
        self.all_class_names = all_class_names
        self.imported_names = imported_names
        self.coupled_classes: Set[str] = set()

    def _is_relevant_class(self, name: str) -> bool:
        """Check if a name refers to a relevant class."""
        return name in self.all_class_names or name in self.imported_names

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Check inheritance coupling."""
        if node.name != self.class_name:
            return

        for base in node.bases:
            if isinstance(base, ast.Name):
                if self._is_relevant_class(base.id) and base.id != self.class_name:
                    self.coupled_classes.add(base.id)
            elif isinstance(base, ast.Attribute):
                if self._is_relevant_class(base.attr) and base.attr != self.class_name:
                    self.coupled_classes.add(base.attr)

        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        """Check name references that might be class usages."""
        if self._is_relevant_class(node.id) and node.id != self.class_name:
            self.coupled_classes.add(node.id)
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        """Check attribute accesses that might indicate coupling."""
        if isinstance(node.value, ast.Name):
            if self._is_relevant_class(node.value.id) and node.value.id != self.class_name:
                self.coupled_classes.add(node.value.id)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        """Check class instantiation and method calls."""
        if isinstance(node.func, ast.Name):
            if self._is_relevant_class(node.func.id) and node.func.id != self.class_name:
                self.coupled_classes.add(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name):
                if self._is_relevant_class(node.func.value.id) and node.func.value.id != self.class_name:
                    self.coupled_classes.add(node.func.value.id)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        """Check type annotations for coupling."""
        self._check_annotation(node.annotation)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        """Check function annotations for coupling."""
        if node.returns:
            self._check_annotation(node.returns)
        for arg in node.args.args:
            if arg.annotation:
                self._check_annotation(arg.annotation)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Check async function annotations for coupling."""
        self.visit_FunctionDef(node)

    def _check_annotation(self, annotation: ast.expr) -> None:
        """Check a type annotation for class references."""
        if isinstance(annotation, ast.Name):
            if self._is_relevant_class(annotation.id) and annotation.id != self.class_name:
                self.coupled_classes.add(annotation.id)
        elif isinstance(annotation, ast.Subscript):
            self._check_annotation(annotation.value)
            if isinstance(annotation.slice, ast.Tuple):
                for elt in annotation.slice.elts:
                    self._check_annotation(elt)
            else:
                self._check_annotation(annotation.slice)
        elif isinstance(annotation, ast.Attribute):
            if self._is_relevant_class(annotation.attr) and annotation.attr != self.class_name:
                self.coupled_classes.add(annotation.attr)
