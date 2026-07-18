"""
Cross-module severity equivalency matrix (DEEPTHINK_11 Step 2, as data).

Each row is a scanner family; the classes listed under a severity level are
asserted to have the *same blast radius* as the classes at that level in
every other family. Unit-tested so a "HIGH" from Secrets means the same as a
"HIGH" from SAST or Container/IaC.
"""

from typing import Dict, List, Optional

# family -> severity -> finding classes at that blast radius
EQUIVALENCY_MATRIX: Dict[str, Dict[str, List[str]]] = {
    "secrets": {
        "critical": ["validated cloud-admin credential"],
        "high": ["scoped live third-party token"],
        "medium": ["internal/test credential"],
        "low": ["dummy/placeholder key"],
    },
    "sast": {
        "critical": ["unauthenticated RCE", "pre-auth SQL injection",
                     "total auth bypass"],
        "high": ["authenticated SQL injection", "stored XSS",
                 "path traversal read"],
        "medium": ["reflected XSS", "DoS", "log injection"],
        "low": ["hygiene finding", "fingerprinting"],
    },
    "sca": {
        "critical": ["exploitable RCE in a reachable dependency"],
        "high": ["exploitable data-exfiltration CVE in a reachable dependency"],
        "medium": ["CVE in dependency without a known reachable path"],
        "low": ["outdated dependency, no known CVE impact"],
    },
    "container_iac": {
        "critical": ["cluster-admin escape / host takeover misconfiguration"],
        "high": ["container root + privileged mode"],
        "medium": ["missing resource limits / writable root filesystem"],
        "low": ["image hygiene (latest tag, missing labels)"],
    },
    "auth_headers": {
        "critical": ["total authentication bypass"],
        "high": ["session fixation / credential over cleartext"],
        "medium": ["missing CSP in web context"],
        "low": ["missing browser header in API context"],
    },
}

_SEVERITIES = ("critical", "high", "medium", "low")


def finding_classes_for(family: str, severity: str) -> List[str]:
    """Finding classes a family places at the given severity."""
    return list(EQUIVALENCY_MATRIX.get(family, {}).get(str(severity).lower(), []))


def severity_of_class(family: str, finding_class: str) -> Optional[str]:
    """Reverse lookup: which severity a family assigns a finding class."""
    row = EQUIVALENCY_MATRIX.get(family, {})
    for severity in _SEVERITIES:
        if finding_class in row.get(severity, []):
            return severity
    return None
