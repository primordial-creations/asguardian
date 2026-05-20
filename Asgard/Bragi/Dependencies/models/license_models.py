"""
Heimdall License Models

Data models for license compliance checking.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set


class LicenseCategory(str, Enum):
    """License categories for compliance classification."""
    PERMISSIVE = "permissive"        # MIT, Apache, BSD - commercial-friendly
    WEAK_COPYLEFT = "weak_copyleft"  # LGPL, MPL - requires attribution
    STRONG_COPYLEFT = "strong_copyleft"  # GPL, AGPL - viral license
    PROPRIETARY = "proprietary"      # Commercial licenses
    PUBLIC_DOMAIN = "public_domain"  # CC0, Unlicense
    UNKNOWN = "unknown"              # Unable to determine


class LicenseSeverity(str, Enum):
    """Severity levels for license issues."""
    CRITICAL = "critical"  # GPL/AGPL - may require open-sourcing
    HIGH = "high"          # LGPL - requires careful handling
    MODERATE = "moderate"  # Unknown license
    LOW = "low"            # Weak copyleft, requires attribution
    OK = "ok"              # Permissive license


class LicenseIssueType(str, Enum):
    """Types of license issues."""
    PROHIBITED = "prohibited"    # License explicitly prohibited
    COPYLEFT = "copyleft"        # Copyleft license detected
    UNKNOWN = "unknown"          # License could not be determined
    OUTDATED = "outdated"        # License info may be outdated
    MULTIPLE = "multiple"        # Package has multiple licenses


@dataclass
class LicenseConfig:
    """Configuration for license checking."""
    scan_path: Path = field(default_factory=lambda: Path("."))
    requirements_files: List[str] = field(default_factory=lambda: [
        "requirements.txt",
        "requirements-dev.txt",
        "requirements-test.txt",
    ])
    allowed_licenses: List[str] = field(default_factory=lambda: [
        "MIT",
        "MIT License",
        "Apache-2.0",
        "Apache Software License",
        "Apache License 2.0",
        "BSD-3-Clause",
        "BSD-2-Clause",
        "BSD License",
        "ISC",
        "ISC License",
        "PSF-2.0",
        "Python Software Foundation License",
        "MPL-2.0",
        "Mozilla Public License 2.0",
        "Unlicense",
        "CC0-1.0",
        "Public Domain",
        "WTFPL",
    ])
    prohibited_licenses: List[str] = field(default_factory=lambda: [
        "GPL-3.0",
        "GPL-3.0-only",
        "GPL-3.0-or-later",
        "GNU General Public License v3",
        "AGPL-3.0",
        "AGPL-3.0-only",
        "AGPL-3.0-or-later",
        "GNU Affero General Public License v3",
        "SSPL",
        "Server Side Public License",
    ])
    warn_licenses: List[str] = field(default_factory=lambda: [
        "LGPL-3.0",
        "LGPL-3.0-only",
        "LGPL-3.0-or-later",
        "GNU Lesser General Public License v3",
        "LGPL-2.1",
        "GPL-2.0",
        "GNU General Public License v2",
    ])
    use_cache: bool = True
    cache_expiry_days: int = 7
    output_format: str = "text"
    verbose: bool = False

    def __post_init__(self):
        if isinstance(self.scan_path, str):
            self.scan_path = Path(self.scan_path)


@dataclass
class PackageLicense:
    """License information for a single package."""
    package_name: str
    version: Optional[str] = None
    license_name: Optional[str] = None
    license_classifier: Optional[str] = None
    category: LicenseCategory = LicenseCategory.UNKNOWN
    severity: LicenseSeverity = LicenseSeverity.MODERATE
    source: str = ""  # Where license info came from (pypi, installed, etc.)
    homepage: Optional[str] = None
    author: Optional[str] = None
    is_allowed: bool = True
    is_prohibited: bool = False
    is_warning: bool = False

    @property
    def display_license(self) -> str:
        """Get display-friendly license name."""
        return self.license_name or self.license_classifier or "Unknown"


@dataclass
class LicenseIssue:
    """A single license compliance issue."""
    issue_type: LicenseIssueType
    severity: LicenseSeverity
    package_name: str
    license_name: Optional[str]
    message: str
    details: Dict = field(default_factory=dict)

    @property
    def is_critical(self) -> bool:
        """Whether this is a critical issue."""
        return self.severity in (LicenseSeverity.CRITICAL, LicenseSeverity.HIGH)


@dataclass
class LicenseResult:
    """Complete license analysis result."""
    scan_path: str
    scanned_at: datetime
    scan_duration_seconds: float
    config: LicenseConfig

    # License information
    packages: List[PackageLicense] = field(default_factory=list)
    requirements_files_found: List[str] = field(default_factory=list)

    # Issues
    issues: List[LicenseIssue] = field(default_factory=list)

    @property
    def total_packages(self) -> int:
        """Total number of packages checked."""
        return len(self.packages)

    @property
    def compliant_packages(self) -> int:
        """Number of packages with allowed licenses."""
        return sum(1 for p in self.packages if p.is_allowed and not p.is_prohibited)

    @property
    def warning_packages(self) -> int:
        """Number of packages with warning licenses."""
        return sum(1 for p in self.packages if p.is_warning)

    @property
    def prohibited_packages(self) -> int:
        """Number of packages with prohibited licenses."""
        return sum(1 for p in self.packages if p.is_prohibited)

    @property
    def unknown_packages(self) -> int:
        """Number of packages with unknown licenses."""
        return sum(1 for p in self.packages if p.category == LicenseCategory.UNKNOWN)

    @property
    def has_issues(self) -> bool:
        """Whether any issues were found."""
        return len(self.issues) > 0

    @property
    def has_critical_issues(self) -> bool:
        """Whether any critical issues were found."""
        return any(i.is_critical for i in self.issues)

    @property
    def compliance_rate(self) -> float:
        """Percentage of packages with compliant licenses."""
        if self.total_packages == 0:
            return 100.0
        return (self.compliant_packages / self.total_packages) * 100

    def get_packages_by_category(self) -> Dict[str, List[PackageLicense]]:
        """Group packages by license category."""
        result: Dict[str, List[PackageLicense]] = {}
        for pkg in self.packages:
            key = pkg.category.value
            if key not in result:
                result[key] = []
            result[key].append(pkg)
        return result

    def get_issues_by_severity(self) -> Dict[str, List[LicenseIssue]]:
        """Group issues by severity."""
        result: Dict[str, List[LicenseIssue]] = {}
        for issue in self.issues:
            key = issue.severity.value
            if key not in result:
                result[key] = []
            result[key].append(issue)
        return result
