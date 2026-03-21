"""
Heimdall Regex Hotspot Checks

Regex-based hotspot detection logic for HotspotDetector.
"""

import re
from typing import List

from Asgard.Heimdall.Security.Hotspots.models.hotspot_models import (
    HotspotCategory,
    HotspotConfig,
    ReviewPriority,
    ReviewStatus,
    SecurityHotspot,
)

_RE_SECURE_FALSE = re.compile(r"\bsecure\s*=\s*False", re.IGNORECASE)
_RE_HTTPONLY_FALSE = re.compile(r"\bhttponly\s*=\s*False", re.IGNORECASE)
_RE_VERIFY_FALSE = re.compile(r"\bverify\s*=\s*False")
_RE_NESTED_QUANTIFIER = re.compile(r"[*+?{][*+?{]|(?:\([^)]*[*+?]\)[*+?{])")
_RE_YAML_LOAD_UNSAFE = re.compile(r"\byaml\.load\s*\((?!.*Loader\s*=\s*yaml\.SafeLoader)")


def detect_regex_hotspots(
    lines: List[str],
    file_path: str,
    config: HotspotConfig,
) -> List[SecurityHotspot]:
    """Perform regex-based hotspot detection on raw source lines."""
    hotspots: List[SecurityHotspot] = []

    for line_num, line in enumerate(lines, start=1):
        if HotspotCategory.COOKIE_CONFIG in config.enabled_categories:
            if _RE_SECURE_FALSE.search(line):
                hotspots.append(SecurityHotspot(
                    file_path=file_path,
                    line_number=line_num,
                    category=HotspotCategory.COOKIE_CONFIG,
                    review_priority=ReviewPriority.MEDIUM,
                    title="Cookie set with secure=False",
                    description=(
                        "Cookie is set with secure=False. This allows the cookie to be "
                        "transmitted over unencrypted HTTP connections."
                    ),
                    code_snippet=line.strip(),
                    review_guidance=(
                        "Set secure=True on all cookies to ensure they are only sent "
                        "over HTTPS. Also set httponly=True to prevent JavaScript access."
                    ),
                    review_status=ReviewStatus.TO_REVIEW,
                    owasp_category="A07:Identification and Authentication Failures",
                    cwe_id="CWE-614",
                ))

            if _RE_HTTPONLY_FALSE.search(line):
                hotspots.append(SecurityHotspot(
                    file_path=file_path,
                    line_number=line_num,
                    category=HotspotCategory.COOKIE_CONFIG,
                    review_priority=ReviewPriority.MEDIUM,
                    title="Cookie set with httponly=False",
                    description=(
                        "Cookie is set with httponly=False. This allows JavaScript to access "
                        "the cookie, increasing XSS risk."
                    ),
                    code_snippet=line.strip(),
                    review_guidance=(
                        "Set httponly=True on session cookies to prevent JavaScript access "
                        "and mitigate XSS attacks."
                    ),
                    review_status=ReviewStatus.TO_REVIEW,
                    owasp_category="A07:Identification and Authentication Failures",
                    cwe_id="CWE-1004",
                ))

        if HotspotCategory.TLS_VERIFICATION in config.enabled_categories:
            if _RE_VERIFY_FALSE.search(line):
                hotspots.append(SecurityHotspot(
                    file_path=file_path,
                    line_number=line_num,
                    category=HotspotCategory.TLS_VERIFICATION,
                    review_priority=ReviewPriority.LOW,
                    title="TLS certificate verification disabled (verify=False)",
                    description=(
                        "TLS certificate verification is disabled. This allows connections to "
                        "servers with invalid or self-signed certificates."
                    ),
                    code_snippet=line.strip(),
                    review_guidance=(
                        "Enable TLS verification (verify=True or use a custom CA bundle). "
                        "If a self-signed certificate is needed, provide it via verify='/path/to/ca.crt'."
                    ),
                    review_status=ReviewStatus.TO_REVIEW,
                    owasp_category="A02:Cryptographic Failures",
                    cwe_id="CWE-295",
                ))

        if HotspotCategory.REGEX_DOS in config.enabled_categories:
            if "re.compile" in line or "re.match" in line or "re.search" in line or "re.fullmatch" in line:
                if _RE_NESTED_QUANTIFIER.search(line):
                    hotspots.append(SecurityHotspot(
                        file_path=file_path,
                        line_number=line_num,
                        category=HotspotCategory.REGEX_DOS,
                        review_priority=ReviewPriority.LOW,
                        title="Potentially vulnerable regex pattern (ReDoS risk)",
                        description=(
                            "Regex pattern contains nested quantifiers which may cause "
                            "catastrophic backtracking on certain inputs."
                        ),
                        code_snippet=line.strip(),
                        review_guidance=(
                            "Review the regex pattern for nested quantifiers such as (a+)+ or (a*)*. "
                            "Consider using atomic groups or possessive quantifiers if available, "
                            "or rewrite to avoid ambiguity."
                        ),
                        review_status=ReviewStatus.TO_REVIEW,
                        owasp_category="A04:Insecure Design",
                        cwe_id="CWE-1333",
                    ))

        if HotspotCategory.INSECURE_DESERIALIZATION in config.enabled_categories:
            if _RE_YAML_LOAD_UNSAFE.search(line):
                hotspots.append(SecurityHotspot(
                    file_path=file_path,
                    line_number=line_num,
                    category=HotspotCategory.INSECURE_DESERIALIZATION,
                    review_priority=ReviewPriority.HIGH,
                    title="Unsafe yaml.load() without SafeLoader",
                    description=(
                        "yaml.load() without Loader=yaml.SafeLoader can execute arbitrary "
                        "Python code embedded in YAML input."
                    ),
                    code_snippet=line.strip(),
                    review_guidance=(
                        "Replace yaml.load(data) with yaml.safe_load(data) or "
                        "yaml.load(data, Loader=yaml.SafeLoader) to prevent code execution."
                    ),
                    review_status=ReviewStatus.TO_REVIEW,
                    owasp_category="A08:Software and Data Integrity Failures",
                    cwe_id="CWE-502",
                ))

    return hotspots
