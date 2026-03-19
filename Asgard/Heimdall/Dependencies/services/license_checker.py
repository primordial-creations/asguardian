"""
Heimdall License Checker Service

Validates that all packages in requirements have acceptable licenses
for commercial use without licensing costs.
"""

import json
import re
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set

from Asgard.Heimdall.Dependencies.models.license_models import (
    LicenseCategory,
    LicenseConfig,
    LicenseIssue,
    LicenseIssueType,
    LicenseResult,
    LicenseSeverity,
    PackageLicense,
)


# License name normalization patterns
LICENSE_PATTERNS = {
    # Permissive licenses
    r"MIT|Expat": ("MIT", LicenseCategory.PERMISSIVE),
    r"Apache.*(2|2\.0)|Apache License,? Version 2|Apache Software License": ("Apache-2.0", LicenseCategory.PERMISSIVE),
    r"BSD.*(3|3-Clause|New|Revised)|BSD 3-Clause": ("BSD-3-Clause", LicenseCategory.PERMISSIVE),
    r"BSD.*(2|2-Clause|Simplified|FreeBSD)|BSD 2-Clause": ("BSD-2-Clause", LicenseCategory.PERMISSIVE),
    r"^BSD$|BSD License|^BSD-": ("BSD", LicenseCategory.PERMISSIVE),
    r"ISC": ("ISC", LicenseCategory.PERMISSIVE),
    r"PSF|Python Software Foundation": ("PSF-2.0", LicenseCategory.PERMISSIVE),
    r"Unlicense|Public Domain": ("Unlicense", LicenseCategory.PUBLIC_DOMAIN),
    r"CC0|Creative Commons Zero": ("CC0-1.0", LicenseCategory.PUBLIC_DOMAIN),
    r"WTFPL": ("WTFPL", LicenseCategory.PUBLIC_DOMAIN),

    # Weak copyleft
    r"LGPL.*(3|3\.0)": ("LGPL-3.0", LicenseCategory.WEAK_COPYLEFT),
    r"LGPL.*(2\.1|2)": ("LGPL-2.1", LicenseCategory.WEAK_COPYLEFT),
    r"MPL.*(2|2\.0)|Mozilla Public License": ("MPL-2.0", LicenseCategory.WEAK_COPYLEFT),

    # Strong copyleft
    r"AGPL.*(3|3\.0)": ("AGPL-3.0", LicenseCategory.STRONG_COPYLEFT),
    r"GPL.*(3|3\.0)": ("GPL-3.0", LicenseCategory.STRONG_COPYLEFT),
    r"GPL.*(2|2\.0)": ("GPL-2.0", LicenseCategory.STRONG_COPYLEFT),
    r"^GPL$|General Public License": ("GPL", LicenseCategory.STRONG_COPYLEFT),
}


