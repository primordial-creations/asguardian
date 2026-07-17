"""Heimdall License Checker - validates package license compliance.

Lookup order (Plan 03 Phase D): disk cache -> installed importlib.metadata
(no `pip show` subprocess) -> PyPI JSON fallback, fetched in parallel with a
bounded pool. Results are deterministic: packages are resolved and reported
in sorted name order.
"""

import importlib.metadata
import subprocess
import time
import json
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set

from Asgard.Bragi.Dependencies.models.license_models import (
    LicenseCategory,
    LicenseConfig,
    LicenseIssue,
    LicenseIssueType,
    LicenseResult,
    LicenseSeverity,
    PackageLicense,
)
from Asgard.Bragi.Dependencies.services._license_cache import LicenseDiskCache
from Asgard.Bragi.Dependencies.services._license_policy import (
    LicenseGateInput,
    LicensePolicy,
    LicenseVerdict,
    normalize_license,
)
from Asgard.Bragi.Dependencies.services._license_reporter import (
    generate_json_report,
    generate_markdown_report,
    generate_text_report,
)


class LicenseChecker:
    """Validates license compliance for Python packages."""

    #: Bounded pool size for parallel PyPI fallback fetches.
    MAX_FETCH_WORKERS = 8

    def __init__(self, config: LicenseConfig):
        self.config = config
        self._cache: Dict[str, PackageLicense] = {}
        self._disk_cache: Optional[LicenseDiskCache] = None
        # Exact-SPDX-id policy engine (Plan 03 Phase A): substring matching
        # is gone - LGPL-3.0 can never be prohibited by containing "GPL-3.0".
        self.policy = LicensePolicy(
            allowed=config.allowed_licenses,
            prohibited=config.prohibited_licenses,
            warn=config.warn_licenses,
        )

    def analyze(self) -> LicenseResult:
        """Run license analysis on packages in requirements."""
        start_time = time.time()
        scan_path = Path(self.config.scan_path).resolve()

        if not scan_path.exists():
            raise FileNotFoundError(f"Path not found: {scan_path}")

        packages, req_files = self._parse_requirements(scan_path)

        if self.config.use_cache:
            self._disk_cache = LicenseDiskCache(
                scan_path, expiry_days=self.config.cache_expiry_days)

        package_licenses = self._resolve_packages(sorted(packages))

        if self._disk_cache is not None:
            self._disk_cache.save()

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
            if not line or line.startswith("#") or line.startswith("-"):
                continue
            pkg_name = self._extract_package_name(line)
            if pkg_name:
                packages.add(pkg_name.lower())
        return packages

    def _extract_package_name(self, line: str) -> Optional[str]:
        """Extract package name from a requirements line."""
        if "[" in line:
            line = line.split("[")[0]
        for op in ["===", "~=", "==", ">=", "<=", "!=", ">", "<", "@"]:
            if op in line:
                line = line.split(op)[0]
                break
        if ";" in line:
            line = line.split(";")[0]
        return line.strip() or None

    def _resolve_packages(self, package_names: List[str]) -> List[PackageLicense]:
        """
        Resolve licenses for all packages: disk cache, then local installed
        metadata, then PyPI in parallel (bounded pool) for the leftovers.
        Output order is deterministic (sorted by package name).
        """
        resolved: Dict[str, PackageLicense] = {}
        needs_network: List[str] = []

        for pkg_name in package_names:
            local = self._get_package_license_local(pkg_name)
            if local is not None:
                resolved[pkg_name] = local
            else:
                needs_network.append(pkg_name)

        if needs_network:
            from concurrent.futures import ThreadPoolExecutor
            workers = min(self.MAX_FETCH_WORKERS, len(needs_network))
            with ThreadPoolExecutor(max_workers=workers) as pool:
                fetched = list(pool.map(self._get_license_from_pypi,
                                        needs_network))
            for pkg_name, lic_info in zip(needs_network, fetched):
                if lic_info is None:
                    lic_info = PackageLicense(
                        package_name=pkg_name,
                        category=LicenseCategory.UNKNOWN,
                        severity=LicenseSeverity.MODERATE,
                        source="not_found",
                    )
                resolved[pkg_name] = self._finish_resolution(pkg_name, lic_info)

        return [resolved[name] for name in package_names]

    def _get_package_license_local(
        self, package_name: str
    ) -> Optional[PackageLicense]:
        """Cache/installed-metadata resolution (no network)."""
        if self.config.use_cache and package_name in self._cache:
            return self._cache[package_name]

        if self._disk_cache is not None:
            record = self._disk_cache.get(package_name)
            if record is not None:
                lic_info = PackageLicense(
                    package_name=package_name,
                    version=record.get("version"),
                    license_name=record.get("license_name"),
                    license_classifier=record.get("license_classifier"),
                    homepage=record.get("homepage"),
                    author=record.get("author"),
                    source=record.get("source", "cache"),
                )
                lic_info = self._classify_license(lic_info)
                if self.config.use_cache:
                    self._cache[package_name] = lic_info
                return lic_info

        lic_info = self._get_license_from_installed(package_name)
        if lic_info is None:
            return None
        return self._finish_resolution(package_name, lic_info)

    def _finish_resolution(
        self, package_name: str, lic_info: PackageLicense
    ) -> PackageLicense:
        """Classify a freshly fetched record and store it in both caches."""
        lic_info = self._classify_license(lic_info)
        if self.config.use_cache:
            self._cache[package_name] = lic_info
        if self._disk_cache is not None and lic_info.source != "not_found":
            self._disk_cache.put(package_name, {
                "version": lic_info.version,
                "license_name": lic_info.license_name,
                "license_classifier": lic_info.license_classifier,
                "homepage": lic_info.homepage,
                "author": lic_info.author,
                "source": lic_info.source,
            })
        return lic_info

    def _get_package_license(self, package_name: str) -> PackageLicense:
        """Get license information for a single package (legacy entry point)."""
        local = self._get_package_license_local(package_name)
        if local is not None:
            return local
        lic_info = self._get_license_from_pypi(package_name)
        if lic_info is None:
            lic_info = PackageLicense(
                package_name=package_name,
                category=LicenseCategory.UNKNOWN,
                severity=LicenseSeverity.MODERATE,
                source="not_found",
            )
        return self._finish_resolution(package_name, lic_info)

    def _get_license_from_installed(
        self, package_name: str
    ) -> Optional[PackageLicense]:
        """License info from installed importlib.metadata (replaces pip show).

        Precedence: PEP 639 License-Expression, then trove classifier, then
        the legacy License header.
        """
        try:
            meta = importlib.metadata.metadata(package_name)
        except importlib.metadata.PackageNotFoundError:
            return None
        except Exception:
            return None

        def _get(key: str) -> Optional[str]:
            try:
                value = meta.get(key)
            except Exception:
                return None
            value = (value or "").strip()
            return value or None

        license_classifier = None
        try:
            classifiers = meta.get_all("Classifier") or []
        except Exception:
            classifiers = []
        for classifier in classifiers:
            if classifier.startswith("License ::"):
                license_classifier = classifier.split(" :: ")[-1].strip()
                break

        license_name = _get("License-Expression") or _get("License")
        return PackageLicense(
            package_name=package_name,
            version=_get("Version"),
            license_name=license_name,
            license_classifier=license_classifier,
            homepage=_get("Home-page"),
            author=_get("Author") or _get("Author-email"),
            source="installed",
        )

    def _get_license_from_pip(self, package_name: str) -> Optional[PackageLicense]:
        """Get license info from pip show."""
        try:
            result = subprocess.run(
                ["pip", "show", package_name],
                capture_output=True, text=True, timeout=10, check=False,
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
        """
        Classify and validate the license via the exact-SPDX-id policy engine.

        Handles SPDX expressions: 'MIT OR GPL-3.0' is compliant via the MIT
        arm (recorded on the package as a MULTIPLE candidate).
        """
        candidates = []
        if pkg_lic.license_classifier:
            candidates.append(pkg_lic.license_classifier)
        if pkg_lic.license_name:
            name_text = pkg_lic.license_name
            if len(name_text) > 100:
                first_line = name_text.split("\n")[0].strip()
                name_text = first_line if first_line and len(first_line) < 100 else ""
            if name_text:
                candidates.append(name_text)

        decision = None
        for candidate in candidates:
            evaluated = self.policy.evaluate(candidate)
            if decision is None or (
                decision.category == LicenseCategory.UNKNOWN
                and evaluated.category != LicenseCategory.UNKNOWN
            ):
                decision = evaluated
            if decision.category != LicenseCategory.UNKNOWN:
                break

        if decision is None or (decision.spdx_id is None and not decision.is_expression):
            pkg_lic.category = LicenseCategory.UNKNOWN
            pkg_lic.is_allowed = False
            pkg_lic.severity = LicenseSeverity.MODERATE
            pkg_lic.verdict = LicenseVerdict.UNKNOWN.value
            return pkg_lic

        if decision.spdx_id:
            pkg_lic.license_name = decision.spdx_id
        pkg_lic.category = decision.category
        pkg_lic.license_expression_arms = list(decision.arms)
        pkg_lic.chosen_expression_arm = decision.chosen_arm

        pkg_lic.verdict = decision.verdict.value
        if decision.verdict == LicenseVerdict.PROHIBITED:
            pkg_lic.is_prohibited = True
            pkg_lic.is_allowed = False
            pkg_lic.severity = LicenseSeverity.CRITICAL
        elif decision.verdict == LicenseVerdict.WARN:
            # Legacy boolean semantics preserved: WARN packages stay
            # is_allowed=True (they count as compliant, as before); the
            # stricter signal lives in the new `verdict` field.
            pkg_lic.is_warning = True
            pkg_lic.is_allowed = True
            pkg_lic.severity = LicenseSeverity.LOW
        elif decision.verdict == LicenseVerdict.ALLOWED:
            pkg_lic.is_allowed = True
            pkg_lic.severity = LicenseSeverity.OK
        else:
            pkg_lic.is_allowed = False
            pkg_lic.severity = LicenseSeverity.MODERATE

        return pkg_lic

    def _normalize_license(self, license_text: str) -> tuple[Optional[str], LicenseCategory]:
        """Normalize license name and determine category (exact-id engine)."""
        return normalize_license(license_text)

    def gate_input(self, result: LicenseResult) -> LicenseGateInput:
        """Summary for Plan 01's non-compensatory license gate."""
        return LicenseGateInput(
            prohibited_count=result.prohibited_packages,
            unknown_count=result.unknown_packages,
        )

    def _find_issues(self, packages: List[PackageLicense]) -> List[LicenseIssue]:
        """Find license compliance issues."""
        issues = []
        for pkg in packages:
            if len(pkg.license_expression_arms) > 1:
                issues.append(LicenseIssue(
                    issue_type=LicenseIssueType.MULTIPLE,
                    severity=LicenseSeverity.OK if pkg.is_allowed else LicenseSeverity.LOW,
                    package_name=pkg.package_name,
                    license_name=pkg.display_license,
                    message=(
                        f"Package '{pkg.package_name}' is multi-licensed "
                        f"({' / '.join(pkg.license_expression_arms)})"
                        + (f"; compliant via {pkg.chosen_expression_arm}"
                           if pkg.chosen_expression_arm and pkg.is_allowed else "")
                    ),
                    details={"arms": pkg.license_expression_arms,
                             "chosen_arm": pkg.chosen_expression_arm},
                ))
            if pkg.is_prohibited:
                issues.append(LicenseIssue(
                    issue_type=LicenseIssueType.PROHIBITED,
                    severity=LicenseSeverity.CRITICAL,
                    package_name=pkg.package_name,
                    license_name=pkg.display_license,
                    message=f"Package '{pkg.package_name}' has prohibited license: {pkg.display_license}",
                    details={"category": pkg.category.value, "version": pkg.version},
                ))
            elif pkg.category in (LicenseCategory.WEAK_COPYLEFT, LicenseCategory.STRONG_COPYLEFT):
                severity = LicenseSeverity.HIGH if pkg.category == LicenseCategory.STRONG_COPYLEFT else LicenseSeverity.LOW
                issues.append(LicenseIssue(
                    issue_type=LicenseIssueType.COPYLEFT,
                    severity=severity,
                    package_name=pkg.package_name,
                    license_name=pkg.display_license,
                    message=f"Package '{pkg.package_name}' has copyleft license: {pkg.display_license}",
                    details={"category": pkg.category.value, "version": pkg.version},
                ))
            elif pkg.category == LicenseCategory.UNKNOWN:
                issues.append(LicenseIssue(
                    issue_type=LicenseIssueType.UNKNOWN,
                    severity=LicenseSeverity.MODERATE,
                    package_name=pkg.package_name,
                    license_name=pkg.display_license,
                    message=f"Package '{pkg.package_name}' has unknown license: {pkg.display_license}",
                    details={"source": pkg.source, "version": pkg.version},
                ))
        return issues

    def generate_report(self, result: LicenseResult, output_format: str = "text") -> str:
        """Generate a formatted report."""
        if output_format == "json":
            return generate_json_report(result)
        elif output_format == "markdown":
            return generate_markdown_report(result)
        else:
            return generate_text_report(result)
