"""
Heimdall OOP Models - Per-Class Metric Dataclasses

ClassCouplingMetrics, ClassInheritanceMetrics, ClassCohesionMetrics,
ClassRFCMetrics, ClassOOPMetrics.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Set

from Asgard.Heimdall.OOP.models._oop_enums import (
    CohesionLevel,
    CouplingLevel,
    OOPConfig,
    OOPSeverity,
)


@dataclass
class ClassCouplingMetrics:
    """Coupling metrics for a single class."""
    class_name: str
    file_path: str
    relative_path: str
    line_number: int

    cbo: int = 0
    afferent_coupling: int = 0
    efferent_coupling: int = 0
    instability: float = 0.0

    coupled_to: Set[str] = field(default_factory=set)
    coupled_from: Set[str] = field(default_factory=set)

    coupling_level: CouplingLevel = CouplingLevel.EXCELLENT
    severity: OOPSeverity = OOPSeverity.INFO

    @staticmethod
    def calculate_coupling_level(cbo: int) -> CouplingLevel:
        """Determine coupling level from CBO value."""
        if cbo <= 3:
            return CouplingLevel.EXCELLENT
        elif cbo <= 6:
            return CouplingLevel.GOOD
        elif cbo <= 10:
            return CouplingLevel.MODERATE
        elif cbo <= 15:
            return CouplingLevel.HIGH
        else:
            return CouplingLevel.CRITICAL

    @staticmethod
    def calculate_severity(cbo: int, threshold: int) -> OOPSeverity:
        """Determine severity based on CBO vs threshold."""
        if cbo <= threshold * 0.5:
            return OOPSeverity.INFO
        elif cbo <= threshold * 0.75:
            return OOPSeverity.LOW
        elif cbo <= threshold:
            return OOPSeverity.MODERATE
        elif cbo <= threshold * 1.5:
            return OOPSeverity.HIGH
        else:
            return OOPSeverity.CRITICAL


@dataclass
class ClassInheritanceMetrics:
    """Inheritance metrics for a single class."""
    class_name: str
    file_path: str
    relative_path: str
    line_number: int

    dit: int = 0
    noc: int = 0

    base_classes: List[str] = field(default_factory=list)
    direct_subclasses: List[str] = field(default_factory=list)
    all_ancestors: List[str] = field(default_factory=list)

    severity: OOPSeverity = OOPSeverity.INFO

    @staticmethod
    def calculate_severity(dit: int, noc: int, dit_threshold: int, noc_threshold: int) -> OOPSeverity:
        """Determine severity based on DIT and NOC vs thresholds."""
        max_ratio = max(
            dit / dit_threshold if dit_threshold > 0 else 0,
            noc / noc_threshold if noc_threshold > 0 else 0
        )
        if max_ratio <= 0.5:
            return OOPSeverity.INFO
        elif max_ratio <= 0.75:
            return OOPSeverity.LOW
        elif max_ratio <= 1.0:
            return OOPSeverity.MODERATE
        elif max_ratio <= 1.5:
            return OOPSeverity.HIGH
        else:
            return OOPSeverity.CRITICAL


@dataclass
class ClassCohesionMetrics:
    """Cohesion metrics for a single class."""
    class_name: str
    file_path: str
    relative_path: str
    line_number: int

    lcom: float = 0.0
    lcom4: float = 0.0

    method_count: int = 0
    attribute_count: int = 0
    method_attribute_usage: Dict[str, Set[str]] = field(default_factory=dict)

    cohesion_level: CohesionLevel = CohesionLevel.EXCELLENT
    severity: OOPSeverity = OOPSeverity.INFO

    @staticmethod
    def calculate_cohesion_level(lcom: float) -> CohesionLevel:
        """Determine cohesion level from LCOM value."""
        if lcom <= 0.2:
            return CohesionLevel.EXCELLENT
        elif lcom <= 0.4:
            return CohesionLevel.GOOD
        elif lcom <= 0.6:
            return CohesionLevel.MODERATE
        elif lcom <= 0.8:
            return CohesionLevel.LOW
        else:
            return CohesionLevel.CRITICAL

    @staticmethod
    def calculate_severity(lcom: float, threshold: float) -> OOPSeverity:
        """Determine severity based on LCOM vs threshold."""
        if lcom <= threshold * 0.5:
            return OOPSeverity.INFO
        elif lcom <= threshold * 0.75:
            return OOPSeverity.LOW
        elif lcom <= threshold:
            return OOPSeverity.MODERATE
        elif lcom <= threshold * 1.25:
            return OOPSeverity.HIGH
        else:
            return OOPSeverity.CRITICAL


@dataclass
class ClassRFCMetrics:
    """Response for Class and Weighted Methods per Class metrics."""
    class_name: str
    file_path: str
    relative_path: str
    line_number: int

    rfc: int = 0
    wmc: int = 0

    method_count: int = 0
    methods_called: Set[str] = field(default_factory=set)
    method_complexities: Dict[str, int] = field(default_factory=dict)

    severity: OOPSeverity = OOPSeverity.INFO

    @staticmethod
    def calculate_severity(rfc: int, wmc: int, rfc_threshold: int, wmc_threshold: int) -> OOPSeverity:
        """Determine severity based on RFC and WMC vs thresholds."""
        max_ratio = max(
            rfc / rfc_threshold if rfc_threshold > 0 else 0,
            wmc / wmc_threshold if wmc_threshold > 0 else 0
        )
        if max_ratio <= 0.5:
            return OOPSeverity.INFO
        elif max_ratio <= 0.75:
            return OOPSeverity.LOW
        elif max_ratio <= 1.0:
            return OOPSeverity.MODERATE
        elif max_ratio <= 1.5:
            return OOPSeverity.HIGH
        else:
            return OOPSeverity.CRITICAL


@dataclass
class ClassOOPMetrics:
    """Combined OOP metrics for a single class."""
    class_name: str
    file_path: str
    relative_path: str
    line_number: int
    end_line: int = 0

    cbo: int = 0
    afferent_coupling: int = 0
    efferent_coupling: int = 0
    instability: float = 0.0

    dit: int = 0
    noc: int = 0

    lcom: float = 0.0
    lcom4: float = 0.0

    rfc: int = 0
    wmc: int = 0

    method_count: int = 0
    attribute_count: int = 0

    base_classes: List[str] = field(default_factory=list)

    coupling_level: CouplingLevel = CouplingLevel.EXCELLENT
    cohesion_level: CohesionLevel = CohesionLevel.EXCELLENT
    overall_severity: OOPSeverity = OOPSeverity.INFO

    violations: List[str] = field(default_factory=list)

    @property
    def qualified_name(self) -> str:
        """Get the qualified class name with file location."""
        return f"{self.relative_path}:{self.class_name}"

    def calculate_overall_severity(self, config: OOPConfig) -> OOPSeverity:
        """Calculate overall severity based on all metrics."""
        severities = [
            ClassCouplingMetrics.calculate_severity(self.cbo, config.cbo_threshold),
            ClassInheritanceMetrics.calculate_severity(
                self.dit, self.noc, config.dit_threshold, config.noc_threshold
            ),
            ClassCohesionMetrics.calculate_severity(self.lcom, config.lcom_threshold),
            ClassRFCMetrics.calculate_severity(
                self.rfc, self.wmc, config.rfc_threshold, config.wmc_threshold
            ),
        ]
        severity_order = [
            OOPSeverity.INFO, OOPSeverity.LOW, OOPSeverity.MODERATE,
            OOPSeverity.HIGH, OOPSeverity.CRITICAL
        ]
        max_idx = max(severity_order.index(s) for s in severities)
        return severity_order[max_idx]
