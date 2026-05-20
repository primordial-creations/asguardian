"""
Heimdall Race Condition Visitor - AST Helper Functions

Standalone helper functions used by RaceConditionVisitor for AST node
inspection and lock-enclosure detection.
"""

import ast
from typing import List, Optional, Set, Tuple


LOCK_CONTEXT_NAMES: Set[str] = {
    "Lock", "RLock", "Semaphore", "BoundedSemaphore",
    "Condition", "Event", "lock", "_lock", "mutex",
}


def is_thread_call(call_node: ast.Call) -> bool:
    """Check if a Call node is a threading.Thread() or Thread() instantiation."""
    func = call_node.func
    return (
        (isinstance(func, ast.Name) and func.id == "Thread")
        or (isinstance(func, ast.Attribute) and func.attr == "Thread")
    )


def get_call_name(call_node: ast.Call) -> Optional[str]:
    """Get the name of the function being called (e.g. 'start', 'join')."""
    if isinstance(call_node.func, ast.Attribute):
        return call_node.func.attr
    return None


def get_call_receiver_name(call_node: ast.Call) -> Optional[str]:
    """Get the variable name the method is called on (e.g. 't' in t.start())."""
    if isinstance(call_node.func, ast.Attribute):
        if isinstance(call_node.func.value, ast.Name):
            return call_node.func.value.id
    return None


def is_self_attr_assignment(node: ast.stmt) -> Optional[str]:
    """
    Check if a statement is a self.attr assignment.
    Returns the attribute name if it is, None otherwise.
    """
    if isinstance(node, ast.Assign):
        for target in node.targets:
            if (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == "self"
            ):
                return target.attr
    elif isinstance(node, ast.AnnAssign):
        if (
            isinstance(node.target, ast.Attribute)
            and isinstance(node.target.value, ast.Name)
            and node.target.value.id == "self"
        ):
            return node.target.attr
    return None


def is_self_attr_to_var(node: ast.stmt) -> Optional[Tuple[str, str]]:
    """
    Check if statement is 'self.x = var_name'.
    Returns (attr_name, var_name) if so, None otherwise.
    """
    if isinstance(node, ast.Assign):
        for target in node.targets:
            if (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == "self"
            ):
                attr_name = target.attr
                if isinstance(node.value, ast.Name):
                    return (attr_name, node.value.id)
    return None


def contains_node(parent: ast.AST, target: ast.AST) -> bool:
    """Check if target node is contained anywhere within parent node."""
    for node in ast.walk(parent):
        if node is target:
            return True
    return False


def has_lock_enclosure(if_node: ast.If, parent_stmts: List[ast.stmt]) -> bool:
    """
    Check if an if statement is enclosed in a with-lock block.
    Examines the parent statement list for a With block that contains this if.
    """
    for stmt in parent_stmts:
        if not isinstance(stmt, ast.With):
            continue
        for item in stmt.items:
            ctx_expr = item.context_expr
            if isinstance(ctx_expr, ast.Name) and ctx_expr.id in LOCK_CONTEXT_NAMES:
                if contains_node(stmt, if_node):
                    return True
            elif isinstance(ctx_expr, ast.Attribute) and ctx_expr.attr in LOCK_CONTEXT_NAMES:
                if contains_node(stmt, if_node):
                    return True
            elif (
                isinstance(ctx_expr, ast.Attribute)
                and isinstance(ctx_expr.value, ast.Name)
                and ctx_expr.value.id == "self"
            ):
                if contains_node(stmt, if_node):
                    return True
    return False


def self_attr_accessed_in_body(body: List[ast.stmt], attr_name: str) -> bool:
    """Check if self.attr_name is accessed (read or called) within a list of statements."""
    for stmt in body:
        for node in ast.walk(stmt):
            if (
                isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id == "self"
                and node.attr == attr_name
            ):
                return True
    return False
