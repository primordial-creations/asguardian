"""
Heimdall OOP Models - Report Dataclasses

FileOOPAnalysis and OOPReport.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List

from Asgard.Heimdall.OOP.models._oop_enums import OOPSeverity
from Asgard.Heimdall.OOP.models._oop_class_metrics import ClassOOPMetrics


@dataclass
class FileOOPAnalysis:
    """OOP analysis for a single file."""
    file_path: str
    relative_path: str

    classes: List[ClassOOPMetrics] = field(default_factory=list)

    total_classes: int = 0
    total_methods: int = 0
    average_cbo: float = 0.0
    average_dit: float = 0.0
    average_lcom: float = 0.0
    max_cbo: int = 0
    max_dit: int = 0
    max_lcom: float = 0.0

    violations: List[ClassOOPMetrics] = field(default_factory=list)

    def add_class(self, cls: ClassOOPMetrics) -> None:
        """Add a class analysis to this file."""
        self.classes.append(cls)
        self.total_classes = len(self.classes)
        self.total_methods += cls.method_count

        if self.total_classes > 0:
            self.average_cbo = sum(c.cbo for c in self.classes) / self.total_classes
            self.average_dit = sum(c.dit for c in self.classes) / self.total_classes
            self.average_lcom = sum(c.lcom for c in self.classes) / self.total_classes

        self.max_cbo = max(c.cbo for c in self.classes)
        self.max_dit = max(c.dit for c in self.classes)
        self.max_lcom = max(c.lcom for c in self.classes)

    def add_violation(self, cls: ClassOOPMetrics) -> None:
        """Add a class that violates thresholds."""
        self.violations.append(cls)


@dataclass
class OOPReport:
    """Complete OOP analysis report."""
    scan_path: str
    scanned_at: datetime = field(default_factory=datetime.now)
    scan_duration_seconds: float = 0.0

    cbo_threshold: int = 10
    dit_threshold: int = 5
    noc_threshold: int = 10
    lcom_threshold: float = 0.8
    rfc_threshold: int = 50
    wmc_threshold: int = 50

    file_analyses: List[FileOOPAnalysis] = field(default_factory=list)
    class_metrics: List[ClassOOPMetrics] = field(default_factory=list)
    violations: List[ClassOOPMetrics] = field(default_factory=list)

    total_files_scanned: int = 0
    total_classes_analyzed: int = 0
    total_violations: int = 0

    average_cbo: float = 0.0
    average_dit: float = 0.0
    average_lcom: float = 0.0
    average_rfc: float = 0.0
    average_wmc: float = 0.0

    max_cbo: int = 0
    max_dit: int = 0
    max_lcom: float = 0.0
    max_rfc: int = 0
    max_wmc: int = 0

    @property
    def has_violations(self) -> bool:
        """Check if any violations exist."""
        return self.total_violations > 0

    @property
    def has_issues(self) -> bool:
        """Check if any violations exist (alias for has_violations)."""
        return self.has_violations

    @property
    def compliance_rate(self) -> float:
        """Calculate the percentage of classes that comply with thresholds."""
        if self.total_classes_analyzed == 0:
            return 100.0
        return ((self.total_classes_analyzed - self.total_violations) /
                self.total_classes_analyzed * 100)

    def add_file_analysis(self, analysis: FileOOPAnalysis) -> None:
        """Add a file analysis to the report."""
        self.file_analyses.append(analysis)
        self.class_metrics.extend(analysis.classes)
        self.violations.extend(analysis.violations)

        self.total_files_scanned = len(self.file_analyses)
        self.total_classes_analyzed = len(self.class_metrics)
        self.total_violations = len(self.violations)

        if self.total_classes_analyzed > 0:
            self.average_cbo = sum(c.cbo for c in self.class_metrics) / self.total_classes_analyzed
            self.average_dit = sum(c.dit for c in self.class_metrics) / self.total_classes_analyzed
            self.average_lcom = sum(c.lcom for c in self.class_metrics) / self.total_classes_analyzed
            self.average_rfc = sum(c.rfc for c in self.class_metrics) / self.total_classes_analyzed
            self.average_wmc = sum(c.wmc for c in self.class_metrics) / self.total_classes_analyzed

            self.max_cbo = max((c.cbo for c in self.class_metrics), default=0)
            self.max_dit = max((c.dit for c in self.class_metrics), default=0)
            self.max_lcom = max((c.lcom for c in self.class_metrics), default=0.0)
            self.max_rfc = max((c.rfc for c in self.class_metrics), default=0)
            self.max_wmc = max((c.wmc for c in self.class_metrics), default=0)

    def get_violations_by_severity(self) -> Dict[str, List[ClassOOPMetrics]]:
        """Group violations by severity level."""
        result: Dict[str, List[ClassOOPMetrics]] = {
            OOPSeverity.CRITICAL.value: [],
            OOPSeverity.HIGH.value: [],
            OOPSeverity.MODERATE.value: [],
            OOPSeverity.LOW.value: [],
            OOPSeverity.INFO.value: [],
        }
        for v in self.violations:
            result[v.overall_severity.value].append(v)
        return result

    def get_coupling_violations(self) -> List[ClassOOPMetrics]:
        """Get classes that violate coupling thresholds."""
        return [c for c in self.class_metrics if c.cbo > self.cbo_threshold]

    def get_inheritance_violations(self) -> List[ClassOOPMetrics]:
        """Get classes that violate inheritance thresholds."""
        return [c for c in self.class_metrics
                if c.dit > self.dit_threshold or c.noc > self.noc_threshold]

    def get_cohesion_violations(self) -> List[ClassOOPMetrics]:
        """Get classes that violate cohesion thresholds."""
        return [c for c in self.class_metrics if c.lcom > self.lcom_threshold]

    def get_rfc_violations(self) -> List[ClassOOPMetrics]:
        """Get classes that violate RFC/WMC thresholds."""
        return [c for c in self.class_metrics
                if c.rfc > self.rfc_threshold or c.wmc > self.wmc_threshold]
