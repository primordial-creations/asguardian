"""
Heimdall OOP Analyzer Service

Unified analyzer that combines all OOP metrics:
- Coupling (CBO, Ca, Ce, Instability)
- Inheritance (DIT, NOC)
- Cohesion (LCOM, LCOM4)
- RFC/WMC (Response for Class, Weighted Methods per Class)

This provides a complete picture of object-oriented design quality.
"""

import time
from pathlib import Path
from typing import Dict, List, Optional

from Asgard.Heimdall.OOP.models.oop_models import (
    ClassCohesionMetrics,
    ClassCouplingMetrics,
    ClassInheritanceMetrics,
    ClassOOPMetrics,
    ClassRFCMetrics,
    FileOOPAnalysis,
    OOPConfig,
    OOPReport,
    OOPSeverity,
)
from Asgard.Heimdall.OOP.services.coupling_analyzer import CouplingAnalyzer
from Asgard.Heimdall.OOP.services.inheritance_analyzer import InheritanceAnalyzer
from Asgard.Heimdall.OOP.services.cohesion_analyzer import CohesionAnalyzer
from Asgard.Heimdall.OOP.services.rfc_analyzer import RFCAnalyzer
from Asgard.Heimdall.OOP.services._oop_reporter import (
    generate_text_report as _gen_text,
    generate_json_report as _gen_json,
    generate_markdown_report as _gen_markdown,
)
from Asgard.Heimdall.OOP.services._oop_merge import (
    build_combined_class_metrics,
    build_violations_list,
)


