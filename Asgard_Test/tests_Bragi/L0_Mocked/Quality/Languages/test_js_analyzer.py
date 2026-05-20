"""
Tests for Heimdall JavaScript Analyzer Service

Unit tests for regex-based static analysis of JavaScript and JSX source files.
Tests write real JS code to temporary files and run the analyzer against them.
"""

import tempfile
from pathlib import Path

import pytest

from Asgard.Bragi.Quality.languages.javascript.models.js_models import (
    JSAnalysisConfig,
    JSRuleCategory,
    JSSeverity,
)
from Asgard.Bragi.Quality.languages.javascript.services.js_analyzer import JSAnalyzer


class TestJSAnalyzerInit:
    """Tests for JSAnalyzer initialisation."""

    def test_init_with_default_config(self):
        """Test that analyzer initialises successfully with default configuration."""
        analyzer = JSAnalyzer()
        assert analyzer._config is not None
        assert analyzer._config.language == "javascript"

    def test_init_with_custom_config(self):
        """Test that analyzer initialises with a provided configuration."""
        config = JSAnalysisConfig(language="javascript", max_file_lines=100)
        analyzer = JSAnalyzer(config)
        assert analyzer._config.max_file_lines == 100


class TestJSAnalyzerNoEval:
    """Tests for the js.no-eval rule."""

    def test_eval_usage_triggers_no_eval(self):
        """Direct eval() call should trigger the js.no-eval rule."""
        with tempfile.TemporaryDirectory() as tmpdir:
            js_file = Path(tmpdir) / "eval_test.js"
            js_file.write_text('const result = eval("1 + 2");\n')

            analyzer = JSAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            rule_ids = [f.rule_id for f in report.findings]
            assert "js.no-eval" in rule_ids

    def test_eval_finding_has_error_severity(self):
        """The js.no-eval finding must be reported as ERROR severity."""
        with tempfile.TemporaryDirectory() as tmpdir:
            js_file = Path(tmpdir) / "eval_test.js"
            js_file.write_text('eval("dangerous_code");\n')

            analyzer = JSAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            eval_findings = [f for f in report.findings if f.rule_id == "js.no-eval"]
            assert len(eval_findings) >= 1
            assert eval_findings[0].severity == JSSeverity.ERROR.value

    def test_eval_finding_has_security_category(self):
        """The js.no-eval finding must be classified under SECURITY category."""
        with tempfile.TemporaryDirectory() as tmpdir:
            js_file = Path(tmpdir) / "eval_test.js"
            js_file.write_text('eval("code");\n')

            analyzer = JSAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            eval_findings = [f for f in report.findings if f.rule_id == "js.no-eval"]
            assert len(eval_findings) >= 1
            assert eval_findings[0].category == JSRuleCategory.SECURITY.value

    def test_eval_with_space_before_paren_triggers_rule(self):
        """eval followed by whitespace before the opening paren should still trigger."""
        with tempfile.TemporaryDirectory() as tmpdir:
            js_file = Path(tmpdir) / "eval_space.js"
            js_file.write_text('eval  ("code");\n')

            analyzer = JSAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            rule_ids = [f.rule_id for f in report.findings]
            assert "js.no-eval" in rule_ids

    def test_no_eval_rule_disabled_suppresses_findings(self):
        """Disabling js.no-eval should suppress any eval findings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            js_file = Path(tmpdir) / "eval_disabled.js"
            js_file.write_text('eval("code");\n')

            config = JSAnalysisConfig(disabled_rules=["js.no-eval"])
            analyzer = JSAnalyzer(config)
            report = analyzer.analyze(scan_path=tmpdir)

            rule_ids = [f.rule_id for f in report.findings]
            assert "js.no-eval" not in rule_ids


class TestJSAnalyzerNoDebugger:
    """Tests for the js.no-debugger rule."""

    def test_debugger_statement_triggers_no_debugger(self):
        """A debugger; statement should trigger the js.no-debugger rule."""
        with tempfile.TemporaryDirectory() as tmpdir:
            js_file = Path(tmpdir) / "debugger_test.js"
            js_file.write_text("function doSomething() {\n    debugger;\n    return 1;\n}\n")

            analyzer = JSAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            rule_ids = [f.rule_id for f in report.findings]
            assert "js.no-debugger" in rule_ids

    def test_debugger_finding_has_warning_severity(self):
        """The js.no-debugger finding must be reported as WARNING severity."""
        with tempfile.TemporaryDirectory() as tmpdir:
            js_file = Path(tmpdir) / "debugger_test.js"
            js_file.write_text("debugger;\n")

            analyzer = JSAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            dbg_findings = [f for f in report.findings if f.rule_id == "js.no-debugger"]
            assert len(dbg_findings) >= 1
            assert dbg_findings[0].severity == JSSeverity.WARNING.value

    def test_debugger_finding_has_correct_line_number(self):
        """The no-debugger finding must point to the correct line number."""
        with tempfile.TemporaryDirectory() as tmpdir:
            js_file = Path(tmpdir) / "debug_line.js"
            js_file.write_text("const x = 1;\nconst y = 2;\ndebugger;\n")

            analyzer = JSAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            dbg_findings = [f for f in report.findings if f.rule_id == "js.no-debugger"]
            assert len(dbg_findings) >= 1
            assert dbg_findings[0].line_number == 3

    def test_no_debugger_rule_disabled_suppresses_findings(self):
        """Disabling js.no-debugger should suppress any debugger findings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            js_file = Path(tmpdir) / "debugger_disabled.js"
            js_file.write_text("debugger;\n")

            config = JSAnalysisConfig(disabled_rules=["js.no-debugger"])
            analyzer = JSAnalyzer(config)
            report = analyzer.analyze(scan_path=tmpdir)

            rule_ids = [f.rule_id for f in report.findings]
            assert "js.no-debugger" not in rule_ids


