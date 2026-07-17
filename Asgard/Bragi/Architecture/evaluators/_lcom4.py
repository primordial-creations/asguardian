"""LCOM4 — connected components over the method/field graph.

Shared by the SRP evaluator and ``Bragi/OOP/services/cir_metrics.py`` so the
two report identical numbers for the same CIR.  See
``_Docs/Planning/Heimdall/05_Cohesion_Coupling.md``.
"""
from typing import Dict, List, Set

from Asgard.Bragi.Architecture.cir.models import ClassInfo


def lcom4_components(cls: ClassInfo) -> List[Set[str]]:
    """Return the connected components (as sets of method names) of *cls*.

    Vertices are non-constructor methods; an edge connects two methods when
    they access a common field or one calls the other.  Methods named
    ``__init__``/``<init>``/``constructor`` are excluded (constructor-only
    coupling is not a cohesion signal).
    """
    ctor_names = {"__init__", "<init>", "constructor"}
    methods = [m for m in cls.methods if m.name not in ctor_names]
    if len(methods) < 2:
        return [{m.name for m in methods}] if methods else []

    adjacency: Dict[str, Set[str]] = {m.name: set() for m in methods}
    for i, m1 in enumerate(methods):
        for m2 in methods[i + 1:]:
            shared_fields = m1.field_accesses & m2.field_accesses
            calls_each_other = (m2.name in m1.method_calls) or (m1.name in m2.method_calls)
            if shared_fields or calls_each_other:
                adjacency[m1.name].add(m2.name)
                adjacency[m2.name].add(m1.name)

    visited: Set[str] = set()
    components: List[Set[str]] = []
    for m in methods:
        if m.name in visited:
            continue
        component: Set[str] = set()
        stack = [m.name]
        while stack:
            cur = stack.pop()
            if cur in visited:
                continue
            visited.add(cur)
            component.add(cur)
            stack.extend(adjacency[cur] - visited)
        components.append(component)

    return components


def lcom4(cls: ClassInfo) -> int:
    """Return the LCOM4 value (number of connected components) for *cls*."""
    return len(lcom4_components(cls))
