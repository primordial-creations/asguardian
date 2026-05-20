"""
Tests for Heimdall Shell Script Analyzer Service

Unit tests for regex-based static analysis of shell and bash script files.
Tests write real shell code to temporary files and run the analyzer against them.
"""

import tempfile
from pathlib import Path

import pytest

from Asgard.Bragi.Quality.languages.shell.models.shell_models import (
    ShellAnalysisConfig,
    ShellRuleCategory,
    ShellSeverity,
)
from Asgard.Bragi.Quality.languages.shell.services.shell_analyzer import ShellAnalyzer


class TestShellAnalyzerInit:
    """Tests for ShellAnalyzer initialisation."""

    def test_init_with_default_config(self):
        """Test that analyzer initialises successfully with default configuration."""
        analyzer = ShellAnalyzer()
        assert analyzer._config is not None

    def test_init_with_custom_config(self):
        """Test that analyzer initialises with a provided configuration."""
        config = ShellAnalysisConfig(also_check_shebangs=False)
        analyzer = ShellAnalyzer(config)
        assert analyzer._config.also_check_shebangs is False


class TestShellAnalyzerEvalInjection:
    """Tests for the shell.eval-injection rule."""

    def test_eval_with_variable_triggers_rule(self):
        """eval with a $ variable argument should trigger shell.eval-injection."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sh_file = Path(tmpdir) / "eval_test.sh"
            sh_file.write_text('#!/bin/bash\nset -eu\neval $user_input\n')

            analyzer = ShellAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            rule_ids = [f.rule_id for f in report.findings]
            assert "shell.eval-injection" in rule_ids

    def test_eval_injection_finding_has_error_severity(self):
        """The shell.eval-injection finding must be reported as ERROR severity."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sh_file = Path(tmpdir) / "eval_severity.sh"
            sh_file.write_text('#!/bin/bash\nset -eu\neval $cmd\n')

            analyzer = ShellAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            eval_findings = [f for f in report.findings if f.rule_id == "shell.eval-injection"]
            assert len(eval_findings) >= 1
            assert eval_findings[0].severity == ShellSeverity.ERROR.value

    def test_eval_injection_finding_has_security_category(self):
        """The shell.eval-injection finding must be classified under SECURITY category."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sh_file = Path(tmpdir) / "eval_category.sh"
            sh_file.write_text('#!/bin/bash\nset -eu\neval $input\n')

            analyzer = ShellAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            eval_findings = [f for f in report.findings if f.rule_id == "shell.eval-injection"]
            assert len(eval_findings) >= 1
            assert eval_findings[0].category == ShellRuleCategory.SECURITY.value

    def test_eval_with_quoted_string_does_not_trigger_rule(self):
        """eval with a literal string argument (not a variable) should not trigger rule."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sh_file = Path(tmpdir) / "eval_literal.sh"
            sh_file.write_text('#!/bin/bash\nset -eu\neval "echo hello"\n')

            analyzer = ShellAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            rule_ids = [f.rule_id for f in report.findings]
            assert "shell.eval-injection" not in rule_ids

    def test_eval_injection_rule_disabled_suppresses_findings(self):
        """Disabling shell.eval-injection should suppress findings for that rule."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sh_file = Path(tmpdir) / "eval_disabled.sh"
            sh_file.write_text('#!/bin/bash\nset -eu\neval $cmd\n')

            config = ShellAnalysisConfig(disabled_rules=["shell.eval-injection"])
            analyzer = ShellAnalyzer(config)
            report = analyzer.analyze(scan_path=tmpdir)

            rule_ids = [f.rule_id for f in report.findings]
            assert "shell.eval-injection" not in rule_ids


class TestShellAnalyzerCurlInsecure:
    """Tests for the shell.curl-insecure rule."""

    def test_curl_k_flag_triggers_rule(self):
        """curl called with -k flag should trigger shell.curl-insecure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sh_file = Path(tmpdir) / "curl_k.sh"
            sh_file.write_text('#!/bin/bash\nset -eu\ncurl -k https://example.com/data\n')

            analyzer = ShellAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            rule_ids = [f.rule_id for f in report.findings]
            assert "shell.curl-insecure" in rule_ids

    def test_curl_insecure_flag_triggers_rule(self):
        """curl called with --insecure flag should trigger shell.curl-insecure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sh_file = Path(tmpdir) / "curl_insecure.sh"
            sh_file.write_text('#!/bin/bash\nset -eu\ncurl --insecure https://example.com/api\n')

            analyzer = ShellAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            rule_ids = [f.rule_id for f in report.findings]
            assert "shell.curl-insecure" in rule_ids

    def test_curl_insecure_finding_has_warning_severity(self):
        """The shell.curl-insecure finding must be reported as WARNING severity."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sh_file = Path(tmpdir) / "curl_warn.sh"
            sh_file.write_text('#!/bin/bash\nset -eu\ncurl -k https://api.example.com\n')

            analyzer = ShellAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            curl_findings = [f for f in report.findings if f.rule_id == "shell.curl-insecure"]
            assert len(curl_findings) >= 1
            assert curl_findings[0].severity == ShellSeverity.WARNING.value

    def test_curl_without_insecure_flag_does_not_trigger_rule(self):
        """curl called without -k or --insecure should not trigger shell.curl-insecure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sh_file = Path(tmpdir) / "curl_safe.sh"
            sh_file.write_text('#!/bin/bash\nset -eu\ncurl https://example.com/data\n')

            analyzer = ShellAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            rule_ids = [f.rule_id for f in report.findings]
            assert "shell.curl-insecure" not in rule_ids


class TestShellAnalyzerHardcodedSecret:
    """Tests for the shell.hardcoded-secret rule."""

    def test_password_variable_with_literal_triggers_rule(self):
        """PASSWORD variable assigned a string literal should trigger shell.hardcoded-secret."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sh_file = Path(tmpdir) / "password.sh"
            sh_file.write_text('#!/bin/bash\nset -eu\nPASSWORD="secret123"\n')

            analyzer = ShellAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            rule_ids = [f.rule_id for f in report.findings]
            assert "shell.hardcoded-secret" in rule_ids

    def test_api_key_variable_with_literal_triggers_rule(self):
        """API_KEY variable assigned a string literal should trigger shell.hardcoded-secret."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sh_file = Path(tmpdir) / "api_key.sh"
            sh_file.write_text('#!/bin/bash\nset -eu\nAPI_KEY="abc123xyz"\n')

            analyzer = ShellAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            rule_ids = [f.rule_id for f in report.findings]
            assert "shell.hardcoded-secret" in rule_ids

    def test_token_variable_with_literal_triggers_rule(self):
        """TOKEN variable assigned a string literal should trigger shell.hardcoded-secret."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sh_file = Path(tmpdir) / "token.sh"
            sh_file.write_text('#!/bin/bash\nset -eu\nTOKEN="my-secret-token"\n')

            analyzer = ShellAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            rule_ids = [f.rule_id for f in report.findings]
            assert "shell.hardcoded-secret" in rule_ids

    def test_hardcoded_secret_finding_has_warning_severity(self):
        """The shell.hardcoded-secret finding must be reported as WARNING severity."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sh_file = Path(tmpdir) / "secret_severity.sh"
            sh_file.write_text('#!/bin/bash\nset -eu\nSECRET="mysecretvalue"\n')

            analyzer = ShellAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            secret_findings = [f for f in report.findings if f.rule_id == "shell.hardcoded-secret"]
            assert len(secret_findings) >= 1
            assert secret_findings[0].severity == ShellSeverity.WARNING.value

    def test_password_from_env_does_not_trigger_rule(self):
        """PASSWORD assigned from an environment variable should not trigger the rule."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sh_file = Path(tmpdir) / "env_pass.sh"
            sh_file.write_text('#!/bin/bash\nset -eu\nPASSWORD=$DB_PASSWORD\n')

            analyzer = ShellAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            rule_ids = [f.rule_id for f in report.findings]
            assert "shell.hardcoded-secret" not in rule_ids