class TestJSAnalyzerNoVar:
    """Tests for the js.no-var rule."""

    def test_var_declaration_triggers_no_var(self):
        """A var declaration should trigger the js.no-var rule."""
        with tempfile.TemporaryDirectory() as tmpdir:
            js_file = Path(tmpdir) / "var_test.js"
            js_file.write_text("var x = 1;\n")

            analyzer = JSAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            rule_ids = [f.rule_id for f in report.findings]
            assert "js.no-var" in rule_ids

    def test_let_declaration_does_not_trigger_no_var(self):
        """A let declaration should not trigger the js.no-var rule."""
        with tempfile.TemporaryDirectory() as tmpdir:
            js_file = Path(tmpdir) / "let_test.js"
            js_file.write_text("let x = 1;\n")

            analyzer = JSAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            rule_ids = [f.rule_id for f in report.findings]
            assert "js.no-var" not in rule_ids

    def test_const_declaration_does_not_trigger_no_var(self):
        """A const declaration should not trigger the js.no-var rule."""
        with tempfile.TemporaryDirectory() as tmpdir:
            js_file = Path(tmpdir) / "const_test.js"
            js_file.write_text("const x = 1;\n")

            analyzer = JSAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            rule_ids = [f.rule_id for f in report.findings]
            assert "js.no-var" not in rule_ids

    def test_no_var_finding_has_warning_severity(self):
        """The js.no-var finding must be reported as WARNING severity."""
        with tempfile.TemporaryDirectory() as tmpdir:
            js_file = Path(tmpdir) / "var_severity.js"
            js_file.write_text("var count = 0;\n")

            analyzer = JSAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            var_findings = [f for f in report.findings if f.rule_id == "js.no-var"]
            assert len(var_findings) >= 1
            assert var_findings[0].severity == JSSeverity.WARNING.value

    def test_no_var_finding_has_code_smell_category(self):
        """The js.no-var finding must be classified as CODE_SMELL."""
        with tempfile.TemporaryDirectory() as tmpdir:
            js_file = Path(tmpdir) / "var_category.js"
            js_file.write_text("var total = 0;\n")

            analyzer = JSAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            var_findings = [f for f in report.findings if f.rule_id == "js.no-var"]
            assert len(var_findings) >= 1
            assert var_findings[0].category == JSRuleCategory.CODE_SMELL.value


