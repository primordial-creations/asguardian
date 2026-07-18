"""
Bragi Remediation Model (Plan 02 Phase B)

Rule/severity -> RemediationFunction registry with pessimism-corrected
minute constants (RESEARCH_04 + Lenarduzzi/Taibi 2020: SonarQube-style
estimates were exceeded in only ~3% of real fixes, so trivial-smell
constants are corrected DOWN to 1-2 minutes).

Severity minutes (SQUORE grid, corrected):
    Tiny 2 / Low 10 / Medium 30 / High 60 / Huge (architectural) 480
"""

import re
from typing import Dict

from Asgard.Bragi.Quality.models.debt_models import (
    DebtItem,
    DebtType,
    RemediationFunction,
)

# Pessimism-corrected minutes per severity class.
SEVERITY_MINUTES: Dict[str, float] = {
    "tiny": 2.0,
    "low": 10.0,
    "medium": 30.0,
    "high": 60.0,
    "critical": 480.0,  # "Huge": architectural-scale work
}

# SBII non-remediation (business impact) factors, RESEARCH_04.
NON_REMEDIATION_FACTORS: Dict[str, float] = {
    "critical": 1000.0,
    "high": 100.0,
    "medium": 15.0,
    "low": 10.0,
    "info": 4.0,
}

# Batchability d per debt type: near 0 for mechanical debt (50 missing
# docstrings batch into one sitting), high for cognitive debt (each God
# class needs independent thought).
DEFAULT_FUNCTIONS: Dict[str, RemediationFunction] = {
    DebtType.DOCUMENTATION.value: RemediationFunction(
        kind="linear", base_minutes=0.0, coefficient_minutes=2.0,
        unit="undocumented_function", batchability=0.05,
    ),
    DebtType.TEST.value: RemediationFunction(
        kind="linear_with_offset", base_minutes=15.0, coefficient_minutes=30.0,
        unit="untested_file", batchability=0.30,
    ),
    DebtType.DEPENDENCIES.value: RemediationFunction(
        kind="constant", base_minutes=30.0, coefficient_minutes=0.0,
        unit="dependency_audit", batchability=0.20,
    ),
    # Cognitive debt: each God function / coupling hotspot needs independent
    # thought, so the discount is weak AND floored at 25% - a pile of smells
    # stays near-additive rather than being capped by the geometric series
    # (which would let debt concentration divide the TDR).
    DebtType.CODE.value: RemediationFunction(
        kind="linear_with_offset", base_minutes=10.0, coefficient_minutes=30.0,
        unit="severity_step", batchability=0.90, discount_floor=0.25,
    ),
    DebtType.DESIGN.value: RemediationFunction(
        kind="linear_with_offset", base_minutes=30.0, coefficient_minutes=60.0,
        unit="coupling_hotspot", batchability=0.90, discount_floor=0.25,
    ),
}

_COUNT_PATTERN = re.compile(r"(\d+)\s+undocumented")


class RemediationModel:
    """Resolves the remediation function and corrected minutes for a debt item."""

    def __init__(self, overrides: Dict[str, RemediationFunction] = None):
        self.functions: Dict[str, RemediationFunction] = dict(DEFAULT_FUNCTIONS)
        if overrides:
            self.functions.update(overrides)

    def function_for(self, item: DebtItem) -> RemediationFunction:
        """Look up the remediation function for a debt item's rule/type."""
        debt_type = item.debt_type if isinstance(item.debt_type, str) else item.debt_type.value
        return self.functions.get(debt_type, DEFAULT_FUNCTIONS[DebtType.CODE.value])

    def minutes_for(self, item: DebtItem) -> float:
        """
        Pessimism-corrected remediation minutes for one debt item.

        Mechanical documentation debt is priced per undocumented function
        (2 min each); other types use the severity grid plus the function's
        offset when the shape carries a context-switch cost.
        """
        function = self.function_for(item)
        debt_type = item.debt_type if isinstance(item.debt_type, str) else item.debt_type.value
        severity = item.severity if isinstance(item.severity, str) else item.severity.value

        if debt_type == DebtType.DOCUMENTATION.value:
            match = _COUNT_PATTERN.search(item.description or "")
            units = int(match.group(1)) if match else 1
            # An aggregated count-item ("50 undocumented public functions")
            # must cost the same as 50 single items: apply the batching
            # discount to the units INSIDE the item (geometric series), so
            # both shapes total identically in the aggregator.
            d = function.batchability
            if d >= 1.0:
                series = float(units)
            else:
                series = (1.0 - d ** units) / (1.0 - d) if d > 0 else 1.0
            return function.base_minutes + function.coefficient_minutes * series

        severity_minutes = SEVERITY_MINUTES.get(severity, SEVERITY_MINUTES["medium"])
        if function.kind == "constant":
            return function.base_minutes
        if function.kind == "linear":
            return function.coefficient_minutes * max(severity_minutes / 30.0, 1.0)
        # linear_with_offset: offset (open file, build mental model) + work.
        return function.base_minutes + severity_minutes

    @staticmethod
    def non_remediation_factor(item: DebtItem) -> float:
        """SBII business-impact factor for the item's severity."""
        severity = item.severity if isinstance(item.severity, str) else item.severity.value
        return NON_REMEDIATION_FACTORS.get(severity, 15.0)
