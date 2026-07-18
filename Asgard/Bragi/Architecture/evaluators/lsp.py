"""LSP evaluator — Refused Bequest only.

Per plan 02, semantic LSP (contract narrowing) is uncomputable from an
isolated CST and is explicitly out of scope. The single detectable, high
precision signal is an *overridden* method whose body is empty or solely
raises an "unimplemented" exception (``NotImplementedError``,
``NotSupportedException``, ``panic``, ...).
"""
from typing import List

from Asgard.Bragi.Architecture.cir.models import ClassInfo, FileInfo
from Asgard.Bragi.Architecture.models.architecture_models import (
    Confidence,
    SOLIDPrinciple,
    SOLIDViolation,
    ViolationSeverity,
)


def evaluate(file_info: FileInfo, cls: ClassInfo) -> List[SOLIDViolation]:
    violations: List[SOLIDViolation] = []
    if not cls.implements and not cls.extends:
        return violations

    for method in cls.methods:
        if method.is_override and (method.is_empty or method.throws_unimplemented):
            violations.append(SOLIDViolation(
                principle=SOLIDPrinciple.LSP,
                class_name=cls.name,
                file_path=cls.filepath,
                line_number=method.start_line,
                message=(
                    f"Overridden method '{method.name}' refuses its inherited contract "
                    "(empty body or raises an unimplemented exception). Subtypes must "
                    "honor the base type's contract (Liskov Substitution)."
                ),
                severity=ViolationSeverity.HIGH,
                suggestion="Either implement the method meaningfully or restructure the hierarchy.",
                confidence=Confidence.HIGH,
                evidence=(
                    f"'{method.name}' is_override=True "
                    f"is_empty={method.is_empty} throws_unimplemented={method.throws_unimplemented}"
                ),
            ))

    return violations