class TestJSAnalyzerNoConsole:
    """Tests for the js.no-console rule."""

    def test_console_log_triggers_no_console(self):
        """console.log() call should trigger the js.no-console rule."""
        with tempfile.TemporaryDirectory() as tmpdir:
            js_file = Path(tmpdir) / "console_log.js"
            js_file.write_text('console.log("debug message");\n')

            analyzer = JSAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            rule_ids = [f.rule_id for f in report.findings]
            assert "js.no-console" in rule_ids

    def test_console_warn_triggers_no_console(self):
        """console.warn() call should trigger the js.no-console rule."""
        with tempfile.TemporaryDirectory() as tmpdir:
            js_file = Path(tmpdir) / "console_warn.js"
            js_file.write_text('console.warn("warning message");\n')

            analyzer = JSAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            rule_ids = [f.rule_id for f in report.findings]
            assert "js.no-console" in rule_ids

    def test_console_error_triggers_no_console(self):
        """console.error() call should trigger the js.no-console rule."""
        with tempfile.TemporaryDirectory() as tmpdir:
            js_file = Path(tmpdir) / "console_error.js"
            js_file.write_text('console.error("error occurred");\n')

            analyzer = JSAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            rule_ids = [f.rule_id for f in report.findings]
            assert "js.no-console" in rule_ids

    def test_console_debug_triggers_no_console(self):
        """console.debug() call should trigger the js.no-console rule."""
        with tempfile.TemporaryDirectory() as tmpdir:
            js_file = Path(tmpdir) / "console_debug.js"
            js_file.write_text('console.debug("trace data");\n')

            analyzer = JSAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            rule_ids = [f.rule_id for f in report.findings]
            assert "js.no-console" in rule_ids

    def test_console_finding_has_info_severity(self):
        """The js.no-console finding must be reported as INFO severity."""
        with tempfile.TemporaryDirectory() as tmpdir:
            js_file = Path(tmpdir) / "console_severity.js"
            js_file.write_text('console.log("test");\n')

            analyzer = JSAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            console_findings = [f for f in report.findings if f.rule_id == "js.no-console"]
            assert len(console_findings) >= 1
            assert console_findings[0].severity == JSSeverity.INFO.value


class TestJSAnalyzerEqeqeq:
    """Tests for the js.eqeqeq rule (loose equality)."""

    def test_loose_equality_triggers_eqeqeq(self):
        """Use of == should trigger the js.eqeqeq rule."""
        with tempfile.TemporaryDirectory() as tmpdir:
            js_file = Path(tmpdir) / "loose_eq.js"
            js_file.write_text("if (x == y) { return true; }\n")

            analyzer = JSAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            rule_ids = [f.rule_id for f in report.findings]
            assert "js.eqeqeq" in rule_ids

    def test_strict_equality_does_not_trigger_eqeqeq(self):
        """Use of === should NOT trigger the js.eqeqeq rule."""
        with tempfile.TemporaryDirectory() as tmpdir:
            js_file = Path(tmpdir) / "strict_eq.js"
            js_file.write_text("if (x === y) { return true; }\n")

            analyzer = JSAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            rule_ids = [f.rule_id for f in report.findings]
            assert "js.eqeqeq" not in rule_ids

    def test_loose_inequality_triggers_eqeqeq(self):
        """Use of != should trigger the js.eqeqeq rule."""
        with tempfile.TemporaryDirectory() as tmpdir:
            js_file = Path(tmpdir) / "loose_neq.js"
            js_file.write_text("if (a != b) { return false; }\n")

            analyzer = JSAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            rule_ids = [f.rule_id for f in report.findings]
            assert "js.eqeqeq" in rule_ids

    def test_eqeqeq_finding_has_warning_severity(self):
        """The js.eqeqeq finding must be reported as WARNING severity."""
        with tempfile.TemporaryDirectory() as tmpdir:
            js_file = Path(tmpdir) / "eq_severity.js"
            js_file.write_text("const result = (x == null);\n")

            analyzer = JSAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            eq_findings = [f for f in report.findings if f.rule_id == "js.eqeqeq"]
            assert len(eq_findings) >= 1
            assert eq_findings[0].severity == JSSeverity.WARNING.value


