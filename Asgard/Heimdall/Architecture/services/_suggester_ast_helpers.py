"""
Heimdall Pattern Suggester - AST Analysis Helper Functions

Standalone functions for AST-based class analysis used by the pattern suggester.
"""

import ast
from typing import Dict, List, Optional, Set


_PATTERN_NAME_FRAGMENTS = frozenset({
    "Factory", "Builder", "Singleton", "Observer", "Strategy", "Command",
    "Adapter", "Facade", "Decorator", "Visitor", "Mediator", "Template",
    "Proxy", "Repository", "Handler", "Manager",
})

_RESPONSIBILITY_GROUPS: Dict[frozenset, str] = {
    frozenset({"validate", "check", "verify", "assert_"}): "validation",
    frozenset({"create", "build", "make", "generate", "produce"}): "creation",
    frozenset({"parse", "process", "transform", "convert", "encode", "decode"}): "processing",
    frozenset({"save", "load", "read", "write", "store", "persist", "fetch", "delete"}): "persistence",
    frozenset({"send", "receive", "notify", "dispatch", "emit", "publish", "broadcast"}): "communication",
    frozenset({"render", "display", "show", "format", "print", "draw"}): "presentation",
    frozenset({"calculate", "compute", "analyze", "score", "measure", "estimate"}): "computation",
}

_NOTIFICATION_PREFIXES = frozenset({
    "on_", "handle_", "notify_", "dispatch_", "emit_", "trigger_", "fire_",
})


def snippet_lineno(method: ast.FunctionDef) -> int:
    return method.lineno


def max_if_chain(method: ast.FunctionDef) -> int:
    """Return the length of the longest if/elif chain in the method."""
    max_chain = 0
    for node in ast.walk(method):
        if isinstance(node, ast.If):
            length = 1
            current = node
            while (
                current.orelse
                and len(current.orelse) == 1
                and isinstance(current.orelse[0], ast.If)
            ):
                length += 1
                current = current.orelse[0]
            max_chain = max(max_chain, length)
    return max_chain


def count_isinstance(method: ast.FunctionDef) -> int:
    """Count isinstance() calls inside a method."""
    return sum(
        1
        for node in ast.walk(method)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "isinstance"
    )


def concrete_instantiations_in_init(
    init_method: ast.FunctionDef,
    known_class_names: Set[str],
) -> List[str]:
    """Return names of classes directly instantiated inside __init__."""
    seen: List[str] = []
    for node in ast.walk(init_method):
        if isinstance(node, ast.Call):
            name: Optional[str] = None
            if isinstance(node.func, ast.Name) and node.func.id[0].isupper():
                name = node.func.id
            elif isinstance(node.func, ast.Attribute) and node.func.attr[0].isupper():
                name = node.func.attr
            if name and name not in ("True", "False", "None", "super") and name in known_class_names:
                seen.append(name)
    return seen


def count_optional_params(init_method: ast.FunctionDef) -> int:
    """Return the number of parameters with default values in __init__."""
    return len(init_method.args.defaults) + len(
        [d for d in init_method.args.kw_defaults if d is not None]
    )


def has_scattered_notifications(class_node: ast.ClassDef) -> int:
    """Count callback/notification calls scattered across the class."""
    count = 0
    for node in ast.walk(class_node):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if any(node.func.attr.startswith(p) for p in _NOTIFICATION_PREFIXES):
                count += 1
    return count


def get_responsibility_groups(methods: List[ast.FunctionDef]) -> Set[str]:
    """Return the set of distinct responsibility groups inferred from method names."""
    groups: Set[str] = set()
    for method in methods:
        if method.name.startswith("_"):
            continue
        first_word = method.name.split("_")[0].lower()
        for word_set, group_name in _RESPONSIBILITY_GROUPS.items():
            if first_word in word_set:
                groups.add(group_name)
                break
    return groups
