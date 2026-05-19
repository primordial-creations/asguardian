"""Tree-sitter query helpers.

All return values contain only plain Python primitives — no Node objects leak
out of this module.  This satisfies the memory rule described in
``_parser_pool``.
"""
from typing import Any, Dict, List, Optional

from Asgard.Heimdall.treesitter._language_loader import get_language_object


def node_text(node, source_bytes: bytes) -> str:
    """Safely extract the UTF-8 text covered by *node*.

    Returns an empty string when *node* is ``None`` or on any error.
    """
    if node is None:
        return ""
    try:
        return source_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="replace")
    except Exception:
        return ""


def node_children_of_type(node, type_name: str) -> list:
    """Return immediate children of *node* whose ``type`` equals *type_name*."""
    if node is None:
        return []
    try:
        return [child for child in node.children if child.type == type_name]
    except Exception:
        return []


def _extract_captures(captures, source_bytes: bytes) -> List[Dict[str, Any]]:
    """Convert a captures dict/list into a list of primitive-only dicts."""
    results: List[Dict[str, Any]] = []
    # tree-sitter ≥ 0.21 returns {capture_name: [Node, …]}
    if isinstance(captures, dict):
        entry: Dict[str, Any] = {}
        for capture_name, nodes in captures.items():
            node_list = nodes if isinstance(nodes, list) else [nodes]
            for node in node_list:
                entry[capture_name] = {
                    "text": node_text(node, source_bytes),
                    "line": node.start_point[0],
                    "col": node.start_point[1],
                }
        if entry:
            results.append(entry)
    elif isinstance(captures, list):
        # Older API: list of (node, capture_name) tuples
        entry = {}
        for item in captures:
            if isinstance(item, tuple) and len(item) == 2:
                node, capture_name = item
                entry[capture_name] = {
                    "text": node_text(node, source_bytes),
                    "line": node.start_point[0],
                    "col": node.start_point[1],
                }
        if entry:
            results.append(entry)
    return results


def run_query(root_node, query_str: str, source_bytes: bytes, language: str) -> List[Dict[str, Any]]:
    """Run a Tree-sitter S-expression query and return match dicts.

    Each dict maps capture name to ``{"text": str, "line": int, "col": int}``.
    Returns ``[]`` when tree-sitter is unavailable, the language binding is
    missing, *root_node* is ``None``, or the query string is invalid.

    All values are extracted as primitives — no Node objects appear in the
    return value.
    """
    if root_node is None:
        return []

    lang_obj = get_language_object(language)
    if lang_obj is None:
        return []

    try:
        from tree_sitter import Query  # noqa: PLC0415
        query = Query(lang_obj, query_str)
        captures = query.captures(root_node)
        return _extract_captures(captures, source_bytes)
    except Exception:
        return []


def run_query_all(root_node, query_str: str, source_bytes: bytes, language: str) -> List[Dict[str, Any]]:
    """Same as :func:`run_query` but returns every capture, not just the first match per pattern.

    Internally uses ``matches()`` when available, falling back to ``captures()``.
    Returns ``[]`` on any error or when tree-sitter is unavailable.
    """
    if root_node is None:
        return []

    lang_obj = get_language_object(language)
    if lang_obj is None:
        return []

    try:
        from tree_sitter import Query  # noqa: PLC0415
        query = Query(lang_obj, query_str)

        results: List[Dict[str, Any]] = []
        try:
            matches = query.matches(root_node)
            for _pattern_index, captures_dict in matches:
                extracted = _extract_captures(captures_dict, source_bytes)
                results.extend(extracted)
        except AttributeError:
            # Fallback for older tree-sitter versions without .matches()
            captures = query.captures(root_node)
            results = _extract_captures(captures, source_bytes)

        return results
    except Exception:
        return []
