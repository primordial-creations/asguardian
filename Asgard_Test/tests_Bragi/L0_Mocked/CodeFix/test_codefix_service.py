"""
Tests for Heimdall CodeFix Service

Unit tests for code fix suggestion generation, covering known rule handlers,
unknown rules, batch report generation, and model enum values.
"""

import pytest

from Asgard.Bragi.CodeFix.models.codefix_models import (
    CodeFix,
    CodeFixReport,
    FixConfidence,
    FixSuggestion,
    FixType,
)
from Asgard.Bragi.CodeFix.services.codefix_service import CodeFixService


class TestFixConfidence:
    """Tests for FixConfidence enum values."""

    def test_high_value(self):
        """Test that HIGH has the expected string value."""
        assert FixConfidence.HIGH == "high"

    def test_medium_value(self):
        """Test that MEDIUM has the expected string value."""
        assert FixConfidence.MEDIUM == "medium"

    def test_low_value(self):
        """Test that LOW has the expected string value."""
        assert FixConfidence.LOW == "low"

    def test_enum_from_string(self):
        """Test constructing FixConfidence from a string value."""
        assert FixConfidence("high") == FixConfidence.HIGH
        assert FixConfidence("medium") == FixConfidence.MEDIUM
        assert FixConfidence("low") == FixConfidence.LOW


class TestFixType:
    """Tests for FixType enum values."""

    def test_automated_value(self):
        """Test that AUTOMATED has the expected string value."""
        assert FixType.AUTOMATED == "automated"

    def test_suggested_value(self):
        """Test that SUGGESTED has the expected string value."""
        assert FixType.SUGGESTED == "suggested"

    def test_informational_value(self):
        """Test that INFORMATIONAL has the expected string value."""
        assert FixType.INFORMATIONAL == "informational"

    def test_enum_from_string(self):
        """Test constructing FixType from a string value."""
        assert FixType("automated") == FixType.AUTOMATED
        assert FixType("suggested") == FixType.SUGGESTED
        assert FixType("informational") == FixType.INFORMATIONAL


class TestCodeFix:
    """Tests for CodeFix model."""

    def test_code_fix_has_non_empty_description(self):
        """Test that a CodeFix instance has a non-empty description."""
        fix = CodeFix(
            rule_id="quality.lazy_imports",
            title="Move import to module level",
            description="Imports inside functions must be moved to module level.",
            fix_type=FixType.AUTOMATED,
            confidence=FixConfidence.HIGH,
        )
        assert fix.description != ""

    def test_code_fix_references_field(self):
        """Test that CodeFix references field is a list."""
        fix = CodeFix(
            rule_id="quality.lazy_imports",
            title="Move import to module level",
            description="Imports inside functions must be moved to module level.",
            fix_type=FixType.AUTOMATED,
            confidence=FixConfidence.HIGH,
            references=["https://peps.python.org/pep-0008/#imports"],
        )
        assert isinstance(fix.references, list)
        assert len(fix.references) == 1

    def test_code_fix_default_references_empty(self):
        """Test that references defaults to an empty list."""
        fix = CodeFix(
            rule_id="some.rule",
            title="title",
            description="description",
            fix_type=FixType.INFORMATIONAL,
            confidence=FixConfidence.LOW,
        )
        assert fix.references == []


