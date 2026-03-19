"""
Heimdall OOP Analyzer Service

Unified analyzer that combines all OOP metrics:
- Coupling (CBO, Ca, Ce, Instability)
- Inheritance (DIT, NOC)
- Cohesion (LCOM, LCOM4)
- RFC/WMC (Response for Class, Weighted Methods per Class)

This provides a complete picture of object-oriented design quality.
"""

import json
import time
from pathlib import Path
from typing import Dict, List, Optional

from Asgard.Heimdall.OOP.models.oop_models import (
    ClassCouplingMetrics,
    ClassInheritanceMetrics,
    ClassCohesionMetrics,
    ClassRFCMetrics,
    ClassOOPMetrics,
    CouplingLevel,
    CohesionLevel,
    FileOOPAnalysis,
    OOPConfig,
    OOPReport,
    OOPSeverity,
)
from Asgard.Heimdall.OOP.services.coupling_analyzer import CouplingAnalyzer
from Asgard.Heimdall.OOP.services.inheritance_analyzer import InheritanceAnalyzer
from Asgard.Heimdall.OOP.services.cohesion_analyzer import CohesionAnalyzer
from Asgard.Heimdall.OOP.services.rfc_analyzer import RFCAnalyzer
from Asgard.Heimdall.OOP.utilities.class_utils import extract_classes_from_file
from Asgard.Heimdall.Quality.utilities.file_utils import scan_directory


