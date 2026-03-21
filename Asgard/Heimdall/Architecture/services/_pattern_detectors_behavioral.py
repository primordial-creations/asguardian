"""
Heimdall Pattern Detector - Behavioral Pattern Detection

Strategy, Observer, Command detectors.
"""

import ast
from typing import Dict, List

from Asgard.Heimdall.Architecture.models.architecture_models import (
    PatternMatch,
    PatternType,
)
from Asgard.Heimdall.Architecture.utilities.ast_utils import (
    get_abstract_methods,
    get_class_bases,
    get_class_methods,
    is_abstract_class,
)


def detect_strategy(
    class_node: ast.ClassDef,
    file_path: str,
    all_classes: Dict[str, Dict],
) -> List[PatternMatch]:
    """Detect Strategy pattern."""
    patterns = []

    if is_abstract_class(class_node):
        abstract_methods = get_abstract_methods(class_node)
        if len(abstract_methods) == 1:
            implementations = []
            for name, info in all_classes.items():
                node = info["node"]
                bases = get_class_bases(node)
                if class_node.name in bases:
                    implementations.append(name)
            if implementations:
                patterns.append(PatternMatch(
                    pattern_type=PatternType.STRATEGY,
                    class_name=class_node.name,
                    file_path=file_path,
                    line_number=class_node.lineno,
                    confidence=0.85,
                    participants=implementations,
                    details=f"Strategy interface with {len(implementations)} implementations",
                ))

    if "Strategy" in class_node.name:
        patterns.append(PatternMatch(
            pattern_type=PatternType.STRATEGY,
            class_name=class_node.name,
            file_path=file_path,
            line_number=class_node.lineno,
            confidence=0.7,
            details="Named as strategy",
        ))

    return patterns


def detect_observer(class_node: ast.ClassDef, file_path: str) -> List[PatternMatch]:
    """Detect Observer pattern."""
    patterns = []

    methods = get_class_methods(class_node)
    method_names = {m.name for m in methods}

    has_subscribe = any(
        name in method_names
        for name in ["subscribe", "attach", "add_observer", "register"]
    )
    has_unsubscribe = any(
        name in method_names
        for name in ["unsubscribe", "detach", "remove_observer", "unregister"]
    )
    has_notify = any(
        name in method_names
        for name in ["notify", "notify_observers", "emit", "dispatch"]
    )

    if has_subscribe and has_unsubscribe and has_notify:
        patterns.append(PatternMatch(
            pattern_type=PatternType.OBSERVER,
            class_name=class_node.name,
            file_path=file_path,
            line_number=class_node.lineno,
            confidence=0.9,
            details="Subject with subscribe/unsubscribe/notify methods",
        ))

    has_update = "update" in method_names or "on_notify" in method_names
    if has_update and ("Observer" in class_node.name or "Listener" in class_node.name):
        patterns.append(PatternMatch(
            pattern_type=PatternType.OBSERVER,
            class_name=class_node.name,
            file_path=file_path,
            line_number=class_node.lineno,
            confidence=0.8,
            details="Observer with update method",
        ))

    return patterns


def detect_command(
    class_node: ast.ClassDef,
    file_path: str,
    all_classes: Dict[str, Dict],
) -> List[PatternMatch]:
    """Detect Command pattern."""
    patterns = []

    methods = get_class_methods(class_node)
    method_names = {m.name for m in methods}

    has_execute = "execute" in method_names or "__call__" in method_names
    has_undo = "undo" in method_names or "rollback" in method_names

    if has_execute:
        confidence = 0.85 if has_undo else 0.65
        if is_abstract_class(class_node):
            implementations = []
            for name, info in all_classes.items():
                node = info["node"]
                bases = get_class_bases(node)
                if class_node.name in bases:
                    implementations.append(name)
            if implementations:
                patterns.append(PatternMatch(
                    pattern_type=PatternType.COMMAND,
                    class_name=class_node.name,
                    file_path=file_path,
                    line_number=class_node.lineno,
                    confidence=confidence,
                    participants=implementations,
                    details=f"Command interface with {len(implementations)} commands",
                ))
        elif "Command" in class_node.name:
            patterns.append(PatternMatch(
                pattern_type=PatternType.COMMAND,
                class_name=class_node.name,
                file_path=file_path,
                line_number=class_node.lineno,
                confidence=confidence,
                details="Concrete command with execute method",
            ))

    return patterns
