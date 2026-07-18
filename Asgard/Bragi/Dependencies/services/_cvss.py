"""
CVSS score -> severity bucket mapping, shared by the OSV and NVD network
lookups. Severity is derived from CVSS where available and is kept
orthogonal to confidence: a live database match is always
`confidence="measured"` regardless of whether a CVSS score was present.

Bucket boundaries follow the published CVSS v3/v3.1 qualitative severity
rating scale (FIRST.org): 0.0 = none, 0.1-3.9 = low, 4.0-6.9 = medium,
7.0-8.9 = high, 9.0-10.0 = critical.
"""

from typing import Any, Optional


def cvss_score_to_severity(score: Optional[float]) -> str:
    """Map a numeric CVSS base score (0.0-10.0) to a severity bucket.
    Returns 'high' (a conservative, non-false-clean default) if no score
    is available -- an unscored vulnerability is never reported as low
    risk purely because scoring data was missing."""
    if score is None:
        return "high"
    try:
        value = float(score)
    except (TypeError, ValueError):
        return "high"
    if value >= 9.0:
        return "critical"
    if value >= 7.0:
        return "high"
    if value >= 4.0:
        return "medium"
    if value > 0.0:
        return "low"
    return "low"


def extract_cvss_score(vuln: dict) -> Optional[float]:
    """Best-effort extraction of a CVSS base score from an OSV vulnerability
    entry. OSV entries carry a `severity` list of {type, score} where
    `score` may be a raw CVSS vector string (e.g. 'CVSS:3.1/AV:N/.../') or,
    for some sources, a bare numeric string. We only need the base score
    number; if only a vector is present we cannot derive the numeric score
    without full CVSS math, so we fall back to None (caller treats that as
    'high', never a false-clean)."""
    if not isinstance(vuln, dict):
        return None
    severities = vuln.get("severity")
    if isinstance(severities, list):
        for entry in severities:
            if not isinstance(entry, dict):
                continue
            raw_score = entry.get("score")
            if raw_score is None:
                continue
            parsed = _parse_numeric(raw_score)
            if parsed is not None:
                return parsed
    # NVD-shaped payload: cvssMetricV31/V30/V2 -> cvssData.baseScore
    metrics = vuln.get("metrics") if isinstance(vuln, dict) else None
    if isinstance(metrics, dict):
        for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
            entries = metrics.get(key)
            if isinstance(entries, list) and entries:
                cvss_data = entries[0].get("cvssData", {}) if isinstance(entries[0], dict) else {}
                base = cvss_data.get("baseScore")
                parsed = _parse_numeric(base)
                if parsed is not None:
                    return parsed
    return None


def _parse_numeric(raw: Any) -> Optional[float]:
    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, str):
        try:
            return float(raw)
        except ValueError:
            return None
    return None
