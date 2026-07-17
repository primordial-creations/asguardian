"""
Heimdall Regex Hotspot Checks

Regex fallback for the six hotspot families on languages without an AST
front-end yet (JS/TS, Go, Java, ...). For Python files the AST checks are
authoritative; the detector deduplicates (category, line) overlaps.
"""

import re
from typing import List, Optional, Pattern, Tuple

from Asgard.Heimdall.Security.Hotspots.models.hotspot_models import (
    HotspotCategory,
    HotspotConfig,
    ReviewPriority,
    ReviewStatus,
    SecurityHotspot,
)

# (category, priority, pattern, title, description, guidance, owasp, cwe)
_RULES: Tuple[Tuple, ...] = (
    (
        HotspotCategory.WEAK_HASHING, ReviewPriority.MEDIUM,
        re.compile(r"""createHash\s*\(\s*['"](?:md5|sha1)['"]\s*\)|MessageDigest\.getInstance\s*\(\s*"(?:MD5|SHA-?1)"|\b(?:md5|sha1)\.New\s*\(""", re.IGNORECASE),
        "Weak hash algorithm (MD5/SHA-1)",
        "MD5/SHA-1 are broken for security purposes; acceptability depends on the business domain (checksum vs credential).",
        "If security-sensitive, migrate to SHA-256+ (bcrypt/argon2 for passwords).",
        "A02:Cryptographic Failures", "CWE-328",
    ),
    (
        HotspotCategory.STANDARD_PRNG, ReviewPriority.LOW,
        re.compile(r"\bMath\.random\s*\(|\bmath/rand\b|new\s+Random\s*\("),
        "Standard (non-cryptographic) PRNG usage",
        "Standard PRNGs are predictable; whether that matters depends on intent (simulation vs token generation).",
        "Use a CSPRNG (crypto.randomBytes, crypto/rand, SecureRandom) for anything security-relevant.",
        "A02:Cryptographic Failures", "CWE-338",
    ),
    (
        HotspotCategory.DISABLED_TLS, ReviewPriority.HIGH,
        re.compile(r"\bverify\s*=\s*False\b|rejectUnauthorized\s*:\s*false|InsecureSkipVerify\s*:\s*true|NODE_TLS_REJECT_UNAUTHORIZED|ssl\._create_unverified_context", re.IGNORECASE),
        "TLS certificate verification disabled",
        "Certificate verification is disabled; acceptability is a network-topology question.",
        "Enable verification or pin a CA bundle; never disable for internet-facing endpoints.",
        "A02:Cryptographic Failures", "CWE-295",
    ),
    (
        HotspotCategory.PERMISSIVE_BINDING, ReviewPriority.MEDIUM,
        re.compile(r"""['"]0\.0\.0\.0['"]|Access-Control-Allow-Origin['"]?\s*[:,]\s*['"]\*|allow_origins\s*=\s*\[?\s*['"]\*"""),
        "Permissive binding or wildcard CORS",
        "Binding to all interfaces / wildcard CORS exposes the service broadly; safety depends on deployment topology.",
        "Bind to loopback or restrict origins unless external exposure is intentional and controlled.",
        "A05:Security Misconfiguration", "CWE-942",
    ),
    (
        HotspotCategory.OPAQUE_DESERIALIZATION, ReviewPriority.HIGH,
        re.compile(r"\bpickle\.loads?\s*\(|\bmarshal\.loads?\s*\(|\byaml\.load\s*\((?!.*SafeLoader)|ObjectInputStream|Marshal\.load|node-serialize"),
        "Opaque deserialization of possibly untrusted data",
        "Deserialization primitives execute code when fed attacker-controlled bytes; provenance cannot be proven statically.",
        "Confirm the data source is trusted; prefer JSON or another data-only format across trust boundaries.",
        "A08:Software and Data Integrity Failures", "CWE-502",
    ),
    (
        HotspotCategory.HAZMAT_CRYPTO, ReviewPriority.MEDIUM,
        re.compile(r"\bcryptography\.hazmat\b|from\s+cryptography\.hazmat"),
        "Low-level crypto primitive usage (hazmat)",
        "Low-level primitives are only as safe as their composition; requires mathematical-soundness review.",
        "Prefer high-level recipes (Fernet); otherwise obtain expert review of the construction.",
        "A02:Cryptographic Failures", "CWE-327",
    ),
)


def detect_regex_hotspots(
    lines: List[str],
    file_path: str,
    config: HotspotConfig,
) -> List[SecurityHotspot]:
    """Regex-based hotspot detection over raw source lines."""
    hotspots: List[SecurityHotspot] = []
    enabled = set(config.enabled_categories)

    for line_num, line in enumerate(lines, start=1):
        for category, priority, pattern, title, description, guidance, owasp, cwe in _RULES:
            if category not in enabled:
                continue
            if pattern.search(line):
                hotspots.append(SecurityHotspot(
                    file_path=file_path,
                    line_number=line_num,
                    category=category,
                    review_priority=priority,
                    title=title,
                    description=description,
                    code_snippet=line.strip(),
                    review_guidance=guidance,
                    review_status=ReviewStatus.TO_REVIEW,
                    owasp_category=owasp,
                    cwe_id=cwe,
                ))
    return hotspots
