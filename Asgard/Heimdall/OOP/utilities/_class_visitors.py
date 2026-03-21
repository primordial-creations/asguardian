"""
Heimdall OOP Class Utilities - AST Visitor Classes

ClassExtractor, MethodAnalyzer, ImportExtractor visitors.
"""

import ast
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set


@dataclass
class ClassInfo:
    """Information about a Python class."""
    name: str
    line_number: int
    end_line: int
    base_classes: List[str] = field(default_factory=list)
    methods: List[str] = field(default_factory=list)
    attributes: Set[str] = field(default_factory=set)
    method_nodes: Dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = field(default_factory=dict)
    class_node: Optional[ast.ClassDef] = None


@dataclass
class MethodInfo:
    """Information about a method."""
    name: str
    line_number: int
    end_line: int
    parameters: List[str] = field(default_factory=list)
    called_methods: Set[str] = field(default_factory=set)
    accessed_attributes: Set[str] = field(default_factory=set)
    complexity: int = 1


class ClassExtractor(ast.NodeVisitor):
    """AST visitor that extracts class information."""

    def __init__(self):
        self.classes: List[ClassInfo] = []
        self._current_class: Optional[ClassInfo] = None

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Extract class definition."""
        base_classes = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                base_classes.append(base.id)
            elif isinstance(base, ast.Attribute):
                parts = []
                current: ast.expr = base
                while isinstance(current, ast.Attribute):
                    parts.append(current.attr)
                    current = current.value
                if isinstance(current, ast.Name):
                    parts.append(current.id)
                base_classes.append(".".join(reversed(parts)))

        class_info = ClassInfo(
            name=node.name,
            line_number=node.lineno,
            end_line=node.end_lineno or node.lineno,
            base_classes=base_classes,
            class_node=node,
        )

        old_class = self._current_class
        self._current_class = class_info

        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                class_info.methods.append(item.name)
                class_info.method_nodes[item.name] = item
            elif isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        class_info.attributes.add(target.id)
            elif isinstance(item, ast.AnnAssign):
                if isinstance(item.target, ast.Name):
                    class_info.attributes.add(item.target.id)

        if "__init__" in class_info.method_nodes:
            init_node = class_info.method_nodes["__init__"]
            class_info.attributes.update(
                self._extract_instance_attributes(init_node)
            )

        self.classes.append(class_info)
        self.generic_visit(node)
        self._current_class = old_class

    def _extract_instance_attributes(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> Set[str]:
        """Extract instance attributes from a method (self.attr assignments)."""
        attributes: Set[str] = set()

        for child in ast.walk(node):
            if isinstance(child, ast.Assign):
                for target in child.targets:
                    if (isinstance(target, ast.Attribute) and
                        isinstance(target.value, ast.Name) and
                        target.value.id == "self"):
                        attributes.add(target.attr)
            elif isinstance(child, ast.AnnAssign):
                if (isinstance(child.target, ast.Attribute) and
                    isinstance(child.target.value, ast.Name) and
                    child.target.value.id == "self"):
                    attributes.add(child.target.attr)

        return attributes


class MethodAnalyzer(ast.NodeVisitor):
    """AST visitor that analyzes method calls and attribute accesses."""

    def __init__(self):
        self.called_methods: Set[str] = set()
        self.accessed_attributes: Set[str] = set()
        self.external_calls: Set[str] = set()
        self.complexity = 1

    def visit_Call(self, node: ast.Call) -> None:
        """Track method calls."""
        if isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name):
                if node.func.value.id == "self":
                    self.called_methods.add(node.func.attr)
                else:
                    self.external_calls.add(f"{node.func.value.id}.{node.func.attr}")
            elif isinstance(node.func.value, ast.Attribute):
                self.external_calls.add(node.func.attr)
        elif isinstance(node.func, ast.Name):
            self.external_calls.add(node.func.id)
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        """Track attribute accesses."""
        if isinstance(node.value, ast.Name) and node.value.id == "self":
            self.accessed_attributes.add(node.attr)
        self.generic_visit(node)

    def visit_If(self, node: ast.If) -> None:
        """Count decision points for complexity."""
        self.complexity += 1
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        """Count loops for complexity."""
        self.complexity += 1
        self.generic_visit(node)

    def visit_While(self, node: ast.While) -> None:
        """Count loops for complexity."""
        self.complexity += 1
        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        """Count exception handlers for complexity."""
        self.complexity += 1
        self.generic_visit(node)

    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        """Count boolean operators for complexity."""
        self.complexity += len(node.values) - 1
        self.generic_visit(node)


class ImportExtractor(ast.NodeVisitor):
    """AST visitor that extracts import information."""

    def __init__(self):
        self.imports: Set[str] = set()
        self.from_imports: Dict[str, Set[str]] = {}
        self.imported_names: Set[str] = set()

    def visit_Import(self, node: ast.Import) -> None:
        """Handle 'import X' statements."""
        for alias in node.names:
            module = alias.name
            self.imports.add(module)
            name = alias.asname if alias.asname else module.split(".")[0]
            self.imported_names.add(name)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Handle 'from X import Y' statements."""
        module = node.module or ""
        if module not in self.from_imports:
            self.from_imports[module] = set()
        for alias in node.names:
            if alias.name == "*":
                self.from_imports[module].add("*")
            else:
                self.from_imports[module].add(alias.name)
                name = alias.asname if alias.asname else alias.name
                self.imported_names.add(name)