class TestShellAnalyzerMissingSetE:
    """Tests for the shell.missing-set-e rule."""

    def test_script_without_set_e_triggers_rule(self):
        """A script lacking 'set -e' should trigger shell.missing-set-e."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sh_file = Path(tmpdir) / "no_set_e.sh"
            sh_file.write_text('#!/bin/bash\nset -u\necho "no errexit"\n')

            analyzer = ShellAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            rule_ids = [f.rule_id for f in report.findings]
            assert "shell.missing-set-e" in rule_ids

    def test_script_with_set_e_does_not_trigger_rule(self):
        """A script containing 'set -e' should not trigger shell.missing-set-e."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sh_file = Path(tmpdir) / "has_set_e.sh"
            sh_file.write_text('#!/bin/bash\nset -eu\necho "safe script"\n')

            analyzer = ShellAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            rule_ids = [f.rule_id for f in report.findings]
            assert "shell.missing-set-e" not in rule_ids

    def test_script_with_set_o_errexit_does_not_trigger_rule(self):
        """A script using 'set -o errexit' should not trigger shell.missing-set-e."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sh_file = Path(tmpdir) / "set_o_errexit.sh"
            sh_file.write_text('#!/bin/bash\nset -u\nset -o errexit\necho "safe"\n')

            analyzer = ShellAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            rule_ids = [f.rule_id for f in report.findings]
            assert "shell.missing-set-e" not in rule_ids

    def test_missing_set_e_finding_has_info_severity(self):
        """The shell.missing-set-e finding must be reported as INFO severity."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sh_file = Path(tmpdir) / "no_set_e_severity.sh"
            sh_file.write_text('#!/bin/bash\nset -u\necho "hello"\n')

            analyzer = ShellAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            sete_findings = [f for f in report.findings if f.rule_id == "shell.missing-set-e"]
            assert len(sete_findings) >= 1
            assert sete_findings[0].severity == ShellSeverity.INFO.value


