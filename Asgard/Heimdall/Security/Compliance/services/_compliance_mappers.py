"""
Heimdall Compliance Mapper Helpers

Standalone functions for mapping security findings to OWASP and CWE categories.
"""

from typing import Dict, List

from Asgard.Heimdall.Security.Compliance.models.compliance_models import CategoryCompliance


_VULN_TO_OWASP: Dict[str, List[str]] = {
    "sql_injection": ["A03"],
    "command_injection": ["A03"],
    "xss": ["A03"],
    "path_traversal": ["A01"],
    "insecure_crypto": ["A02"],
    "insecure_deserialization": ["A08"],
    "ssrf": ["A10"],
    "missing_auth": ["A07"],
    "hardcoded_secret": ["A02"],
    "insecure_random": ["A02"],
    "weak_hash": ["A02"],
    "open_redirect": ["A01"],
    "improper_input_validation": ["A03"],
    "template_injection": ["A03"],
}

_VULN_TO_CWE: Dict[str, List[str]] = {
    "sql_injection": ["CWE-89"],
    "command_injection": ["CWE-78", "CWE-77"],
    "xss": ["CWE-79"],
    "path_traversal": ["CWE-22"],
    "insecure_crypto": ["CWE-327"],
    "insecure_deserialization": ["CWE-502"],
    "ssrf": ["CWE-918"],
    "missing_auth": ["CWE-306"],
    "hardcoded_secret": ["CWE-798"],
    "insecure_random": ["CWE-338"],
    "weak_hash": ["CWE-327"],
    "open_redirect": ["CWE-601"],
    "improper_input_validation": ["CWE-20"],
    "template_injection": ["CWE-94"],
}

_HOTSPOT_TO_OWASP: Dict[str, List[str]] = {
    "cookie_config": ["A07"],
    "crypto_usage": ["A02"],
    "dynamic_execution": ["A03"],
    "regex_dos": ["A04"],
    "xxe": ["A05"],
    "insecure_deserialization": ["A08"],
    "ssrf": ["A10"],
    "insecure_random": ["A02"],
    "permission_check": ["A01"],
    "tls_verification": ["A02"],
}

_HOTSPOT_TO_CWE: Dict[str, List[str]] = {
    "cookie_config": ["CWE-287"],
    "crypto_usage": ["CWE-327"],
    "dynamic_execution": ["CWE-94"],
    "regex_dos": [],
    "xxe": [],
    "insecure_deserialization": ["CWE-502"],
    "ssrf": ["CWE-918"],
    "insecure_random": ["CWE-338"],
    "permission_check": ["CWE-269"],
    "tls_verification": [],
}


def get_finding_severity(finding) -> str:
    """Extract the normalized severity string from a finding object."""
    sev = getattr(finding, "severity", None)
    if sev is None:
        return "low"
    return str(sev).lower()


def get_finding_description(finding) -> str:
    """Build a short description string for a finding."""
    title = getattr(finding, "title", None) or getattr(finding, "description", None) or ""
    file_path = getattr(finding, "file_path", "")
    line_number = getattr(finding, "line_number", "")
    if file_path and line_number:
        return f"{title} ({file_path}:{line_number})"
    return title


def add_finding_to_category(
    category: CategoryCompliance, severity: str, description: str
) -> None:
    """Increment the finding counts in a CategoryCompliance object."""
    category.findings_count += 1
    if severity == "critical":
        category.critical_count += 1
    elif severity == "high":
        category.high_count += 1
    elif severity == "medium":
        category.medium_count += 1
    else:
        category.low_count += 1
    if description:
        category.mapped_findings.append(description)


def map_vulnerabilities_to_owasp(
    findings: List, categories: Dict[str, CategoryCompliance]
) -> int:
    """Map vulnerability findings to OWASP categories."""
    count = 0
    for finding in findings:
        vuln_type = str(getattr(finding, "vulnerability_type", "") or "").lower()
        owasp_cats = _VULN_TO_OWASP.get(vuln_type, [])
        severity = get_finding_severity(finding)
        desc = get_finding_description(finding)
        for cat_id in owasp_cats:
            if cat_id in categories:
                add_finding_to_category(categories[cat_id], severity, desc)
                count += 1
    return count


