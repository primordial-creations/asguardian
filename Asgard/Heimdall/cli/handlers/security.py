import argparse
import json
from pathlib import Path

from Asgard.Heimdall.Security.models.security_models import (
    SecurityScanConfig,
    SecuritySeverity,
)
from Asgard.Heimdall.Security.services.static_security_service import StaticSecurityService
from Asgard.Heimdall.Security.Hotspots.models.hotspot_models import HotspotConfig, ReviewPriority
from Asgard.Heimdall.Security.Hotspots.services.hotspot_detector import HotspotDetector
from Asgard.Heimdall.Security.Compliance.models.compliance_models import ComplianceConfig
from Asgard.Heimdall.Security.Compliance.services.compliance_reporter import ComplianceReporter
from Asgard.Heimdall.Security.services.static_security_service import StaticSecurityService as _StaticSecuritySvc


def run_security_analysis(args: argparse.Namespace, verbose: bool = False, analysis_type: str = "all") -> int:
    scan_path = Path(args.path).resolve()

    if not scan_path.exists():
        print(f"Error: Path does not exist: {scan_path}")
        return 1

    exclude_patterns = list(args.exclude) if args.exclude else []

    severity_map = {
        "info": SecuritySeverity.INFO,
        "low": SecuritySeverity.LOW,
        "medium": SecuritySeverity.MEDIUM,
        "high": SecuritySeverity.HIGH,
        "critical": SecuritySeverity.CRITICAL,
    }
    min_severity = severity_map.get(args.severity, SecuritySeverity.LOW)

    config = SecurityScanConfig(
        scan_path=scan_path,
        scan_type=analysis_type,
        min_severity=min_severity,
        exclude_patterns=exclude_patterns,
        output_format=args.format,
        verbose=verbose,
    )

    try:
        service = StaticSecurityService(config)
        result = service.analyze(scan_path)
        report = service.generate_report(result, args.format)
        print(report)
        return 1 if result.has_issues else 0

    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1


def run_hotspots_analysis(args: argparse.Namespace, verbose: bool = False) -> int:
    scan_path = Path(args.path).resolve()

    if not scan_path.exists():
        print(f"Error: Path does not exist: {scan_path}")
        return 1

    exclude_patterns = list(args.exclude) if args.exclude else []
    priority_str = getattr(args, "priority", "low")
    try:
        min_priority = ReviewPriority(priority_str)
    except ValueError:
        min_priority = ReviewPriority.LOW

    config = HotspotConfig(
        scan_path=scan_path,
        min_priority=min_priority,
        include_tests=getattr(args, "include_tests", True),
        exclude_patterns=exclude_patterns if exclude_patterns else [
            "__pycache__", "node_modules", ".git", ".venv", "venv", "build", "dist",
        ],
        output_format=getattr(args, "format", "text"),
    )

    try:
        detector = HotspotDetector(config)
        report = detector.scan(scan_path)

        if args.format == "json":
            output = {
                "scan_info": {
                    "scan_path": report.scan_path,
                    "scanned_at": report.scanned_at.isoformat(),
                    "duration_seconds": report.scan_duration_seconds,
                },
                "summary": {
                    "total_hotspots": report.total_hotspots,
                    "high_priority": report.high_priority_count,
                    "medium_priority": report.medium_priority_count,
                    "low_priority": report.low_priority_count,
                    "by_category": report.hotspots_by_category,
                },
                "hotspots": [
                    {
                        "file_path": h.file_path,
                        "line_number": h.line_number,
                        "category": h.category,
                        "review_priority": h.review_priority,
                        "title": h.title,
                        "description": h.description,
                        "code_snippet": h.code_snippet,
                        "review_guidance": h.review_guidance,
                        "owasp_category": h.owasp_category,
                        "cwe_id": h.cwe_id,
                    }
                    for h in report.hotspots
                ],
            }
            print(json.dumps(output, indent=2))
        else:
            lines = [
                "",
                "=" * 70,
                "  HEIMDALL SECURITY HOTSPOT REPORT",
                "=" * 70,
                "",
                f"  Scan Path:      {report.scan_path}",
                f"  Scanned At:     {report.scanned_at.strftime('%Y-%m-%d %H:%M:%S')}",
                f"  Duration:       {report.scan_duration_seconds:.2f}s",
                "",
                f"  Total Hotspots: {report.total_hotspots}",
                f"  [HIGH]:         {report.high_priority_count}",
                f"  [MEDIUM]:       {report.medium_priority_count}",
                f"  [LOW]:          {report.low_priority_count}",
                "",
            ]
            if report.hotspots:
                lines.extend(["-" * 70, "  HOTSPOTS", "-" * 70, ""])
                for h in report.hotspots:
                    priority_label = str(h.review_priority).upper()
                    lines.append(f"  [{priority_label}] {h.title}")
                    lines.append(f"  File: {h.file_path}:{h.line_number}")
                    if h.owasp_category:
                        lines.append(f"  OWASP: {h.owasp_category}  CWE: {h.cwe_id or 'N/A'}")
                    if verbose:
                        lines.append(f"  Description: {h.description}")
                        lines.append(f"  Guidance: {h.review_guidance}")
                    if h.code_snippet:
                        lines.append(f"  Code: {h.code_snippet}")
                    lines.append("")
            else:
                lines.extend(["  No security hotspots detected.", ""])
            lines.append("=" * 70)
            print("\n".join(lines))

        return 1 if report.high_priority_count > 0 else 0

    except Exception as e:
        print(f"Error: {e}")
        return 1


