"""L3 contracts for the public C++ quality-analysis models.

These models form the boundary between C++ analyzers and downstream report
consumers.  The tests pin required finding identity, enum validation,
configuration defaults and isolation, and report serialization/counting.
"""

from pathlib import Path

import pytest
from pydantic import ValidationError

from Asgard.Bragi.Quality.languages.cpp.models.cpp_models import (
    CppFinding,
    CppReport,
    CppRuleCategory,
    CppScanConfig,
    CppSeverity,
)


def _finding(**overrides) -> CppFinding:
    fields = {
        "file_path": "src/widget.cpp",
        "line_number": 17,
        "rule_id": "cppcoreguidelines-owning-memory",
        "category": CppRuleCategory.CORRECTNESS,
        "severity": CppSeverity.WARNING,
        "title": "ownership is unclear",
        "description": "A raw pointer obscures ownership.",
    }
    fields.update(overrides)
    return CppFinding(**fields)


class TestCppFindingContract:
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
            CppFinding(**values)

    def test_optional_location_and_remediation_text_have_stable_defaults(self):
        finding = _finding()

        assert finding.column == 0
        assert finding.code_snippet == ""
        assert finding.fix_suggestion == ""

    @pytest.mark.parametrize(
        ("field", "value"),
        [("category", "unknown-category"), ("severity", "critical")],
    )
    def test_rejects_unknown_enum_values(self, field, value):
        with pytest.raises(ValidationError):
            _finding(**{field: value})

    def test_json_shape_uses_wire_enum_values(self):
        payload = _finding(
            category=CppRuleCategory.SECURITY,
            severity=CppSeverity.ERROR,
            code_snippet="char *buffer = new char[8];",
        ).model_dump(mode="json")

        assert payload["category"] == "security"
        assert payload["severity"] == "error"
        assert payload["file_path"] == "src/widget.cpp"


class TestCppScanConfigContract:
    def test_defaults_cover_supported_cpp_files_and_common_artifacts(self):
        config = CppScanConfig()

        assert config.scan_path == Path(".")
        assert config.include_extensions == [
            ".cpp",
            ".cc",
            ".cxx",
            ".c",
            ".h",
            ".hpp",
            ".hxx",
        ]
        assert "*/vendor/*" in config.exclude_patterns
        assert "*/build/*" in config.exclude_patterns
        assert config.max_findings == 1000
        assert config.max_file_lines == 10000
        assert config.rules == {}

    def test_path_and_custom_rule_configuration_round_trip(self):
        config = CppScanConfig(
            scan_path="native/src",
            include_extensions=[".cpp", ".hpp"],
            exclude_patterns=["*/generated/*"],
            max_findings=25,
            max_file_lines=2000,
            rules={"clang-analyzer-core.NullDereference": False},
        )

        assert config.scan_path == Path("native/src")
        assert config.model_dump(mode="json") == {
            "scan_path": "native/src",
            "include_extensions": [".cpp", ".hpp"],
            "exclude_patterns": ["*/generated/*"],
            "max_findings": 25,
            "max_file_lines": 2000,
            "rules": {"clang-analyzer-core.NullDereference": False},
        }

    def test_mutable_defaults_are_isolated_between_scans(self):
        first, second = CppScanConfig(), CppScanConfig()

        first.include_extensions.append(".ixx")
        first.exclude_patterns.append("*/third_party/*")
        first.rules["performance-unnecessary-value-param"] = True

        assert ".ixx" not in second.include_extensions
        assert "*/third_party/*" not in second.exclude_patterns
        assert second.rules == {}

    @pytest.mark.parametrize("field", ["max_findings", "max_file_lines"])
    def test_rejects_non_integer_limits(self, field):
        with pytest.raises(ValidationError):
            CppScanConfig(**{field: "unbounded"})


class TestCppReportContract:
    def test_empty_report_is_an_explicit_clean_result(self):
        report = CppReport(scan_path="native")

        assert report.findings == []
        assert report.total_findings == 0
        assert report.model_dump(mode="json") == {
            "findings": [],
            "scan_path": "native",
        }

    def test_findings_are_validated_and_counted_from_wire_data(self):
        finding_payload = _finding().model_dump(mode="json")
        report = CppReport(findings=[finding_payload], scan_path="native")

        assert isinstance(report.findings[0], CppFinding)
        assert report.total_findings == 1
        assert report.model_dump(mode="json")["findings"][0] == finding_payload

    def test_finding_lists_are_not_shared_between_reports(self):
        first, second = CppReport(), CppReport()

        first.findings.append(_finding())

        assert first.total_findings == 1
        assert second.findings == []
        assert second.total_findings == 0

    def test_rejects_invalid_nested_findings(self):
        with pytest.raises(ValidationError):
            CppReport(findings=[{"file_path": "broken.cpp"}])
