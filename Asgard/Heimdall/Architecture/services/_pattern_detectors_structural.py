"""
Heimdall Pattern Detector - Structural Pattern Detection

Adapter, Decorator, Facade detectors.
"""

import ast
from typing import Dict, List

from Asgard.Heimdall.Architecture.models.architecture_models import (
    PatternMatch,
    PatternType,
)
from Asgard.Heimdall.Architecture.utilities.ast_utils import (
    get_class_bases,
    get_class_methods,
    get_constructor_params,
)


def detect_adapter(
    class_node: ast.ClassDef,
    file_path: str,
    all_classes: Dict[str, Dict],
) -> List[PatternMatch]:
    """Detect Adapter pattern."""
    patterns = []

    if "Adapter" in class_node.name:
        params = get_constructor_params(class_node)
        if params:
            patterns.append(PatternMatch(
                pattern_type=PatternType.ADAPTER,
                class_name=class_node.name,
                file_path=file_path,
                line_number=class_node.lineno,
                confidence=0.8,
                participants=params,
                details=f"Adapter wrapping: {', '.join(params)}",
            ))

    bases = get_class_bases(class_node)
    if bases:
        methods = get_class_methods(class_node)
        for method in methods:
            if method.name == "__init__":
                continue
            for node in ast.walk(method):
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Attribute):
                        if isinstance(node.func.value, ast.Attribute):
                            if isinstance(node.func.value.value, ast.Name):
                                if node.func.value.value.id == "self":
                                    patterns.append(PatternMatch(
                                        pattern_type=PatternType.ADAPTER,
                                        class_name=class_node.name,
                                        file_path=file_path,
                                        line_number=class_node.lineno,
                                        confidence=0.6,
                                        details="Delegates to wrapped object",
                                    ))
                                    break

    return patterns


def detect_decorator(
    class_node: ast.ClassDef,
    file_path: str,
    all_classes: Dict[str, Dict],
) -> List[PatternMatch]:
    """Detect Decorator pattern (not Python decorators)."""
    patterns: List[PatternMatch] = []

    bases = get_class_bases(class_node)
    if not bases:
        return patterns

    params = get_constructor_params(class_node)
    for base in bases:
        base_lower = base.lower()
        for param in params:
            if (
                base_lower in param.lower()
                or "component" in param.lower()
                or "wrapped" in param.lower()
            ):
                patterns.append(PatternMatch(
                    pattern_type=PatternType.DECORATOR,
                    class_name=class_node.name,
                    file_path=file_path,
                    line_number=class_node.lineno,
                    confidence=0.75,
                    participants=[base, param],
                    details=f"Decorates {base} via {param}",
                ))
                break

    return patterns


def detect_facade(class_node: ast.ClassDef, file_path: str) -> List[PatternMatch]:
    """Detect Facade pattern."""
    patterns = []

    if "Facade" in class_node.name or "Service" in class_node.name:
        params = get_constructor_params(class_node)
        if len(params) >= 3:
            patterns.append(PatternMatch(
                pattern_type=PatternType.FACADE,
                class_name=class_node.name,
                file_path=file_path,
                line_number=class_node.lineno,
                confidence=0.7,
                participants=params,
                details=f"Facade coordinating {len(params)} subsystems",
            ))

    return patterns
