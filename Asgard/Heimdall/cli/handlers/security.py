import argparse
import json
from pathlib import Path

from Asgard.Heimdall.Security.models.security_models import (
    SecurityScanConfig,
    SecuritySeverity,
)
from Asgard.Heimdall.Security.models.security_models_base import (
    VulnerabilityFinding,
    VulnerabilityType,
)
from Asgard.Heimdall.Security.models.security_models_findings import VulnerabilityReport
from Asgard.Heimdall.Security.services.static_security_service import StaticSecurityService
from Asgard.Heimdall.Security.Hotspots.models.hotspot_models import HotspotConfig, ReviewPriority
from Asgard.Heimdall.Security.Hotspots.services.hotspot_detector import HotspotDetector
from Asgard.Heimdall.Security.Compliance.models.compliance_models import ComplianceConfig
from Asgard.Heimdall.Security.Compliance.services.compliance_reporter import ComplianceReporter
from Asgard.Heimdall.Security.services.static_security_service import StaticSecurityService as _StaticSecuritySvc
from Asgard.Heimdall.cli.handlers._security_dispatch import (
    count_lines_of_code,
    format_dispatch_text,
    load_heimdall_yml,
    run_dispatch_scan,
)

#: Best-effort rule_id/message substring -> VulnerabilityType mapping for
#: DispatchEngine findings folded into StaticSecurityService's
#: VulnerabilityReport (see `_dispatch_entry_to_finding`).
_VULN_TYPE_HINTS = (
    ("sql", VulnerabilityType.SQL_INJECTION),
    ("command", VulnerabilityType.COMMAND_INJECTION),
    ("os_command", VulnerabilityType.COMMAND_INJECTION),
    ("exec", VulnerabilityType.COMMAND_INJECTION),
    ("xss", VulnerabilityType.XSS),
    ("html", VulnerabilityType.XSS),
    ("path", VulnerabilityType.PATH_TRAVERSAL),
    ("traversal", VulnerabilityType.PATH_TRAVERSAL),
    ("pickle", VulnerabilityType.INSECURE_DESERIALIZATION),
    ("deserial", VulnerabilityType.INSECURE_DESERIALIZATION),
    ("yaml", VulnerabilityType.INSECURE_DESERIALIZATION),
    ("ssrf", VulnerabilityType.SSRF),
    ("http_request", VulnerabilityType.SSRF),
    ("redirect", VulnerabilityType.OPEN_REDIRECT),
    ("hash", VulnerabilityType.WEAK_HASH),
    ("random", VulnerabilityType.INSECURE_RANDOM),
    ("crypto", VulnerabilityType.INSECURE_CRYPTO),
    ("secret", VulnerabilityType.HARDCODED_SECRET),
    ("auth", VulnerabilityType.MISSING_AUTH),
)

#: Qualitative confidence bucket labels (see BUCKET_LABELS in
#: _security_dispatch.py) mapped back to a representative float within
#: their band, so `score_weight()`/`confidence_bucket()` treat them
#: identically to how they were originally classified. dispatch entries
#: only ever expose the qualitative label, never the raw probability.
_BUCKET_TO_CONFIDENCE = {
    "Certain": 0.90,
    "Probable": 0.65,
    "Possible": 0.35,
    "Unlikely": 0.10,
}


