"""
Universal CIA-impact severity criteria (DEEPTHINK_11).

Modules stop assigning free-text severities; they report a
``(mechanism_id, confidence, context_tags)`` triple and this engine maps the
mechanism to severity via universal impact criteria:

    CRITICAL : unauthenticated host/database takeover, RCE, total auth
               bypass, validated cloud-admin credential.
    HIGH     : PII exfiltration, authenticated SQLi, stored XSS, path
               traversal read, scoped live 3rd-party token, container
               root+privileged.
    MEDIUM   : defense-in-depth bypass, reflected XSS, DoS, missing CSP in a
               web context, internal test credentials.
    LOW      : hygiene, fingerprinting, missing header in an API context,
               dummy keys.

Severity/confidence orthogonality: a low-confidence RCE stays CRITICAL with
an "unlikely"/"possible" confidence bucket and is routed to review -- it is
never downgraded. Context tags may downgrade *contextually inapplicable*
mechanisms (a browser-only header finding in a JSON API), which is a
statement about impact, not certainty.

Unmapped mechanism ids pass through the caller-provided fallback severity
with ``normalized=False`` so module sweeps can proceed incrementally.
"""

from dataclasses import dataclass, field
from typing import Dict, Optional, Sequence

from Asgard.Heimdall.Security.normalization.priority import confidence_bucket, priority


@dataclass(frozen=True)
class Mechanism:
    """A normalized vulnerability mechanism."""
    mechanism_id: str
    severity: str            # CIA-impact severity: critical/high/medium/low
    category: str            # security sub-module family (scoring category)
    cwe_id: str = ""
    browser_only: bool = False   # inapplicable in pure-API contexts
    description: str = ""


def _m(mid, severity, category, cwe="", browser_only=False, description=""):
    return Mechanism(mid, severity, category, cwe, browser_only, description)


# The universal impact matrix. Keys are stable mechanism ids scanners emit.
MECHANISMS: Dict[str, Mechanism] = {m.mechanism_id: m for m in [
    # --- CRITICAL: takeover / RCE / total bypass / cloud-admin credential ---
    _m("rce.unauthenticated", "critical", "injection", "CWE-94",
       description="Unauthenticated remote code execution"),
    _m("injection.code_eval", "critical", "injection", "CWE-95",
       description="Untrusted data reaches eval/exec"),
    _m("injection.command", "critical", "injection", "CWE-78",
       description="Untrusted data reaches a shell command"),
    _m("injection.sql.unauthenticated", "critical", "injection", "CWE-89",
       description="Pre-auth SQL injection (database takeover)"),
    _m("auth.total_bypass", "critical", "auth",
       description="Authentication can be bypassed entirely"),
    _m("secret.cloud_admin.validated", "critical", "secrets",
       description="Validated cloud-admin credential in source"),
    _m("deserialization.untrusted", "critical", "deserialization", "CWE-502",
       description="Untrusted data deserialized (pickle/yaml.load)"),
    # --- HIGH: exfiltration-class impact ---
    _m("injection.sql.authenticated", "high", "injection", "CWE-89",
       description="Authenticated SQL injection"),
    _m("xss.stored", "high", "xss", "CWE-79",
       description="Stored cross-site scripting"),
    _m("path_traversal.read", "high", "path_traversal", "CWE-22",
       description="Path traversal file read"),
    _m("template_injection", "high", "injection", "CWE-94",
       description="Server-side template injection"),
    _m("ldap_injection", "high", "injection", "CWE-90",
       description="LDAP injection"),
    _m("secret.third_party.scoped_live", "high", "secrets",
       description="Scoped, live third-party token"),
    _m("container.root_privileged", "high", "container",
       description="Container runs as root with privileged mode"),
    _m("ssrf.full_url_control", "high", "ssrf", "CWE-918",
       description="Attacker controls full outbound request URL"),
    _m("pii.exfiltration", "high", "data_exfil",
       description="PII exfiltration path"),
    # --- MEDIUM: defense-in-depth / conditional impact ---
    _m("xss.reflected", "medium", "xss", "CWE-79",
       description="Reflected cross-site scripting"),
    _m("dos", "medium", "availability", "CWE-400",
       description="Denial of service"),
    _m("redos", "medium", "redos", "CWE-1333",
       description="Regular-expression denial of service"),
    _m("header.missing_csp", "medium", "headers", browser_only=True,
       description="Missing Content-Security-Policy in a web context"),
    _m("secret.internal_test", "medium", "secrets",
       description="Internal/test credential in source"),
    _m("defense_in_depth.bypass", "medium", "hardening",
       description="Bypass of a defense-in-depth layer"),
    _m("auth.timing_unsafe_compare", "medium", "auth", "CWE-208",
       description="Secret/token compared with a non-constant-time operator"),
    _m("access.bola_advisory", "medium", "access",
       description="Object fetched by request-supplied ID without an "
                    "ownership filter in the same slice (advisory; SAST "
                    "cannot prove exploitability -- pair with "
                    "contract-driven fuzzing, e.g. Schemathesis)"),
    _m("open_redirect", "medium", "redirect", "CWE-601",
       description="Open redirect"),
    _m("log_injection", "medium", "logging", "CWE-117",
       description="Log injection / log forging"),
    _m("file_write.tainted", "medium", "injection", "CWE-73",
       description="Untrusted data controls file write"),
    # --- LOW: hygiene / fingerprinting / dummy material ---
    _m("hygiene", "low", "hardening",
       description="Security hygiene issue"),
    _m("fingerprinting", "low", "info_disclosure",
       description="Version/stack fingerprinting exposure"),
    _m("header.missing.api", "low", "headers",
       description="Missing browser header in an API-only context"),
    _m("secret.dummy", "low", "secrets",
       description="Placeholder/dummy key"),
    _m("deserialization.hotspot", "low", "deserialization", "CWE-502",
       description="Deserialization sink with unconfirmed data provenance "
                    "(reviewed as a hotspot, not a proven finding)"),
]}