class OOPAnalyzer:
    """
    Unified analyzer for all OOP metrics.

    Combines coupling, inheritance, cohesion, and RFC/WMC analysis
    to provide a complete assessment of object-oriented design quality.
    """

    def __init__(self, config: Optional[OOPConfig] = None):
        """Initialize the OOP analyzer."""
        self.config = config or OOPConfig()

        # Initialize sub-analyzers
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

        # Run all sub-analyzers
        coupling_metrics = self.coupling_analyzer.analyze(path)
        inheritance_metrics = self.inheritance_analyzer.analyze(path)
        cohesion_metrics = self.cohesion_analyzer.analyze(path)
        rfc_metrics = self.rfc_analyzer.analyze(path)

        # Create lookup dictionaries by class name
        coupling_by_class: Dict[str, ClassCouplingMetrics] = {
            m.class_name: m for m in coupling_metrics
        }
        inheritance_by_class: Dict[str, ClassInheritanceMetrics] = {
            m.class_name: m for m in inheritance_metrics
        }
        cohesion_by_class: Dict[str, ClassCohesionMetrics] = {
            m.class_name: m for m in cohesion_metrics
        }
        rfc_by_class: Dict[str, ClassRFCMetrics] = {
            m.class_name: m for m in rfc_metrics
        }

        # Combine into unified metrics
        all_class_names = (
            set(coupling_by_class.keys()) |
            set(inheritance_by_class.keys()) |
            set(cohesion_by_class.keys()) |
            set(rfc_by_class.keys())
        )

        # Group by file
        file_classes: Dict[str, List[str]] = {}
        file_paths: Dict[str, str] = {}  # class -> file path

        for name in all_class_names:
            # Get file path from any available metric
            file_path = None
            relative_path = None

            if name in coupling_by_class:
                file_path = coupling_by_class[name].file_path
                relative_path = coupling_by_class[name].relative_path
            elif name in inheritance_by_class:
                file_path = inheritance_by_class[name].file_path
                relative_path = inheritance_by_class[name].relative_path
            elif name in cohesion_by_class:
                file_path = cohesion_by_class[name].file_path
                relative_path = cohesion_by_class[name].relative_path
            elif name in rfc_by_class:
                file_path = rfc_by_class[name].file_path
                relative_path = rfc_by_class[name].relative_path

            if file_path:
                file_paths[name] = file_path
                if file_path not in file_classes:
                    file_classes[file_path] = []
                file_classes[file_path].append(name)

        # Build report
        report = OOPReport(
            scan_path=str(path),
            cbo_threshold=self.config.cbo_threshold,
            dit_threshold=self.config.dit_threshold,
            noc_threshold=self.config.noc_threshold,
            lcom_threshold=self.config.lcom_threshold,
            rfc_threshold=self.config.rfc_threshold,
            wmc_threshold=self.config.wmc_threshold,
        )

        # Process each file
        for file_path, class_names in file_classes.items():
            # Determine relative path
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

            file_analysis = FileOOPAnalysis(
                file_path=file_path,
                relative_path=relative_path,
            )

            # Process each class in the file
            for class_name in class_names:
                coupling = coupling_by_class.get(class_name)
                inheritance = inheritance_by_class.get(class_name)
                cohesion = cohesion_by_class.get(class_name)
                rfc = rfc_by_class.get(class_name)

                # Build combined metrics
                combined = ClassOOPMetrics(
                    class_name=class_name,
                    file_path=file_path,
                    relative_path=relative_path,
                    line_number=self._get_line_number(coupling, inheritance, cohesion, rfc),
                    end_line=0,
                    cbo=coupling.cbo if coupling else 0,
                    afferent_coupling=coupling.afferent_coupling if coupling else 0,
                    efferent_coupling=coupling.efferent_coupling if coupling else 0,
                    instability=coupling.instability if coupling else 0.0,
                    dit=inheritance.dit if inheritance else 0,
                    noc=inheritance.noc if inheritance else 0,
                    lcom=cohesion.lcom if cohesion else 0.0,
                    lcom4=cohesion.lcom4 if cohesion else 0.0,
                    rfc=rfc.rfc if rfc else 0,
                    wmc=rfc.wmc if rfc else 0,
                    method_count=rfc.method_count if rfc else (cohesion.method_count if cohesion else 0),
                    attribute_count=cohesion.attribute_count if cohesion else 0,
                    base_classes=inheritance.base_classes if inheritance else [],
                    coupling_level=coupling.coupling_level if coupling else CouplingLevel.EXCELLENT,
                    cohesion_level=cohesion.cohesion_level if cohesion else CohesionLevel.EXCELLENT,
                )

                # Calculate overall severity
                combined.overall_severity = combined.calculate_overall_severity(self.config)

                # Check for violations
                violations = []
                if combined.cbo > self.config.cbo_threshold:
                    violations.append(f"Coupling Between Objects (CBO) {combined.cbo} exceeds threshold {self.config.cbo_threshold}")
                if combined.dit > self.config.dit_threshold:
                    violations.append(f"Depth of Inheritance Tree (DIT) {combined.dit} exceeds threshold {self.config.dit_threshold}")
                if combined.noc > self.config.noc_threshold:
                    violations.append(f"Number of Children (NOC) {combined.noc} exceeds threshold {self.config.noc_threshold}")
                if combined.lcom > self.config.lcom_threshold:
                    violations.append(f"Lack of Cohesion of Methods (LCOM) {combined.lcom:.2f} exceeds threshold {self.config.lcom_threshold}")
                if combined.rfc > self.config.rfc_threshold:
                    violations.append(f"Response for a Class (RFC) {combined.rfc} exceeds threshold {self.config.rfc_threshold}")
                if combined.wmc > self.config.wmc_threshold:
                    violations.append(f"Weighted Methods per Class (WMC) {combined.wmc} exceeds threshold {self.config.wmc_threshold}")

                combined.violations = violations

                file_analysis.add_class(combined)

                if violations:
                    file_analysis.add_violation(combined)

            report.add_file_analysis(file_analysis)

        report.scan_duration_seconds = time.time() - start_time

        # Sort violations by severity
        severity_order = {
            OOPSeverity.CRITICAL: 0,
            OOPSeverity.HIGH: 1,
            OOPSeverity.MODERATE: 2,
            OOPSeverity.LOW: 3,
            OOPSeverity.INFO: 4,
        }
        report.violations.sort(key=lambda v: severity_order.get(v.overall_severity, 5))

        return report

    def _get_line_number(self, *metrics) -> int:
        """Get line number from first available metric."""
        for m in metrics:
            if m and hasattr(m, "line_number"):
                return m.line_number
        return 0

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

        # Run sub-analyzers on file
        coupling_metrics = self.coupling_analyzer.analyze_file(path)
        inheritance_metrics = self.inheritance_analyzer.analyze_file(path)
        cohesion_metrics = self.cohesion_analyzer.analyze_file(path)
        rfc_metrics = self.rfc_analyzer.analyze_file(path)

        # Create lookup dictionaries
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

        file_analysis = FileOOPAnalysis(
            file_path=str(path),
            relative_path=path.name,
        )

        for class_name in all_class_names:
            coupling = coupling_by_class.get(class_name)
            inheritance = inheritance_by_class.get(class_name)
            cohesion = cohesion_by_class.get(class_name)
            rfc = rfc_by_class.get(class_name)

            combined = ClassOOPMetrics(
                class_name=class_name,
                file_path=str(path),
                relative_path=path.name,
                line_number=self._get_line_number(coupling, inheritance, cohesion, rfc),
                cbo=coupling.cbo if coupling else 0,
                afferent_coupling=coupling.afferent_coupling if coupling else 0,
                efferent_coupling=coupling.efferent_coupling if coupling else 0,
                instability=coupling.instability if coupling else 0.0,
                dit=inheritance.dit if inheritance else 0,
                noc=inheritance.noc if inheritance else 0,
                lcom=cohesion.lcom if cohesion else 0.0,
                lcom4=cohesion.lcom4 if cohesion else 0.0,
                rfc=rfc.rfc if rfc else 0,
                wmc=rfc.wmc if rfc else 0,
                method_count=rfc.method_count if rfc else (cohesion.method_count if cohesion else 0),
                attribute_count=cohesion.attribute_count if cohesion else 0,
                base_classes=inheritance.base_classes if inheritance else [],
                coupling_level=coupling.coupling_level if coupling else CouplingLevel.EXCELLENT,
                cohesion_level=cohesion.cohesion_level if cohesion else CohesionLevel.EXCELLENT,
            )

            combined.overall_severity = combined.calculate_overall_severity(self.config)
            file_analysis.add_class(combined)

            # Check for violations
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

        god_classes = []
        for cls in report.class_metrics:
            # God class indicators:
            # - High coupling (CBO > threshold)
            # - Low cohesion (LCOM > threshold)
            # - High complexity (WMC > threshold)
            if (cls.cbo > self.config.cbo_threshold and
                cls.lcom > self.config.lcom_threshold and
                cls.wmc > self.config.wmc_threshold):
                god_classes.append(cls)

        return god_classes

    def get_design_smells(self, scan_path: Optional[Path] = None) -> Dict[str, List[ClassOOPMetrics]]:
        """
        Identify common OOP design smells.

        Args:
            scan_path: Root path to scan

        Returns:
            Dictionary of smell types to affected classes
        """
        report = self.analyze(scan_path)

        smells = {
            "god_class": [],           # High coupling + low cohesion + high WMC
            "data_class": [],          # Low RFC + high attribute count + low method count
            "feature_envy": [],        # High efferent coupling to specific classes
            "deep_hierarchy": [],      # DIT > threshold
            "wide_hierarchy": [],      # NOC > threshold
            "unstable_class": [],      # High instability (I > 0.8)
            "blob": [],                # Very high WMC
        }

        for cls in report.class_metrics:
            # God class
            if (cls.cbo > self.config.cbo_threshold and
                cls.lcom > self.config.lcom_threshold and
                cls.wmc > self.config.wmc_threshold):
                smells["god_class"].append(cls)

            # Data class (mostly data, few methods)
            if (cls.rfc < 5 and
                cls.attribute_count > 5 and
                cls.method_count < 3):
                smells["data_class"].append(cls)

            # Deep hierarchy
            if cls.dit > self.config.dit_threshold:
                smells["deep_hierarchy"].append(cls)

            # Wide hierarchy
            if cls.noc > self.config.noc_threshold:
                smells["wide_hierarchy"].append(cls)

            # Unstable class
            if cls.instability > 0.8 and cls.efferent_coupling > 3:
                smells["unstable_class"].append(cls)

            # Blob (very high complexity)
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
            return self._generate_json_report(result)
        elif format == "markdown":
            return self._generate_markdown_report(result)
        else:
            return self._generate_text_report(result)

    def _generate_text_report(self, result: OOPReport) -> str:
        """Generate text format report."""
        lines = []
        lines.append("")
        lines.append("=" * 70)
        lines.append("  HEIMDALL OOP METRICS REPORT")
        lines.append("=" * 70)
        lines.append("")
        lines.append(f"  Scan Path:    {result.scan_path}")
        lines.append(f"  Scanned At:   {result.scanned_at.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"  Duration:     {result.scan_duration_seconds:.2f}s")
        lines.append("")
        lines.append("  METRIC DEFINITIONS")
        lines.append("  " + "-" * 47)
        lines.append("  Coupling Between Objects (CBO): Number of classes a class is coupled to.")
        lines.append("    High CBO means the class is hard to reuse and changes ripple widely.")
        lines.append("  Depth of Inheritance Tree (DIT): How deep this class is in the inheritance")
        lines.append("    hierarchy. Deep hierarchies are harder to understand and maintain.")
        lines.append("  Number of Children (NOC): Number of direct subclasses. High NOC means the")
        lines.append("    base class is heavily relied upon — changes break many subclasses.")
        lines.append("  Lack of Cohesion of Methods (LCOM): Measures how well the methods of a class")
        lines.append("    relate to each other. High LCOM means the class is doing too many things.")
        lines.append("  Response for a Class (RFC): Number of methods that can be executed in")
        lines.append("    response to a message. High RFC means high complexity and testing burden.")
        lines.append("  Weighted Methods per Class (WMC): Sum of complexities of all methods.")
        lines.append("    High WMC means the class is too complex and should be split.")
        lines.append("")
        lines.append("  Thresholds:")
        lines.append(f"    Coupling Between Objects (CBO):  {result.cbo_threshold}    Depth of Inheritance Tree (DIT): {result.dit_threshold}    Number of Children (NOC): {result.noc_threshold}")
        lines.append(f"    Lack of Cohesion of Methods (LCOM): {result.lcom_threshold}  Response for a Class (RFC): {result.rfc_threshold}   Weighted Methods per Class (WMC): {result.wmc_threshold}")
        lines.append("")

        if result.has_violations:
            lines.append("-" * 70)
            lines.append("  VIOLATIONS")
            lines.append("-" * 70)
            lines.append("")

            for v in result.violations:
                lines.append(f"  [{v.overall_severity.value.upper()}] {v.class_name}")
                lines.append(f"    File: {v.relative_path}:{v.line_number}")
                lines.append(f"    Coupling Between Objects (CBO)={v.cbo} Depth of Inheritance Tree (DIT)={v.dit} Lack of Cohesion of Methods (LCOM)={v.lcom:.2f} Response for a Class (RFC)={v.rfc} Weighted Methods per Class (WMC)={v.wmc}")
                for violation in v.violations:
                    lines.append(f"    - {violation}")
                lines.append("")
        else:
            lines.append("  No OOP metric violations found!")
            lines.append("")

        lines.append("-" * 70)
        lines.append("  SUMMARY")
        lines.append("-" * 70)
        lines.append("")
        lines.append(f"  Files Analyzed:     {result.total_files_scanned}")
        lines.append(f"  Classes Analyzed:   {result.total_classes_analyzed}")
        lines.append(f"  Violations:         {result.total_violations}")
        lines.append(f"  Compliance Rate:    {result.compliance_rate:.1f}%")
        lines.append("")
        lines.append("  Averages:")
        lines.append(f"    Coupling Between Objects (CBO):  {result.average_cbo:.2f}    Depth of Inheritance Tree (DIT): {result.average_dit:.2f}")
        lines.append(f"    Lack of Cohesion of Methods (LCOM): {result.average_lcom:.2f}  Response for a Class (RFC): {result.average_rfc:.2f}  Weighted Methods per Class (WMC): {result.average_wmc:.2f}")
        lines.append("")
        lines.append("  Maximums:")
        lines.append(f"    Coupling Between Objects (CBO):  {result.max_cbo}    Depth of Inheritance Tree (DIT): {result.max_dit}")
        lines.append(f"    Lack of Cohesion of Methods (LCOM): {result.max_lcom:.2f}  Response for a Class (RFC): {result.max_rfc}  Weighted Methods per Class (WMC): {result.max_wmc}")
        lines.append("")
        lines.append("=" * 70)

        return "\n".join(lines)

    def _generate_json_report(self, result: OOPReport) -> str:
        """Generate JSON format report."""
        output = {
            "scan_path": result.scan_path,
            "scanned_at": result.scanned_at.isoformat(),
            "scan_duration_seconds": result.scan_duration_seconds,
            "thresholds": {
                "cbo": result.cbo_threshold,
                "dit": result.dit_threshold,
                "noc": result.noc_threshold,
                "lcom": result.lcom_threshold,
                "rfc": result.rfc_threshold,
                "wmc": result.wmc_threshold,
            },
            "summary": {
                "total_files": result.total_files_scanned,
                "total_classes": result.total_classes_analyzed,
                "total_violations": result.total_violations,
                "compliance_rate": round(result.compliance_rate, 2),
            },
            "averages": {
                "cbo": round(result.average_cbo, 2),
                "dit": round(result.average_dit, 2),
                "lcom": round(result.average_lcom, 2),
                "rfc": round(result.average_rfc, 2),
                "wmc": round(result.average_wmc, 2),
            },
            "classes": [
                {
                    "name": c.class_name,
                    "file": c.relative_path,
                    "line": c.line_number,
                    "cbo": c.cbo,
                    "dit": c.dit,
                    "noc": c.noc,
                    "lcom": round(c.lcom, 2),
                    "rfc": c.rfc,
                    "wmc": c.wmc,
                    "severity": c.overall_severity.value,
                    "violations": c.violations,
                }
                for c in result.class_metrics
            ],
        }

        return json.dumps(output, indent=2)

    def _generate_markdown_report(self, result: OOPReport) -> str:
        """Generate Markdown format report."""
        lines = []
        lines.append("# Heimdall OOP Metrics Report")
        lines.append("")
        lines.append(f"- **Scan Path:** `{result.scan_path}`")
        lines.append(f"- **Scanned At:** {result.scanned_at.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"- **Duration:** {result.scan_duration_seconds:.2f}s")
        lines.append("")
        lines.append("## Thresholds")
        lines.append("")
        lines.append("| Metric | Threshold |")
        lines.append("|--------|-----------|")
        lines.append(f"| CBO | {result.cbo_threshold} |")
        lines.append(f"| DIT | {result.dit_threshold} |")
        lines.append(f"| NOC | {result.noc_threshold} |")
        lines.append(f"| LCOM | {result.lcom_threshold} |")
        lines.append(f"| RFC | {result.rfc_threshold} |")
        lines.append(f"| WMC | {result.wmc_threshold} |")
        lines.append("")

        if result.has_violations:
            lines.append("## Violations")
            lines.append("")
            lines.append("| Class | File | CBO | DIT | LCOM | RFC | WMC | Severity |")
            lines.append("|-------|------|-----|-----|------|-----|-----|----------|")

            for v in result.violations:
                lines.append(
                    f"| {v.class_name} | `{v.relative_path}:{v.line_number}` | "
                    f"{v.cbo} | {v.dit} | {v.lcom:.2f} | {v.rfc} | {v.wmc} | "
                    f"{v.overall_severity.value.upper()} |"
                )

            lines.append("")

        lines.append("## Summary")
        lines.append("")
        lines.append(f"- **Files Analyzed:** {result.total_files_scanned}")
        lines.append(f"- **Classes Analyzed:** {result.total_classes_analyzed}")
        lines.append(f"- **Violations:** {result.total_violations}")
        lines.append(f"- **Compliance Rate:** {result.compliance_rate:.1f}%")
        lines.append("")

        return "\n".join(lines)
