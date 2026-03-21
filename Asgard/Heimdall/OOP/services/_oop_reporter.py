"""
Heimdall OOP Analyzer - Report Generators

Text, JSON, and Markdown report generation for OOPReport.
"""

import json

from Asgard.Heimdall.OOP.models.oop_models import OOPReport


def generate_text_report(result: OOPReport) -> str:
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
    lines.append(
        f"    Coupling Between Objects (CBO):  {result.cbo_threshold}"
        f"    Depth of Inheritance Tree (DIT): {result.dit_threshold}"
        f"    Number of Children (NOC): {result.noc_threshold}"
    )
    lines.append(
        f"    Lack of Cohesion of Methods (LCOM): {result.lcom_threshold}"
        f"  Response for a Class (RFC): {result.rfc_threshold}"
        f"   Weighted Methods per Class (WMC): {result.wmc_threshold}"
    )
    lines.append("")

    if result.has_violations:
        lines.append("-" * 70)
        lines.append("  VIOLATIONS")
        lines.append("-" * 70)
        lines.append("")

        for v in result.violations:
            lines.append(f"  [{v.overall_severity.value.upper()}] {v.class_name}")
            lines.append(f"    File: {v.relative_path}:{v.line_number}")
            lines.append(
                f"    Coupling Between Objects (CBO)={v.cbo}"
                f" Depth of Inheritance Tree (DIT)={v.dit}"
                f" Lack of Cohesion of Methods (LCOM)={v.lcom:.2f}"
                f" Response for a Class (RFC)={v.rfc}"
                f" Weighted Methods per Class (WMC)={v.wmc}"
            )
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
    lines.append(
        f"    Coupling Between Objects (CBO):  {result.average_cbo:.2f}"
        f"    Depth of Inheritance Tree (DIT): {result.average_dit:.2f}"
    )
    lines.append(
        f"    Lack of Cohesion of Methods (LCOM): {result.average_lcom:.2f}"
        f"  Response for a Class (RFC): {result.average_rfc:.2f}"
        f"  Weighted Methods per Class (WMC): {result.average_wmc:.2f}"
    )
    lines.append("")
    lines.append("  Maximums:")
    lines.append(
        f"    Coupling Between Objects (CBO):  {result.max_cbo}"
        f"    Depth of Inheritance Tree (DIT): {result.max_dit}"
    )
    lines.append(
        f"    Lack of Cohesion of Methods (LCOM): {result.max_lcom:.2f}"
        f"  Response for a Class (RFC): {result.max_rfc}"
        f"  Weighted Methods per Class (WMC): {result.max_wmc}"
    )
    lines.append("")
    lines.append("=" * 70)

    return "\n".join(lines)


def generate_json_report(result: OOPReport) -> str:
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


def generate_markdown_report(result: OOPReport) -> str:
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