# Severity a browser-only mechanism drops to when the surrounding context is
# a non-browser API (progressive contextualization).
_API_CONTEXT_DOWNGRADE = "low"


@dataclass
class NormalizedFinding:
    """Result of normalizing a (mechanism_id, confidence, context) triple."""
    mechanism_id: str
    severity: str
    confidence: float
    confidence_bucket: str
    priority: float
    normalized: bool
    context_modifier: float = 1.0
    context_tags: tuple = field(default_factory=tuple)


def normalize_finding(
    mechanism_id: str,
    confidence: float,
    context_tags: Sequence[str] = (),
    fallback_severity: str = "medium",
    context_modifier: float = 1.0,
) -> NormalizedFinding:
    """
    Map a mechanism id to its universal severity and compute priority.

    - Unknown mechanism ids pass through ``fallback_severity`` with
      ``normalized=False`` (incremental module sweep support).
    - ``context_tags`` may include ``"api_context"``: browser-only
      mechanisms are downgraded to LOW there (impact statement).
    - ``context_modifier`` (0.5-1.0) comes from repo-level declarations
      (e.g. ``tier: internal-service``) and scales priority only.
    - Confidence NEVER changes severity.
    """
    tags = tuple(context_tags)
    mech = MECHANISMS.get(mechanism_id)
    if mech is None:
        severity = str(fallback_severity).lower()
        normalized = False
    else:
        severity = mech.severity
        normalized = True
        if mech.browser_only and "api_context" in tags:
            severity = _API_CONTEXT_DOWNGRADE
    conf = max(0.0, min(1.0, float(confidence)))
    ctx = max(0.5, min(1.0, float(context_modifier)))
    return NormalizedFinding(
        mechanism_id=mechanism_id,
        severity=severity,
        confidence=conf,
        confidence_bucket=confidence_bucket(conf),
        priority=priority(severity, conf, ctx),
        normalized=normalized,
        context_modifier=ctx,
        context_tags=tags,
    )
