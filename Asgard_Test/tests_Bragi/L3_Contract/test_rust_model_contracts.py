"""L3 contracts for the public Rust quality-analysis models.

These models form the boundary between Rust analyzers and report consumers.
The tests pin diagnostic identity, enum wire values, scan defaults and
isolation, and nested report validation/counting.
"""

from pathlib import Path

import pytest
from pydantic import ValidationError

from Asgard.Bragi.Quality.languages.rust.models.rust_models import (
    RustFinding,
    RustReport,
    RustRuleCategory,
    RustScanConfig,
    RustSeverity,
)


def _finding(**overrides) -> RustFinding:
    fields = {
        "file_path": "crates/accounts/src/profile.rs",
        "line_number": 31,
        "rule_id": "clippy::needless_borrow",
        "category": RustRuleCategory.CORRECTNESS,
        "severity": RustSeverity.WARNING,
        "title": "Needless borrow",
        "description": "Remove the borrow before passing this value.",
    }
    fields.update(overrides)
    return RustFinding(**fields)


class TestRustFindingContract:
    def test_rule_category_wire_map_is_exact_and_exhaustive(self):
        assert {member.name: member.value for member in RustRuleCategory} == {
            "SECURITY": "security",
            "QUALITY": "quality",
            "STYLE": "style",
            "PERFORMANCE": "performance",
            "CORRECTNESS": "correctness",
        }

    def test_severity_wire_map_is_exact_and_exhaustive(self):
        assert {member.name: member.value for member in RustSeverity} == {
            "ERROR": "error",
            "WARNING": "warning",
            "INFO": "info",
        }

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
            RustFinding(**values)

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
            category=RustRuleCategory.SECURITY,
            severity=RustSeverity.ERROR,
            code_snippet="unsafe { read_ptr(ptr) }",
        ).model_dump(mode="json")

        assert payload["category"] == "security"
        assert payload["severity"] == "error"
        assert payload["file_path"] == "crates/accounts/src/profile.rs"


class TestRustScanConfigContract:
    def test_defaults_target_rust_and_exclude_common_artifacts(self):
        config = RustScanConfig()

        assert config.scan_path == Path(".")
        assert config.include_extensions == [".rs"]
        assert "*/vendor/*" in config.exclude_patterns
        assert "*/build/*" in config.exclude_patterns
        assert config.max_findings == 1000
        assert config.max_file_lines == 10000
        assert config.rules == {}

    def test_path_and_custom_rule_configuration_round_trip(self):
        config = RustScanConfig(
            scan_path="crates/api",
            include_extensions=[".rs", ".rs.in"],
            exclude_patterns=["*/generated/*"],
            max_findings=35,
            max_file_lines=2400,
            rules={"clippy::needless_borrow": False},
        )

        assert config.scan_path == Path("crates/api")
        assert config.model_dump(mode="json") == {
            "scan_path": "crates/api",
            "include_extensions": [".rs", ".rs.in"],
            "exclude_patterns": ["*/generated/*"],
            "max_findings": 35,
            "max_file_lines": 2400,
            "rules": {"clippy::needless_borrow": False},
        }

    def test_mutable_defaults_are_isolated_between_scans(self):
        first, second = RustScanConfig(), RustScanConfig()

        first.include_extensions.append(".rs.in")
        first.exclude_patterns.append("*/generated/*")
        first.rules["clippy::needless_borrow"] = True

        assert second.include_extensions == [".rs"]
        assert "*/generated/*" not in second.exclude_patterns
        assert second.rules == {}

    @pytest.mark.parametrize("field", ["max_findings", "max_file_lines"])
    def test_rejects_non_integer_limits(self, field):
        with pytest.raises(ValidationError):
            RustScanConfig(**{field: "unbounded"})


class TestRustReportContract:
    def test_empty_report_is_an_explicit_clean_result(self):
        report = RustReport(scan_path="crates")

        assert report.findings == []
        assert report.total_findings == 0
        assert report.model_dump(mode="json") == {
            "findings": [],
            "scan_path": "crates",
        }

    def test_findings_are_validated_and_counted_from_wire_data(self):
        finding_payload = _finding().model_dump(mode="json")
        report = RustReport(findings=[finding_payload], scan_path="crates")

        assert isinstance(report.findings[0], RustFinding)
        assert report.total_findings == 1
        assert report.model_dump(mode="json")["findings"][0] == finding_payload

    def test_finding_lists_are_not_shared_between_reports(self):
        first, second = RustReport(), RustReport()

        first.findings.append(_finding())

        assert first.total_findings == 1
        assert second.findings == []
        assert second.total_findings == 0

    def test_rejects_invalid_nested_findings(self):
        with pytest.raises(ValidationError):
            RustReport(findings=[{"file_path": "broken.rs"}])
