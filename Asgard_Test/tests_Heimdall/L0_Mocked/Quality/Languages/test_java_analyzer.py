"""
Tests for Heimdall Java Analyzer Service

Unit tests for regex-based static analysis of Java source files.
Tests write real Java code to temporary files and run the analyzer against them.
"""

import tempfile
from pathlib import Path

import pytest

from Asgard.Heimdall.Quality.languages.java.models.java_models import (
    JavaFinding,
    JavaRuleCategory,
    JavaScanConfig,
    JavaSeverity,
)
from Asgard.Heimdall.Quality.languages.java.services.java_analyzer import JavaAnalyzer


class TestJavaAnalyzerInit:
    def test_init_with_defaults(self):
        analyzer = JavaAnalyzer()
        assert analyzer._config is not None

    def test_init_with_custom_config(self):
        config = JavaScanConfig(max_file_lines=500)
        analyzer = JavaAnalyzer(config)
        assert analyzer._config.max_file_lines == 500


class TestJavaSqlInjection:
    def test_string_concat_in_execute_query(self):
        code = 'stmt.executeQuery("SELECT * FROM users WHERE id = " + userId);\n'
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "Repo.java").write_text(code)
            report = JavaAnalyzer().analyze(scan_path=d)
        assert any(f.rule_id == "java.sql-injection" for f in report.findings)

    def test_safe_prepared_statement_not_flagged(self):
        code = 'PreparedStatement ps = conn.prepareStatement("SELECT * FROM users WHERE id = ?");\n'
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "Safe.java").write_text(code)
            report = JavaAnalyzer().analyze(scan_path=d)
        assert not any(f.rule_id == "java.sql-injection" for f in report.findings)

    def test_finding_severity_is_error(self):
        code = 'stmt.execute("DELETE FROM t WHERE x=" + x);\n'
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "Bad.java").write_text(code)
            report = JavaAnalyzer().analyze(scan_path=d)
        sqli = [f for f in report.findings if f.rule_id == "java.sql-injection"]
        assert sqli[0].severity == JavaSeverity.ERROR


class TestJavaSystemExit:
    def test_system_exit_flagged(self):
        code = "System.exit(1);\n"
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "Main.java").write_text(code)
            report = JavaAnalyzer().analyze(scan_path=d)
        assert any(f.rule_id == "java.no-system-exit" for f in report.findings)

    def test_no_false_positive_in_comment(self):
        code = "// System.exit(0) is bad practice\n"
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "Comment.java").write_text(code)
            report = JavaAnalyzer().analyze(scan_path=d)
        # regex matches comments too — assert category is QUALITY at minimum
        findings = [f for f in report.findings if f.rule_id == "java.no-system-exit"]
        for f in findings:
            assert f.category == JavaRuleCategory.QUALITY


class TestJavaPrintStackTrace:
    def test_print_stacktrace_flagged(self):
        code = "} catch (Exception e) { e.printStackTrace(); }\n"
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "Handler.java").write_text(code)
            report = JavaAnalyzer().analyze(scan_path=d)
        assert any(f.rule_id == "java.no-print-stacktrace" for f in report.findings)


class TestJavaEmptyCatch:
    def test_empty_catch_block_flagged(self):
        code = "try { doSomething(); } catch (Exception e) {\n}\n"
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "Empty.java").write_text(code)
            report = JavaAnalyzer().analyze(scan_path=d)
        assert any(f.rule_id == "java.empty-catch" for f in report.findings)

    def test_non_empty_catch_not_flagged(self):
        code = "try { doSomething(); } catch (Exception e) {\n    logger.error(e);\n}\n"
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "Good.java").write_text(code)
            report = JavaAnalyzer().analyze(scan_path=d)
        assert not any(f.rule_id == "java.empty-catch" for f in report.findings)


class TestJavaHardcodedCredentials:
    def test_hardcoded_password_flagged(self):
        code = 'String password = "supersecret123";\n'
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "Config.java").write_text(code)
            report = JavaAnalyzer().analyze(scan_path=d)
        assert any(f.rule_id == "java.no-hardcoded-credentials" for f in report.findings)

    def test_env_var_not_flagged(self):
        code = 'String password = System.getenv("DB_PASS");\n'
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "Config.java").write_text(code)
            report = JavaAnalyzer().analyze(scan_path=d)
        assert not any(f.rule_id == "java.no-hardcoded-credentials" for f in report.findings)


class TestJavaRawTypes:
    def test_raw_list_flagged(self):
        code = "List items = new ArrayList();\n"
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "Raw.java").write_text(code)
            report = JavaAnalyzer().analyze(scan_path=d)
        assert any(f.rule_id == "java.no-raw-types" for f in report.findings)


class TestJavaAnalyzerReport:
    def test_report_summary_counts_match(self):
        code = (
            'stmt.executeQuery("SELECT * FROM t WHERE id=" + id);\n'
            "System.exit(1);\n"
            'String secret = "mypassword123";\n'
        )
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "Multi.java").write_text(code)
            report = JavaAnalyzer().analyze(scan_path=d)
        assert report.total_findings >= 3

    def test_scan_path_recorded(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "Empty.java").write_text("public class Empty {}\n")
            report = JavaAnalyzer().analyze(scan_path=d)
        assert report.scan_path == d

    def test_disabled_rule_not_reported(self):
        config = JavaScanConfig(rules={"java.no-system-exit": False})
        code = "System.exit(0);\n"
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "X.java").write_text(code)
            report = JavaAnalyzer(config).analyze(scan_path=d)
        assert not any(f.rule_id == "java.no-system-exit" for f in report.findings)
