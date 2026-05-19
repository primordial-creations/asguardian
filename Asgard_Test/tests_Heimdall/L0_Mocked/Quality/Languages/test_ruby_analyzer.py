"""
Tests for Heimdall Ruby Analyzer Service

Unit tests for regex-based static analysis of Ruby source files.
Tests write real Ruby code to temporary files and run the analyzer against them.
"""

import tempfile
from pathlib import Path

import pytest

from Asgard.Heimdall.Quality.languages.ruby.models.ruby_models import (
    RubyFinding,
    RubyRuleCategory,
    RubyScanConfig,
    RubySeverity,
)
from Asgard.Heimdall.Quality.languages.ruby.services.ruby_analyzer import RubyAnalyzer


class TestRubyAnalyzerInit:
    def test_init_with_defaults(self):
        analyzer = RubyAnalyzer()
        assert analyzer._config is not None

    def test_init_with_custom_config(self):
        config = RubyScanConfig(max_file_lines=200)
        analyzer = RubyAnalyzer(config)
        assert analyzer._config.max_file_lines == 200


class TestRubySqlInjection:
    def test_string_interpolation_in_where_flagged(self):
        code = 'User.where("name = \'#{params[:name]}\'")\n'
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "users_controller.rb").write_text(code)
            report = RubyAnalyzer().analyze(scan_path=d)
        assert any(f.rule_id == "ruby.sql-injection" for f in report.findings)

    def test_parameterised_where_not_flagged(self):
        code = "User.where('name = ?', params[:name])\n"
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "safe.rb").write_text(code)
            report = RubyAnalyzer().analyze(scan_path=d)
        assert not any(f.rule_id == "ruby.sql-injection" for f in report.findings)

    def test_finding_is_error_severity(self):
        code = 'User.find_by_sql("SELECT * WHERE id=#{id}")\n'
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "q.rb").write_text(code)
            report = RubyAnalyzer().analyze(scan_path=d)
        findings = [f for f in report.findings if f.rule_id == "ruby.sql-injection"]
        assert findings[0].severity == RubySeverity.ERROR


class TestRubyNoEval:
    def test_eval_flagged(self):
        code = "eval(user_input)\n"
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "bad.rb").write_text(code)
            report = RubyAnalyzer().analyze(scan_path=d)
        assert any(f.rule_id == "ruby.no-eval" for f in report.findings)

    def test_no_eval_category_is_security(self):
        code = "eval(params[:code])\n"
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "bad.rb").write_text(code)
            report = RubyAnalyzer().analyze(scan_path=d)
        findings = [f for f in report.findings if f.rule_id == "ruby.no-eval"]
        assert findings[0].category == RubyRuleCategory.SECURITY


class TestRubyCommandInjection:
    def test_backtick_interpolation_flagged(self):
        code = 'result = `ls #{params[:dir]}`\n'
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "cmd.rb").write_text(code)
            report = RubyAnalyzer().analyze(scan_path=d)
        assert any(f.rule_id == "ruby.command-injection" for f in report.findings)

    def test_system_with_interpolation_flagged(self):
        code = 'system("rm -rf #{user_path}")\n'
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "cmd.rb").write_text(code)
            report = RubyAnalyzer().analyze(scan_path=d)
        assert any(f.rule_id == "ruby.command-injection" for f in report.findings)


class TestRubyYamlLoad:
    def test_yaml_load_flagged(self):
        code = "data = YAML.load(user_data)\n"
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "loader.rb").write_text(code)
            report = RubyAnalyzer().analyze(scan_path=d)
        assert any(f.rule_id == "ruby.no-yaml-load" for f in report.findings)

    def test_yaml_safe_load_not_flagged(self):
        code = "data = YAML.safe_load(user_data)\n"
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "safe.rb").write_text(code)
            report = RubyAnalyzer().analyze(scan_path=d)
        assert not any(f.rule_id == "ruby.no-yaml-load" for f in report.findings)


class TestRubyMassAssignment:
    def test_params_directly_in_update_flagged(self):
        code = "@user.update_attributes(params)\n"
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "users_controller.rb").write_text(code)
            report = RubyAnalyzer().analyze(scan_path=d)
        assert any(f.rule_id == "ruby.mass-assignment" for f in report.findings)

    def test_permitted_params_not_flagged(self):
        code = "@user.update(params.require(:user).permit(:name, :email))\n"
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "safe.rb").write_text(code)
            report = RubyAnalyzer().analyze(scan_path=d)
        assert not any(f.rule_id == "ruby.mass-assignment" for f in report.findings)


class TestRubyHardcodedCredentials:
    def test_hardcoded_password_flagged(self):
        code = 'password = "s3cr3tpassword"\n'
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "config.rb").write_text(code)
            report = RubyAnalyzer().analyze(scan_path=d)
        assert any(f.rule_id == "ruby.no-hardcoded-credentials" for f in report.findings)

    def test_env_var_not_flagged(self):
        code = "password = ENV['DB_PASS']\n"
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "config.rb").write_text(code)
            report = RubyAnalyzer().analyze(scan_path=d)
        assert not any(f.rule_id == "ruby.no-hardcoded-credentials" for f in report.findings)


class TestRubyWeakHash:
    def test_md5_for_password_flagged(self):
        code = "hash = Digest::MD5.hexdigest(password)\n"
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "auth.rb").write_text(code)
            report = RubyAnalyzer().analyze(scan_path=d)
        assert any(f.rule_id == "ruby.no-md5-sha1" for f in report.findings)

    def test_sha1_flagged(self):
        code = "hash = Digest::SHA1.digest(secret)\n"
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "auth.rb").write_text(code)
            report = RubyAnalyzer().analyze(scan_path=d)
        assert any(f.rule_id == "ruby.no-md5-sha1" for f in report.findings)


class TestRubyAnalyzerReport:
    def test_multiple_findings_counted(self):
        code = (
            "eval(user_input)\n"
            'password = "hardcodedpass"\n'
            "data = YAML.load(input)\n"
        )
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "bad.rb").write_text(code)
            report = RubyAnalyzer().analyze(scan_path=d)
        assert report.total_findings >= 3

    def test_disabled_rule_skipped(self):
        config = RubyScanConfig(rules={"ruby.no-eval": False})
        code = "eval(user_input)\n"
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "x.rb").write_text(code)
            report = RubyAnalyzer(config).analyze(scan_path=d)
        assert not any(f.rule_id == "ruby.no-eval" for f in report.findings)
