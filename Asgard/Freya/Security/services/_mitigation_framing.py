"""
Freya Security Mitigation Framing (DEEPTHINK_06)

Asymmetry principle: external observation reliably proves the ABSENCE
of a defense, almost never the EFFECTIVENESS of one. Everything here
speaks Threat-Mitigation language — never "Secure"/"Vulnerable" — and
every report carries the executive disclaimer plus a scope matrix
separating observable signals from unverifiable posture.
"""

from typing import Any, Dict, List, Optional

from Asgard.Freya.Security.models.security_header_models import (
    MitigationStatus,
    SecurityHeader,
    SecurityHeaderStatus,
)

#: Display label for the numeric score (field name kept for API compat).
DEFENSE_IN_DEPTH_SCORE_LABEL = "Frontend Defense-in-Depth Score"

#: Executive disclaimer (DEEPTHINK_06 §5) for every security report.
EXECUTIVE_DISCLAIMER = (
    "SCOPE OF THIS ASSESSMENT: This report evaluates observable, "
    "externally-verifiable browser security signals (HTTP response "
    "headers, resource integrity attributes, transport of subresources). "
    "It measures defense-in-depth mitigations, not the presence or "
    "absence of vulnerabilities. A high score means the browser has "
    "been given instructions to contain a breach; it does not mean the "
    "application is free of exploitable flaws. Confirming actual "
    "security posture requires DAST, penetration testing, and manual "
    "code review. Findings are framed as 'Missing Mitigation' because "
    "external observation can prove a defense is absent, but almost "
    "never that a present defense is effective."
)

#: Four-row scope matrix (DEEPTHINK_06): observable signal vs what
#: still requires DAST/manual verification.
SCOPE_MATRIX: List[Dict[str, str]] = [
    {
        "control": "Content-Security-Policy",
        "tool_validates": "Header presence, directive parsing, "
                          "self-sabotaging values (unsafe-inline, wildcards)",
        "requires_manual": "Whether the policy actually blocks injected "
                           "payloads; nonce entropy and per-response uniqueness",
    },
    {
        "control": "HSTS",
        "tool_validates": "Header presence, max-age, includeSubDomains, preload",
        "requires_manual": "Whether the server refuses plain-HTTP before "
                           "preload pinning; certificate/TLS configuration quality",
    },
    {
        "control": "Subresource Integrity",
        "tool_validates": "integrity/crossorigin attributes on cross-origin "
                          "scripts and stylesheets; hash format validity",
        "requires_manual": "Whether the pinned version is itself trustworthy; "
                           "coverage of dynamically injected scripts",
    },
    {
        "control": "Framing protection",
        "tool_validates": "X-Frame-Options / frame-ancestors presence and values",
        "requires_manual": "Whether any sensitive flow is actually "
                           "clickjackable in supported browsers",
    },
]

#: Assume-breach conditional threat context per header (DEEPTHINK_06 §4A).
THREAT_CONTEXT: Dict[str, str] = {
    "Content-Security-Policy": (
        "If an XSS vulnerability exists anywhere in this application, the "
        "browser has no instructions to block the injected payload."
    ),
    "Strict-Transport-Security": (
        "If a user ever connects over plain HTTP (captive portal, typed "
        "URL), the browser will not force the connection onto HTTPS, "
        "exposing the session to interception."
    ),
    "X-Frame-Options": (
        "If an attacker embeds this site in a hostile iframe, the browser "
        "has no instruction to refuse, enabling clickjacking of any "
        "sensitive action."
    ),
    "X-Content-Type-Options": (
        "If an attacker can upload or influence a served file, the browser "
        "may MIME-sniff it into an executable type."
    ),
    "X-XSS-Protection": (
        "Legacy filter header; modern browsers ignore it. If XSS exists, "
        "containment must come from CSP, not this header."
    ),
    "Referrer-Policy": (
        "If users navigate away from pages with sensitive URLs, the full "
        "URL (including path and query) may leak to third-party sites."
    ),
    "Permissions-Policy": (
        "If a compromised or malicious script runs in this page, it may "
        "access powerful browser features (camera, geolocation, sensors) "
        "without restriction."
    ),
    "Cross-Origin-Opener-Policy": (
        "If a hostile site opens this page, it retains a window handle "
        "into it, enabling cross-window attacks such as tab-nabbing and "
        "XS-Leaks."
    ),
    "Cross-Origin-Embedder-Policy": (
        "If this page embeds cross-origin resources, they load without "
        "explicit opt-in, weakening isolation against speculative "
        "execution (Spectre-class) leaks."
    ),
    "Cross-Origin-Resource-Policy": (
        "If a hostile origin embeds this site's resources, the browser "
        "has no instruction to refuse, enabling cross-site inclusion leaks."
    ),
    "Subresource Integrity": (
        "If a third-party CDN serving this page's scripts is compromised, "
        "the altered code executes with full page privileges — cookies, "
        "DOM, and user input included."
    ),
    "Mixed Content": (
        "If a network attacker sits between the user and an http:// "
        "subresource of this https:// page, they can read or modify that "
        "traffic; for scripts and frames, MITM code execution is "
        "deterministic."
    ),
}

