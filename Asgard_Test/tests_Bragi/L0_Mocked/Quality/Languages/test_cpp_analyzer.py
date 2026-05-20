"""Unit tests for the C++ analyzer."""

import pytest
from Asgard.Bragi.Quality.languages.cpp.models.cpp_models import (
    CppScanConfig, CppSeverity, CppRuleCategory,
)
from Asgard.Bragi.Quality.languages.cpp.services._cpp_rules import (
    check_buffer_overflow,
    check_format_string,
    check_hardcoded_credentials,
    check_command_injection,
    check_use_after_free,
)
from Asgard.Bragi.Quality.languages.cpp.services.cpp_analyzer import CppAnalyzer


class TestCppAnalyzerInit:
    def test_default_config(self):
        analyzer = CppAnalyzer()
        assert analyzer._config is not None
        assert ".cpp" in analyzer._config.include_extensions
        assert analyzer._config.max_findings == 1000

    def test_custom_config(self):
        config = CppScanConfig(max_findings=500)
        analyzer = CppAnalyzer(config=config)
        assert analyzer._config.max_findings == 500


class TestCppBufferOverflow:
    def test_strcpy_flagged(self):
        lines = ['    strcpy(buf, input);']
        findings = check_buffer_overflow("test.cpp", lines)
        assert len(findings) == 1
        assert findings[0].rule_id == "cpp.buffer-overflow"
        assert findings[0].severity == CppSeverity.ERROR

    def test_gets_flagged(self):
        lines = ['    gets(buf);']
        findings = check_buffer_overflow("test.cpp", lines)
        assert len(findings) == 1

    def test_strncpy_not_flagged(self):
        lines = ['    strncpy(buf, input, sizeof(buf));']
        findings = check_buffer_overflow("test.cpp", lines)
        assert len(findings) == 0

    def test_disabled_rule_returns_empty(self):
        lines = ['    strcpy(buf, input);']
        findings = check_buffer_overflow("test.cpp", lines, enabled=False)
        assert findings == []


class TestCppFormatString:
    def test_printf_variable_flagged(self):
        lines = ['    printf(userMsg);']
        findings = check_format_string("test.cpp", lines)
        assert len(findings) == 1
        assert findings[0].rule_id == "cpp.format-string"

    def test_printf_format_string_not_flagged(self):
        lines = ['    printf("%s", msg);']
        findings = check_format_string("test.cpp", lines)
        assert len(findings) == 0

    def test_disabled_rule_returns_empty(self):
        lines = ['    printf(userMsg);']
        findings = check_format_string("test.cpp", lines, enabled=False)
        assert findings == []


class TestCppHardcodedCredentials:
    def test_const_char_password_flagged(self):
        lines = ['const char* password = "secret123";']
        findings = check_hardcoded_credentials("test.cpp", lines)
        assert len(findings) == 1
        assert findings[0].rule_id == "cpp.hardcoded-credentials"
        assert findings[0].severity == CppSeverity.ERROR

    def test_string_password_flagged(self):
        lines = ['std::string password = "hunter2";']
        findings = check_hardcoded_credentials("test.cpp", lines)
        assert len(findings) == 1

    def test_no_credential_not_flagged(self):
        lines = ['std::string username = "admin";']
        findings = check_hardcoded_credentials("test.cpp", lines)
        assert len(findings) == 0


class TestCppCommandInjection:
    def test_system_with_variable_flagged(self):
        lines = ['    system(userCmd);']
        findings = check_command_injection("test.cpp", lines)
        assert len(findings) == 1
        assert findings[0].rule_id == "cpp.command-injection"
        assert findings[0].category == CppRuleCategory.SECURITY

    def test_system_with_literal_not_flagged(self):
        lines = ['    system("ls");']
        findings = check_command_injection("test.cpp", lines)
        assert len(findings) == 0

    def test_popen_with_variable_flagged(self):
        lines = ['    popen(cmd, "r");']
        findings = check_command_injection("test.cpp", lines)
        assert len(findings) == 1

    def test_disabled_rule_returns_empty(self):
        lines = ['    system(userCmd);']
        findings = check_command_injection("test.cpp", lines, enabled=False)
        assert findings == []


class TestCppAnalyzerReport:
    def test_multiple_findings_counted(self):
        analyzer = CppAnalyzer()
        lines = [
            'strcpy(buf, input);',
            'printf(userMsg);',
            'const char* password = "secret";',
        ]
        from Asgard.Bragi.Quality.languages.cpp.services._cpp_rules import (
            check_buffer_overflow, check_format_string, check_hardcoded_credentials,
        )
        findings = []
        findings.extend(check_buffer_overflow("f.cpp", lines))
        findings.extend(check_format_string("f.cpp", lines))
        findings.extend(check_hardcoded_credentials("f.cpp", lines))
        assert len(findings) == 3

    def test_disabled_rule_skipped(self):
        config = CppScanConfig(rules={"cpp.buffer-overflow": False})
        analyzer = CppAnalyzer(config=config)
        lines = ['strcpy(buf, input);']
        rule_id = check_buffer_overflow.__doc__.split(":")[0].strip()
        enabled = config.rules.get(rule_id, True)
        findings = check_buffer_overflow("f.cpp", lines, enabled=enabled)
        assert findings == []
