"""
Tests for Heimdall PHP Analyzer Service

Unit tests for regex-based static analysis of PHP source files.
Tests write real PHP code to temporary files and run the analyzer against them.
"""

import tempfile
from pathlib import Path

import pytest

from Asgard.Heimdall.Quality.languages.php.models.php_models import (
    PhpFinding,
    PhpRuleCategory,
    PhpScanConfig,
    PhpSeverity,
)
from Asgard.Heimdall.Quality.languages.php.services.php_analyzer import PhpAnalyzer


class TestPhpAnalyzerInit:
    def test_init_with_defaults(self):
        analyzer = PhpAnalyzer()
        assert analyzer._config is not None

    def test_init_with_custom_config(self):
        config = PhpScanConfig(max_file_lines=400)
        analyzer = PhpAnalyzer(config)
        assert analyzer._config.max_file_lines == 400


class TestPhpSqlInjection:
    def test_user_input_in_query_flagged(self):
        code = "<?php\n$result = mysql_query(\"SELECT * FROM users WHERE id=\" . $_GET['id']);\n"
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "users.php").write_text(code)
            report = PhpAnalyzer().analyze(scan_path=d)
        assert any(f.rule_id == "php.sql-injection" for f in report.findings)

    def test_pdo_prepared_statement_not_flagged(self):
        code = "<?php\n$stmt = $pdo->prepare('SELECT * FROM users WHERE id = ?');\n$stmt->execute([$_GET['id']]);\n"
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "safe.php").write_text(code)
            report = PhpAnalyzer().analyze(scan_path=d)
        assert not any(f.rule_id == "php.sql-injection" for f in report.findings)

    def test_finding_severity_is_error(self):
        code = "<?php\n$r = mysqli_query($conn, \"DELETE FROM t WHERE x=\" . $_POST['x']);\n"
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "bad.php").write_text(code)
            report = PhpAnalyzer().analyze(scan_path=d)
        findings = [f for f in report.findings if f.rule_id == "php.sql-injection"]
        assert findings[0].severity == PhpSeverity.ERROR


class TestPhpXss:
    def test_unescaped_echo_flagged(self):
        code = "<?php\necho $_GET['name'];\n"
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "out.php").write_text(code)
            report = PhpAnalyzer().analyze(scan_path=d)
        assert any(f.rule_id == "php.xss" for f in report.findings)

    def test_htmlspecialchars_not_flagged(self):
        code = "<?php\necho htmlspecialchars($_GET['name'], ENT_QUOTES, 'UTF-8');\n"
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "safe.php").write_text(code)
            report = PhpAnalyzer().analyze(scan_path=d)
        assert not any(f.rule_id == "php.xss" for f in report.findings)

    def test_post_variable_also_flagged(self):
        code = "<?php\necho $_POST['comment'];\n"
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "xss.php").write_text(code)
            report = PhpAnalyzer().analyze(scan_path=d)
        assert any(f.rule_id == "php.xss" for f in report.findings)


class TestPhpEval:
    def test_eval_flagged(self):
        code = "<?php\neval($_POST['code']);\n"
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "eval.php").write_text(code)
            report = PhpAnalyzer().analyze(scan_path=d)
        assert any(f.rule_id == "php.no-eval" for f in report.findings)

    def test_category_is_security(self):
        code = "<?php\neval($dynamic);\n"
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "eval.php").write_text(code)
            report = PhpAnalyzer().analyze(scan_path=d)
        findings = [f for f in report.findings if f.rule_id == "php.no-eval"]
        assert findings[0].category == PhpRuleCategory.SECURITY


class TestPhpFileInclusion:
    def test_include_with_get_param_flagged(self):
        code = "<?php\ninclude($_GET['page']);\n"
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "router.php").write_text(code)
            report = PhpAnalyzer().analyze(scan_path=d)
        assert any(f.rule_id == "php.file-inclusion" for f in report.findings)

    def test_require_once_with_post_flagged(self):
        code = "<?php\nrequire_once($_POST['module']);\n"
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "loader.php").write_text(code)
            report = PhpAnalyzer().analyze(scan_path=d)
        assert any(f.rule_id == "php.file-inclusion" for f in report.findings)

    def test_static_include_not_flagged(self):
        code = "<?php\ninclude('header.php');\n"
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "page.php").write_text(code)
            report = PhpAnalyzer().analyze(scan_path=d)
        assert not any(f.rule_id == "php.file-inclusion" for f in report.findings)


class TestPhpCommandInjection:
    def test_system_with_user_input_flagged(self):
        code = "<?php\nsystem('ls ' . $_GET['dir']);\n"
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "cmd.php").write_text(code)
            report = PhpAnalyzer().analyze(scan_path=d)
        assert any(f.rule_id == "php.command-injection" for f in report.findings)


class TestPhpMd5Password:
    def test_md5_flagged(self):
        code = "<?php\n$hash = md5($password);\n"
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "auth.php").write_text(code)
            report = PhpAnalyzer().analyze(scan_path=d)
        assert any(f.rule_id == "php.no-md5-password" for f in report.findings)

    def test_password_hash_not_flagged(self):
        code = "<?php\n$hash = password_hash($password, PASSWORD_BCRYPT);\n"
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "safe.php").write_text(code)
            report = PhpAnalyzer().analyze(scan_path=d)
        assert not any(f.rule_id == "php.no-md5-password" for f in report.findings)


class TestPhpExtract:
    def test_extract_on_get_flagged(self):
        code = "<?php\nextract($_GET);\n"
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "bad.php").write_text(code)
            report = PhpAnalyzer().analyze(scan_path=d)
        assert any(f.rule_id == "php.no-extract" for f in report.findings)


class TestPhpHardcodedCredentials:
    def test_hardcoded_password_flagged(self):
        code = "<?php\n$password = 'mysecretpass';\n"
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "config.php").write_text(code)
            report = PhpAnalyzer().analyze(scan_path=d)
        assert any(f.rule_id == "php.no-hardcoded-credentials" for f in report.findings)


class TestPhpAnalyzerReport:
    def test_multiple_findings_across_rules(self):
        code = (
            "<?php\n"
            "echo $_GET['name'];\n"
            "eval($code);\n"
            "$hash = md5($password);\n"
        )
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "multi.php").write_text(code)
            report = PhpAnalyzer().analyze(scan_path=d)
        assert report.total_findings >= 3

    def test_disabled_rule_skipped(self):
        config = PhpScanConfig(rules={"php.no-eval": False})
        code = "<?php\neval($x);\n"
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "x.php").write_text(code)
            report = PhpAnalyzer(config).analyze(scan_path=d)
        assert not any(f.rule_id == "php.no-eval" for f in report.findings)