def map_secrets_to_owasp(
    findings: List, categories: Dict[str, CategoryCompliance]
) -> int:
    """Map secret findings to A02."""
    count = 0
    for finding in findings:
        severity = get_finding_severity(finding)
        desc = get_finding_description(finding)
        if "A02" in categories:
            add_finding_to_category(categories["A02"], severity, desc)
            count += 1
    return count


def map_crypto_to_owasp(
    findings: List, categories: Dict[str, CategoryCompliance]
) -> int:
    """Map crypto findings to A02."""
    count = 0
    for finding in findings:
        severity = get_finding_severity(finding)
        desc = get_finding_description(finding)
        if "A02" in categories:
            add_finding_to_category(categories["A02"], severity, desc)
            count += 1
    return count


def map_dependencies_to_owasp(
    findings: List, categories: Dict[str, CategoryCompliance]
) -> int:
    """Map high/critical dependency vulnerabilities to A06."""
    count = 0
    for finding in findings:
        severity = get_finding_severity(finding)
        if severity in ("critical", "high"):
            desc = get_finding_description(finding)
            if "A06" in categories:
                add_finding_to_category(categories["A06"], severity, desc)
                count += 1
    return count


def map_hotspots_to_owasp(
    hotspots: List, categories: Dict[str, CategoryCompliance]
) -> int:
    """Map hotspot findings to OWASP categories."""
    count = 0
    for hotspot in hotspots:
        cat_str = str(getattr(hotspot, "category", "") or "").lower()
        owasp_cats = _HOTSPOT_TO_OWASP.get(cat_str, [])
        priority = str(getattr(hotspot, "review_priority", "low") or "low").lower()
        severity = "high" if priority == "high" else ("medium" if priority == "medium" else "low")
        desc = getattr(hotspot, "title", str(hotspot.category))
        for cat_id in owasp_cats:
            if cat_id in categories:
                add_finding_to_category(categories[cat_id], severity, desc)
                count += 1
    return count


def map_vulnerabilities_to_cwe(
    findings: List, top_25: Dict[str, CategoryCompliance]
) -> None:
    """Map vulnerability findings to CWE entries."""
    for finding in findings:
        vuln_type = str(getattr(finding, "vulnerability_type", "") or "").lower()
        cwe_ids = _VULN_TO_CWE.get(vuln_type, [])
        finding_cwe = getattr(finding, "cwe_id", None)
        if finding_cwe and finding_cwe not in cwe_ids:
            cwe_ids = cwe_ids + [finding_cwe]
        severity = get_finding_severity(finding)
        desc = get_finding_description(finding)
        for cwe_id in cwe_ids:
            if cwe_id in top_25:
                add_finding_to_category(top_25[cwe_id], severity, desc)


def map_secrets_to_cwe(
    findings: List, top_25: Dict[str, CategoryCompliance]
) -> None:
    """Map secrets findings to CWE-798."""
    for finding in findings:
        severity = get_finding_severity(finding)
        desc = get_finding_description(finding)
        if "CWE-798" in top_25:
            add_finding_to_category(top_25["CWE-798"], severity, desc)


def map_crypto_to_cwe(
    findings: List, top_25: Dict[str, CategoryCompliance]
) -> None:
    """Map crypto findings to their CWE entries if present in top 25."""
    for finding in findings:
        finding_cwe = getattr(finding, "cwe_id", None)
        if finding_cwe and finding_cwe in top_25:
            severity = get_finding_severity(finding)
            desc = get_finding_description(finding)
            add_finding_to_category(top_25[finding_cwe], severity, desc)


def map_hotspots_to_cwe(
    hotspots: List, top_25: Dict[str, CategoryCompliance]
) -> None:
    """Map hotspot findings to CWE entries."""
    for hotspot in hotspots:
        cat_str = str(getattr(hotspot, "category", "") or "").lower()
        cwe_ids = _HOTSPOT_TO_CWE.get(cat_str, [])
        hotspot_cwe = getattr(hotspot, "cwe_id", None)
        if hotspot_cwe and hotspot_cwe not in cwe_ids:
            cwe_ids = cwe_ids + [hotspot_cwe]
        priority = str(getattr(hotspot, "review_priority", "low") or "low").lower()
        severity = "high" if priority == "high" else ("medium" if priority == "medium" else "low")
        desc = getattr(hotspot, "title", str(hotspot.category))
        for cwe_id in cwe_ids:
            if cwe_id in top_25:
                add_finding_to_category(top_25[cwe_id], severity, desc)
