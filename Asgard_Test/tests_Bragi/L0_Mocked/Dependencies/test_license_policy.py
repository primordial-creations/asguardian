"""
Tests for the Bragi license policy engine and checker delegation (Plan 03 A).

Named regression: LGPL-3.0 must classify as WARN, never PROHIBITED - the old
bidirectional substring match flagged it because "gpl-3.0" is inside
"lgpl-3.0". Also covers SPDX OR/AND expression handling and gate export.
"""

import pytest

from Asgard.Bragi.Dependencies.models.license_models import (
    LicenseCategory,
    LicenseConfig,
    LicenseIssueType,
    LicenseSeverity,
    PackageLicense,
)
from Asgard.Bragi.Dependencies.services._license_policy import (
    LicensePolicy,
    LicenseVerdict,
    canonical_spdx_id,
    normalize_license,
)
from Asgard.Bragi.Dependencies.services.license_checker import LicenseChecker


def _policy():
    config = LicenseConfig()
    return LicensePolicy(
        allowed=config.allowed_licenses,
        prohibited=config.prohibited_licenses,
        warn=config.warn_licenses,
    )


def _checker():
    return LicenseChecker(LicenseConfig())


class TestNormalization:
    def test_lgpl_never_normalizes_to_gpl(self):
        spdx_id, category = normalize_license("LGPL-3.0")
        assert spdx_id == "LGPL-3.0"
        assert category == LicenseCategory.WEAK_COPYLEFT

    def test_gnu_lesser_text(self):
        spdx_id, _ = normalize_license("GNU Lesser General Public License v3 (LGPLv3)")
        assert spdx_id == "LGPL-3.0"

    def test_agpl_beats_gpl(self):
        spdx_id, category = normalize_license("GNU Affero General Public License v3")
        assert spdx_id == "AGPL-3.0"
        assert category == LicenseCategory.STRONG_COPYLEFT

    def test_common_permissive(self):
        assert normalize_license("MIT License")[0] == "MIT"
        assert normalize_license("Apache Software License")[0] == "Apache-2.0"
        assert normalize_license("BSD 3-Clause")[0] == "BSD-3-Clause"

    def test_unknown_text(self):
        spdx_id, category = normalize_license("Custom Proprietary EULA v7")
        assert spdx_id is None
        assert category == LicenseCategory.UNKNOWN

    def test_canonical_aliases(self):
        assert canonical_spdx_id("GPL-3.0-only") == "GPL-3.0"
        assert canonical_spdx_id("gpl-3.0-or-later") == "GPL-3.0"
        assert canonical_spdx_id("nonsense") is None


class TestExactIdPolicy:
    def test_lgpl3_is_warn_not_prohibited(self):
        """THE substring-bug regression test."""
        decision = _policy().evaluate("LGPL-3.0")
        assert decision.verdict == LicenseVerdict.WARN
        assert decision.verdict != LicenseVerdict.PROHIBITED

    def test_gpl3_prohibited(self):
        assert _policy().evaluate("GPL-3.0").verdict == LicenseVerdict.PROHIBITED

    def test_agpl_prohibited(self):
        assert _policy().evaluate("AGPL-3.0").verdict == LicenseVerdict.PROHIBITED

    def test_mit_allowed(self):
        assert _policy().evaluate("MIT").verdict == LicenseVerdict.ALLOWED

    def test_empty_is_unknown(self):
        assert _policy().evaluate("").verdict == LicenseVerdict.UNKNOWN

    def test_no_substring_matching_either_direction(self):
        # "GPL" alone must not match the prohibited GPL-3.0 entry by substring;
        # it normalizes to GPL-2.0-or-later which is copyleft -> WARN.
        decision = _policy().evaluate("GPL")
        assert decision.verdict != LicenseVerdict.PROHIBITED


class TestSpdxExpressions:
    def test_or_compliant_via_mit_arm(self):
        decision = _policy().evaluate("MIT OR GPL-3.0")
        assert decision.verdict == LicenseVerdict.ALLOWED
        assert decision.is_expression is True
        assert decision.chosen_arm == "MIT"
        assert set(decision.arms) == {"MIT", "GPL-3.0"}

    def test_or_all_prohibited(self):
        decision = _policy().evaluate("GPL-3.0 OR AGPL-3.0")
        assert decision.verdict == LicenseVerdict.PROHIBITED

    def test_and_worst_arm_wins(self):
        decision = _policy().evaluate("MIT AND GPL-3.0")
        assert decision.verdict == LicenseVerdict.PROHIBITED

    def test_and_of_allowed(self):
        decision = _policy().evaluate("MIT AND Apache-2.0")
        assert decision.verdict == LicenseVerdict.ALLOWED

    def test_with_exception_clause(self):
        decision = _policy().evaluate("Apache-2.0 WITH LLVM-exception OR MIT")
        assert decision.verdict == LicenseVerdict.ALLOWED

    def test_parenthesized(self):
        decision = _policy().evaluate("(MIT OR GPL-3.0) AND ISC")
        # Parenthesized OR group is an arm; policy still finds a compliant path.
        assert decision.verdict in (LicenseVerdict.ALLOWED, LicenseVerdict.WARN)


