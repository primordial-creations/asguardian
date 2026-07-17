"""ISP evaluator — Stubbed Implementer + Fat Interface.

Per ``_Docs/Planning/Heimdall/02_SOLID_Detection.md``:
- Stubbed Implementer: a class with ``implements`` where >25% of methods are
  empty stubs / throw NotImplemented (confidence HIGH, ~85% precision).
- Fat Interface: an interface with >12 methods AND distinct param-type
  strings >5 (confidence LOW, "Architectural Smell").
"""
from typing import List

from Asgard.Bragi.Architecture.cir.models import ClassInfo, FileInfo
from Asgard.Bragi.Architecture.models.architecture_models import (
    Confidence,
    SOLIDPrinciple,
    SOLIDViolation,
    ViolationSeverity,
)

STUB_RATIO_THRESHOLD = 0.25
FAT_INTERFACE_METHOD_THRESHOLD = 12
FAT_INTERFACE_PARAM_TYPE_THRESHOLD = 5


def evaluate(file_info: FileInfo, cls: ClassInfo) -> List[SOLIDViolation]:
    violations: List[SOLIDViolation] = []

    if cls.is_interface or cls.is_abstract:
        violations.extend(_fat_interface(cls))
    elif cls.implements and cls.methods:
        # Only concrete classes can "stub" an implementation; an
        # interface/abstract class's own abstract methods are not stubs of
        # something else, they're the contract being defined.
        violations.extend(_stubbed_implementer(cls))

    return violations


def _stubbed_implementer(cls: ClassInfo) -> List[SOLIDViolation]:
    total = len(cls.methods)
    if total == 0:
        return []
    stub_count = sum(1 for m in cls.methods if m.is_empty or m.throws_unimplemented)
    ratio = stub_count / total
    if ratio > STUB_RATIO_THRESHOLD:
        return [SOLIDViolation(
            principle=SOLIDPrinciple.ISP,
            class_name=cls.name,
            file_path=cls.filepath,
            line_number=cls.start_line,
            message=(
                f"Class '{cls.name}' implements {', '.join(sorted(cls.implements)) or '<interface>'} "
                f"but stubs {stub_count}/{total} methods ({ratio:.0%}). "
                "Its interface is too wide for this implementer."
            ),
            severity=ViolationSeverity.MODERATE,
            suggestion="Split the interface so implementers only depend on methods they use.",
            confidence=Confidence.HIGH,
            evidence=f"stub_ratio={ratio:.2f} ({stub_count}/{total})",
        )]
    return []


def _fat_interface(cls: ClassInfo) -> List[SOLIDViolation]:
    method_count = cls.method_count
    if method_count <= FAT_INTERFACE_METHOD_THRESHOLD:
        return []

    param_types: set = set()
    for m in cls.methods:
        param_types |= m.param_types

    distinct_param_types = len(param_types) if param_types else 0
    if distinct_param_types > FAT_INTERFACE_PARAM_TYPE_THRESHOLD or not param_types:
        # When param-type extraction is unavailable (most CIR handlers today
        # leave param_types empty) fall back to method-count alone at LOW
        # confidence — an honest "Architectural Smell", never silence.
        return [SOLIDViolation(
            principle=SOLIDPrinciple.ISP,
            class_name=cls.name,
            file_path=cls.filepath,
            line_number=cls.start_line,
            message=(
                f"Interface '{cls.name}' declares {method_count} methods "
                f"(threshold {FAT_INTERFACE_METHOD_THRESHOLD}). Consider splitting "
                "into smaller, role-specific interfaces."
            ),
            severity=ViolationSeverity.LOW,
            suggestion="Apply Interface Segregation: break into focused interfaces.",
            confidence=Confidence.LOW,
            evidence=f"method_count={method_count} distinct_param_types={distinct_param_types}",
        )]
    return []
