"""OCP evaluator — Type-Dispatch Cascade.

Flags conditional chains whose branch condition tests the runtime type of a
value (``instanceof``/``isinstance``/``typeof``/``is``) rather than
dispatching polymorphically. Detected at extraction time via
``MethodInfo.type_switches`` (populated as an approximation by counting
``instantiations``/``all_identifiers`` hits against a type-check name set is
not reliable across languages without raw text, so this evaluator instead
inspects ``all_identifiers`` for the canonical type-check call names that
the CIR builder always resolves as ordinary calls/identifiers).
"""
from typing import List

from Asgard.Bragi.Architecture.cir.models import ClassInfo, FileInfo
from Asgard.Bragi.Architecture.models.architecture_models import (
    Confidence,
    SOLIDPrinciple,
    SOLIDViolation,
    ViolationSeverity,
)

_TYPE_CHECK_NAMES = {"isinstance", "type", "instanceof", "typeof"}
MIN_BRANCHES = 3


def evaluate(file_info: FileInfo, cls: ClassInfo) -> List[SOLIDViolation]:
    violations: List[SOLIDViolation] = []
    for method in cls.methods:
        hits = method.all_identifiers & _TYPE_CHECK_NAMES
        if hits and method.type_switches >= MIN_BRANCHES:
            violations.append(_violation(cls, method, method.type_switches))
        elif hits and method.type_switches == 0:
            # Extraction couldn't count branches; still report at LOW
            # confidence since the type-check call itself is unambiguous.
            violations.append(_violation(cls, method, 1, confidence=Confidence.LOW))
    return violations


def _violation(cls: ClassInfo, method, branch_count: int, confidence: Confidence = Confidence.HIGH) -> SOLIDViolation:
    return SOLIDViolation(
        principle=SOLIDPrinciple.OCP,
        class_name=cls.name,
        file_path=cls.filepath,
        line_number=method.start_line,
        message=(
            f"Method '{method.name}' dispatches on runtime type "
            f"({branch_count} type-check(s) detected). Extending this requires "
            "modifying the method for every new type, violating Open/Closed."
        ),
        severity=ViolationSeverity.LOW,
        suggestion="Replace type dispatch with polymorphism or the Strategy pattern.",
        confidence=confidence,
        evidence=f"type_switches={branch_count} in method '{method.name}'",
    )