class TestCheckerDelegation:
    def test_lgpl_package_not_prohibited(self):
        checker = _checker()
        pkg = PackageLicense(package_name="paramiko", license_name="LGPL-3.0")
        classified = checker._classify_license(pkg)
        assert classified.is_prohibited is False
        assert classified.is_warning is True
        assert classified.severity == LicenseSeverity.LOW
        assert classified.category == LicenseCategory.WEAK_COPYLEFT

    def test_gpl_package_prohibited(self):
        pkg = PackageLicense(package_name="x", license_name="GPL-3.0")
        classified = _checker()._classify_license(pkg)
        assert classified.is_prohibited is True
        assert classified.severity == LicenseSeverity.CRITICAL

    def test_mit_package_allowed(self):
        pkg = PackageLicense(package_name="x", license_name="MIT")
        classified = _checker()._classify_license(pkg)
        assert classified.is_allowed is True
        assert classified.severity == LicenseSeverity.OK

    def test_unknown_package_flagged_moderate(self):
        pkg = PackageLicense(package_name="x", license_name="My Custom EULA")
        classified = _checker()._classify_license(pkg)
        assert classified.is_allowed is False
        assert classified.severity == LicenseSeverity.MODERATE
        assert classified.category == LicenseCategory.UNKNOWN

    def test_or_expression_emits_multiple_issue(self):
        checker = _checker()
        pkg = PackageLicense(package_name="dual", license_name="MIT OR GPL-3.0")
        classified = checker._classify_license(pkg)
        assert classified.is_allowed is True
        assert classified.chosen_expression_arm == "MIT"
        issues = checker._find_issues([classified])
        multiple = [i for i in issues if i.issue_type == LicenseIssueType.MULTIPLE]
        assert len(multiple) == 1
        assert "MIT" in multiple[0].message

    def test_gate_input_export(self):
        from datetime import datetime
        from Asgard.Bragi.Dependencies.models.license_models import LicenseResult
        checker = _checker()
        prohibited = checker._classify_license(
            PackageLicense(package_name="p", license_name="AGPL-3.0"))
        unknown = checker._classify_license(
            PackageLicense(package_name="u", license_name="Weird License"))
        result = LicenseResult(
            scan_path=".", scanned_at=datetime.now(), scan_duration_seconds=0.0,
            config=checker.config, packages=[prohibited, unknown])
        gate = checker.gate_input(result)
        assert gate.prohibited_count == 1
        assert gate.unknown_count == 1


class TestPurlAndSBOM:
    def test_purl_underscore_to_hyphen(self):
        """Spec regression: typing_extensions -> pkg:pypi/typing-extensions."""
        from Asgard.Bragi.Dependencies.services._sbom_parsers import make_purl
        assert make_purl("typing_extensions", "4.7.1") == "pkg:pypi/typing-extensions@4.7.1"

    def test_purl_hyphen_preserved(self):
        from Asgard.Bragi.Dependencies.services._sbom_parsers import make_purl
        assert make_purl("python-dateutil", "2.8.2") == "pkg:pypi/python-dateutil@2.8.2"

    def test_purl_dots_normalized_and_spec_stripped(self):
        from Asgard.Bragi.Dependencies.services._sbom_parsers import make_purl
        assert make_purl("zope.interface", ">=5.0") == "pkg:pypi/zope-interface@5.0"

    def test_sbom_resolved_version_not_spec(self, tmp_path):
        """A generated component for an installed package must carry the
        resolved version, with the spec preserved separately."""
        from Asgard.Bragi.Dependencies.models.sbom_models import SBOMConfig
        from Asgard.Bragi.Dependencies.services.sbom_generator import SBOMGenerator
        import pydantic
        (tmp_path / "requirements.txt").write_text("pydantic>=1.0\nnot-a-real-pkg-xyz==9.9\n")
        document = SBOMGenerator(SBOMConfig(scan_path=tmp_path)).generate(str(tmp_path))
        by_name = {c.name: c for c in document.components}
        assert by_name["pydantic"].version == pydantic.VERSION
        assert by_name["pydantic"].version_spec == ">=1.0"
        assert by_name["pydantic"].version_resolution == "resolved"
        assert by_name["not-a-real-pkg-xyz"].version_resolution == "declared-only"
        assert by_name["not-a-real-pkg-xyz"].version == "==9.9"

    def test_sbom_completeness_marker(self, tmp_path):
        from Asgard.Bragi.Dependencies.models.sbom_models import SBOMConfig
        from Asgard.Bragi.Dependencies.services.sbom_generator import SBOMGenerator
        (tmp_path / "requirements.txt").write_text("requests==2.28.0\n")
        document = SBOMGenerator(SBOMConfig(scan_path=tmp_path)).generate(str(tmp_path))
        assert document.resolution == "declared-only"


class TestGetModuleIndex:
    def test_get_module_o1_lookup_correct(self):
        from Asgard.Bragi.Dependencies.models.dependency_models import (
            DependencyReport,
            ModuleDependencies,
        )
        report = DependencyReport(scan_path=".")
        for i in range(100):
            report.add_module(ModuleDependencies(
                module_name=f"pkg.mod{i}", file_path=f"/p/mod{i}.py",
                relative_path=f"mod{i}.py"))
        assert report.get_module("pkg.mod42").file_path == "/p/mod42.py"
        assert report.get_module("missing") is None
        # Index refreshes when modules are added after a lookup.
        report.add_module(ModuleDependencies(
            module_name="late", file_path="/p/late.py", relative_path="late.py"))
        assert report.get_module("late") is not None
