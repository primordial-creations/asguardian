"""
Tests for Heimdall Go Analyzer Service

Unit tests for regex-based static analysis of Go source files.
Tests write real Go code to temporary files and run the analyzer against them.
"""

import tempfile
from pathlib import Path

import pytest

from Asgard.Heimdall.Quality.languages.go.models.go_models import (
    GoFinding,
    GoRuleCategory,
    GoScanConfig,
    GoSeverity,
)
from Asgard.Heimdall.Quality.languages.go.services.go_analyzer import GoAnalyzer


class TestGoAnalyzerInit:
    def test_init_with_defaults(self):
        analyzer = GoAnalyzer()
        assert analyzer._config is not None

    def test_init_with_custom_config(self):
        config = GoScanConfig(max_file_lines=300)
        analyzer = GoAnalyzer(config)
        assert analyzer._config.max_file_lines == 300


class TestGoErrorNotChecked:
    def test_discarded_error_flagged(self):
        code = "_, = os.Open(filename)\n"
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "main.go").write_text(code)
            report = GoAnalyzer().analyze(scan_path=d)
        assert any(f.rule_id == "go.error-not-checked" for f in report.findings)

    def test_checked_error_not_flagged(self):
        code = "f, err := os.Open(filename)\nif err != nil { return err }\n"
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "main.go").write_text(code)
            report = GoAnalyzer().analyze(scan_path=d)
        assert not any(f.rule_id == "go.error-not-checked" for f in report.findings)


class TestGoPanic:
    def test_panic_flagged(self):
        code = 'panic("something went wrong")\n'
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "handler.go").write_text(code)
            report = GoAnalyzer().analyze(scan_path=d)
        assert any(f.rule_id == "go.no-panic" for f in report.findings)

    def test_finding_is_warning(self):
        code = 'panic("bad state")\n'
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "handler.go").write_text(code)
            report = GoAnalyzer().analyze(scan_path=d)
        panics = [f for f in report.findings if f.rule_id == "go.no-panic"]
        assert panics[0].severity == GoSeverity.WARNING


class TestGoSqlInjection:
    def test_fmt_sprintf_in_query_flagged(self):
        code = 'rows, _ := db.Query(fmt.Sprintf("SELECT * FROM users WHERE id=%s", id))\n'
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "repo.go").write_text(code)
            report = GoAnalyzer().analyze(scan_path=d)
        assert any(f.rule_id == "go.sql-injection" for f in report.findings)

    def test_parameterised_query_not_flagged(self):
        code = 'rows, err := db.Query("SELECT * FROM users WHERE id=?", id)\n'
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "repo.go").write_text(code)
            report = GoAnalyzer().analyze(scan_path=d)
        assert not any(f.rule_id == "go.sql-injection" for f in report.findings)


class TestGoDeferInLoop:
    def test_defer_in_for_loop_flagged(self):
        code = "for _, f := range files {\n    defer f.Close()\n}\n"
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "loop.go").write_text(code)
            report = GoAnalyzer().analyze(scan_path=d)
        assert any(f.rule_id == "go.no-defer-in-loop" for f in report.findings)

    def test_defer_outside_loop_not_flagged(self):
        code = "f, _ := os.Open(name)\ndefer f.Close()\n"
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "ok.go").write_text(code)
            report = GoAnalyzer().analyze(scan_path=d)
        assert not any(f.rule_id == "go.no-defer-in-loop" for f in report.findings)


class TestGoHardcodedCredentials:
    def test_hardcoded_password_flagged(self):
        code = 'password := "hunter2secret"\n'
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "cfg.go").write_text(code)
            report = GoAnalyzer().analyze(scan_path=d)
        assert any(f.rule_id == "go.no-hardcoded-credentials" for f in report.findings)

    def test_env_var_not_flagged(self):
        code = 'password := os.Getenv("DB_PASS")\n'
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "cfg.go").write_text(code)
            report = GoAnalyzer().analyze(scan_path=d)
        assert not any(f.rule_id == "go.no-hardcoded-credentials" for f in report.findings)


class TestGoGlobalMutex:
    def test_global_mutex_flagged(self):
        code = "var mu sync.Mutex\n"
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "state.go").write_text(code)
            report = GoAnalyzer().analyze(scan_path=d)
        assert any(f.rule_id == "go.no-global-mutex" for f in report.findings)


class TestGoContextNotPropagated:
    def test_background_context_flagged(self):
        code = "ctx := context.Background()\n"
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "svc.go").write_text(code)
            report = GoAnalyzer().analyze(scan_path=d)
        assert any(f.rule_id == "go.context-not-propagated" for f in report.findings)


class TestGoAnalyzerReport:
    def test_multiple_findings_counted(self):
        code = (
            'panic("oh no")\n'
            'password := "topsecret123"\n'
            "var lock sync.Mutex\n"
        )
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "bad.go").write_text(code)
            report = GoAnalyzer().analyze(scan_path=d)
        assert report.total_findings >= 3

    def test_disabled_rule_skipped(self):
        config = GoScanConfig(rules={"go.no-panic": False})
        code = 'panic("oops")\n'
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "p.go").write_text(code)
            report = GoAnalyzer(config).analyze(scan_path=d)
        assert not any(f.rule_id == "go.no-panic" for f in report.findings)
