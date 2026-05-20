"""
Tests for Heimdall TypeScript Analyzer Service

Unit tests for regex-based static analysis of TypeScript and TSX source files.
Tests write real TS code to temporary files and run the analyzer against them.
"""

import tempfile
from pathlib import Path

import pytest

from Asgard.Bragi.Quality.languages.javascript.models.js_models import (
    JSAnalysisConfig,
    JSRuleCategory,
    JSSeverity,
)
from Asgard.Bragi.Quality.languages.typescript.services.ts_analyzer import TSAnalyzer


class TestTSAnalyzerInit:
    """Tests for TSAnalyzer initialisation."""

    def test_init_with_default_config(self):
        """Test that analyzer initialises successfully with default configuration."""
        analyzer = TSAnalyzer()
        assert analyzer._config is not None
        assert analyzer._config.language == "typescript"

    def test_init_forces_typescript_language(self):
        """Even if a JS config is passed, the language must be overridden to typescript."""
        config = JSAnalysisConfig(language="javascript")
        analyzer = TSAnalyzer(config)
        assert analyzer._config.language == "typescript"

    def test_init_forces_ts_extensions(self):
        """The analyzer must always target .ts and .tsx extensions."""
        analyzer = TSAnalyzer()
        assert ".ts" in analyzer._config.include_extensions
        assert ".tsx" in analyzer._config.include_extensions

    def test_js_files_are_not_analyzed(self):
        """A .js file should not be picked up by the TypeScript analyzer."""
        with tempfile.TemporaryDirectory() as tmpdir:
            js_file = Path(tmpdir) / "script.js"
            js_file.write_text('eval("code");\n')

            analyzer = TSAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            assert report.files_analyzed == 0


class TestTSAnalyzerJSRulesOnTSFiles:
    """Tests confirming that all JS rules also fire on TypeScript files."""

    def test_eval_triggers_on_ts_file(self):
        """js.no-eval should trigger on a .ts file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ts_file = Path(tmpdir) / "eval_test.ts"
            ts_file.write_text('const result = eval("1 + 2");\n')

            analyzer = TSAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            rule_ids = [f.rule_id for f in report.findings]
            assert "js.no-eval" in rule_ids

    def test_debugger_triggers_on_ts_file(self):
        """js.no-debugger should trigger on a .ts file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ts_file = Path(tmpdir) / "debugger_test.ts"
            ts_file.write_text("function run(): void {\n    debugger;\n}\n")

            analyzer = TSAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            rule_ids = [f.rule_id for f in report.findings]
            assert "js.no-debugger" in rule_ids

    def test_var_triggers_on_ts_file(self):
        """js.no-var should trigger on a .ts file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ts_file = Path(tmpdir) / "var_test.ts"
            ts_file.write_text("var x: number = 1;\n")

            analyzer = TSAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            rule_ids = [f.rule_id for f in report.findings]
            assert "js.no-var" in rule_ids

    def test_console_log_triggers_on_ts_file(self):
        """js.no-console should trigger on a .ts file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ts_file = Path(tmpdir) / "console_test.ts"
            ts_file.write_text('console.log("debug");\n')

            analyzer = TSAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            rule_ids = [f.rule_id for f in report.findings]
            assert "js.no-console" in rule_ids

    def test_loose_equality_triggers_on_ts_file(self):
        """js.eqeqeq should trigger on a .ts file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ts_file = Path(tmpdir) / "eq_test.ts"
            ts_file.write_text("if (x == y) { return true; }\n")

            analyzer = TSAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            rule_ids = [f.rule_id for f in report.findings]
            assert "js.eqeqeq" in rule_ids


class TestTSAnalyzerNoExplicitAny:
    """Tests for the ts.no-explicit-any rule."""

    def test_explicit_any_annotation_triggers_rule(self):
        """A ': any' type annotation should trigger ts.no-explicit-any."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ts_file = Path(tmpdir) / "any_type.ts"
            ts_file.write_text("function process(data: any): void {\n    console.log(data);\n}\n")

            analyzer = TSAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            rule_ids = [f.rule_id for f in report.findings]
            assert "ts.no-explicit-any" in rule_ids

    def test_any_in_variable_annotation_triggers_rule(self):
        """A variable annotated as any should trigger ts.no-explicit-any."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ts_file = Path(tmpdir) / "any_var.ts"
            ts_file.write_text("let value: any = null;\n")

            analyzer = TSAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            rule_ids = [f.rule_id for f in report.findings]
            assert "ts.no-explicit-any" in rule_ids

    def test_specific_type_annotation_does_not_trigger_rule(self):
        """A properly typed annotation should not trigger ts.no-explicit-any."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ts_file = Path(tmpdir) / "typed.ts"
            ts_file.write_text("function process(data: string): void {\n    return;\n}\n")

            config = JSAnalysisConfig(
                language="typescript",
                disabled_rules=[
                    "js.no-console",
                    "js.no-trailing-spaces",
                    "ts.no-implicit-any",
                ],
            )
            analyzer = TSAnalyzer(config)
            report = analyzer.analyze(scan_path=tmpdir)

            rule_ids = [f.rule_id for f in report.findings]
            assert "ts.no-explicit-any" not in rule_ids

    def test_no_explicit_any_finding_has_warning_severity(self):
        """The ts.no-explicit-any finding must be reported as WARNING severity."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ts_file = Path(tmpdir) / "any_severity.ts"
            ts_file.write_text("const x: any = 42;\n")

            analyzer = TSAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            any_findings = [f for f in report.findings if f.rule_id == "ts.no-explicit-any"]
            assert len(any_findings) >= 1
            assert any_findings[0].severity == JSSeverity.WARNING.value

    def test_no_explicit_any_rule_disabled_suppresses_findings(self):
        """Disabling ts.no-explicit-any should suppress findings for that rule."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ts_file = Path(tmpdir) / "any_disabled.ts"
            ts_file.write_text("const x: any = 1;\n")

            config = JSAnalysisConfig(
                language="typescript",
                disabled_rules=["ts.no-explicit-any"],
            )
            analyzer = TSAnalyzer(config)
            report = analyzer.analyze(scan_path=tmpdir)

            rule_ids = [f.rule_id for f in report.findings]
            assert "ts.no-explicit-any" not in rule_ids


