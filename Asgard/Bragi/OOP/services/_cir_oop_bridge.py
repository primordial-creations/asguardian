"""
Heimdall OOP Analyzer - CIR bridge.

Wires ``Asgard/Bragi/OOP/services/cir_metrics.py`` (multi-language LCOM4/
CBO/RFC via the tree-sitter CIR) into ``OOPAnalyzer.analyze()`` so
``heimdall scan``'s OOP category reports real cohesion/coupling metrics for
non-Python languages instead of silently omitting them (N/A).

Python is excluded here — it keeps its dedicated ast-based path
(coupling_analyzer / inheritance_analyzer / cohesion_analyzer / rfc_analyzer)
since it's the reference-language implementation with DIT/NOC/WMC support
the CIR path doesn't have yet.
"""
from pathlib import Path
from typing import List

from Asgard.Bragi.OOP.models.oop_models import (
    ClassCohesionMetrics,
    ClassCouplingMetrics,
    ClassOOPMetrics,
    FileOOPAnalysis,
    OOPConfig,
)
from Asgard.Bragi.OOP.services._oop_merge import build_violations_list
from Asgard.Bragi.OOP.services.cir_metrics import CIRClassMetrics, analyze_path

#: Extensions for every language the CIR builder supports besides Python
#: (Asgard/Bragi/Architecture/cir/builder.py: python, java, javascript,
#: typescript, go, csharp, ruby, php, rust, cpp). Files in unsupported
#: languages, or whose grammar isn't installed, are silently skipped by
#: cir_metrics.analyze_path — no fabricated metrics.
CIR_OOP_EXTENSIONS = [
    ".java", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".go",
    ".cs", ".rb", ".php", ".rs", ".cpp", ".cxx", ".cc", ".hpp", ".hxx",
]


def _relative_path(file_path: str, scan_root: Path) -> str:
    try:
        return str(Path(file_path).resolve().relative_to(scan_root))
    except ValueError:
        return Path(file_path).name


def _to_class_oop_metrics(m: CIRClassMetrics, relative_path: str, config: OOPConfig) -> ClassOOPMetrics:
    # Henderson-Sellers-style density approximation of true LCOM4's
    # component count, purely so the existing 0..1 `lcom` severity
    # threshold (config.lcom_threshold) has something meaningful to compare
    # against; the authoritative, honest value is `lcom4` (component count).
    if m.method_count > 1:
        lcom_density = min(1.0, max(0.0, (m.lcom4 - 1) / (m.method_count - 1)))
    else:
        lcom_density = 0.0

    combined = ClassOOPMetrics(
        class_name=m.class_name,
        file_path=m.file_path,
        relative_path=relative_path,
        line_number=0,
        cbo=m.cbo,
        lcom=lcom_density,
        lcom4=float(m.lcom4),
        rfc=m.rfc,
        method_count=m.method_count,
        language=m.language,
        metrics_source="cir",
    )
    combined.coupling_level = ClassCouplingMetrics.calculate_coupling_level(combined.cbo)
    combined.cohesion_level = ClassCohesionMetrics.calculate_cohesion_level(combined.lcom)
    combined.overall_severity = combined.calculate_overall_severity(config)
    return combined


def build_cir_file_analyses(scan_path: Path, config: OOPConfig) -> List[FileOOPAnalysis]:
    """Return one :class:`FileOOPAnalysis` per non-Python file with classes.

    Returns ``[]`` when no non-Python CIR-supported files exist under
    *scan_path*, or none of their grammars are available.
    """
    results = analyze_path(scan_path, extensions=CIR_OOP_EXTENSIONS)

    file_analyses: List[FileOOPAnalysis] = []
    for file_path, metrics_list in results.items():
        if not metrics_list:
            continue
        relative_path = _relative_path(file_path, scan_path)
        file_analysis = FileOOPAnalysis(file_path=file_path, relative_path=relative_path)
        for m in metrics_list:
            combined = _to_class_oop_metrics(m, relative_path, config)
            violations = build_violations_list(combined, config)
            combined.violations = violations
            file_analysis.add_class(combined)
            if violations:
                file_analysis.add_violation(combined)
        file_analyses.append(file_analysis)

    return file_analyses
