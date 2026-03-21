"""
Heimdall Cohesion Analyzer Helpers

LCOM calculation functions and cohesion split suggestions.
"""

from typing import Dict, List, Set, Tuple

from Asgard.Heimdall.OOP.models.oop_models import ClassCohesionMetrics


def calculate_lcom_ck(method_attr_usage: Dict[str, Set[str]]) -> float:
    """
    Calculate LCOM using Chidamber-Kemerer method.

    LCOM = P / total_pairs where P = pairs not sharing attributes.
    Normalized to 0-1 range.
    """
    methods = list(method_attr_usage.keys())
    n = len(methods)

    if n < 2:
        return 0.0

    p = 0
    q = 0

    for i in range(n):
        for j in range(i + 1, n):
            attrs_i = method_attr_usage[methods[i]]
            attrs_j = method_attr_usage[methods[j]]

            if attrs_i & attrs_j:
                q += 1
            else:
                p += 1

    total_pairs = p + q
    if total_pairs == 0:
        return 0.0

    return p / total_pairs


def calculate_lcom_hs(method_attr_usage: Dict[str, Set[str]], num_attributes: int) -> float:
    """
    Calculate LCOM using Henderson-Sellers method.

    LCOM4 = (m - sum(mA)/a) / (m - 1)
    """
    m = len(method_attr_usage)
    a = num_attributes

    if m <= 1 or a == 0:
        return 0.0

    attr_access_count: Dict[str, int] = {}
    for method_name, accessed in method_attr_usage.items():
        for attr in accessed:
            attr_access_count[attr] = attr_access_count.get(attr, 0) + 1

    sum_ma = sum(attr_access_count.values())
    lcom4 = (m - sum_ma / a) / (m - 1)
    return max(0.0, min(1.0, lcom4))


def suggest_splits(cls_metrics: ClassCohesionMetrics) -> List[Tuple[str, Set[str]]]:
    """
    Suggest how to split a low-cohesion class.

    Groups methods by shared attribute access to suggest potential class splits.
    """
    if cls_metrics.lcom < 0.5:
        return []

    methods = list(cls_metrics.method_attribute_usage.keys())
    method_groups: List[Set[str]] = []

    for method in methods:
        attrs = cls_metrics.method_attribute_usage[method]
        found_group = False
        for group in method_groups:
            for existing_method in group:
                existing_attrs = cls_metrics.method_attribute_usage[existing_method]
                if attrs & existing_attrs:
                    group.add(method)
                    found_group = True
                    break
            if found_group:
                break

        if not found_group:
            method_groups.append({method})

    merged = True
    while merged:
        merged = False
        for i, group_i in enumerate(method_groups):
            for j, group_j in enumerate(method_groups[i + 1:], i + 1):
                attrs_i: Set[str] = set()
                for m in group_i:
                    attrs_i.update(cls_metrics.method_attribute_usage[m])

                attrs_j: Set[str] = set()
                for m in group_j:
                    attrs_j.update(cls_metrics.method_attribute_usage[m])

                if attrs_i & attrs_j:
                    method_groups[i] = group_i | group_j
                    method_groups.pop(j)
                    merged = True
                    break
            if merged:
                break

    suggestions = []
    for idx, group in enumerate(method_groups):
        if len(group) >= 2:
            name = f"{cls_metrics.class_name}Part{idx + 1}"
            suggestions.append((name, group))

    return suggestions