class TestTSAnalyzerNoAnyCast:
    """Tests for the ts.no-any-cast rule."""

    def test_as_any_cast_triggers_rule(self):
        """An 'as any' cast expression should trigger ts.no-any-cast."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ts_file = Path(tmpdir) / "any_cast.ts"
            ts_file.write_text("const value = (someObject as any).property;\n")

            analyzer = TSAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            rule_ids = [f.rule_id for f in report.findings]
            assert "ts.no-any-cast" in rule_ids

    def test_as_any_in_function_argument_triggers_rule(self):
        """An 'as any' used as function argument should trigger ts.no-any-cast."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ts_file = Path(tmpdir) / "any_arg.ts"
            ts_file.write_text("process(value as any);\n")

            analyzer = TSAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            rule_ids = [f.rule_id for f in report.findings]
            assert "ts.no-any-cast" in rule_ids

    def test_as_specific_type_does_not_trigger_rule(self):
        """An 'as SpecificType' cast should not trigger ts.no-any-cast."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ts_file = Path(tmpdir) / "as_typed.ts"
            ts_file.write_text("const user = (data as User);\n")

            config = JSAnalysisConfig(
                language="typescript",
                disabled_rules=[
                    "js.no-trailing-spaces",
                    "ts.no-implicit-any",
                ],
            )
            analyzer = TSAnalyzer(config)
            report = analyzer.analyze(scan_path=tmpdir)

            rule_ids = [f.rule_id for f in report.findings]
            assert "ts.no-any-cast" not in rule_ids

    def test_no_any_cast_finding_has_warning_severity(self):
        """The ts.no-any-cast finding must be reported as WARNING severity."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ts_file = Path(tmpdir) / "cast_severity.ts"
            ts_file.write_text("const x = (obj as any).prop;\n")

            analyzer = TSAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            cast_findings = [f for f in report.findings if f.rule_id == "ts.no-any-cast"]
            assert len(cast_findings) >= 1
            assert cast_findings[0].severity == JSSeverity.WARNING.value


