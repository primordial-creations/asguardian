"""
Tests for Heimdall C# Analyzer Service

Unit tests for regex-based static analysis of C# source files.
Tests write real C# code to temporary files and run the analyzer against them.
"""

import tempfile
from pathlib import Path

import pytest

from Asgard.Bragi.Quality.languages.csharp.models.csharp_models import (
    CsharpFinding,
    CsharpRuleCategory,
    CsharpScanConfig,
    CsharpSeverity,
)
from Asgard.Bragi.Quality.languages.csharp.services.csharp_analyzer import CsharpAnalyzer


class TestCsharpAnalyzerInit:
    def test_init_with_defaults(self):
        analyzer = CsharpAnalyzer()
        assert analyzer._config is not None

    def test_init_with_custom_config(self):
        config = CsharpScanConfig(max_file_lines=600)
        analyzer = CsharpAnalyzer(config)
        assert analyzer._config.max_file_lines == 600


class TestCsharpSqlInjection:
    def test_string_concat_in_sql_command_flagged(self):
        code = 'var cmd = new SqlCommand("SELECT * FROM Users WHERE Id=" + userId);\n'
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "Repo.cs").write_text(code)
            report = CsharpAnalyzer().analyze(scan_path=d)
        assert any(f.rule_id == "csharp.sql-injection" for f in report.findings)

    def test_parameterised_query_not_flagged(self):
        code = 'var cmd = new SqlCommand("SELECT * FROM Users WHERE Id=@id");\ncmd.Parameters.AddWithValue("@id", userId);\n'
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "Safe.cs").write_text(code)
            report = CsharpAnalyzer().analyze(scan_path=d)
        assert not any(f.rule_id == "csharp.sql-injection" for f in report.findings)

    def test_finding_is_error_severity(self):
        code = 'var cmd = new SqlCommand("DELETE FROM t WHERE x=" + x);\n'
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "Bad.cs").write_text(code)
            report = CsharpAnalyzer().analyze(scan_path=d)
        findings = [f for f in report.findings if f.rule_id == "csharp.sql-injection"]
        assert findings[0].severity == CsharpSeverity.ERROR


class TestCsharpHardcodedCredentials:
    def test_hardcoded_password_flagged(self):
        code = 'string password = "MySecretPass123";\n'
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "Config.cs").write_text(code)
            report = CsharpAnalyzer().analyze(scan_path=d)
        assert any(f.rule_id == "csharp.no-hardcoded-credentials" for f in report.findings)

    def test_env_var_not_flagged(self):
        code = 'string password = Environment.GetEnvironmentVariable("DB_PASS");\n'
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "Config.cs").write_text(code)
            report = CsharpAnalyzer().analyze(scan_path=d)
        assert not any(f.rule_id == "csharp.no-hardcoded-credentials" for f in report.findings)


class TestCsharpEmptyCatch:
    def test_empty_catch_flagged(self):
        code = "try { DoSomething(); } catch (Exception e) {\n}\n"
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "Handler.cs").write_text(code)
            report = CsharpAnalyzer().analyze(scan_path=d)
        assert any(f.rule_id == "csharp.no-empty-catch" for f in report.findings)

    def test_non_empty_catch_not_flagged(self):
        code = "try { DoSomething(); } catch (Exception e) {\n    _logger.LogError(e, \"Failed\");\n}\n"
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "Handler.cs").write_text(code)
            report = CsharpAnalyzer().analyze(scan_path=d)
        assert not any(f.rule_id == "csharp.no-empty-catch" for f in report.findings)


class TestCsharpXss:
    def test_response_write_with_request_flagged(self):
        code = "Response.Write(Request[\"name\"]);\n"
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "Page.cs").write_text(code)
            report = CsharpAnalyzer().analyze(scan_path=d)
        assert any(f.rule_id == "csharp.xss" for f in report.findings)

    def test_category_is_security(self):
        code = "Response.Write(Request.QueryString[\"q\"]);\n"
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "Page.cs").write_text(code)
            report = CsharpAnalyzer().analyze(scan_path=d)
        findings = [f for f in report.findings if f.rule_id == "csharp.xss"]
        assert findings[0].category == CsharpRuleCategory.SECURITY


class TestCsharpWeakCrypto:
    def test_md5_flagged(self):
        code = "var hash = new MD5CryptoServiceProvider();\n"
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "Crypto.cs").write_text(code)
            report = CsharpAnalyzer().analyze(scan_path=d)
        assert any(f.rule_id == "csharp.no-weak-crypto" for f in report.findings)

    def test_sha1_flagged(self):
        code = "var hmac = new HMACSHA1();\n"
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "Crypto.cs").write_text(code)
            report = CsharpAnalyzer().analyze(scan_path=d)
        assert any(f.rule_id == "csharp.no-weak-crypto" for f in report.findings)