class TestShellAnalyzerMissingSetU:
    """Tests for the shell.missing-set-u rule."""

    def test_script_without_set_u_triggers_rule(self):
        """A script lacking 'set -u' should trigger shell.missing-set-u."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sh_file = Path(tmpdir) / "no_set_u.sh"
            sh_file.write_text('#!/bin/bash\nset -e\necho "no nounset"\n')

            analyzer = ShellAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            rule_ids = [f.rule_id for f in report.findings]
            assert "shell.missing-set-u" in rule_ids

    def test_script_with_set_u_does_not_trigger_rule(self):
        """A script containing 'set -u' should not trigger shell.missing-set-u."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sh_file = Path(tmpdir) / "has_set_u.sh"
            sh_file.write_text('#!/bin/bash\nset -eu\necho "safe script"\n')

            analyzer = ShellAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            rule_ids = [f.rule_id for f in report.findings]
            assert "shell.missing-set-u" not in rule_ids

    def test_script_with_set_o_nounset_does_not_trigger_rule(self):
        """A script using 'set -o nounset' should not trigger shell.missing-set-u."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sh_file = Path(tmpdir) / "set_o_nounset.sh"
            sh_file.write_text('#!/bin/bash\nset -e\nset -o nounset\necho "safe"\n')

            analyzer = ShellAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            rule_ids = [f.rule_id for f in report.findings]
            assert "shell.missing-set-u" not in rule_ids

    def test_missing_set_u_finding_has_info_severity(self):
        """The shell.missing-set-u finding must be reported as INFO severity."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sh_file = Path(tmpdir) / "no_set_u_severity.sh"
            sh_file.write_text('#!/bin/bash\nset -e\necho "hello"\n')

            analyzer = ShellAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            setu_findings = [f for f in report.findings if f.rule_id == "shell.missing-set-u"]
            assert len(setu_findings) >= 1
            assert setu_findings[0].severity == ShellSeverity.INFO.value


