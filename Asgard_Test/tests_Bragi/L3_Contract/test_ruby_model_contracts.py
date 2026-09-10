"""L3 contracts for the public Ruby quality-analysis models.

These models form the boundary between Ruby analyzers and report consumers.
The tests pin required diagnostic identity, enum wire values, scan defaults
and isolation, and nested report validation/counting.
"""

from pathlib import Path

import pytest
from pydantic import ValidationError

from Asgard.Bragi.Quality.languages.ruby.models.ruby_models import (
    RubyFinding,
    RubyReport,
    RubyRuleCategory,
    RubyScanConfig,
    RubySeverity,
)


def _finding(**overrides) -> RubyFinding:
    fields = {
        "file_path": "lib/accounts/profile.rb",
        "line_number": 31,
        "rule_id": "Style/GuardClause",
        "category": RubyRuleCategory.CORRECTNESS,
        "severity": RubySeverity.WARNING,
        "title": "Guard clause preferred",
        "description": "Use a guard clause to reduce nesting.",
    }
    fields.update(overrides)
    return RubyFinding(**fields)


class TestRubyFindingContract:
    @pytest.mark.parametrize(
        "missing",
        [
            "file_path",
            "line_number",
            "rule_id",
            "category",
            "severity",
            "title",
            "description",
        ],
    )
    def test_requires_each_identity_and_diagnostic_field(self, missing):
        values = _finding().model_dump()
        del values[missing]

        with pytest.raises(ValidationError):
            RubyFinding(**values)

    def test_optional_location_and_remediation_text_have_stable_defaults(self):
        finding = _finding()

        assert finding.column == 0
        assert finding.code_snippet == ""
        assert finding.fix_suggestion == ""

    @pytest.mark.parametrize(
        ("field", "value"),
        [("category", "reliability"), ("severity", "critical")],
    )
    def test_rejects_unknown_enum_values(self, field, value):
        with pytest.raises(ValidationError):
            _finding(**{field: value})

    def test_json_shape_uses_wire_enum_values(self):
        payload = _finding(
            category=RubyRuleCategory.SECURITY,
            severity=RubySeverity.ERROR,
            code_snippet="Kernel.exec(command)",
        ).model_dump(mode="json")

        assert payload["category"] == "security"
        assert payload["severity"] == "error"
        assert payload["file_path"] == "lib/accounts/profile.rb"


class TestRubyScanConfigContract:
    def test_defaults_target_ruby_and_exclude_common_artifacts(self):
        config = RubyScanConfig()

        assert config.scan_path == Path(".")
        assert config.include_extensions == [".rb", ".rake", ".gemspec"]
        assert "*/vendor/*" in config.exclude_patterns
        assert "*/build/*" in config.exclude_patterns
        assert config.max_findings == 1000
        assert config.max_file_lines == 10000
        assert config.rules == {}

    def test_path_and_custom_rule_configuration_round_trip(self):
        config = RubyScanConfig(
            scan_path="services/api",
            include_extensions=[".rb", ".ru"],
            exclude_patterns=["*/generated/*"],
            max_findings=35,
            max_file_lines=2400,
            rules={"Style/GuardClause": False},
        )

        assert config.scan_path == Path("services/api")
        assert config.model_dump(mode="json") == {
            "scan_path": "services/api",
            "include_extensions": [".rb", ".ru"],
            "exclude_patterns": ["*/generated/*"],
            "max_findings": 35,
            "max_file_lines": 2400,
            "rules": {"Style/GuardClause": False},
        }

    def test_mutable_defaults_are_isolated_between_scans(self):
        first, second = RubyScanConfig(), RubyScanConfig()

        first.include_extensions.append(".ru")
        first.exclude_patterns.append("*/generated/*")
        first.rules["Style/GuardClause"] = True

        assert second.include_extensions == [".rb", ".rake", ".gemspec"]
        assert "*/generated/*" not in second.exclude_patterns
        assert second.rules == {}

    @pytest.mark.parametrize("field", ["max_findings", "max_file_lines"])
    def test_rejects_non_integer_limits(self, field):
        with pytest.raises(ValidationError):
            RubyScanConfig(**{field: "unbounded"})


class TestRubyReportContract:
    def test_empty_report_is_an_explicit_clean_result(self):
        report = RubyReport(scan_path="services")

        assert report.findings == []
        assert report.total_findings == 0
        assert report.model_dump(mode="json") == {
            "findings": [],
            "scan_path": "services",
        }

    def test_findings_are_validated_and_counted_from_wire_data(self):
        finding_payload = _finding().model_dump(mode="json")
        report = RubyReport(findings=[finding_payload], scan_path="services")

        assert isinstance(report.findings[0], RubyFinding)
        assert report.total_findings == 1
        assert report.model_dump(mode="json")["findings"][0] == finding_payload

    def test_finding_lists_are_not_shared_between_reports(self):
        first, second = RubyReport(), RubyReport()

        first.findings.append(_finding())

        assert first.total_findings == 1
        assert second.findings == []
        assert second.total_findings == 0

    def test_rejects_invalid_nested_findings(self):
        with pytest.raises(ValidationError):
            RubyReport(findings=[{"file_path": "broken.rb"}])
