"""
Bragi Report Extractors

One place that turns loosely-typed analyzer report objects (DebtReport,
quality reports, SecurityReport) into typed FileMetricBundles for the
composite score engine, recording which sources were actually present
(feeding ScoreConfidence - Plan 01 section 3.5).
"""

from typing import Any, Dict, List, Optional, Tuple

from Asgard.Bragi.Ratings.models._scoring_models import FileMetricBundle

_SEVERITY_KEYS = ("blocker", "critical", "high", "medium", "low", "info")

SOURCE_DEBT = "debt_report"
SOURCE_QUALITY = "quality_report"
SOURCE_SECURITY = "security_report"


def _severity_of(obj: Any) -> Optional[str]:
    severity = getattr(obj, "severity", None)
    if severity is None:
        return None
    text = str(severity.value if hasattr(severity, "value") else severity).lower()
    return text if text in _SEVERITY_KEYS else "medium"


def _file_of(obj: Any) -> str:
    return str(getattr(obj, "file_path", "") or getattr(obj, "file", "") or "")


def _iter_security_findings(security_report: Any) -> List[Any]:
    """Collect findings from the known SecurityReport shapes."""
    findings: List[Any] = []
    for attr in ("vulnerability_findings", "vulnerabilities", "findings"):
        found = getattr(security_report, attr, None) or []
        if found:
            findings.extend(found)
            break
    nested = getattr(security_report, "vulnerability_report", None)
    if nested is not None:
        for attr in ("findings", "vulnerabilities"):
            found = getattr(nested, attr, None) or []
            if found:
                findings.extend(found)
                break
    secrets = getattr(security_report, "secrets_report", None)
    if secrets is not None:
        findings.extend(getattr(secrets, "findings", None) or [])
    return findings


def extract_bundles(
    debt_report: Any = None,
    quality_report: Any = None,
    security_report: Any = None,
) -> Tuple[List[FileMetricBundle], FileMetricBundle]:
    """
    Build (per-file bundles, project-level bundle) from the supplied reports.

    Sources that were not supplied are recorded in sources_missing on every
    bundle so the engine can renormalize weights and annotate confidence.
    """
    present: List[str] = []
    missing: List[str] = []
    per_file_counts: Dict[str, Dict[str, int]] = {}
    project_counts: Dict[str, int] = {}
    security_blocker_files: Dict[str, str] = {}
    has_blocker = False
    blocker_desc = ""

    def _tally(file_path: str, severity: Optional[str]) -> None:
        sev = severity or "medium"
        counts = per_file_counts.setdefault(file_path or "<unknown>", {})
        counts[sev] = counts.get(sev, 0) + 1
        project_counts[sev] = project_counts.get(sev, 0) + 1

    if debt_report is not None:
        present.append(SOURCE_DEBT)
        for item in getattr(debt_report, "debt_items", None) or []:
            _tally(_file_of(item), _severity_of(item))
    else:
        missing.append(SOURCE_DEBT)

    if quality_report is not None:
        present.append(SOURCE_QUALITY)
        for smell in getattr(quality_report, "detected_smells", None) or []:
            _tally(_file_of(smell), _severity_of(smell))
    else:
        missing.append(SOURCE_QUALITY)

    if security_report is not None:
        present.append(SOURCE_SECURITY)
        for finding in _iter_security_findings(security_report):
            severity = _severity_of(finding)
            _tally(_file_of(finding), severity)
            # The blocker cap is reserved for Blocker/Critical BUGS and
            # VULNERABILITIES (Plan 01 section 3.3) - a critical *debt* item
            # (e.g. very high complexity) is capped at D by the complexity
            # gate, never at E by this one.
            if severity in ("blocker", "critical"):
                description = (
                    f"{severity} security finding: "
                    f"{str(getattr(finding, 'description', '') or getattr(finding, 'message', '') or 'unnamed')[:80]}"
                )
                security_blocker_files.setdefault(_file_of(finding) or "<unknown>", description)
                if not has_blocker:
                    has_blocker = True
                    blocker_desc = description
    else:
        missing.append(SOURCE_SECURITY)

    file_bundles: List[FileMetricBundle] = []
    for file_path, counts in sorted(per_file_counts.items()):
        file_blocker = security_blocker_files.get(file_path, "")
        file_bundles.append(FileMetricBundle(
            file_path=file_path,
            bug_counts_by_severity=counts,
            has_blocker_issue=bool(file_blocker),
            blocker_description=file_blocker,
            sources_present=present,
            sources_missing=missing,
        ))

    tdr: Optional[float] = None
    if debt_report is not None:
        tdr = getattr(debt_report, "tdr_percent", None)

    project_bundle = FileMetricBundle(
        file_path="",
        loc=int(getattr(debt_report, "total_lines_of_code", 0) or 0) if debt_report is not None else 0,
        bug_counts_by_severity=project_counts if present else None,
        debt_ratio_percent=tdr,
        has_blocker_issue=has_blocker,
        blocker_description=blocker_desc,
        sources_present=present,
        sources_missing=missing,
    )
    return file_bundles, project_bundle
