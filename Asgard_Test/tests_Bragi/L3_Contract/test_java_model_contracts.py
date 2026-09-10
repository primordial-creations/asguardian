"""L3 contracts for the public Java quality-analysis models.

These models form the boundary between Java analyzers and report consumers.
The tests pin required diagnostic identity, enum wire values, scan defaults
and isolation, and nested report validation/counting.
"""

from pathlib import Path

import pytest
from pydantic import ValidationError

from Asgard.Bragi.Quality.languages.java.models.java_models import (
    JavaFinding,
    JavaReport,
    JavaRuleCategory,
    JavaScanConfig,
    JavaSeverity,
)


def _finding(**overrides) -> JavaFinding:
    fields = {
        "file_path": "src/main/java/com/example/App.java",
        "line_number": 31,
        "rule_id": "JAVA-S106",
        "category": JavaRuleCategory.CORRECTNESS,
        "severity": JavaSeverity.WARNING,
        "title": "Standard output used",
        "description": "Use the application logger instead.",
    }
    fields.update(overrides)
    return JavaFinding(**fields)


class TestJavaFindingContract:
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
            JavaFinding(**values)

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
            category=JavaRuleCategory.SECURITY,
            severity=JavaSeverity.ERROR,
            code_snippet="logger.info(message);",
        ).model_dump(mode="json")

        assert payload["category"] == "security"
        assert payload["severity"] == "error"
        assert payload["file_path"] == "src/main/java/com/example/App.java"


class TestJavaScanConfigContract:
    def test_defaults_target_java_and_exclude_common_artifacts(self):
        config = JavaScanConfig()

        assert config.scan_path == Path(".")
        assert config.include_extensions == [".java"]
        assert "*/vendor/*" in config.exclude_patterns
        assert "*/build/*" in config.exclude_patterns
        assert config.max_findings == 1000
        assert config.max_file_lines == 10000
        assert config.rules == {}

    def test_path_and_custom_rule_configuration_round_trip(self):
        config = JavaScanConfig(
            scan_path="services/api",
            include_extensions=[".java", ".jav"],
            exclude_patterns=["*/generated/*"],
            max_findings=35,
            max_file_lines=2400,
            rules={"JAVA-S106": False},
        )

        assert config.scan_path == Path("services/api")
        assert config.model_dump(mode="json") == {
            "scan_path": "services/api",
            "include_extensions": [".java", ".jav"],
            "exclude_patterns": ["*/generated/*"],
            "max_findings": 35,
            "max_file_lines": 2400,
            "rules": {"JAVA-S106": False},
        }

    def test_mutable_defaults_are_isolated_between_scans(self):
        first, second = JavaScanConfig(), JavaScanConfig()

        first.include_extensions.append(".jav")
        first.exclude_patterns.append("*/generated/*")
        first.rules["JAVA-S106"] = True

        assert second.include_extensions == [".java"]
        assert "*/generated/*" not in second.exclude_patterns
        assert second.rules == {}

    @pytest.mark.parametrize("field", ["max_findings", "max_file_lines"])
    def test_rejects_non_integer_limits(self, field):
        with pytest.raises(ValidationError):
            JavaScanConfig(**{field: "unbounded"})


class TestJavaReportContract:
    def test_empty_report_is_an_explicit_clean_result(self):
        report = JavaReport(scan_path="services")

        assert report.findings == []
        assert report.total_findings == 0
        assert report.model_dump(mode="json") == {
            "findings": [],
            "scan_path": "services",
        }

    def test_findings_are_validated_and_counted_from_wire_data(self):
        finding_payload = _finding().model_dump(mode="json")
        report = JavaReport(findings=[finding_payload], scan_path="services")

        assert isinstance(report.findings[0], JavaFinding)
        assert report.total_findings == 1
        assert report.model_dump(mode="json")["findings"][0] == finding_payload

    def test_finding_lists_are_not_shared_between_reports(self):
        first, second = JavaReport(), JavaReport()

        first.findings.append(_finding())

        assert first.total_findings == 1
        assert second.findings == []
        assert second.total_findings == 0

    def test_rejects_invalid_nested_findings(self):
        with pytest.raises(ValidationError):
            JavaReport(findings=[{"file_path": "broken.java"}])