def _dispatch_entry_to_finding(entry: dict) -> VulnerabilityFinding:
    """Convert a run_dispatch_scan() display entry into a real finding so
    it flows through VulnerabilityReport.calculate_totals() -- the single
    source of truth for both issue counts and the security score -- instead
    of being hand-tallied into counters the score never sees."""
    rule_id = str(entry.get("rule_id", ""))
    message = str(entry.get("message", ""))
    haystack = f"{rule_id} {message}".lower()
    vuln_type = VulnerabilityType.IMPROPER_INPUT_VALIDATION
    for needle, mapped in _VULN_TYPE_HINTS:
        if needle in haystack:
            vuln_type = mapped
            break
    confidence = _BUCKET_TO_CONFIDENCE.get(str(entry.get("confidence")), 0.65)
    return VulnerabilityFinding(
        file_path=entry["file_path"],
        line_number=int(entry["line"]),
        vulnerability_type=vuln_type,
        severity=str(entry["severity"]).lower(),
        title=rule_id or "Dispatch engine finding",
        description=message,
        cwe_id=entry.get("cwe_id") or None,
        confidence=confidence,
    )


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
        scoring_version=getattr(args, "scoring", "v1"),
        enable_network=bool(getattr(args, "online", False)),
        nvd_fallback=bool(getattr(args, "nvd_fallback", False)),
    )

    # .heimdall.yml zero-config plumbing (test context + strict paths).
    yml = load_heimdall_yml(scan_path)
    test_context_enabled = bool(yml.get("test_context_enabled", True))
    strict_scan_paths = list(yml.get("strict_scan_paths", []) or [])
    include_test_context = bool(getattr(args, "include_test_context", False))

    try:
        service = StaticSecurityService(config)
        result = service.analyze(scan_path)

        # LOC for v2 size normalization; recompute the dual-reported scores.
        result.total_lines_of_code = count_lines_of_code(
            scan_path, exclude_patterns
        )
        result.calculate_totals()

        # Route the full scan through the layered dispatch engine.
        dispatch_entries = []
        if analysis_type == "all":
            dispatch_entries = run_dispatch_scan(
                scan_path,
                exclude_patterns=exclude_patterns,
                include_test_context=include_test_context,
                test_context_enabled=test_context_enabled,
                strict_scan_paths=strict_scan_paths,
            )

        # StaticSecurityService's totals (and hence the summary header:
        # "Total Issues" / "Critical" / "security_score" / "is_passing")
        # never see the DispatchEngine's findings -- those were previously
        # only appended as a separate text/JSON section below, so the
        # header undercounted and the score stayed a false 100.
        #
        # run_dispatch_scan() also re-scans .py files (it isn't restricted
        # to non-Python), so anything it finds there is *already* counted
        # by StaticSecurityService -- folding those back in would double
        # count a single Python finding. Restrict to non-.py so this is a
        # disjoint union, matching the same filter used for `heimdall scan`
        # (scan_steps_1_6.py).
        multilang_entries = [
            e for e in dispatch_entries
            if not str(e["file_path"]).endswith(".py")
        ]
        if multilang_entries:
            if result.vulnerability_report is None:
                result.vulnerability_report = VulnerabilityReport(
                    scan_path=str(scan_path)
                )
            result.vulnerability_report.findings.extend(
                _dispatch_entry_to_finding(e) for e in multilang_entries
            )
            # Single recompute over ALL findings (StaticSecurityService's
            # plus the newly-added multilang ones): counts, legacy_score,
            # security_score_v2, and security_score all come out mutually
            # consistent -- no separate hand-tally that the score misses.
            result.calculate_totals()

        report = service.generate_report(result, args.format)
        if args.format == "json":
            try:
                payload = json.loads(report)
                payload["scoring"] = {
                    "version": config.scoring_version,
                    "legacy_score": result.legacy_score,
                    "security_score_v2": result.security_score_v2,
                    "total_lines_of_code": result.total_lines_of_code,
                }
                if dispatch_entries:
                    payload["dispatch_findings"] = dispatch_entries
                report = json.dumps(payload, indent=2, default=str)
            except (json.JSONDecodeError, TypeError):
                pass
            print(report)
        else:
            print(report)
            if dispatch_entries:
                print(format_dispatch_text(dispatch_entries))
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

    yml = load_heimdall_yml(scan_path)
    config = HotspotConfig(
        scan_path=scan_path,
        min_priority=min_priority,
        include_tests=getattr(args, "include_tests", True),
        exclude_patterns=exclude_patterns if exclude_patterns else [
            "__pycache__", "node_modules", ".git", ".venv", "venv", "build", "dist",
        ],
        output_format=getattr(args, "format", "text"),
        test_context_enabled=bool(yml.get("test_context_enabled", True))
        and not getattr(args, "include_test_context", False),
        strict_scan_paths=list(yml.get("strict_scan_paths", []) or []),
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