class TestTSAnalyzerNoNonNullAssertion:
    """Tests for the ts.no-non-null-assertion rule."""

    def test_non_null_assertion_before_dot_triggers_rule(self):
        """An 'x!.method()' non-null assertion should trigger ts.no-non-null-assertion."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ts_file = Path(tmpdir) / "non_null.ts"
            ts_file.write_text("const name = user!.getName();\n")

            analyzer = TSAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            rule_ids = [f.rule_id for f in report.findings]
            assert "ts.no-non-null-assertion" in rule_ids

    def test_non_null_assertion_before_bracket_triggers_rule(self):
        """An 'x![0]' non-null assertion should trigger ts.no-non-null-assertion."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ts_file = Path(tmpdir) / "non_null_bracket.ts"
            ts_file.write_text("const first = items![0];\n")

            analyzer = TSAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            rule_ids = [f.rule_id for f in report.findings]
            assert "ts.no-non-null-assertion" in rule_ids

    def test_non_null_assertion_finding_has_info_severity(self):
        """The ts.no-non-null-assertion finding must be reported as INFO severity."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ts_file = Path(tmpdir) / "nn_severity.ts"
            ts_file.write_text("const val = obj!.value;\n")

            analyzer = TSAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            nn_findings = [f for f in report.findings if f.rule_id == "ts.no-non-null-assertion"]
            assert len(nn_findings) >= 1
            assert nn_findings[0].severity == JSSeverity.INFO.value


class TestTSAnalyzerPreferInterface:
    """Tests for the ts.prefer-interface rule."""

    def test_type_alias_for_object_shape_triggers_rule(self):
        """A 'type Foo = {...}' type alias should trigger ts.prefer-interface."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ts_file = Path(tmpdir) / "type_alias.ts"
            ts_file.write_text("type UserProfile = {\n    name: string;\n    age: number;\n};\n")

            analyzer = TSAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            rule_ids = [f.rule_id for f in report.findings]
            assert "ts.prefer-interface" in rule_ids

    def test_interface_declaration_does_not_trigger_rule(self):
        """An 'interface Foo {...}' declaration should not trigger ts.prefer-interface."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ts_file = Path(tmpdir) / "interface_decl.ts"
            ts_file.write_text(
                "interface UserProfile {\n    name: string;\n    age: number;\n}\n"
            )

            config = JSAnalysisConfig(
                language="typescript",
                disabled_rules=[
                    "js.no-trailing-spaces",
                    "ts.no-implicit-any",
                ],
            )
            analyzer = TSAnalyzer(config)
            report = analyzer.analyze(scan_path=tmpdir)

            rule_ids = [f.rule_id for f in report.findings]
            assert "ts.prefer-interface" not in rule_ids

    def test_prefer_interface_finding_has_info_severity(self):
        """The ts.prefer-interface finding must be reported as INFO severity."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ts_file = Path(tmpdir) / "prefer_iface.ts"
            ts_file.write_text("type Config = { host: string; port: number; };\n")

            analyzer = TSAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            pi_findings = [f for f in report.findings if f.rule_id == "ts.prefer-interface"]
            assert len(pi_findings) >= 1
            assert pi_findings[0].severity == JSSeverity.INFO.value


class TestTSAnalyzerCleanFile:
    """Tests for clean TypeScript files that should produce no critical findings."""

    def test_clean_ts_file_no_ts_specific_violations(self):
        """A well-typed TS file should produce no TypeScript-specific violations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ts_file = Path(tmpdir) / "clean.ts"
            ts_file.write_text(
                "interface User {\n"
                "    name: string;\n"
                "    age: number;\n"
                "}\n"
                "\n"
                "function greet(user: User): string {\n"
                "    return 'Hello ' + user.name;\n"
                "}\n"
            )

            analyzer = TSAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            ts_specific_rule_ids = [
                f.rule_id for f in report.findings
                if f.rule_id in (
                    "ts.no-explicit-any",
                    "ts.no-any-cast",
                    "ts.no-non-null-assertion",
                    "ts.prefer-interface",
                )
            ]
            assert ts_specific_rule_ids == []

    def test_empty_ts_file_produces_empty_report(self):
        """An empty .ts file should produce no findings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ts_file = Path(tmpdir) / "empty.ts"
            ts_file.write_text("")

            analyzer = TSAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            assert report.total_findings == 0

    def test_report_language_is_typescript(self):
        """The report language field should be 'typescript'."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ts_file = Path(tmpdir) / "test.ts"
            ts_file.write_text("const x: number = 1;\n")

            analyzer = TSAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            assert report.language == "typescript"

    def test_tsx_files_are_analyzed(self):
        """Files with .tsx extension should be included in TypeScript analysis."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tsx_file = Path(tmpdir) / "component.tsx"
            tsx_file.write_text("var count: number = 0;\n")

            analyzer = TSAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            assert report.files_analyzed == 1
            rule_ids = [f.rule_id for f in report.findings]
            assert "js.no-var" in rule_ids


