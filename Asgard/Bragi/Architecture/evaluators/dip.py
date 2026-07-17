"""DIP evaluator — Lexical Concretion Instantiation.

Flags instantiation of a concrete-looking class (name suffix
Service/Repository/Manager/Controller/Client/Dao/Engine) from inside another
class, unless the enclosing class is itself a composition-root type
(Factory/Builder/Provider/Module/Config) or the instantiation happens in
``main``.
"""
import re
from typing import List

from Asgard.Bragi.Architecture.cir.models import ClassInfo, FileInfo
from Asgard.Bragi.Architecture.models.architecture_models import (
    Confidence,
    SOLIDPrinciple,
    SOLIDViolation,
    ViolationSeverity,
)

_CONCRETE_SUFFIX = re.compile(
    r"(?:Service|Repository|Manager|Controller|Client|Dao|Engine)$"
)
_COMPOSITION_ROOT_SUFFIX = re.compile(
    r"(?:Factory|Builder|Provider|Module|Config)$", re.IGNORECASE
)


def evaluate(file_info: FileInfo, cls: ClassInfo) -> List[SOLIDViolation]:
    if _COMPOSITION_ROOT_SUFFIX.search(cls.name):
        return []

    violations: List[SOLIDViolation] = []
    for method in cls.methods:
        if method.name == "main":
            continue
        for target in sorted(method.instantiations):
            if _CONCRETE_SUFFIX.search(target):
                violations.append(SOLIDViolation(
                    principle=SOLIDPrinciple.DIP,
                    class_name=cls.name,
                    file_path=cls.filepath,
                    line_number=method.start_line,
                    message=(
                        f"'{cls.name}.{method.name}' instantiates concrete class "
                        f"'{target}' directly. High-level modules should depend on "
                        "abstractions, not concretions."
                    ),
                    severity=ViolationSeverity.HIGH,
                    suggestion="Inject the dependency via constructor or a DI container.",
                    confidence=Confidence.HIGH,
                    evidence=f"instantiation of '{target}' in '{method.name}'",
                ))
    return violations
