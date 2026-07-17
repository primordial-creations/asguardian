"""
Bragi Package Health (Plan 03 Phase E) — abandoned/renamed package signals.

Flags dependencies on packages that are known-abandoned or have been renamed
or superseded (RESEARCH_18's pycrypto-class problem). The curated table below
is fully offline; yanked-version detection against PyPI is available only via
the opt-in VulnerabilityChecker-style network flag.

The table is seeded with the RESEARCH_18 examples and well-documented
ecosystem renames. Matching is by PEP 503 canonical name — never substrings.
"""

import re
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional


def canonical_name(name: str) -> str:
    """PEP 503 canonical package name."""
    return re.sub(r"[-_.]+", "-", name).lower()


@dataclass
class PackageHealthEntry:
    """Curated health record for a problematic package."""
    package: str
    status: str                    # abandoned | renamed | superseded
    replacement: Optional[str] = None
    note: str = ""


#: Curated, offline table (RESEARCH_18 seed set + documented renames).
KNOWN_PACKAGE_HEALTH: Dict[str, PackageHealthEntry] = {
    entry.package: entry
    for entry in [
        PackageHealthEntry(
            "pycrypto", "abandoned", "pycryptodome",
            "Unmaintained since 2013 with known CVEs; use pyca/cryptography "
            "or pycryptodome.",
        ),
        PackageHealthEntry(
            "pil", "superseded", "pillow",
            "PIL is unmaintained; Pillow is the maintained fork.",
        ),
        PackageHealthEntry(
            "sklearn", "renamed", "scikit-learn",
            "'sklearn' is a deprecated brownout shim; depend on scikit-learn.",
        ),
        PackageHealthEntry(
            "bs4", "renamed", "beautifulsoup4",
            "'bs4' is a dummy package; depend on beautifulsoup4.",
        ),
        PackageHealthEntry(
            "distribute", "superseded", "setuptools",
            "distribute merged back into setuptools in 2013.",
        ),
        PackageHealthEntry(
            "nose", "abandoned", "pytest",
            "nose is unmaintained and fails on modern Python; use pytest.",
        ),
        PackageHealthEntry(
            "optparse", "superseded", "argparse",
            "optparse is soft-deprecated in the stdlib; use argparse.",
        ),
        PackageHealthEntry(
            "imp", "superseded", "importlib",
            "imp was removed in Python 3.12; use importlib.",
        ),
        PackageHealthEntry(
            "flask-script", "abandoned", "flask>=0.11 (built-in CLI)",
            "Flask-Script is unmaintained; use the built-in flask CLI.",
        ),
        PackageHealthEntry(
            "python-memcached", "abandoned", "pymemcache",
            "python-memcached is effectively unmaintained; use pymemcache.",
        ),
    ]
}


@dataclass
class PackageHealthIssue:
    """A dependency that hit the curated health table."""
    package_name: str
    status: str
    replacement: Optional[str]
    message: str
    severity: str = "moderate"
    confidence: str = "measured"   # curated table match, not a heuristic


@dataclass
class PackageHealthResult:
    """Outcome of the offline package-health sweep."""
    packages_checked: int = 0
    issues: List[PackageHealthIssue] = field(default_factory=list)

    @property
    def has_issues(self) -> bool:
        return bool(self.issues)


def check_package_health(package_names: Iterable[str]) -> PackageHealthResult:
    """
    Offline sweep of dependency names against the curated health table.

    Args:
        package_names: declared dependency names (any capitalization).

    Returns:
        PackageHealthResult with one issue per flagged package (sorted).
    """
    names = sorted({canonical_name(n) for n in package_names if n})
    issues: List[PackageHealthIssue] = []
    for name in names:
        entry = KNOWN_PACKAGE_HEALTH.get(name)
        if entry is None:
            continue
        severity = "high" if entry.status == "abandoned" else "moderate"
        replacement = f"; use {entry.replacement}" if entry.replacement else ""
        issues.append(PackageHealthIssue(
            package_name=name,
            status=entry.status,
            replacement=entry.replacement,
            severity=severity,
            message=(
                f"Package '{name}' is {entry.status}{replacement}. {entry.note}"
            ).strip(),
        ))
    return PackageHealthResult(packages_checked=len(names), issues=issues)
