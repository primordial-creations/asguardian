"""
Freya Severity Mapper

Deterministic, data-driven mapping from each category's native severity
vocabulary to the universal Blocker/Critical/Major/Minor scale
(DEEPTHINK_04). Tables live in data, not logic, so pending research can
recalibrate them without code churn.

PROVISIONAL calibrations pending research:
    - SEO severity table     # PROVISIONAL pending RESEARCH_05
    - Links severity table   # PROVISIONAL pending RESEARCH_06
    - Images severity table  # PROVISIONAL pending RESEARCH_07
    - Console severity table # PROVISIONAL pending RESEARCH_10
"""

from typing import Any, Dict, List, Optional

from Asgard.Freya.Scoring.models.scoring_models import Finding, UniversalSeverity

_B = UniversalSeverity.BLOCKER
_C = UniversalSeverity.CRITICAL
_M = UniversalSeverity.MAJOR
_N = UniversalSeverity.MINOR

#: Per-category mapping from native severity strings to the universal scale.
#: Interactive-context escalation is applied on top (see escalate_for_criticality).
CATEGORY_SEVERITY_MAPS: Dict[str, Dict[str, UniversalSeverity]] = {
    "accessibility": {
        "critical": _C,   # BLOCKER when on an interactive element or a keyboard trap
        "serious": _M,    # CRITICAL when on an interactive element
        "moderate": _N,   # MAJOR when on an interactive element
        "minor": _N,
        "info": _N,
    },
    "visual": {
        "critical": _C,   # diff above hard threshold vs valid baseline
        "serious": _M,    # diff above soft threshold
        "moderate": _N,
        "minor": _N,      # metadata-only mismatch
    },
    "responsive": {
        "critical": _C,   # BLOCKER when overflow hides an interactive element
        "serious": _M,    # touch target below minimum, viewport meta issues
        "moderate": _N,
        "minor": _N,
    },
    "security": {
        "critical": _B,   # e.g. unsafe-inline + unsafe-eval together / no CSP on auth route
        "serious": _C,    # missing HSTS on https, CSP wildcard script-src
        "moderate": _M,   # other missing headers
        "minor": _N,      # informational header advice
    },
    "performance": {
        # Lab data cannot prove a Blocker (DEEPTHINK_03) - ceiling is CRITICAL.
        "critical": _C,   # hard-budget breach
        "serious": _M,    # soft-budget breach
        "moderate": _N,
        "minor": _N,
    },
    "links": {  # PROVISIONAL pending RESEARCH_06
        "critical": _C,   # 404 on internal link; BLOCKER when on nav/primary CTA
        "serious": _M,    # redirect chains, 4xx external
        "moderate": _N,   # anchors, slow links
        "minor": _N,
    },
    "seo": {  # PROVISIONAL pending RESEARCH_05 - no Blocker until research lands
        "critical": _C,   # page-level, e.g. accidental noindex
        "serious": _M,
        "moderate": _M,
        "minor": _N,
    },
    "console": {  # PROVISIONAL pending RESEARCH_10 - no Blocker until research lands
        "critical": _C,   # uncaught exception
        "serious": _M,
        "moderate": _M,
        "minor": _N,
    },
    "images": {  # PROVISIONAL pending RESEARCH_07 - no Blocker until research lands
        "critical": _C,
        "serious": _M,
        "moderate": _M,
        "minor": _N,
    },
}

#: Categories whose lab-only evidence can never justify a BLOCKER.
NO_BLOCKER_CATEGORIES = {"performance", "seo", "console", "images", "visual"}

#: WCAG criteria that indicate journey-failing keyboard traps -> BLOCKER.
KEYBOARD_TRAP_CRITERIA = {"2.1.2"}

_ESCALATION = {
    _N: _M,
    _M: _C,
    _C: _B,
    _B: _B,
}


def escalate_for_criticality(
    severity: UniversalSeverity,
    category: str,
    criticality: Optional[str] = None,
) -> UniversalSeverity:
    """Escalate a mapped severity one step when the element is interactive."""
    if criticality in ("primary_interactive", "interactive"):
        escalated = _ESCALATION[severity]
        if escalated == _B and category in NO_BLOCKER_CATEGORIES:
            return _C
        return escalated
    return severity


class SeverityMapper:
    """Maps native category severities to the universal scale."""

    def map(
        self,
        category: str,
        source_severity: Optional[str],
        check_id: str = "",
        criticality: Optional[str] = None,
        wcag_reference: Optional[str] = None,
    ) -> UniversalSeverity:
        """
        Map a native severity to the universal scale.

        Args:
            category: Freya category name (lowercase)
            source_severity: native severity string
            check_id: check identifier (used for special-case escalation)
            criticality: optional component criticality (Plan 02)
            wcag_reference: optional WCAG criterion for trap detection

        Returns:
            UniversalSeverity
        """
        table = CATEGORY_SEVERITY_MAPS.get(category.lower(), {})
        severity = table.get((source_severity or "").lower(), _N)

        if category.lower() == "accessibility":
            reference = (wcag_reference or "").strip()
            if reference in KEYBOARD_TRAP_CRITERIA or "keyboard trap" in check_id.lower():
                return _B

        return escalate_for_criticality(severity, category.lower(), criticality)

    def map_unified_result(self, result: Any) -> Optional[Finding]:
        """
        Convert a failed UnifiedTestResult into a Finding.

        Returns None for passing results.
        """
        if getattr(result, "passed", False):
            return None

        category_raw = getattr(result, "category", "")
        category = getattr(category_raw, "value", category_raw) or "unknown"

        severity_raw = getattr(result, "severity", None)
        source_severity = getattr(severity_raw, "value", severity_raw)

        wcag_reference = getattr(result, "wcag_reference", None)
        test_name = getattr(result, "test_name", "") or ""
        message = getattr(result, "message", "") or ""
        check_id = _build_check_id(category, test_name, wcag_reference, message)

        details = getattr(result, "details", None) or {}
        criticality = details.get("criticality") if isinstance(details, dict) else None
        needs_review = bool(details.get("needs_review")) if isinstance(details, dict) else False

        severity = self.map(
            category=str(category),
            source_severity=str(source_severity) if source_severity else None,
            check_id=f"{check_id} {message}",
            criticality=criticality,
            wcag_reference=wcag_reference,
        )

        return Finding(
            category=str(category),
            severity=severity,
            check_id=check_id,
            message=message,
            selector=getattr(result, "element_selector", None),
            source_severity=str(source_severity) if source_severity else None,
            needs_review=needs_review,
        )

    def map_unified_results(self, results: List[Any]) -> List[Finding]:
        """Convert a list of UnifiedTestResults into Findings (failures only)."""
        findings = []
        for result in results:
            finding = self.map_unified_result(result)
            if finding is not None:
                findings.append(finding)
        return findings