class TestShellAnalyzerWellWrittenScript:
    """Tests for well-written scripts that should have fewer or no key violations."""

    def test_script_with_set_eu_has_no_missing_set_violations(self):
        """A script with 'set -eu' should not have missing-set-e or missing-set-u findings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sh_file = Path(tmpdir) / "good_script.sh"
            sh_file.write_text(
                '#!/bin/bash\n'
                'set -eu\n'
                '\n'
                'main() {\n'
                '    local result\n'
                '    result=$(echo "hello")\n'
                '    echo "$result"\n'
                '}\n'
                '\n'
                'main "$@"\n'
            )

            analyzer = ShellAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            rule_ids = [f.rule_id for f in report.findings]
            assert "shell.missing-set-e" not in rule_ids
            assert "shell.missing-set-u" not in rule_ids

    def test_well_written_script_has_no_security_findings(self):
        """A well-written script should produce no security-category findings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sh_file = Path(tmpdir) / "secure_script.sh"
            sh_file.write_text(
                '#!/bin/bash\n'
                'set -eu\n'
                'DEST_DIR="/tmp/safe_dir"\n'
                'curl https://example.com/data -o output.json\n'
                'echo "Done"\n'
            )

            analyzer = ShellAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            security_findings = [
                f for f in report.findings
                if f.category == ShellRuleCategory.SECURITY.value
            ]
            assert security_findings == []


class TestShellAnalyzerEmptyFile:
    """Tests for empty shell files."""

    def test_empty_sh_file_produces_no_rule_findings(self):
        """An empty .sh file should produce findings only for the set-e and set-u rules."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sh_file = Path(tmpdir) / "empty.sh"
            sh_file.write_text("")

            config = ShellAnalysisConfig(
                disabled_rules=["shell.missing-set-e", "shell.missing-set-u"]
            )
            analyzer = ShellAnalyzer(config)
            report = analyzer.analyze(scan_path=tmpdir)

            assert report.total_findings == 0

    def test_empty_directory_produces_no_files_analyzed(self):
        """An empty directory should produce a report with zero files analyzed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            analyzer = ShellAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            assert report.files_analyzed == 0
            assert report.total_findings == 0


class TestShellAnalyzerFileDiscovery:
    """Tests for file discovery logic in ShellAnalyzer."""

    def test_sh_extension_files_are_analyzed(self):
        """Files with .sh extension should be picked up by the analyzer."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sh_file = Path(tmpdir) / "script.sh"
            sh_file.write_text('#!/bin/bash\nset -eu\necho "hello"\n')

            analyzer = ShellAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            assert report.files_analyzed >= 1

    def test_bash_extension_files_are_analyzed(self):
        """Files with .bash extension should be picked up by the analyzer."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bash_file = Path(tmpdir) / "script.bash"
            bash_file.write_text('#!/bin/bash\nset -eu\necho "hello"\n')

            analyzer = ShellAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            assert report.files_analyzed >= 1

    def test_shebang_file_without_extension_is_analyzed_when_enabled(self):
        """A file with a shell shebang but no .sh extension should be analyzed when also_check_shebangs=True."""
        with tempfile.TemporaryDirectory() as tmpdir:
            shebang_file = Path(tmpdir) / "runscript"
            shebang_file.write_text('#!/bin/bash\nset -eu\necho "hello"\n')

            config = ShellAnalysisConfig(also_check_shebangs=True)
            analyzer = ShellAnalyzer(config)
            report = analyzer.analyze(scan_path=tmpdir)

            assert report.files_analyzed >= 1

    def test_py_file_not_analyzed(self):
        """A .py file should not be analyzed by the shell analyzer."""
        with tempfile.TemporaryDirectory() as tmpdir:
            py_file = Path(tmpdir) / "script.py"
            py_file.write_text('eval("dangerous")\n')

            config = ShellAnalysisConfig(also_check_shebangs=False)
            analyzer = ShellAnalyzer(config)
            report = analyzer.analyze(scan_path=tmpdir)

            assert report.files_analyzed == 0

    def test_report_has_scan_path(self):
        """The report should record the scan path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            analyzer = ShellAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            assert report.scan_path != ""

    def test_report_total_findings_matches_findings_list(self):
        """total_findings should equal the length of the findings list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sh_file = Path(tmpdir) / "mixed.sh"
            sh_file.write_text(
                '#!/bin/bash\n'
                'eval $user_input\n'
                'curl -k https://example.com\n'
            )

            analyzer = ShellAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            assert report.total_findings == len(report.findings)
