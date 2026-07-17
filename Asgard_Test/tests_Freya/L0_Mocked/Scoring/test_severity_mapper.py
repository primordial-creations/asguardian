"""
Freya Severity Mapper Tests

L0 tests for the per-category severity mapping tables.
"""

import pytest

from Asgard.Freya.Integration.models.integration_models import (
    TestCategory,
    TestSeverity,
    UnifiedTestResult,
)
from Asgard.Freya.Scoring.models.scoring_models import UniversalSeverity
from Asgard.Freya.Scoring.services.severity_mapper import (
    CATEGORY_SEVERITY_MAPS,
    SeverityMapper,
    escalate_for_criticality,
    issue_dicts_to_findings,
)


class TestMappingTables:
    def test_all_categories_present(self):
        for category in ("accessibility", "visual", "responsive", "security",
                         "performance", "links", "seo", "console", "images"):
            assert category in CATEGORY_SEVERITY_MAPS

    def test_accessibility_representative(self):
        mapper = SeverityMapper()
        assert mapper.map("accessibility", "critical") == UniversalSeverity.CRITICAL
        assert mapper.map("accessibility", "serious") == UniversalSeverity.MAJOR
        assert mapper.map("accessibility", "info") == UniversalSeverity.MINOR

    def test_security_critical_is_blocker(self):
        assert SeverityMapper().map("security", "critical") == UniversalSeverity.BLOCKER

    def test_performance_never_blocker(self):
        mapper = SeverityMapper()
        for source in ("critical", "serious", "moderate", "minor"):
            assert mapper.map("performance", source) != UniversalSeverity.BLOCKER

    def test_unknown_category_defaults_minor(self):
        assert SeverityMapper().map("nonexistent", "critical") == UniversalSeverity.MINOR

    def test_unknown_severity_defaults_minor(self):
        assert SeverityMapper().map("visual", "bizarre") == UniversalSeverity.MINOR

    def test_keyboard_trap_is_blocker(self):
        mapper = SeverityMapper()
        assert mapper.map(
            "accessibility", "critical", wcag_reference="2.1.2"
        ) == UniversalSeverity.BLOCKER
        assert mapper.map(
            "accessibility", "serious", check_id="Keyboard trap detected"
        ) == UniversalSeverity.BLOCKER


class TestCriticalityEscalation:
    def test_interactive_escalates_one_step(self):
        assert escalate_for_criticality(
            UniversalSeverity.MAJOR, "accessibility", "interactive"
        ) == UniversalSeverity.CRITICAL
        assert escalate_for_criticality(
            UniversalSeverity.CRITICAL, "accessibility", "primary_interactive"
        ) == UniversalSeverity.BLOCKER

    def test_static_does_not_escalate(self):
        assert escalate_for_criticality(
            UniversalSeverity.MAJOR, "accessibility", "content"
        ) == UniversalSeverity.MAJOR
        assert escalate_for_criticality(
            UniversalSeverity.MAJOR, "accessibility", None
        ) == UniversalSeverity.MAJOR

    def test_no_blocker_categories_capped_at_critical(self):
        assert escalate_for_criticality(
            UniversalSeverity.CRITICAL, "performance", "primary_interactive"
        ) == UniversalSeverity.CRITICAL


class TestMapUnifiedResult:
    def test_passing_result_returns_none(self):
        result = UnifiedTestResult(
            category=TestCategory.ACCESSIBILITY,
            test_name="WCAG Validation",
            passed=True,
            message="ok",
        )
        assert SeverityMapper().map_unified_result(result) is None

    def test_failed_result_maps(self):
        result = UnifiedTestResult(
            category=TestCategory.ACCESSIBILITY,
            test_name="Color Contrast",
            passed=False,
            severity=TestSeverity.SERIOUS,
            message="Insufficient contrast",
            element_selector=".text",
            wcag_reference="1.4.3",
        )
        finding = SeverityMapper().map_unified_result(result)
        assert finding is not None
        assert finding.category == "accessibility"
        assert finding.severity == UniversalSeverity.MAJOR
        assert finding.check_id == "wcag.1.4.3"
        assert finding.selector == ".text"
        assert finding.source_severity == "serious"

    def test_map_unified_results_skips_passes(self):
        results = [
            UnifiedTestResult(category=TestCategory.VISUAL, test_name="t",
                              passed=True, message="ok"),
            UnifiedTestResult(category=TestCategory.VISUAL, test_name="Layout",
                              passed=False, severity=TestSeverity.CRITICAL, message="broken"),
        ]
        findings = SeverityMapper().map_unified_results(results)
        assert len(findings) == 1
        assert findings[0].severity == UniversalSeverity.CRITICAL


class TestIssueDictAdapter:
    def test_basic_mapping(self):
        findings = issue_dicts_to_findings(
            [{"type": "missing-alt", "severity": "serious", "message": "Image missing alt"}],
            url="https://example.com",
            category="accessibility",
        )
        assert len(findings) == 1
        assert findings[0].severity == UniversalSeverity.MAJOR
        assert findings[0].url == "https://example.com"
        assert findings[0].check_id == "accessibility.missing-alt"

    def test_non_dict_items_skipped(self):
        assert issue_dicts_to_findings(["not-a-dict"], category="visual") == []

    def test_unknown_category_falls_back(self):
        findings = issue_dicts_to_findings(
            [{"type": "x", "severity": "minor", "message": "m"}],
            category="weird",
        )
        assert findings[0].category == "accessibility"
