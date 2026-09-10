"""L3 contracts for the public C# quality-analysis models.

These models form the boundary between C# analyzers and report consumers.
The tests pin required diagnostic identity, enum wire values, scan defaults
and isolation, and nested report validation/counting.
"""

from pathlib import Path

import pytest
from pydantic import ValidationError

from Asgard.Bragi.Quality.languages.csharp.models.csharp_models import (
    CsharpFinding,
    CsharpReport,
    CsharpRuleCategory,
    CsharpScanConfig,
    CsharpSeverity,
)


def _finding(**overrides) -> CsharpFinding:
    fields = {
        "file_path": "src/Widget.cs",
        "line_number": 23,
        "rule_id": "CA2000",
        "category": CsharpRuleCategory.CORRECTNESS,
        "severity": CsharpSeverity.WARNING,
        "title": "Dispose objects before losing scope",
        "description": "A disposable object is not disposed on every path.",
    }
    fields.update(overrides)
    return CsharpFinding(**fields)


class TestCsharpFindingContract:
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
            CsharpFinding(**values)

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
            category=CsharpRuleCategory.SECURITY,
            severity=CsharpSeverity.ERROR,
            code_snippet="using var client = new HttpClient();",
        ).model_dump(mode="json")

        assert payload["category"] == "security"
        assert payload["severity"] == "error"
        assert payload["file_path"] == "src/Widget.cs"


class TestCsharpScanConfigContract:
    def test_defaults_target_csharp_and_exclude_common_artifacts(self):
        config = CsharpScanConfig()

        assert config.scan_path == Path(".")
        assert config.include_extensions == [".cs"]
        assert "*/vendor/*" in config.exclude_patterns
        assert "*/build/*" in config.exclude_patterns
        assert config.max_findings == 1000
        assert config.max_file_lines == 10000
        assert config.rules == {}

    def test_path_and_custom_rule_configuration_round_trip(self):
        config = CsharpScanConfig(
            scan_path="dotnet/src",
            include_extensions=[".cs", ".csx"],
            exclude_patterns=["*/Generated/*"],
            max_findings=40,
            max_file_lines=2500,
            rules={"CA2000": False},
        )

        assert config.scan_path == Path("dotnet/src")
        assert config.model_dump(mode="json") == {
            "scan_path": "dotnet/src",
            "include_extensions": [".cs", ".csx"],
            "exclude_patterns": ["*/Generated/*"],
            "max_findings": 40,
            "max_file_lines": 2500,
            "rules": {"CA2000": False},
        }

    def test_mutable_defaults_are_isolated_between_scans(self):
        first, second = CsharpScanConfig(), CsharpScanConfig()

        first.include_extensions.append(".csx")
        first.exclude_patterns.append("*/Generated/*")
        first.rules["CA2000"] = True

        assert second.include_extensions == [".cs"]
        assert "*/Generated/*" not in second.exclude_patterns
        assert second.rules == {}

    @pytest.mark.parametrize("field", ["max_findings", "max_file_lines"])
    def test_rejects_non_integer_limits(self, field):
        with pytest.raises(ValidationError):
            CsharpScanConfig(**{field: "unbounded"})


class TestCsharpReportContract:
    def test_empty_report_is_an_explicit_clean_result(self):
        report = CsharpReport(scan_path="dotnet")

        assert report.findings == []
        assert report.total_findings == 0
        assert report.model_dump(mode="json") == {
            "findings": [],
            "scan_path": "dotnet",
        }

    def test_findings_are_validated_and_counted_from_wire_data(self):
        finding_payload = _finding().model_dump(mode="json")
        report = CsharpReport(findings=[finding_payload], scan_path="dotnet")

        assert isinstance(report.findings[0], CsharpFinding)
        assert report.total_findings == 1
        assert report.model_dump(mode="json")["findings"][0] == finding_payload

    def test_finding_lists_are_not_shared_between_reports(self):
        first, second = CsharpReport(), CsharpReport()

        first.findings.append(_finding())

        assert first.total_findings == 1
        assert second.findings == []
        assert second.total_findings == 0

    def test_rejects_invalid_nested_findings(self):
        with pytest.raises(ValidationError):
            CsharpReport(findings=[{"file_path": "broken.cs"}])
