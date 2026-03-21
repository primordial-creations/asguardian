"""
Heimdall Inheritance Analyzer Helpers

DIT (Depth of Inheritance Tree) calculation helpers.
"""

from typing import Dict, List, Optional, Set


def calculate_dit(
    class_name: str,
    all_classes: Dict[str, Dict],
    dit_cache: Dict[str, int],
    visited: Optional[Set[str]] = None,
) -> int:
    """Calculate Depth of Inheritance Tree recursively."""
    if visited is None:
        visited = set()

    if class_name in dit_cache:
        return dit_cache[class_name]

    if class_name in visited:
        return 0

    visited.add(class_name)

    if class_name not in all_classes:
        return 0

    bases = all_classes[class_name]["bases"]
    if not bases:
        dit_cache[class_name] = 0
        return 0

    max_parent_dit = 0
    for base in bases:
        base_name = base.split(".")[-1]
        if base_name in all_classes:
            parent_dit = calculate_dit(base_name, all_classes, dit_cache, visited.copy())
            max_parent_dit = max(max_parent_dit, parent_dit)

    dit = max_parent_dit + 1
    dit_cache[class_name] = dit
    return dit


def collect_ancestors(
    class_name: str,
    all_classes: Dict[str, Dict],
    collected: Optional[Set[str]] = None,
) -> List[str]:
    """Collect all ancestor class names recursively."""
    if collected is None:
        collected = set()

    ancestors: List[str] = []
    if class_name not in all_classes:
        return ancestors

    for base in all_classes[class_name]["bases"]:
        base_name = base.split(".")[-1]
        if base_name not in collected:
            collected.add(base_name)
            ancestors.append(base_name)
            ancestors.extend(collect_ancestors(base_name, all_classes, collected))

    return ancestors


def calculate_dit_in_file(
    class_name: str,
    class_list: list,
    class_names: Set[str],
    dit_cache: Dict[str, int],
    visited: Optional[Set[str]] = None,
) -> int:
    """Calculate DIT for classes within a single file."""
    if visited is None:
        visited = set()

    if class_name in dit_cache:
        return dit_cache[class_name]

    if class_name in visited:
        return 0

    visited.add(class_name)

    cls_info = next((c for c in class_list if c.name == class_name), None)
    if not cls_info:
        return 0

    if not cls_info.base_classes:
        dit_cache[class_name] = 0
        return 0

    max_parent_dit = 0
    for base in cls_info.base_classes:
        base_name = base.split(".")[-1]
        if base_name in class_names:
            parent_dit = calculate_dit_in_file(
                base_name, class_list, class_names, dit_cache, visited.copy()
            )
            max_parent_dit = max(max_parent_dit, parent_dit)

    dit = max_parent_dit + 1
    dit_cache[class_name] = dit
    return dit
