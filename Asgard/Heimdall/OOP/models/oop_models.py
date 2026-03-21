"""
Heimdall OOP Models

Data models for object-oriented programming metrics analysis.

Metrics included:
- CBO (Coupling Between Objects): Count of classes this class is coupled to
- Ca (Afferent Coupling): Classes that depend on this class
- Ce (Efferent Coupling): Classes this class depends on
- I (Instability): Ce / (Ca + Ce) - ranges from 0 (stable) to 1 (unstable)
- DIT (Depth of Inheritance Tree): Maximum path from class to root
- NOC (Number of Children): Direct subclasses count
- LCOM (Lack of Cohesion of Methods): Measures class cohesion
- RFC (Response for a Class): Methods + methods called by methods
- WMC (Weighted Methods per Class): Sum of cyclomatic complexity
"""

from Asgard.Heimdall.OOP.models._oop_enums import (
    CohesionLevel,
    CouplingLevel,
    OOPConfig,
    OOPSeverity,
)
from Asgard.Heimdall.OOP.models._oop_class_metrics import (
    ClassCohesionMetrics,
    ClassCouplingMetrics,
    ClassInheritanceMetrics,
    ClassOOPMetrics,
    ClassRFCMetrics,
)
from Asgard.Heimdall.OOP.models._oop_report import (
    FileOOPAnalysis,
    OOPReport,
)

__all__ = [
    "CohesionLevel",
    "CouplingLevel",
    "OOPConfig",
    "OOPSeverity",
    "ClassCohesionMetrics",
    "ClassCouplingMetrics",
    "ClassInheritanceMetrics",
    "ClassOOPMetrics",
    "ClassRFCMetrics",
    "FileOOPAnalysis",
    "OOPReport",
]