def _build_check_id(
    category: Any,
    test_name: str,
    wcag_reference: Optional[str],
    message: str,
) -> str:
    """Build a stable check identifier for a finding."""
    if wcag_reference:
        return f"wcag.{wcag_reference}"
    slug = test_name.lower().replace(" ", "_") or "check"
    return f"{category}.{slug}"


def issue_dicts_to_findings(
    issues: List[Dict[str, Any]],
    url: Optional[str] = None,
    mapper: Optional[SeverityMapper] = None,
    category: Optional[str] = None,
) -> List[Finding]:
    """
    Adapter: convert crawler issue dicts ({"type", "severity", "message", ...})
    into universal Findings.

    Args:
        issues: crawler issue dicts
        url: page URL
        mapper: optional shared SeverityMapper
        category: category of these issues; falls back to each dict's
            "category" key, then "accessibility"
    """
    mapper = mapper or SeverityMapper()
    findings = []
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        issue_category = str(category or issue.get("category") or "accessibility").lower()
        if issue_category not in CATEGORY_SEVERITY_MAPS:
            issue_category = "accessibility"
        issue_type = str(issue.get("type", "check"))
        severity = mapper.map(
            category=issue_category,
            source_severity=issue.get("severity"),
            check_id=f"{issue_type} {issue.get('message', '')}",
            wcag_reference=issue.get("wcag_reference"),
        )
        findings.append(Finding(
            category=issue_category,
            severity=severity,
            check_id=str(issue.get("check_id") or f"{issue_category}.{issue_type}"),
            message=str(issue.get("message", "")),
            url=url,
            selector=issue.get("selector") or issue.get("element_selector"),
            source_severity=str(issue.get("severity")) if issue.get("severity") else None,
        ))
    return findings


def _report_issues_to_findings(
    category: str,
    items: List[Any],
    url: Optional[str],
    check_prefix: str,
) -> List[Finding]:
    """Shared adapter for standalone subpackage report issue lists."""
    mapper = SeverityMapper()
    findings = []
    for item in items:
        severity_raw = getattr(item, "severity", None)
        source_severity = getattr(severity_raw, "value", severity_raw)
        message = (
            getattr(item, "description", None)
            or getattr(item, "message", None)
            or getattr(item, "text", None)
            or str(item)
        )
        issue_type = getattr(item, "issue_type", None) or getattr(item, "violation_type", None)
        issue_type = getattr(issue_type, "value", issue_type)
        check_id = f"{check_prefix}.{issue_type}" if issue_type else f"{check_prefix}.check"
        findings.append(Finding(
            category=category,
            severity=mapper.map(category, str(source_severity) if source_severity else None, check_id),
            check_id=check_id,
            message=str(message),
            url=url,
            selector=getattr(item, "element_selector", None),
            source_severity=str(source_severity) if source_severity else None,
        ))
    return findings


def security_report_to_findings(report: Any) -> List[Finding]:
    """Adapter: SecurityHeaderReport / CSPReport -> universal Findings."""
    url = getattr(report, "url", None)
    items = list(getattr(report, "issues", None) or getattr(report, "violations", None) or [])
    items += list(getattr(report, "missing_headers", None) or [])
    return _report_issues_to_findings("security", items, url, "security")


def performance_report_to_findings(report: Any) -> List[Finding]:
    """Adapter: PerformanceReport -> universal Findings."""
    url = getattr(report, "url", None)
    items = list(getattr(report, "issues", None) or [])
    return _report_issues_to_findings("performance", items, url, "performance")


def seo_report_to_findings(report: Any) -> List[Finding]:
    """Adapter: SEOReport -> universal Findings."""
    url = getattr(report, "url", None)
    items = list(getattr(report, "issues", None) or [])
    return _report_issues_to_findings("seo", items, url, "seo")


def console_report_to_findings(report: Any) -> List[Finding]:
    """Adapter: ConsoleReport -> universal Findings."""
    url = getattr(report, "url", None)
    items = list(getattr(report, "errors", None) or getattr(report, "messages", None) or [])
    return _report_issues_to_findings("console", items, url, "console")


def links_report_to_findings(report: Any) -> List[Finding]:
    """Adapter: LinkReport -> universal Findings."""
    url = getattr(report, "url", None)
    items = list(getattr(report, "broken_links", None) or [])
    items += list(getattr(report, "redirect_chains", None) or [])
    return _report_issues_to_findings("links", items, url, "links")


def images_report_to_findings(report: Any) -> List[Finding]:
    """Adapter: ImageReport -> universal Findings."""
    url = getattr(report, "url", None)
    items = list(getattr(report, "issues", None) or [])
    return _report_issues_to_findings("images", items, url, "images")
