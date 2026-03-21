"""
Heimdall Pattern Detector - Creational Pattern Detection

Singleton, Factory, Builder detectors.
"""

import ast
from typing import Dict, List

from Asgard.Heimdall.Architecture.models.architecture_models import (
    PatternMatch,
    PatternType,
)
from Asgard.Heimdall.Architecture.utilities.ast_utils import (
    get_abstract_methods,
    get_class_attributes,
    get_class_methods,
    is_abstract_class,
)


def detect_singleton(class_node: ast.ClassDef, file_path: str) -> List[PatternMatch]:
    """Detect Singleton pattern."""
    patterns = []

    methods = get_class_methods(class_node)
    method_names = {m.name for m in methods}
    attributes = get_class_attributes(class_node)

    has_instance = "_instance" in attributes or "instance" in attributes
    has_new = "__new__" in method_names
    has_get_instance = "get_instance" in method_names or "getInstance" in method_names

    for node in class_node.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    if target.id in ("_instance", "instance"):
                        has_instance = True

    if has_instance and (has_new or has_get_instance):
        confidence = 0.9 if has_new else 0.7
        patterns.append(PatternMatch(
            pattern_type=PatternType.SINGLETON,
            class_name=class_node.name,
            file_path=file_path,
            line_number=class_node.lineno,
            confidence=confidence,
            details="Uses _instance with __new__ or get_instance method",
        ))

    return patterns


def detect_factory(
    class_node: ast.ClassDef,
    file_path: str,
    all_classes: Dict[str, Dict],
) -> List[PatternMatch]:
    """Detect Factory pattern."""
    patterns = []

    if "Factory" in class_node.name:
        methods = get_class_methods(class_node)
        create_methods = [
            m for m in methods
            if m.name.startswith(("create", "make", "build", "get"))
            and not m.name.startswith("_")
        ]
        if create_methods:
            patterns.append(PatternMatch(
                pattern_type=PatternType.FACTORY,
                class_name=class_node.name,
                file_path=file_path,
                line_number=class_node.lineno,
                confidence=0.85,
                participants=[m.name for m in create_methods],
                details=f"Factory class with {len(create_methods)} creation methods",
            ))

    if is_abstract_class(class_node) and "Factory" in class_node.name:
        abstract_methods = get_abstract_methods(class_node)
        create_methods = [
            m for m in abstract_methods
            if m.startswith(("create", "make", "build"))
        ]
        if len(create_methods) >= 2:
            patterns.append(PatternMatch(
                pattern_type=PatternType.ABSTRACT_FACTORY,
                class_name=class_node.name,
                file_path=file_path,
                line_number=class_node.lineno,
                confidence=0.8,
                participants=create_methods,
                details="Abstract factory with multiple creation methods",
            ))

    return patterns


def detect_builder(class_node: ast.ClassDef, file_path: str) -> List[PatternMatch]:
    """Detect Builder pattern."""
    patterns = []

    if "Builder" in class_node.name:
        methods = get_class_methods(class_node)
        method_names = [m.name for m in methods]
        fluent_methods = []

        for method in methods:
            if method.name.startswith("_"):
                continue
            for node in ast.walk(method):
                if isinstance(node, ast.Return):
                    if isinstance(node.value, ast.Name) and node.value.id == "self":
                        fluent_methods.append(method.name)
                        break

        has_build = "build" in method_names
        if fluent_methods and has_build:
            patterns.append(PatternMatch(
                pattern_type=PatternType.BUILDER,
                class_name=class_node.name,
                file_path=file_path,
                line_number=class_node.lineno,
                confidence=0.9,
                participants=fluent_methods + ["build"],
                details=f"Builder with {len(fluent_methods)} fluent methods",
            ))

    return patterns
