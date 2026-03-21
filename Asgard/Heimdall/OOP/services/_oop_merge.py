"""
Heimdall OOP Analyzer - Metric merge helpers.

Provides utilities for combining per-class metrics from multiple analyzers
(coupling, inheritance, cohesion, RFC) into a unified ClassOOPMetrics object.
"""

from typing import Optional, cast

from Asgard.Heimdall.OOP.models.oop_models import (
    ClassCohesionMetrics,
    ClassCouplingMetrics,
    ClassInheritanceMetrics,
    ClassOOPMetrics,
    ClassRFCMetrics,
    CohesionLevel,
    CouplingLevel,
    OOPConfig,
)


def get_line_number_from_metrics(*metrics) -> int:
    """Return the line number from the first available metric object."""
    for m in metrics:
        if m and hasattr(m, "line_number"):
            return cast(int, m.line_number)
    return 0


def build_combined_class_metrics(
    class_name: str,
    file_path: str,
    relative_path: str,
    coupling: Optional[ClassCouplingMetrics],
    inheritance: Optional[ClassInheritanceMetrics],
    cohesion: Optional[ClassCohesionMetrics],
    rfc: Optional[ClassRFCMetrics],
    config: OOPConfig,
    end_line: int = 0,
) -> ClassOOPMetrics:
    """
    Merge individual per-class metric objects into a single ClassOOPMetrics.

    Args:
        class_name: Name of the class being analysed.
        file_path: Absolute path to the file containing the class.
        relative_path: Path relative to the scan root.
        coupling: Coupling metrics for the class, or None.
        inheritance: Inheritance metrics for the class, or None.
        cohesion: Cohesion metrics for the class, or None.
        rfc: RFC/WMC metrics for the class, or None.
        config: OOP configuration (thresholds).
        end_line: Last line number of the class definition (default 0).

    Returns:
        A fully-populated ClassOOPMetrics with overall_severity set.
    """
    line_number = get_line_number_from_metrics(coupling, inheritance, cohesion, rfc)

    combined = ClassOOPMetrics(
        class_name=class_name,
        file_path=file_path,
        relative_path=relative_path,
        line_number=line_number,
        end_line=end_line,
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

    combined.overall_severity = combined.calculate_overall_severity(config)
    return combined


def build_violations_list(combined: ClassOOPMetrics, config: OOPConfig) -> list:
    """Build the list of violation description strings for a class."""
    violations = []
    if combined.cbo > config.cbo_threshold:
        violations.append(
            f"Coupling Between Objects (CBO) {combined.cbo} exceeds threshold {config.cbo_threshold}"
        )
    if combined.dit > config.dit_threshold:
        violations.append(
            f"Depth of Inheritance Tree (DIT) {combined.dit} exceeds threshold {config.dit_threshold}"
        )
    if combined.noc > config.noc_threshold:
        violations.append(
            f"Number of Children (NOC) {combined.noc} exceeds threshold {config.noc_threshold}"
        )
    if combined.lcom > config.lcom_threshold:
        violations.append(
            f"Lack of Cohesion of Methods (LCOM) {combined.lcom:.2f} exceeds threshold {config.lcom_threshold}"
        )
    if combined.rfc > config.rfc_threshold:
        violations.append(
            f"Response for a Class (RFC) {combined.rfc} exceeds threshold {config.rfc_threshold}"
        )
    if combined.wmc > config.wmc_threshold:
        violations.append(
            f"Weighted Methods per Class (WMC) {combined.wmc} exceeds threshold {config.wmc_threshold}"
        )
    return violations
