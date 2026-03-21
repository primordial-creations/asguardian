"""
Heimdall Security Access Decorator Utilities

Helper functions for detecting and analyzing decorators in code.
"""

import ast
import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


class RouteHandler:
    """Represents a detected route handler."""

    def __init__(
        self,
        function_name: str,
        line_number: int,
        decorators: List[str],
        endpoint: Optional[str] = None,
        http_method: Optional[str] = None,
    ):
        self.function_name = function_name
        self.line_number = line_number
        self.decorators = decorators
        self.endpoint = endpoint
        self.http_method = http_method

    @property
    def location(self) -> str:
        """Get location string."""
        return f"line {self.line_number}"


def extract_decorators(node: ast.FunctionDef | ast.AsyncFunctionDef) -> List[str]:
    """
    Extract decorator names from an AST function definition.

    Args:
        node: AST FunctionDef node

    Returns:
        List of decorator names as strings
    """
    decorators = []
    for decorator in node.decorator_list:
        if isinstance(decorator, ast.Name):
            decorators.append(decorator.id)
        elif isinstance(decorator, ast.Call):
            if isinstance(decorator.func, ast.Name):
                decorators.append(decorator.func.id)
            elif isinstance(decorator.func, ast.Attribute):
                decorators.append(f"{_get_attribute_chain(decorator.func)}")
        elif isinstance(decorator, ast.Attribute):
            decorators.append(_get_attribute_chain(decorator))
    return decorators


def _get_attribute_chain(node: ast.Attribute) -> str:
    """
    Get the full attribute chain from an Attribute node.

    Args:
        node: AST Attribute node

    Returns:
        Full attribute chain as a string (e.g., "app.route")
    """
    parts = []
    current: ast.expr = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
    return ".".join(reversed(parts))


def has_auth_decorator(decorators: List[str], auth_decorator_names: List[str]) -> bool:
    """
    Check if any decorator indicates authentication.

    Args:
        decorators: List of decorator names
        auth_decorator_names: List of known auth decorator names

    Returns:
        True if an auth decorator is present
    """
    for decorator in decorators:
        for auth_name in auth_decorator_names:
            if auth_name.lower() in decorator.lower():
                return True
    return False


def find_route_handlers(
    content: str,
    route_decorators: List[str],
) -> List[RouteHandler]:
    """
    Find all route handlers in Python source code.

    Args:
        content: Python source code content
        route_decorators: List of decorator names that indicate routes

    Returns:
        List of RouteHandler objects
    """
    handlers: List[RouteHandler] = []

    try:
        tree = ast.parse(content)
    except SyntaxError:
        return handlers

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            decorators = extract_decorators(node)
            route_decorator = _find_route_decorator(decorators, route_decorators)

            if route_decorator:
                endpoint = _extract_endpoint(node, route_decorator)
                http_method = _extract_http_method(decorators, route_decorator)

                handler = RouteHandler(
                    function_name=node.name,
                    line_number=node.lineno,
                    decorators=decorators,
                    endpoint=endpoint,
                    http_method=http_method,
                )
                handlers.append(handler)

    return handlers


def _find_route_decorator(decorators: List[str], route_decorators: List[str]) -> Optional[str]:
    """
    Find the route decorator from a list of decorators.

    Args:
        decorators: List of decorator names
        route_decorators: Known route decorator patterns

    Returns:
        The route decorator name if found
    """
    for decorator in decorators:
        for route_dec in route_decorators:
            if route_dec.lower() in decorator.lower():
                return decorator
    return None


def _extract_endpoint(node: ast.FunctionDef | ast.AsyncFunctionDef, route_decorator: str) -> Optional[str]:
    """
    Extract the endpoint path from a route decorator.

    Args:
        node: AST FunctionDef node
        route_decorator: The route decorator name

    Returns:
        Endpoint path if found
    """
    for decorator in node.decorator_list:
        if isinstance(decorator, ast.Call):
            if decorator.args:
                first_arg = decorator.args[0]
                if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
                    return first_arg.value
    return None


def _extract_http_method(decorators: List[str], route_decorator: str) -> Optional[str]:
    """
    Extract the HTTP method from decorators.

    Args:
        decorators: List of decorator names
        route_decorator: The route decorator name

    Returns:
        HTTP method if identifiable
    """
    route_lower = route_decorator.lower()
    if "get" in route_lower:
        return "GET"
    elif "post" in route_lower:
        return "POST"
    elif "put" in route_lower:
        return "PUT"
    elif "delete" in route_lower:
        return "DELETE"
    elif "patch" in route_lower:
        return "PATCH"
    return None


def find_role_checks(content: str) -> List[Tuple[int, str]]:
    """
    Find role checking patterns in code.

    Args:
        content: Source code content

    Returns:
        List of (line_number, pattern_matched) tuples
    """
    patterns = [
        (r'if\s+.*role\s*[=!]=', "role comparison"),
        (r'if\s+.*is_admin', "admin check"),
        (r'if\s+.*has_role\s*\(', "has_role check"),
        (r'if\s+.*has_permission\s*\(', "has_permission check"),
        (r'require_role\s*\(', "require_role decorator"),
        (r'check_permission\s*\(', "check_permission call"),
    ]

    matches = []
    lines = content.split("\n")

    for i, line in enumerate(lines, start=1):
        for pattern, name in patterns:
            if re.search(pattern, line, re.IGNORECASE):
                matches.append((i, name))

    return matches


def find_ownership_checks(content: str) -> List[Tuple[int, str]]:
    """
    Find resource ownership checking patterns in code.

    Args:
        content: Source code content

    Returns:
        List of (line_number, pattern_matched) tuples
    """
    patterns = [
        (r'if\s+.*\.user_id\s*[=!]=', "user_id comparison"),
        (r'if\s+.*\.owner\s*[=!]=', "owner comparison"),
        (r'if\s+.*\.created_by\s*[=!]=', "created_by comparison"),
        (r'\.filter\s*\(\s*.*user', "user filter"),
        (r'get_object_or_404.*user', "object user check"),
    ]

    matches = []
    lines = content.split("\n")

    for i, line in enumerate(lines, start=1):
        for pattern, name in patterns:
            if re.search(pattern, line, re.IGNORECASE):
                matches.append((i, name))

    return matches