class TestCodeFixService:
    """Tests for CodeFixService class."""

    def test_get_fix_lazy_imports_returns_code_fix(self):
        """Test that get_fix for quality.lazy_imports returns a CodeFix."""
        service = CodeFixService()
        fix = service.get_fix("quality.lazy_imports", code_snippet="    import os")
        assert fix is not None
        assert isinstance(fix, CodeFix)

    def test_get_fix_lazy_imports_has_fixed_code(self):
        """Test that the lazy_imports fix includes a fixed_code value."""
        service = CodeFixService()
        fix = service.get_fix("quality.lazy_imports", code_snippet="    import os")
        assert fix is not None
        assert fix.fixed_code != ""

    def test_get_fix_lazy_imports_confidence_high(self):
        """Test that lazy_imports fix has HIGH confidence."""
        service = CodeFixService()
        fix = service.get_fix("quality.lazy_imports", code_snippet="import os")
        assert fix is not None
        assert fix.confidence == FixConfidence.HIGH.value

    def test_get_fix_lazy_imports_fix_type_automated(self):
        """Test that lazy_imports fix is of type AUTOMATED."""
        service = CodeFixService()
        fix = service.get_fix("quality.lazy_imports", code_snippet="import os")
        assert fix is not None
        assert fix.fix_type == FixType.AUTOMATED.value

    def test_get_fix_lazy_imports_has_references(self):
        """Test that the lazy_imports fix has at least one reference."""
        service = CodeFixService()
        fix = service.get_fix("quality.lazy_imports", code_snippet="import os")
        assert fix is not None
        assert len(fix.references) > 0

    def test_get_fix_hardcoded_secret_returns_code_fix(self):
        """Test that get_fix for security.hardcoded_secret returns a CodeFix."""
        service = CodeFixService()
        fix = service.get_fix(
            "security.hardcoded_secret",
            code_snippet='password = "secret123"',
        )
        assert fix is not None
        assert isinstance(fix, CodeFix)

    def test_get_fix_hardcoded_secret_has_description(self):
        """Test that hardcoded_secret fix has a non-empty description."""
        service = CodeFixService()
        fix = service.get_fix(
            "security.hardcoded_secret",
            code_snippet='api_key = "abc123"',
        )
        assert fix is not None
        assert fix.description != ""

    def test_get_fix_hardcoded_secret_has_references(self):
        """Test that hardcoded_secret fix contains at least one reference."""
        service = CodeFixService()
        fix = service.get_fix(
            "security.hardcoded_secret",
            code_snippet='secret = "hunter2"',
        )
        assert fix is not None
        assert len(fix.references) > 0

    def test_get_fix_hardcoded_secret_fix_type_suggested(self):
        """Test that hardcoded_secret fix is of type SUGGESTED."""
        service = CodeFixService()
        fix = service.get_fix(
            "security.hardcoded_secret",
            code_snippet='password = "secret"',
        )
        assert fix is not None
        assert fix.fix_type == FixType.SUGGESTED.value

    def test_get_fix_unknown_rule_returns_fallback(self):
        """Test that an unknown rule ID returns a fallback CodeFix rather than None."""
        service = CodeFixService()
        fix = service.get_fix("unknown.rule.id")
        assert fix is not None
        assert isinstance(fix, CodeFix)

    def test_get_fix_unknown_rule_confidence_low(self):
        """Test that an unknown rule returns a fix with LOW confidence."""
        service = CodeFixService()
        fix = service.get_fix("unknown.rule.id")
        assert fix is not None
        assert fix.confidence == FixConfidence.LOW.value

    def test_get_fix_unknown_rule_no_fixed_code(self):
        """Test that an unknown rule fallback fix has no fixed_code."""
        service = CodeFixService()
        fix = service.get_fix("unknown.rule.id")
        assert fix is not None
        assert fix.fixed_code == ""

    def test_get_fix_unknown_rule_fix_type_informational(self):
        """Test that an unknown rule fallback fix has INFORMATIONAL type."""
        service = CodeFixService()
        fix = service.get_fix("unknown.rule.id")
        assert fix is not None
        assert fix.fix_type == FixType.INFORMATIONAL.value

    def test_get_fix_env_fallback_returns_fix(self):
        """Test that env_fallback rule returns a CodeFix."""
        service = CodeFixService()
        fix = service.get_fix(
            "quality.env_fallback",
            code_snippet="os.environ.get('SECRET_KEY', 'default')",
        )
        assert fix is not None
        assert isinstance(fix, CodeFix)

    def test_get_fix_env_fallback_has_fixed_code(self):
        """Test that env_fallback fix contains transformed fixed_code."""
        service = CodeFixService()
        fix = service.get_fix(
            "quality.env_fallback",
            code_snippet="os.environ.get('MY_VAR', 'default')",
        )
        assert fix is not None
        assert fix.fixed_code != ""

    def test_get_fix_cyclomatic_complexity_returns_fix(self):
        """Test that cyclomatic_complexity rule returns a CodeFix."""
        service = CodeFixService()
        fix = service.get_fix("quality.cyclomatic_complexity")
        assert fix is not None
        assert isinstance(fix, CodeFix)

    def test_get_fix_eval_injection_returns_fix(self):
        """Test that eval_injection rule returns a CodeFix."""
        service = CodeFixService()
        fix = service.get_fix(
            "security.eval_injection",
            code_snippet="result = eval(user_input)",
        )
        assert fix is not None
        assert isinstance(fix, CodeFix)

    def test_get_fix_shell_missing_set_e_returns_fix(self):
        """Test that shell.missing_set_e rule returns a CodeFix."""
        service = CodeFixService()
        fix = service.get_fix(
            "shell.missing_set_e",
            code_snippet="#!/usr/bin/env bash\necho hello\n",
        )
        assert fix is not None
        assert isinstance(fix, CodeFix)

    def test_get_fix_shell_missing_set_e_fixed_code_contains_set_e(self):
        """Test that shell.missing_set_e fix inserts set -e."""
        service = CodeFixService()
        fix = service.get_fix(
            "shell.missing_set_e",
            code_snippet="#!/usr/bin/env bash\necho hello\n",
        )
        assert fix is not None
        assert "set -e" in fix.fixed_code

    def test_get_fixes_for_report_with_multiple_findings(self):
        """Test that get_fixes_for_report generates a report from a list of findings."""
        service = CodeFixService()
        findings = [
            {
                "rule_id": "quality.lazy_imports",
                "file_path": "/project/module.py",
                "line_number": 42,
                "title": "Lazy import detected",
                "code_snippet": "    import os",
            },
            {
                "rule_id": "security.hardcoded_secret",
                "file_path": "/project/config.py",
                "line_number": 10,
                "title": "Hardcoded secret",
                "code_snippet": 'PASSWORD = "supersecret"',
            },
        ]

        report = service.get_fixes_for_report(findings)

        assert isinstance(report, CodeFixReport)
        assert report.total_suggestions == 2
        assert len(report.suggestions) == 2

    def test_get_fixes_for_report_suggestion_has_file_path(self):
        """Test that each suggestion in the report contains the correct file path."""
        service = CodeFixService()
        findings = [
            {
                "rule_id": "quality.lazy_imports",
                "file_path": "/project/main.py",
                "line_number": 5,
                "title": "Lazy import",
                "code_snippet": "    import json",
            }
        ]

        report = service.get_fixes_for_report(findings)

        assert report.suggestions[0].file_path == "/project/main.py"

    def test_get_fixes_for_report_suggestion_has_line_number(self):
        """Test that each suggestion in the report contains the correct line number."""
        service = CodeFixService()
        findings = [
            {
                "rule_id": "quality.lazy_imports",
                "file_path": "/project/main.py",
                "line_number": 99,
                "title": "Lazy import",
                "code_snippet": "    import sys",
            }
        ]

        report = service.get_fixes_for_report(findings)

        assert report.suggestions[0].line_number == 99

    def test_get_fixes_for_report_counts_automated(self):
        """Test that automated_count is correctly incremented for AUTOMATED fixes."""
        service = CodeFixService()
        findings = [
            {
                "rule_id": "quality.lazy_imports",
                "file_path": "/project/a.py",
                "line_number": 1,
                "title": "Lazy import",
                "code_snippet": "    import os",
            },
            {
                "rule_id": "quality.lazy_imports",
                "file_path": "/project/b.py",
                "line_number": 2,
                "title": "Lazy import",
                "code_snippet": "    import sys",
            },
        ]

        report = service.get_fixes_for_report(findings)

        assert report.automated_count == 2

    def test_get_fixes_for_report_empty_findings(self):
        """Test that an empty findings list produces an empty CodeFixReport."""
        service = CodeFixService()
        report = service.get_fixes_for_report([])

        assert isinstance(report, CodeFixReport)
        assert report.total_suggestions == 0
        assert len(report.suggestions) == 0
        assert report.automated_count == 0
        assert report.suggested_count == 0

    def test_get_fixes_for_report_unknown_rule_included(self):
        """Test that findings with unknown rule IDs are still included via fallback."""
        service = CodeFixService()
        findings = [
            {
                "rule_id": "custom.team.rule",
                "file_path": "/project/x.py",
                "line_number": 7,
                "title": "Custom rule violation",
                "code_snippet": "some_code()",
            }
        ]

        report = service.get_fixes_for_report(findings)

        assert report.total_suggestions == 1

    def test_get_fix_no_code_snippet_still_returns_fix(self):
        """Test that get_fix returns a CodeFix even when code_snippet is empty."""
        service = CodeFixService()
        fix = service.get_fix("quality.lazy_imports", code_snippet="")
        assert fix is not None
        assert isinstance(fix, CodeFix)

    def test_get_fix_rule_id_set_on_returned_fix(self):
        """Test that the returned fix has the correct rule_id set."""
        service = CodeFixService()
        fix = service.get_fix("quality.lazy_imports", code_snippet="    import re")
        assert fix is not None
        assert fix.rule_id == "quality.lazy_imports"

    def test_get_fix_returns_none_not_raised(self):
        """Test that get_fix never raises an exception for unknown inputs."""
        service = CodeFixService()
        try:
            fix = service.get_fix("totally.unknown.xyz.rule", code_snippet="")
            assert fix is not None
        except Exception as exc:
            pytest.fail(f"get_fix raised an unexpected exception: {exc}")

    def test_get_fix_naming_snake_case_violation(self):
        """Test that naming.snake_case_violation returns a fix."""
        service = CodeFixService()
        fix = service.get_fix(
            "naming.snake_case_violation",
            code_snippet="myFunctionName",
            context={"identifier": "myFunctionName"},
        )
        assert fix is not None
        assert fix.fix_type == FixType.SUGGESTED.value

    def test_get_fix_naming_pascal_case_violation(self):
        """Test that naming.pascal_case_violation returns a fix."""
        service = CodeFixService()
        fix = service.get_fix(
            "naming.pascal_case_violation",
            code_snippet="my_class_name",
            context={"identifier": "my_class_name"},
        )
        assert fix is not None
        assert fix.fixed_code != ""