class TestTSSecurityRules:
    """Tests confirming that JS security rules fire on .ts files via delegation."""

    def test_js_no_eval_fires_on_ts_file(self):
        """js.no-eval should fire on a .ts file containing eval()."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ts_file = Path(tmpdir) / "evil.ts"
            ts_file.write_text("const result = eval(userInput);\n")

            analyzer = TSAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            rule_ids = [f.rule_id for f in report.findings]
            assert "js.no-eval" in rule_ids

    def test_js_sql_injection_fires_on_ts_file(self):
        """js.sql-injection should fire on a .ts file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ts_file = Path(tmpdir) / "db.ts"
            ts_file.write_text('db.query("SELECT * FROM users WHERE id=" + userId);\n')

            analyzer = TSAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            rule_ids = [f.rule_id for f in report.findings]
            assert "js.sql-injection" in rule_ids

    def test_js_no_prototype_pollution_fires_on_ts_file(self):
        """js.no-prototype-pollution should fire on a .ts file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ts_file = Path(tmpdir) / "proto.ts"
            ts_file.write_text("obj.__proto__ = malicious;\n")

            analyzer = TSAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            rule_ids = [f.rule_id for f in report.findings]
            assert "js.no-prototype-pollution" in rule_ids


class TestTSSpecificSecurityRules:
    """Tests for the TS-specific security rules."""

    def test_unsafe_any_fires_near_fetch(self):
        """ts.unsafe-any should fire when 'as any' appears near 'fetch'."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ts_file = Path(tmpdir) / "api.ts"
            ts_file.write_text("const data = (await fetch(url) as any).json();\n")

            analyzer = TSAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            rule_ids = [f.rule_id for f in report.findings]
            assert "ts.unsafe-any" in rule_ids

    def test_unsafe_any_fires_near_query(self):
        """ts.unsafe-any should fire when 'as any' appears near 'query'."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ts_file = Path(tmpdir) / "db.ts"
            ts_file.write_text("const result = (db.query(sql) as any).rows;\n")

            analyzer = TSAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            rule_ids = [f.rule_id for f in report.findings]
            assert "ts.unsafe-any" in rule_ids

    def test_unsafe_any_does_not_fire_without_sensitive_context(self):
        """ts.unsafe-any should not fire when 'as any' is not near a sensitive function."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ts_file = Path(tmpdir) / "safe.ts"
            ts_file.write_text("const x = (legacyValue as any).prop;\n")

            config = JSAnalysisConfig(
                language="typescript",
                enabled_rules=["ts.unsafe-any"],
            )
            analyzer = TSAnalyzer(config)
            report = analyzer.analyze(scan_path=tmpdir)

            rule_ids = [f.rule_id for f in report.findings]
            assert "ts.unsafe-any" not in rule_ids

    def test_no_unsafe_assertion_fires_on_req(self):
        """ts.no-unsafe-assertion should fire on 'req.body!' non-null assertion."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ts_file = Path(tmpdir) / "handler.ts"
            ts_file.write_text("const name = req.body!.name;\n")

            analyzer = TSAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            rule_ids = [f.rule_id for f in report.findings]
            assert "ts.no-unsafe-assertion" in rule_ids

    def test_no_unsafe_assertion_fires_on_query(self):
        """ts.no-unsafe-assertion should fire on 'query.id!' non-null assertion."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ts_file = Path(tmpdir) / "ctrl.ts"
            ts_file.write_text("const id = query.id!.toString();\n")

            analyzer = TSAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            rule_ids = [f.rule_id for f in report.findings]
            assert "ts.no-unsafe-assertion" in rule_ids

    def test_no_unsafe_assertion_does_not_fire_on_safe_code(self):
        """ts.no-unsafe-assertion should not fire when '!' is used on local variables."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ts_file = Path(tmpdir) / "safe.ts"
            ts_file.write_text("const val = localVar!.prop;\n")

            config = JSAnalysisConfig(
                language="typescript",
                enabled_rules=["ts.no-unsafe-assertion"],
            )
            analyzer = TSAnalyzer(config)
            report = analyzer.analyze(scan_path=tmpdir)

            rule_ids = [f.rule_id for f in report.findings]
            assert "ts.no-unsafe-assertion" not in rule_ids

    def test_ts_prototype_pollution_fires(self):
        """ts.prototype-pollution should fire on __proto__ assignment in .ts files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ts_file = Path(tmpdir) / "pollute.ts"
            ts_file.write_text("target.__proto__ = source;\n")

            analyzer = TSAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            rule_ids = [f.rule_id for f in report.findings]
            assert "ts.prototype-pollution" in rule_ids

    def test_ts_prototype_pollution_severity_is_error(self):
        """ts.prototype-pollution findings should have ERROR severity."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ts_file = Path(tmpdir) / "pollute.ts"
            ts_file.write_text("obj.__proto__ = evil;\n")

            analyzer = TSAnalyzer()
            report = analyzer.analyze(scan_path=tmpdir)

            findings = [f for f in report.findings if f.rule_id == "ts.prototype-pollution"]
            assert len(findings) >= 1
            assert findings[0].severity == JSSeverity.ERROR.value
