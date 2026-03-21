"""
Heimdall Architecture Analyzer - JSON report generation.
"""

import json

from Asgard.Heimdall.Architecture.models.architecture_models import ArchitectureReport
from Asgard.Heimdall.Architecture.services._arch_reporter_text import generate_recommendations


def generate_json_report(result: ArchitectureReport) -> str:
    """Generate JSON format report."""
    output = {
        "scan_path": result.scan_path,
        "scanned_at": result.scanned_at.isoformat(),
        "scan_duration_seconds": result.scan_duration_seconds,
        "summary": {
            "total_violations": result.total_violations,
            "total_patterns": result.total_patterns,
            "is_healthy": result.is_healthy,
        },
    }

    if result.solid_report:
        output["solid"] = {
            "total_classes": result.solid_report.total_classes,
            "total_violations": result.solid_report.total_violations,
            "violations": [
                {
                    "principle": v.principle.value,
                    "class_name": v.class_name,
                    "file_path": v.file_path,
                    "line_number": v.line_number,
                    "message": v.message,
                    "severity": v.severity.value,
                }
                for v in result.solid_report.violations
            ],
        }

    if result.layer_report:
        output["layers"] = {
            "is_valid": result.layer_report.is_valid,
            "total_violations": result.layer_report.total_violations,
            "layers": [
                {
                    "name": l.name,
                    "patterns": l.patterns,
                    "allowed_dependencies": l.allowed_dependencies,
                }
                for l in result.layer_report.layers
            ],
            "violations": [
                {
                    "source_module": v.source_module,
                    "source_layer": v.source_layer,
                    "target_module": v.target_module,
                    "target_layer": v.target_layer,
                    "message": v.message,
                }
                for v in result.layer_report.violations
            ],
        }

    if result.pattern_report:
        output["patterns"] = {
            "total_patterns": result.pattern_report.total_patterns,
            "patterns": [
                {
                    "pattern_type": p.pattern_type.value,
                    "class_name": p.class_name,
                    "file_path": p.file_path,
                    "confidence": p.confidence,
                }
                for p in result.pattern_report.patterns
            ],
        }

    if result.hexagonal_report:
        output["hexagonal"] = {
            "is_valid": result.hexagonal_report.is_valid,
            "total_violations": result.hexagonal_report.total_violations,
            "ports": [
                {
                    "name": p.name,
                    "direction": p.direction.value,
                    "abstract_methods": p.abstract_methods,
                }
                for p in result.hexagonal_report.ports
            ],
            "adapters": [
                {
                    "name": a.name,
                    "implements_port": a.implements_port,
                    "zone": a.zone.value,
                }
                for a in result.hexagonal_report.adapters
            ],
            "violations": [
                {
                    "source_zone": v.source_zone.value,
                    "target_zone": v.target_zone.value,
                    "message": v.message,
                    "severity": v.severity.value,
                }
                for v in result.hexagonal_report.violations
            ],
        }

    if result.suggestion_report:
        output["pattern_suggestions"] = {
            "total_suggestions": result.suggestion_report.total_suggestions,
            "suggestions": [
                {
                    "pattern_type": s.pattern_type.value,
                    "class_name": s.class_name,
                    "file_path": s.file_path,
                    "line_number": s.line_number,
                    "confidence": s.confidence,
                    "rationale": s.rationale,
                    "signals": s.signals,
                    "benefit": s.benefit,
                }
                for s in result.suggestion_report.suggestions
            ],
        }

    output["recommendations"] = generate_recommendations(result)
    return json.dumps(output, indent=2)
