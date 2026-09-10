"""Owner hotspot profile adapter; detector rules stay in HotspotDetector."""
from pathlib import Path


def scan_hotspots(target: Path, limit: int, *, logical_root: Path | None = None):
    from Asgard.Heimdall.Security.Hotspots.models.hotspot_models import HotspotConfig
    from Asgard.Heimdall.Security.Hotspots.services.hotspot_detector import HotspotDetector
    from Asgard.Heimdall.cli.handlers._security_dispatch import load_heimdall_yml

    try:
        settings = load_heimdall_yml(target, strict=True)
    except Exception as error:
        return dict(state="incomplete", complete=False, truncated=False, findings=[],
                    errors=[{"code": "scan_configuration_error", "error_type": type(error).__name__}],
                    finding_kind="security_hotspot"), 1
    config = HotspotConfig(scan_path=target,
                          test_context_enabled=settings.get("test_context_enabled", True),
                          strict_scan_paths=settings.get("strict_scan_paths", []))
    report = HotspotDetector(config).scan(target, strict_io=True, logical_root=logical_root)
    truncated = len(report.hotspots) > limit
    complete = report.analysis_complete and not truncated
    return dict(state="complete" if complete else "incomplete", complete=complete,
                truncated=truncated, finding_kind="security_hotspot",
                findings=[hotspot.model_dump(mode="json") for hotspot in report.hotspots[:limit]],
                errors=[{"code": "scan_analysis_failure", **error} for error in report.analysis_errors],
                summary=dict(total_hotspots=report.total_hotspots,
                             high_priority=report.high_priority_count,
                             medium_priority=report.medium_priority_count,
                             low_priority=report.low_priority_count,
                             by_category=report.hotspots_by_category,
                             suppressed_by_context=report.suppressed_by_context_count,
                             files_analyzed=report.files_analyzed)), (0 if complete and not report.hotspots else 1)