class OOPAnalyzer:
    """
    Unified analyzer for all OOP metrics.

    Combines coupling, inheritance, cohesion, and RFC/WMC analysis
    to provide a complete assessment of object-oriented design quality.
    """

    def __init__(self, config: Optional[OOPConfig] = None):
        """Initialize the OOP analyzer."""
        self.config = config or OOPConfig()
        self.coupling_analyzer = CouplingAnalyzer(self.config)
        self.inheritance_analyzer = InheritanceAnalyzer(self.config)
        self.cohesion_analyzer = CohesionAnalyzer(self.config)
        self.rfc_analyzer = RFCAnalyzer(self.config)

    def analyze(self, scan_path: Optional[Path] = None) -> OOPReport:
        """
        Perform complete OOP analysis on the specified path.

        Args:
            scan_path: Root path to scan. Uses config path if not provided.

        Returns:
            OOPReport containing all findings
        """
        path = scan_path or self.config.scan_path
        path = Path(path).resolve()

        if not path.exists():
            raise FileNotFoundError(f"Scan path does not exist: {path}")

        start_time = time.time()

        coupling_metrics = self.coupling_analyzer.analyze(path)
        inheritance_metrics = self.inheritance_analyzer.analyze(path)
        cohesion_metrics = self.cohesion_analyzer.analyze(path)
        rfc_metrics = self.rfc_analyzer.analyze(path)

        coupling_by_class: Dict[str, ClassCouplingMetrics] = {m.class_name: m for m in coupling_metrics}
        inheritance_by_class: Dict[str, ClassInheritanceMetrics] = {m.class_name: m for m in inheritance_metrics}
        cohesion_by_class: Dict[str, ClassCohesionMetrics] = {m.class_name: m for m in cohesion_metrics}
        rfc_by_class: Dict[str, ClassRFCMetrics] = {m.class_name: m for m in rfc_metrics}

        all_class_names = (
            set(coupling_by_class.keys()) |
            set(inheritance_by_class.keys()) |
            set(cohesion_by_class.keys()) |
            set(rfc_by_class.keys())
        )

        file_classes: Dict[str, List[str]] = {}
        for name in all_class_names:
            file_path = None
            if name in coupling_by_class:
                file_path = coupling_by_class[name].file_path
            elif name in inheritance_by_class:
                file_path = inheritance_by_class[name].file_path
            elif name in cohesion_by_class:
                file_path = cohesion_by_class[name].file_path
            elif name in rfc_by_class:
                file_path = rfc_by_class[name].file_path

            if file_path:
                if file_path not in file_classes:
                    file_classes[file_path] = []
                file_classes[file_path].append(name)

        report = OOPReport(
            scan_path=str(path),
            cbo_threshold=self.config.cbo_threshold,
            dit_threshold=self.config.dit_threshold,
            noc_threshold=self.config.noc_threshold,
            lcom_threshold=self.config.lcom_threshold,
            rfc_threshold=self.config.rfc_threshold,
            wmc_threshold=self.config.wmc_threshold,
        )

        for file_path, class_names in file_classes.items():
            relative_path = None
            for name in class_names:
                if name in coupling_by_class:
                    relative_path = coupling_by_class[name].relative_path
                    break
                elif name in inheritance_by_class:
                    relative_path = inheritance_by_class[name].relative_path
                    break

            if not relative_path:
                relative_path = Path(file_path).name

            file_analysis = FileOOPAnalysis(file_path=file_path, relative_path=relative_path)

            for class_name in class_names:
                combined = build_combined_class_metrics(
                    class_name=class_name,
                    file_path=file_path,
                    relative_path=relative_path,
                    coupling=coupling_by_class.get(class_name),
                    inheritance=inheritance_by_class.get(class_name),
                    cohesion=cohesion_by_class.get(class_name),
                    rfc=rfc_by_class.get(class_name),
                    config=self.config,
                    end_line=0,
                )
                violations = build_violations_list(combined, self.config)
                combined.violations = violations
                file_analysis.add_class(combined)
                if violations:
                    file_analysis.add_violation(combined)

            report.add_file_analysis(file_analysis)

        report.scan_duration_seconds = time.time() - start_time

        severity_order = {
            OOPSeverity.CRITICAL: 0, OOPSeverity.HIGH: 1,
            OOPSeverity.MODERATE: 2, OOPSeverity.LOW: 3, OOPSeverity.INFO: 4,
        }
        report.violations.sort(key=lambda v: severity_order.get(v.overall_severity, 5))

        return report

    def analyze_file(self, file_path: Path) -> FileOOPAnalysis:
        """
        Analyze a single file for OOP metrics.

        Args:
            file_path: Path to the Python file

        Returns:
            FileOOPAnalysis with metrics for all classes
        """
        path = Path(file_path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"File does not exist: {path}")

        coupling_metrics = self.coupling_analyzer.analyze_file(path)
        inheritance_metrics = self.inheritance_analyzer.analyze_file(path)
        cohesion_metrics = self.cohesion_analyzer.analyze_file(path)
        rfc_metrics = self.rfc_analyzer.analyze_file(path)

        coupling_by_class = {m.class_name: m for m in coupling_metrics}
        inheritance_by_class = {m.class_name: m for m in inheritance_metrics}
        cohesion_by_class = {m.class_name: m for m in cohesion_metrics}
        rfc_by_class = {m.class_name: m for m in rfc_metrics}

        all_class_names = (
            set(coupling_by_class.keys()) |
            set(inheritance_by_class.keys()) |
            set(cohesion_by_class.keys()) |
            set(rfc_by_class.keys())
        )

        file_analysis = FileOOPAnalysis(file_path=str(path), relative_path=path.name)

        for class_name in all_class_names:
            combined = build_combined_class_metrics(
                class_name=class_name,
                file_path=str(path),
                relative_path=path.name,
                coupling=coupling_by_class.get(class_name),
                inheritance=inheritance_by_class.get(class_name),
                cohesion=cohesion_by_class.get(class_name),
                rfc=rfc_by_class.get(class_name),
                config=self.config,
            )
            file_analysis.add_class(combined)

            if (combined.cbo > self.config.cbo_threshold or
                combined.dit > self.config.dit_threshold or
                combined.noc > self.config.noc_threshold or
                combined.lcom > self.config.lcom_threshold or
                combined.rfc > self.config.rfc_threshold or
                combined.wmc > self.config.wmc_threshold):
                file_analysis.add_violation(combined)

        return file_analysis

    def get_god_classes(self, scan_path: Optional[Path] = None) -> List[ClassOOPMetrics]:
        """
        Identify potential god classes (high coupling, low cohesion, high WMC).

        Args:
            scan_path: Root path to scan

        Returns:
            List of classes that exhibit god class characteristics
        """
        report = self.analyze(scan_path)
        return [
            cls for cls in report.class_metrics
            if (cls.cbo > self.config.cbo_threshold and
                cls.lcom > self.config.lcom_threshold and
                cls.wmc > self.config.wmc_threshold)
        ]

    def get_design_smells(self, scan_path: Optional[Path] = None) -> Dict[str, List[ClassOOPMetrics]]:
        """Identify common OOP design smells. Returns a dict of smell type to affected classes."""
        report = self.analyze(scan_path)

        smells: Dict[str, List[ClassOOPMetrics]] = {
            "god_class": [],
            "data_class": [],
            "feature_envy": [],
            "deep_hierarchy": [],
            "wide_hierarchy": [],
            "unstable_class": [],
            "blob": [],
        }

        for cls in report.class_metrics:
            if (cls.cbo > self.config.cbo_threshold and
                cls.lcom > self.config.lcom_threshold and
                cls.wmc > self.config.wmc_threshold):
                smells["god_class"].append(cls)

            if cls.rfc < 5 and cls.attribute_count > 5 and cls.method_count < 3:
                smells["data_class"].append(cls)

            if cls.dit > self.config.dit_threshold:
                smells["deep_hierarchy"].append(cls)

            if cls.noc > self.config.noc_threshold:
                smells["wide_hierarchy"].append(cls)

            if cls.instability > 0.8 and cls.efferent_coupling > 3:
                smells["unstable_class"].append(cls)

            if cls.wmc > self.config.wmc_threshold * 2:
                smells["blob"].append(cls)

        return smells

    def generate_report(self, result: OOPReport, format: str = "text") -> str:
        """
        Generate a formatted report.

        Args:
            result: OOPReport to format
            format: Output format ("text", "json", "markdown")

        Returns:
            Formatted report string
        """
        if format == "json":
            return _gen_json(result)
        elif format == "markdown":
            return _gen_markdown(result)
        else:
            return _gen_text(result)