#: "Yes, but…" contextualized-pass notes (DEEPTHINK_06 §4).
MANUAL_VERIFICATION: Dict[str, str] = {
    "Content-Security-Policy": (
        "Manual Verification Required: ensure nonces are cryptographically "
        "random and unique per response, and that the policy blocks (not "
        "just reports) in production."
    ),
    "Strict-Transport-Security": (
        "Manual Verification Required: verify the server drops plain-HTTP "
        "(redirect or refuse) before relying on preload pinning."
    ),
    "Subresource Integrity": (
        "Manual Verification Required: an integrity hash pins a version, "
        "not its safety — confirm the pinned version is itself reviewed."
    ),
}


#: Header name -> scope-matrix control row.
_SCOPE_ROW_BY_HEADER: Dict[str, str] = {
    "Content-Security-Policy": "Content-Security-Policy",
    "Strict-Transport-Security": "HSTS",
    "X-Frame-Options": "Framing protection",
}


def classify_mitigation_status(header: Optional[SecurityHeader]) -> Optional[MitigationStatus]:
    """
    Map an analyzed SecurityHeader to its MitigationStatus:
        MISSING       — header absent
        MISCONFIGURED — present but self-sabotaging (issues found)
        PRESENT_NEEDS_VERIFICATION — present, effectiveness unverifiable
        PRESENT       — present and no observable misconfiguration
    """
    if header is None:
        return None
    if header.status == SecurityHeaderStatus.MISSING:
        return MitigationStatus.MISSING
    if header.status == SecurityHeaderStatus.INVALID or (
        header.status in (SecurityHeaderStatus.PRESENT, SecurityHeaderStatus.WEAK)
        and not header.is_secure
    ):
        return MitigationStatus.MISCONFIGURED
    if header.name in MANUAL_VERIFICATION:
        return MitigationStatus.PRESENT_NEEDS_VERIFICATION
    return MitigationStatus.PRESENT


def apply_mitigation_framing(header: Optional[SecurityHeader]) -> Optional[SecurityHeader]:
    """Populate mitigation_status / threat_context / manual_verification."""
    if header is None:
        return None
    header.mitigation_status = classify_mitigation_status(header)
    if header.mitigation_status in (
        MitigationStatus.MISSING, MitigationStatus.MISCONFIGURED
    ):
        header.threat_context = THREAT_CONTEXT.get(header.name)
    if header.mitigation_status in (
        MitigationStatus.PRESENT, MitigationStatus.PRESENT_NEEDS_VERIFICATION
    ):
        header.manual_verification = MANUAL_VERIFICATION.get(header.name)
    row_name = _SCOPE_ROW_BY_HEADER.get(header.name)
    if row_name:
        row = next((r for r in SCOPE_MATRIX if r["control"] == row_name), None)
        if row:
            header.observable_signal = row["tool_validates"]
            header.unverifiable_posture = row["requires_manual"]
    return header
