"""SRP evaluator — Disjoint-Domain God Class via LCOM4 + import-root fan-out.

Per ``_Docs/Planning/Heimdall/02_SOLID_Detection.md``: flag when
``methods > 20`` AND (``LCOM4 > 1`` OR ``import_roots >= 3``).
"""
from typing import List

from Asgard.Bragi.Architecture.cir.models import ClassInfo, FileInfo
from Asgard.Bragi.Architecture.evaluators._lcom4 import lcom4, lcom4_components
from Asgard.Bragi.Architecture.models.architecture_models import (
    Confidence,
    SOLIDPrinciple,
    SOLIDViolation,
    ViolationSeverity,
)

METHOD_THRESHOLD = 20
IMPORT_ROOT_THRESHOLD = 3


def evaluate(file_info: FileInfo, cls: ClassInfo) -> List[SOLIDViolation]:
    violations: List[SOLIDViolation] = []

    if cls.method_count > METHOD_THRESHOLD:
        components = lcom4_components(cls)
        lcom_value = len(components)
        import_fanout = len(cls.import_roots)

        if lcom_value > 1 or import_fanout >= IMPORT_ROOT_THRESHOLD:
            evidence_parts = []
            if lcom_value > 1:
                comp_desc = " | ".join(
                    "{" + ", ".join(sorted(c)) + "}" for c in components if c
                )
                evidence_parts.append(f"LCOM4={lcom_value}: {comp_desc}")
            if import_fanout >= IMPORT_ROOT_THRESHOLD:
                evidence_parts.append(f"import_roots={import_fanout}")

            violations.append(SOLIDViolation(
                principle=SOLIDPrinciple.SRP,
                class_name=cls.name,
                file_path=cls.filepath,
                line_number=cls.start_line,
                message=(
                    f"Class '{cls.name}' has {cls.method_count} methods "
                    f"(threshold {METHOD_THRESHOLD}) and shows signs of disjoint "
                    "responsibilities. Consider splitting into smaller, focused classes."
                ),
                severity=ViolationSeverity.MODERATE,
                suggestion="Split responsibilities into separate classes/modules.",
                confidence=Confidence.MEDIUM,
                evidence="; ".join(evidence_parts),
            ))

    return violations