class TestCsharpPathTraversal:
    def test_file_read_with_request_flagged(self):
        code = "File.ReadAllText(Request[\"path\"]);\n"
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "Download.cs").write_text(code)
            report = CsharpAnalyzer().analyze(scan_path=d)
        assert any(f.rule_id == "csharp.path-traversal" for f in report.findings)


class TestCsharpCommandInjection:
    def test_process_start_with_user_input_flagged(self):
        code = "Process.Start(Request[\"cmd\"]);\n"
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "Exec.cs").write_text(code)
            report = CsharpAnalyzer().analyze(scan_path=d)
        assert any(f.rule_id == "csharp.command-injection" for f in report.findings)


class TestCsharpDebugCode:
    def test_console_writeline_flagged(self):
        code = "Console.WriteLine(\"debug: \" + value);\n"
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "Svc.cs").write_text(code)
            report = CsharpAnalyzer().analyze(scan_path=d)
        assert any(f.rule_id == "csharp.no-debug-code" for f in report.findings)

    def test_ilogger_not_flagged(self):
        code = '_logger.LogInformation("value: {Value}", value);\n'
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "Svc.cs").write_text(code)
            report = CsharpAnalyzer().analyze(scan_path=d)
        assert not any(f.rule_id == "csharp.no-debug-code" for f in report.findings)


class TestCsharpAnalyzerReport:
    def test_multiple_findings_counted(self):
        code = (
            'var cmd = new SqlCommand("SELECT * FROM t WHERE id=" + id);\n'
            'string secret = "MyApiKey123";\n'
            "Console.WriteLine(data);\n"
        )
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "Multi.cs").write_text(code)
            report = CsharpAnalyzer().analyze(scan_path=d)
        assert report.total_findings >= 3

    def test_disabled_rule_skipped(self):
        config = CsharpScanConfig(rules={"csharp.no-debug-code": False})
        code = "Console.WriteLine(x);\n"
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "X.cs").write_text(code)
            report = CsharpAnalyzer(config).analyze(scan_path=d)
        assert not any(f.rule_id == "csharp.no-debug-code" for f in report.findings)


class TestCsharpUnsafeDeserialization:
    def test_binary_formatter_flagged(self):
        code = "var formatter = new BinaryFormatter();\n"
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "Serial.cs").write_text(code)
            report = CsharpAnalyzer().analyze(scan_path=d)
        assert any(f.rule_id == "csharp.unsafe-deserialization" for f in report.findings)

    def test_net_data_contract_serializer_flagged(self):
        code = "var s = new NetDataContractSerializer();\n"
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "Serial.cs").write_text(code)
            report = CsharpAnalyzer().analyze(scan_path=d)
        assert any(f.rule_id == "csharp.unsafe-deserialization" for f in report.findings)

    def test_json_serializer_not_flagged(self):
        code = "var s = new JsonSerializer();\n"
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "Safe.cs").write_text(code)
            report = CsharpAnalyzer().analyze(scan_path=d)
        assert not any(f.rule_id == "csharp.unsafe-deserialization" for f in report.findings)

    def test_finding_severity_is_error(self):
        code = "var f = new LosFormatter();\n"
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "Serial.cs").write_text(code)
            report = CsharpAnalyzer().analyze(scan_path=d)
        findings = [f for f in report.findings if f.rule_id == "csharp.unsafe-deserialization"]
        assert findings[0].severity == CsharpSeverity.ERROR


class TestCsharpUnsafeReflection:
    def test_assembly_load_with_variable_flagged(self):
        code = "var asm = Assembly.Load(userInput);\n"
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "Reflect.cs").write_text(code)
            report = CsharpAnalyzer().analyze(scan_path=d)
        assert any(f.rule_id == "csharp.unsafe-reflection" for f in report.findings)

    def test_activator_create_instance_with_variable_flagged(self):
        code = "var obj = Activator.CreateInstance(typeName);\n"
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "Reflect.cs").write_text(code)
            report = CsharpAnalyzer().analyze(scan_path=d)
        assert any(f.rule_id == "csharp.unsafe-reflection" for f in report.findings)

    def test_assembly_load_with_string_literal_not_flagged(self):
        code = 'var asm = Assembly.Load("MyLib");\n'
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "Safe.cs").write_text(code)
            report = CsharpAnalyzer().analyze(scan_path=d)
        assert not any(f.rule_id == "csharp.unsafe-reflection" for f in report.findings)

    def test_finding_severity_is_error(self):
        code = "var obj = Activator.CreateInstance(dynamicType);\n"
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "Reflect.cs").write_text(code)
            report = CsharpAnalyzer().analyze(scan_path=d)
        findings = [f for f in report.findings if f.rule_id == "csharp.unsafe-reflection"]
        assert findings[0].severity == CsharpSeverity.ERROR