class LicenseChecker:
    """
    Validates license compliance for Python packages.

    Features:
    - Checks packages against allowed/prohibited license lists
    - Uses pip show and PyPI API for license info
    - Categorizes licenses by copyleft level
    - Generates compliance reports
    """

    def __init__(self, config: LicenseConfig):
        """Initialize the license checker."""
        self.config = config
        self._cache: Dict[str, PackageLicense] = {}

    def analyze(self) -> LicenseResult:
        """
        Run license analysis on packages in requirements.

        Returns:
            LicenseResult with all findings
        """
        start_time = time.time()
        scan_path = Path(self.config.scan_path).resolve()

        if not scan_path.exists():
            raise FileNotFoundError(f"Path not found: {scan_path}")

        # Parse requirements files
        packages, req_files = self._parse_requirements(scan_path)

        # Get license info for each package
        package_licenses = []
        for pkg_name in packages:
            lic_info = self._get_package_license(pkg_name)
            package_licenses.append(lic_info)

        # Find issues
        issues = self._find_issues(package_licenses)

        duration = time.time() - start_time

        return LicenseResult(
            scan_path=str(scan_path),
            scanned_at=datetime.now(),
            scan_duration_seconds=duration,
            config=self.config,
            packages=package_licenses,
            requirements_files_found=req_files,
            issues=issues,
        )

    def _parse_requirements(self, scan_path: Path) -> tuple[Set[str], List[str]]:
        """Parse all requirements files and get package names."""
        packages: Set[str] = set()
        found_files = []

        for req_file in self.config.requirements_files:
            req_path = scan_path / req_file
            if req_path.exists():
                found_files.append(req_file)
                pkg_names = self._parse_requirements_file(req_path)
                packages.update(pkg_names)

        return packages, found_files

    def _parse_requirements_file(self, req_path: Path) -> Set[str]:
        """Parse a single requirements file for package names."""
        packages = set()
        content = req_path.read_text()

        for line in content.split("\n"):
            line = line.strip()

            # Skip empty lines, comments, options
            if not line or line.startswith("#") or line.startswith("-"):
                continue

            # Extract package name (before version specifier, extras, etc.)
            pkg_name = self._extract_package_name(line)
            if pkg_name:
                packages.add(pkg_name.lower())

        return packages

    def _extract_package_name(self, line: str) -> Optional[str]:
        """Extract package name from a requirements line."""
        # Remove extras [...]
        if "[" in line:
            line = line.split("[")[0]

        # Remove version specifiers
        for op in ["===", "~=", "==", ">=", "<=", "!=", ">", "<", "@"]:
            if op in line:
                line = line.split(op)[0]
                break

        # Remove environment markers
        if ";" in line:
            line = line.split(";")[0]

        return line.strip() or None

    def _get_package_license(self, package_name: str) -> PackageLicense:
        """Get license information for a package."""
        # Check cache
        if self.config.use_cache and package_name in self._cache:
            return self._cache[package_name]

        # Try pip show first (installed packages)
        lic_info = self._get_license_from_pip(package_name)

        if lic_info is None:
            # Package not installed, try PyPI
            lic_info = self._get_license_from_pypi(package_name)

        if lic_info is None:
            # Create unknown license entry
            lic_info = PackageLicense(
                package_name=package_name,
                category=LicenseCategory.UNKNOWN,
                severity=LicenseSeverity.MODERATE,
                source="not_found",
            )

        # Classify the license
        lic_info = self._classify_license(lic_info)

        # Cache result
        if self.config.use_cache:
            self._cache[package_name] = lic_info

        return lic_info

    def _get_license_from_pip(self, package_name: str) -> Optional[PackageLicense]:
        """Get license info from pip show."""
        try:
            result = subprocess.run(
                ["pip", "show", package_name],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )

            if result.returncode != 0:
                return None

            info = {}
            for line in result.stdout.split("\n"):
                if ": " in line:
                    key, value = line.split(": ", 1)
                    info[key.strip().lower()] = value.strip()

            return PackageLicense(
                package_name=package_name,
                version=info.get("version"),
                license_name=info.get("license"),
                homepage=info.get("home-page"),
                author=info.get("author"),
                source="pip",
            )

        except (subprocess.TimeoutExpired, FileNotFoundError):
            return None

    def _get_license_from_pypi(self, package_name: str) -> Optional[PackageLicense]:
        """Get license info from PyPI API."""
        try:
            url = f"https://pypi.org/pypi/{package_name}/json"
            with urllib.request.urlopen(url, timeout=10) as response:
                data = json.loads(response.read().decode())

            info = data.get("info", {})
            classifiers = info.get("classifiers", [])

            # Extract license from classifiers
            license_classifier = None
            for classifier in classifiers:
                if classifier.startswith("License ::"):
                    license_classifier = classifier.split(" :: ")[-1]
                    break

            return PackageLicense(
                package_name=package_name,
                version=info.get("version"),
                license_name=info.get("license"),
                license_classifier=license_classifier,
                homepage=info.get("home_page"),
                author=info.get("author"),
                source="pypi",
            )

        except (urllib.error.URLError, json.JSONDecodeError, TimeoutError):
            return None

    def _classify_license(self, pkg_lic: PackageLicense) -> PackageLicense:
        """Classify and validate the license."""
        # Try license_classifier first as classifiers are more standardized
        # But fall back to license_name if classifier doesn't give a useful match
        license_text = ""
        normalized_name = None
        category = LicenseCategory.UNKNOWN

        # First try the classifier
        if pkg_lic.license_classifier:
            classifier_text = pkg_lic.license_classifier
            normalized_name, category = self._normalize_license(classifier_text)
            if category != LicenseCategory.UNKNOWN:
                license_text = classifier_text

        # If classifier didn't match, try license_name
        if category == LicenseCategory.UNKNOWN and pkg_lic.license_name:
            name_text = pkg_lic.license_name
            # If license_name looks like full license text (too long), extract first line
            if len(name_text) > 100:
                first_line = name_text.split("\n")[0].strip()
                if first_line and len(first_line) < 100:
                    name_text = first_line
                else:
                    name_text = ""

            if name_text:
                normalized_name, category = self._normalize_license(name_text)
                if category != LicenseCategory.UNKNOWN:
                    license_text = name_text

        if normalized_name:
            pkg_lic.license_name = normalized_name
        pkg_lic.category = category

        # Check against allowed/prohibited lists
        license_lower = license_text.lower().strip()

        # Only check license lists if we have a non-empty license text
        if license_lower:
            # Check prohibited
            for prohibited in self.config.prohibited_licenses:
                prohibited_lower = prohibited.lower()
                if prohibited_lower in license_lower or license_lower in prohibited_lower:
                    pkg_lic.is_prohibited = True
                    pkg_lic.is_allowed = False
                    pkg_lic.severity = LicenseSeverity.CRITICAL
                    break

            # Check warnings (only if not already prohibited)
            if not pkg_lic.is_prohibited:
                for warn in self.config.warn_licenses:
                    warn_lower = warn.lower()
                    if warn_lower in license_lower or license_lower in warn_lower:
                        pkg_lic.is_warning = True
                        pkg_lic.severity = LicenseSeverity.LOW
                        break

            # Check allowed (only if not prohibited)
            if not pkg_lic.is_prohibited:
                for allowed in self.config.allowed_licenses:
                    allowed_lower = allowed.lower()
                    if allowed_lower in license_lower or license_lower in allowed_lower:
                        pkg_lic.is_allowed = True
                        pkg_lic.severity = LicenseSeverity.OK
                        break

        # Unknown license
        if not license_text or category == LicenseCategory.UNKNOWN:
            pkg_lic.is_allowed = False
            pkg_lic.severity = LicenseSeverity.MODERATE

        return pkg_lic

    def _normalize_license(self, license_text: str) -> tuple[Optional[str], LicenseCategory]:
        """Normalize license name and determine category."""
        if not license_text:
            return None, LicenseCategory.UNKNOWN

        for pattern, (name, category) in LICENSE_PATTERNS.items():
            if re.search(pattern, license_text, re.IGNORECASE):
                return name, category

        return None, LicenseCategory.UNKNOWN

    def _find_issues(self, packages: List[PackageLicense]) -> List[LicenseIssue]:
        """Find license compliance issues."""
        issues = []

        for pkg in packages:
            # Prohibited license
            if pkg.is_prohibited:
                issues.append(LicenseIssue(
                    issue_type=LicenseIssueType.PROHIBITED,
                    severity=LicenseSeverity.CRITICAL,
                    package_name=pkg.package_name,
                    license_name=pkg.display_license,
                    message=f"Package '{pkg.package_name}' has prohibited license: {pkg.display_license}",
                    details={
                        "category": pkg.category.value,
                        "version": pkg.version,
                    },
                ))

            # Copyleft warning
            elif pkg.category in (LicenseCategory.WEAK_COPYLEFT, LicenseCategory.STRONG_COPYLEFT):
                if pkg.category == LicenseCategory.STRONG_COPYLEFT:
                    severity = LicenseSeverity.HIGH
                else:
                    severity = LicenseSeverity.LOW

                issues.append(LicenseIssue(
                    issue_type=LicenseIssueType.COPYLEFT,
                    severity=severity,
                    package_name=pkg.package_name,
                    license_name=pkg.display_license,
                    message=f"Package '{pkg.package_name}' has copyleft license: {pkg.display_license}",
                    details={
                        "category": pkg.category.value,
                        "version": pkg.version,
                    },
                ))

            # Unknown license
            elif pkg.category == LicenseCategory.UNKNOWN:
                issues.append(LicenseIssue(
                    issue_type=LicenseIssueType.UNKNOWN,
                    severity=LicenseSeverity.MODERATE,
                    package_name=pkg.package_name,
                    license_name=pkg.display_license,
                    message=f"Package '{pkg.package_name}' has unknown license: {pkg.display_license}",
                    details={
                        "source": pkg.source,
                        "version": pkg.version,
                    },
                ))

        return issues

    def generate_report(self, result: LicenseResult, output_format: str = "text") -> str:
        """Generate a formatted report."""
        if output_format == "json":
            return self._generate_json_report(result)
        elif output_format == "markdown":
            return self._generate_markdown_report(result)
        else:
            return self._generate_text_report(result)

    def _generate_text_report(self, result: LicenseResult) -> str:
        """Generate text format report."""
        lines = []
        lines.append("")
        lines.append("=" * 70)
        lines.append("  HEIMDALL LICENSE CHECK REPORT")
        lines.append("=" * 70)
        lines.append("")
        lines.append(f"  Scan Path:           {result.scan_path}")
        lines.append(f"  Scanned At:          {result.scanned_at.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"  Duration:            {result.scan_duration_seconds:.2f}s")
        lines.append(f"  Requirements Files:  {', '.join(result.requirements_files_found) or 'None found'}")
        lines.append("")

        if result.has_issues:
            lines.append("-" * 70)
            lines.append("  LICENSE ISSUES")
            lines.append("-" * 70)
            lines.append("")

            by_severity = result.get_issues_by_severity()

            for severity in [LicenseSeverity.CRITICAL, LicenseSeverity.HIGH, LicenseSeverity.MODERATE, LicenseSeverity.LOW]:
                issues = by_severity.get(severity.value, [])
                if issues:
                    lines.append(f"  [{severity.value.upper()}] ({len(issues)} packages):")
                    lines.append("")
                    for issue in issues:
                        lines.append(f"    - {issue.package_name}: {issue.license_name}")
                        lines.append(f"        {issue.message}")
                    lines.append("")
        else:
            lines.append("  All packages have compliant licenses!")
            lines.append("")

        lines.append("-" * 70)
        lines.append("  LICENSE SUMMARY BY CATEGORY")
        lines.append("-" * 70)
        lines.append("")

        by_category = result.get_packages_by_category()
        for category in [LicenseCategory.PERMISSIVE, LicenseCategory.PUBLIC_DOMAIN,
                         LicenseCategory.WEAK_COPYLEFT, LicenseCategory.STRONG_COPYLEFT,
                         LicenseCategory.UNKNOWN]:
            pkgs = by_category.get(category.value, [])
            if pkgs:
                lines.append(f"  {category.value.upper()} ({len(pkgs)} packages):")
                for pkg in pkgs[:5]:
                    lines.append(f"    - {pkg.package_name}: {pkg.display_license}")
                if len(pkgs) > 5:
                    lines.append(f"    ... and {len(pkgs) - 5} more")
                lines.append("")

        lines.append("-" * 70)
        lines.append("  SUMMARY")
        lines.append("-" * 70)
        lines.append("")
        lines.append(f"  Total Packages:      {result.total_packages}")
        lines.append(f"  Compliant:           {result.compliant_packages}")
        lines.append(f"  Warnings:            {result.warning_packages}")
        lines.append(f"  Prohibited:          {result.prohibited_packages}")
        lines.append(f"  Unknown:             {result.unknown_packages}")
        lines.append(f"  Compliance Rate:     {result.compliance_rate:.1f}%")
        lines.append("")
        lines.append("=" * 70)
        lines.append("")

        return "\n".join(lines)

    def _generate_json_report(self, result: LicenseResult) -> str:
        """Generate JSON format report."""
        output = {
            "scan_path": result.scan_path,
            "scanned_at": result.scanned_at.isoformat(),
            "scan_duration_seconds": result.scan_duration_seconds,
            "requirements_files": result.requirements_files_found,
            "summary": {
                "total_packages": result.total_packages,
                "compliant": result.compliant_packages,
                "warnings": result.warning_packages,
                "prohibited": result.prohibited_packages,
                "unknown": result.unknown_packages,
                "compliance_rate": round(result.compliance_rate, 2),
                "has_issues": result.has_issues,
            },
            "packages": [
                {
                    "name": p.package_name,
                    "version": p.version,
                    "license": p.display_license,
                    "category": p.category.value,
                    "severity": p.severity.value,
                    "is_allowed": p.is_allowed,
                    "is_prohibited": p.is_prohibited,
                }
                for p in result.packages
            ],
            "issues": [
                {
                    "type": i.issue_type.value,
                    "severity": i.severity.value,
                    "package": i.package_name,
                    "license": i.license_name,
                    "message": i.message,
                }
                for i in result.issues
            ],
        }

        return json.dumps(output, indent=2)

    def _generate_markdown_report(self, result: LicenseResult) -> str:
        """Generate Markdown format report."""
        lines = []
        lines.append("# Heimdall License Check Report")
        lines.append("")
        lines.append(f"- **Scan Path:** `{result.scan_path}`")
        lines.append(f"- **Scanned At:** {result.scanned_at.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"- **Duration:** {result.scan_duration_seconds:.2f}s")
        lines.append(f"- **Requirements Files:** {', '.join(result.requirements_files_found) or 'None found'}")
        lines.append("")

        lines.append("## Summary")
        lines.append("")
        lines.append(f"- **Total Packages:** {result.total_packages}")
        lines.append(f"- **Compliant:** {result.compliant_packages}")
        lines.append(f"- **Warnings:** {result.warning_packages}")
        lines.append(f"- **Prohibited:** {result.prohibited_packages}")
        lines.append(f"- **Unknown:** {result.unknown_packages}")
        lines.append(f"- **Compliance Rate:** {result.compliance_rate:.1f}%")
        lines.append("")

        if result.has_issues:
            lines.append("## Issues")
            lines.append("")
            lines.append("| Package | License | Category | Severity |")
            lines.append("|---------|---------|----------|----------|")
            for issue in result.issues:
                lines.append(
                    f"| `{issue.package_name}` | {issue.license_name} | "
                    f"{issue.issue_type.value} | {issue.severity.value.upper()} |"
                )
            lines.append("")

        lines.append("## All Packages")
        lines.append("")
        lines.append("| Package | Version | License | Category |")
        lines.append("|---------|---------|---------|----------|")
        for pkg in result.packages:
            lines.append(
                f"| `{pkg.package_name}` | {pkg.version or 'N/A'} | "
                f"{pkg.display_license} | {pkg.category.value} |"
            )
        lines.append("")

        return "\n".join(lines)