class TestJSAnalyzerCleanFile:
    """Tests for clean JavaScript files that produce no findings."""

    def test_clean_js_file_no_findings(self):
        """A well-written JS file should produce no rule violations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            js_file = Path(tmpdir) / "clean.js"
            js_file.write_text(
                "function add(a, b) {\n"
                "    return a + b;\n"
                "}\n"
                "\n"
                "const result = add(1, 2);\n"
            )

            analyzer = JSAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            violation_rule_ids = [
                f.rule_id for f in report.findings
                if f.rule_id in (
                    "js.no-eval", "js.no-debugger", "js.no-var",
                    "js.no-console", "js.eqeqeq"
                )
            ]
            assert violation_rule_ids == []

    def test_empty_js_file_produces_empty_report(self):
        """An empty JS file should produce no findings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            js_file = Path(tmpdir) / "empty.js"
            js_file.write_text("")

            analyzer = JSAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            assert report.total_findings == 0
            assert report.findings == []

    def test_empty_directory_produces_empty_report(self):
        """An empty directory should produce a report with zero files analyzed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            analyzer = JSAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            assert report.files_analyzed == 0
            assert report.total_findings == 0


class TestJSAnalyzerFileDiscovery:
    """Tests for file discovery logic in JSAnalyzer."""

    def test_non_js_extension_not_analyzed(self):
        """A .py file should not be analyzed by the JS analyzer."""
        with tempfile.TemporaryDirectory() as tmpdir:
            py_file = Path(tmpdir) / "not_js.py"
            py_file.write_text('eval("dangerous")\n')

            analyzer = JSAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            assert report.files_analyzed == 0
            assert report.total_findings == 0

    def test_only_js_files_are_analyzed(self):
        """Only .js and .jsx files should be analyzed, not other extensions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            js_file = Path(tmpdir) / "script.js"
            ts_file = Path(tmpdir) / "script.ts"
            txt_file = Path(tmpdir) / "notes.txt"

            js_file.write_text("const x = 1;\n")
            ts_file.write_text("const y: number = 1;\n")
            txt_file.write_text("var z = 1;\n")

            analyzer = JSAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            assert report.files_analyzed == 1

    def test_jsx_files_are_analyzed(self):
        """Files with .jsx extension should be included in analysis."""
        with tempfile.TemporaryDirectory() as tmpdir:
            jsx_file = Path(tmpdir) / "component.jsx"
            jsx_file.write_text("var count = 0;\n")

            analyzer = JSAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            assert report.files_analyzed == 1
            rule_ids = [f.rule_id for f in report.findings]
            assert "js.no-var" in rule_ids

    def test_multiple_js_files_all_analyzed(self):
        """Multiple JS files in a directory should all be analyzed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "a.js").write_text("const a = 1;\n")
            (Path(tmpdir) / "b.js").write_text("const b = 2;\n")
            (Path(tmpdir) / "c.js").write_text("const c = 3;\n")

            analyzer = JSAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            assert report.files_analyzed == 3

    def test_report_language_is_javascript(self):
        """The report language field should be 'javascript'."""
        with tempfile.TemporaryDirectory() as tmpdir:
            js_file = Path(tmpdir) / "test.js"
            js_file.write_text("const x = 1;\n")

            analyzer = JSAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            assert report.language == "javascript"


class TestJSAnalyzerReportCounters:
    """Tests for report summary counter accuracy."""

    def test_error_count_incremented_for_eval(self):
        """The error_count in the report should increment for js.no-eval (ERROR severity)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            js_file = Path(tmpdir) / "eval_count.js"
            js_file.write_text('eval("a");\neval("b");\n')

            analyzer = JSAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            assert report.error_count >= 2

    def test_warning_count_incremented_for_var(self):
        """The warning_count should increment for js.no-var (WARNING severity)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            js_file = Path(tmpdir) / "var_count.js"
            js_file.write_text("var x = 1;\nvar y = 2;\n")

            analyzer = JSAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            assert report.warning_count >= 2

    def test_total_findings_matches_findings_list_length(self):
        """total_findings should equal the length of the findings list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            js_file = Path(tmpdir) / "mixed.js"
            js_file.write_text(
                'eval("x");\n'
                "var y = 1;\n"
                "debugger;\n"
            )

            analyzer = JSAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            assert report.total_findings == len(report.findings)

    def test_has_findings_false_for_clean_file(self):
        """has_findings should return False when no rules are violated."""
        with tempfile.TemporaryDirectory() as tmpdir:
            js_file = Path(tmpdir) / "clean.js"
            js_file.write_text("function greet(name) {\n    return 'Hello ' + name;\n}\n")

            config = JSAnalysisConfig(
                disabled_rules=[
                    "js.no-trailing-spaces",
                    "js.max-line-length",
                    "js.max-file-lines",
                    "js.complexity",
                    "js.no-empty-block",
                ]
            )
            analyzer = JSAnalyzer(config)
            report = analyzer.analyze(scan_path=tmpdir)

            assert report.has_findings is False

    def test_has_findings_true_when_violations_present(self):
        """has_findings should return True when at least one rule is violated."""
        with tempfile.TemporaryDirectory() as tmpdir:
            js_file = Path(tmpdir) / "violation.js"
            js_file.write_text("debugger;\n")

            analyzer = JSAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            assert report.has_findings is True
