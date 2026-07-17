"""Common Intermediate Representation (CIR) data model.

Language-agnostic view of a class/interface produced from tree-sitter CSTs
via :mod:`Asgard.Bragi.Architecture.cir.builder`.  Pure-Python SOLID
evaluators (``Asgard/Bragi/Architecture/evaluators/*``) and cohesion/coupling
metrics (``Asgard/Bragi/OOP/services/cir_metrics.py``) consume this
representation instead of walking tree-sitter nodes directly.

See ``_Docs/Planning/Heimdall/02_SOLID_Detection.md`` §"CIR data model".
"""
from dataclasses import dataclass, field
from typing import List, Set


@dataclass(slots=True)
class MethodInfo:
    """A single method/function declared inside a class or interface."""

    name: str
    start_line: int
    end_line: int
    is_override: bool = False
    is_empty: bool = False
    throws_unimplemented: bool = False
    is_abstract: bool = False
    is_public: bool = True
    type_switches: int = 0
    param_types: Set[str] = field(default_factory=set)
    param_count: int = 0
    # Every identifier referenced in the method body (field names, called
    # method names, local variable names — undifferentiated).  Evaluators
    # narrow this down against ``ClassInfo.fields`` / method names as needed.
    all_identifiers: Set[str] = field(default_factory=set)
    # Receiver-qualified field accesses only (self.x / this.x / recv.x).
    field_accesses: Set[str] = field(default_factory=set)
    # Names of sibling methods called from within this method's body.
    method_calls: Set[str] = field(default_factory=set)
    # `ClassName(...)` / `new ClassName(...)` instantiations inside the body.
    instantiations: Set[str] = field(default_factory=set)


@dataclass(slots=True)
class ClassInfo:
    """A class/interface/struct extracted from a single file."""

    name: str
    filepath: str
    start_line: int
    end_line: int
    language: str = ""
    is_interface: bool = False
    is_abstract: bool = False
    fields: Set[str] = field(default_factory=set)
    methods: List[MethodInfo] = field(default_factory=list)
    implements: Set[str] = field(default_factory=set)
    extends: Set[str] = field(default_factory=set)
    import_roots: Set[str] = field(default_factory=set)

    @property
    def method_count(self) -> int:
        return len(self.methods)

    def method_names(self) -> Set[str]:
        return {m.name for m in self.methods}


@dataclass(slots=True)
class FileInfo:
    """All classes/interfaces extracted from one source file."""

    filepath: str
    language: str
    classes: List[ClassInfo] = field(default_factory=list)
    imports: Set[str] = field(default_factory=set)