def run_compliance_analysis(args: argparse.Namespace, verbose: bool = False) -> int:
    scan_path = Path(args.path).resolve()

    if not scan_path.exists():
        print(f"Error: Path does not exist: {scan_path}")
        return 1

    include_owasp = not getattr(args, "no_owasp", False)
    include_cwe = not getattr(args, "no_cwe", False)

    config = ComplianceConfig(
        include_owasp=include_owasp,
        include_cwe=include_cwe,
    )

    try:
        sec_config = SecurityScanConfig(scan_path=scan_path)
        sec_service = _StaticSecuritySvc(sec_config)
        security_report = sec_service.scan(str(scan_path))

        hotspot_detector = HotspotDetector()
        hotspot_report = hotspot_detector.scan(scan_path)

        reporter = ComplianceReporter(config)

        if args.format == "json":
            output = {}
            if include_owasp:
                owasp = reporter.generate_owasp_report(security_report, hotspot_report, str(scan_path))
                output["owasp"] = {
                    "version": owasp.owasp_version,
                    "overall_grade": owasp.overall_grade,
                    "total_findings_mapped": owasp.total_findings_mapped,
                    "categories": {
                        cat_id: {
                            "name": cat.category_name,
                            "grade": cat.grade,
                            "findings": cat.findings_count,
                            "critical": cat.critical_count,
                            "high": cat.high_count,
                            "medium": cat.medium_count,
                            "low": cat.low_count,
                        }
                        for cat_id, cat in sorted(owasp.categories.items())
                    },
                }
            if include_cwe:
                cwe = reporter.generate_cwe_report(security_report, hotspot_report, str(scan_path))
                output["cwe"] = {
                    "version": cwe.cwe_version,
                    "overall_grade": cwe.overall_grade,
                    "top_25": {
                        cwe_id: {
                            "name": entry.category_name,
                            "grade": entry.grade,
                            "findings": entry.findings_count,
                        }
                        for cwe_id, entry in sorted(cwe.top_25_coverage.items())
                        if entry.findings_count > 0
                    },
                }
            print(json.dumps(output, indent=2))
        else:
            lines = [
                "",
                "=" * 70,
                "  HEIMDALL COMPLIANCE REPORT",
                "=" * 70,
                "",
                f"  Scan Path: {scan_path}",
                "",
            ]

            if include_owasp:
                owasp = reporter.generate_owasp_report(security_report, hotspot_report, str(scan_path))
                lines.extend([
                    f"  OWASP Top 10 (2021) - Overall Grade: {owasp.overall_grade}",
                    "-" * 70,
                ])
                for cat_id, cat in sorted(owasp.categories.items()):
                    marker = "  " if cat.findings_count == 0 else "! "
                    lines.append(
                        f"  {marker}{cat_id} [{cat.grade}] {cat.category_name} "
                        f"({cat.findings_count} finding(s))"
                    )
                lines.append("")

            if include_cwe:
                cwe = reporter.generate_cwe_report(security_report, hotspot_report, str(scan_path))
                lines.extend([
                    f"  CWE Top 25 (2024) - Overall Grade: {cwe.overall_grade}",
                    "-" * 70,
                ])
                flagged = [
                    (cwe_id, entry)
                    for cwe_id, entry in sorted(cwe.top_25_coverage.items())
                    if entry.findings_count > 0
                ]
                if flagged:
                    for cwe_id, entry in flagged:
                        lines.append(
                            f"  ! {cwe_id} [{entry.grade}] {entry.category_name} "
                            f"({entry.findings_count} finding(s))"
                        )
                else:
                    lines.append("  No CWE Top 25 findings detected.")
                lines.append("")

            lines.append("=" * 70)
            print("\n".join(lines))

        return 0

    except Exception as e:
        print(f"Error: {e}")
        return 1
