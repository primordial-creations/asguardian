"""Pure-Python SOLID evaluators operating on the CIR.

Each evaluator module exposes ``evaluate(file_info, class_info) -> list[SOLIDViolation]``.
:func:`evaluate_file` runs all five over every class in a
:class:`~Asgard.Bragi.Architecture.cir.models.FileInfo`.
"""
from typing import List

from Asgard.Bragi.Architecture.cir.models import FileInfo
from Asgard.Bragi.Architecture.models.architecture_models import SOLIDViolation
from Asgard.Bragi.Architecture.evaluators import srp, ocp, lsp, isp, dip

_EVALUATORS = (srp, ocp, lsp, isp, dip)


def evaluate_file(file_info: FileInfo) -> List[SOLIDViolation]:
    """Run every SOLID evaluator over every class in *file_info*."""
    violations: List[SOLIDViolation] = []
    for cls in file_info.classes:
        for module in _EVALUATORS:
            violations.extend(module.evaluate(file_info, cls))
    return violations
