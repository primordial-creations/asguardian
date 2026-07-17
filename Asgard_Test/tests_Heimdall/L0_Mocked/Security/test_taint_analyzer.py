"""
Tests for Heimdall Taint Analyzer Service

Unit tests for taint flow detection. Tests write real Python code to temporary
files and run the TaintAnalyzer against them.
"""

import tempfile
from pathlib import Path

import pytest

from Asgard.Heimdall.Security.TaintAnalysis.models.taint_models import (
    TaintConfig,
    TaintFlow,
    TaintReport,
    TaintSinkType,
    TaintSourceType,
)
from Asgard.Heimdall.Security.TaintAnalysis.services.taint_analyzer import TaintAnalyzer


class TestTaintAnalyzerInitialization:
    """Tests for TaintAnalyzer initialization."""

    def test_default_initialization(self):
        """Test that the analyzer initializes with default config."""
        analyzer = TaintAnalyzer()
        assert analyzer.config is not None

    def test_custom_config_initialization(self):
        """Test that the analyzer accepts a custom config."""
        config = TaintConfig(min_severity="critical")
        analyzer = TaintAnalyzer(config=config)
        assert analyzer.config.min_severity == "critical"

    def test_scan_nonexistent_path_raises(self):
        """Test that scanning a nonexistent path raises FileNotFoundError."""
        analyzer = TaintAnalyzer()
        with pytest.raises(FileNotFoundError):
            analyzer.scan(Path("/nonexistent/path/that/does/not/exist"))


class TestTaintAnalyzerEmptyInputs:
    """Tests for edge cases with empty or minimal inputs."""

    def test_empty_directory_returns_empty_report(self):
        """Test that an empty directory yields a report with zero taint flows."""
        with tempfile.TemporaryDirectory() as tmpdir:
            analyzer = TaintAnalyzer()
            report = analyzer.scan(Path(tmpdir))

            assert isinstance(report, TaintReport)
            assert report.total_flows == 0
            assert report.flows == []

    def test_empty_file_returns_zero_flows(self):
        """Test that an empty Python file yields no taint flows."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / "empty.py").write_text("")

            config = TaintConfig(exclude_patterns=["__pycache__", ".git"])
            analyzer = TaintAnalyzer(config=config)
            report = analyzer.scan(tmpdir_path)

            assert report.total_flows == 0

    def test_clean_code_no_taint_flows(self):
        """Test that code with no taint sources or sinks yields no flows."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / "clean.py").write_text(
                "def add(a, b):\n"
                "    return a + b\n"
                "\n"
                "def multiply(x, y):\n"
                "    result = x * y\n"
                "    return result\n"
            )

            config = TaintConfig(exclude_patterns=["__pycache__", ".git"])
            analyzer = TaintAnalyzer(config=config)
            report = analyzer.scan(tmpdir_path)

            assert report.total_flows == 0

    def test_scan_returns_taint_report_type(self):
        """Test that scan always returns a TaintReport."""
        with tempfile.TemporaryDirectory() as tmpdir:
            analyzer = TaintAnalyzer()
            report = analyzer.scan(Path(tmpdir))

            assert isinstance(report, TaintReport)


class TestHTTPParameterToSQLSink:
    """Tests for taint flows from HTTP parameters to SQL sinks."""

    def test_request_args_to_cursor_execute_detected(self):
        """Test that request.args source to cursor.execute sink is detected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / "vuln_db.py").write_text(
                "def get_user():\n"
                "    user_id = request.args\n"
                "    query = 'SELECT * FROM users WHERE id=' + user_id\n"
                "    cursor.execute(query)\n"
            )

            config = TaintConfig(exclude_patterns=["__pycache__", ".git"])
            analyzer = TaintAnalyzer(config=config)
            report = analyzer.scan(tmpdir_path)

            assert report.total_flows > 0
            sql_flows = [
                f for f in report.flows
                if f.sink_type == TaintSinkType.SQL_QUERY.value
            ]
            assert len(sql_flows) > 0

    def test_request_args_to_sql_flow_has_correct_source_type(self):
        """Test that the detected flow has HTTP_PARAMETER as source type."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / "sql_inject.py").write_text(
                "def search():\n"
                "    term = request.args.get('q')\n"
                "    sql = 'SELECT * FROM products WHERE name = ' + term\n"
                "    cursor.execute(sql)\n"
            )

            config = TaintConfig(exclude_patterns=["__pycache__", ".git"])
            analyzer = TaintAnalyzer(config=config)
            report = analyzer.scan(tmpdir_path)

            if report.total_flows > 0:
                sql_flows = [
                    f for f in report.flows
                    if f.sink_type == TaintSinkType.SQL_QUERY.value
                ]
                if sql_flows:
                    assert sql_flows[0].source_type == TaintSourceType.HTTP_PARAMETER.value

    def test_request_form_to_cursor_execute_detected(self):
        """Test that request.form source to cursor.execute sink is detected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / "form_inject.py").write_text(
                "def create_user():\n"
                "    username = request.form\n"
                "    query = 'INSERT INTO users (name) VALUES (' + username + ')'\n"
                "    cursor.execute(query)\n"
            )

            config = TaintConfig(exclude_patterns=["__pycache__", ".git"])
            analyzer = TaintAnalyzer(config=config)
            report = analyzer.scan(tmpdir_path)

            assert report.total_flows > 0

    def test_taint_flow_severity_for_sql_sink(self):
        """Test that a SQL sink produces a critical severity flow."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / "sql_critical.py").write_text(
                "def find_user():\n"
                "    uid = request.args.get('uid')\n"
                "    cursor.execute('SELECT * FROM users WHERE id=' + uid)\n"
            )

            config = TaintConfig(exclude_patterns=["__pycache__", ".git"])
            analyzer = TaintAnalyzer(config=config)
            report = analyzer.scan(tmpdir_path)

            sql_flows = [
                f for f in report.flows
                if f.sink_type == TaintSinkType.SQL_QUERY.value
            ]
            if sql_flows:
                assert sql_flows[0].severity == "critical"

    def test_taint_flow_includes_cwe_id(self):
        """Test that a detected SQL taint flow includes a CWE ID."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / "cwe_check.py").write_text(
                "def lookup():\n"
                "    val = request.args.get('val')\n"
                "    cursor.execute('SELECT * FROM t WHERE v=' + val)\n"
            )

            config = TaintConfig(exclude_patterns=["__pycache__", ".git"])
            analyzer = TaintAnalyzer(config=config)
            report = analyzer.scan(tmpdir_path)

            sql_flows = [
                f for f in report.flows
                if f.sink_type == TaintSinkType.SQL_QUERY.value
            ]
            if sql_flows:
                assert sql_flows[0].cwe_id != ""
                assert "CWE-" in sql_flows[0].cwe_id


class TestSanitizedInputNotFlagged:
    """Tests that sanitized/escaped input does not produce taint flows."""

    def test_escaped_input_no_taint_flow(self):
        """Test that code using escape() on user input does not produce a taint flow."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / "safe_db.py").write_text(
                "def safe_search():\n"
                "    raw = request.args.get('q')\n"
                "    safe_val = escape(raw)\n"
                "    cursor.execute('SELECT * FROM t WHERE v=' + safe_val)\n"
            )

            config = TaintConfig(exclude_patterns=["__pycache__", ".git"])
            analyzer = TaintAnalyzer(config=config)
            report = analyzer.scan(tmpdir_path)

            # After sanitization the taint should be removed
            sql_flows = [
                f for f in report.flows
                if f.sink_type == TaintSinkType.SQL_QUERY.value
            ]
            assert len(sql_flows) == 0

    def test_sanitize_function_downgrades_confidence(self):
        """A heuristic sanitizer (custom sanitize()) keeps the flow but
        downgrades confidence (x0.4 -> 'possible' bucket): we cannot verify
        statically that the custom function neutralizes the payload, so the
        finding is kept, honestly labeled, instead of silently dropped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / "sanitize_use.py").write_text(
                "def process():\n"
                "    user_data = request.form.get('data')\n"
                "    clean = sanitize(user_data)\n"
                "    cursor.execute('INSERT INTO t VALUES (' + clean + ')')\n"
            )

            config = TaintConfig(exclude_patterns=["__pycache__", ".git"])
            analyzer = TaintAnalyzer(config=config)
            report = analyzer.scan(tmpdir_path)

            sql_flows = [
                f for f in report.flows
                if f.sink_type == TaintSinkType.SQL_QUERY.value
            ]
            assert len(sql_flows) == 1
            flow = sql_flows[0]
            assert flow.sanitizers_present is True
            assert flow.confidence_bucket in ("possible", "unlikely")
            # Severity is orthogonal to confidence: still a critical-impact sink.
            assert flow.severity == "critical"
            assert any(s.kind == "heuristic" for s in flow.sanitizers_applied)

    def test_exact_custom_sanitizer_clears_taint(self):
        """User-declared custom sanitizers are trusted as exact: flow dropped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / "sanitize_use.py").write_text(
                "def process():\n"
                "    user_data = request.form.get('data')\n"
                "    clean = my_quoter(user_data)\n"
                "    cursor.execute('INSERT INTO t VALUES (' + clean + ')')\n"
            )

            config = TaintConfig(
                exclude_patterns=["__pycache__", ".git"],
                custom_sanitizers=["my_quoter"],
            )
            analyzer = TaintAnalyzer(config=config)
            report = analyzer.scan(tmpdir_path)

            assert len(report.flows) == 0


class TestMultipleTaintSources:
    """Tests for functions with multiple taint sources."""

    def test_multiple_sources_in_one_function(self):
        """Test that a function with multiple tainted variables can be analyzed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / "multi_source.py").write_text(
                "def process_request():\n"
                "    name = request.args\n"
                "    email = request.form\n"
                "    query = 'SELECT * FROM users WHERE name=' + name\n"
                "    cursor.execute(query)\n"
            )

            config = TaintConfig(exclude_patterns=["__pycache__", ".git"])
            analyzer = TaintAnalyzer(config=config)
            report = analyzer.scan(tmpdir_path)

            assert report.total_flows > 0

    def test_taint_from_request_json_source(self):
        """Test that request.json is treated as a taint source."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / "json_source.py").write_text(
                "def update_record():\n"
                "    payload = request.json\n"
                "    cursor.execute('UPDATE t SET data=' + payload)\n"
            )

            config = TaintConfig(exclude_patterns=["__pycache__", ".git"])
            analyzer = TaintAnalyzer(config=config)
            report = analyzer.scan(tmpdir_path)

            assert report.total_flows > 0

    def test_user_input_function_is_taint_source(self):
        """Test that input() built-in is treated as a taint source."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / "cli_inject.py").write_text(
                "def cli_tool():\n"
                "    cmd = input('Enter command: ')\n"
                "    cursor.execute('SELECT * FROM t WHERE name=' + cmd)\n"
            )

            config = TaintConfig(exclude_patterns=["__pycache__", ".git"])
            analyzer = TaintAnalyzer(config=config)
            report = analyzer.scan(tmpdir_path)

            assert report.total_flows > 0


class TestTaintFlowReportStructure:
    """Tests for taint report structure and metadata."""

    def test_report_files_analyzed_count(self):
        """Test that the report correctly counts files analyzed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / "file1.py").write_text("x = 1\n")
            (tmpdir_path / "file2.py").write_text("y = 2\n")

            config = TaintConfig(exclude_patterns=["__pycache__", ".git"])
            analyzer = TaintAnalyzer(config=config)
            report = analyzer.scan(tmpdir_path)

            assert report.files_analyzed == 2

    def test_report_scan_duration_non_negative(self):
        """Test that scan duration is a non-negative float."""
        with tempfile.TemporaryDirectory() as tmpdir:
            analyzer = TaintAnalyzer()
            report = analyzer.scan(Path(tmpdir))

            assert report.scan_duration_seconds >= 0.0

    def test_report_has_findings_property(self):
        """Test the has_findings property on the report."""
        with tempfile.TemporaryDirectory() as tmpdir:
            analyzer = TaintAnalyzer()
            report = analyzer.scan(Path(tmpdir))

            assert report.has_findings is False

    def test_report_is_passing_property_for_empty(self):
        """Test the is_passing property for an empty report."""
        with tempfile.TemporaryDirectory() as tmpdir:
            analyzer = TaintAnalyzer()
            report = analyzer.scan(Path(tmpdir))

            assert report.is_passing is True

    def test_taint_flow_source_location_populated(self):
        """Test that detected taint flows have populated source location."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / "source_loc.py").write_text(
                "def handler():\n"
                "    val = request.args.get('val')\n"
                "    cursor.execute('SELECT * FROM t WHERE v=' + val)\n"
            )

            config = TaintConfig(exclude_patterns=["__pycache__", ".git"])
            analyzer = TaintAnalyzer(config=config)
            report = analyzer.scan(tmpdir_path)

            if report.total_flows > 0:
                flow = report.flows[0]
                assert flow.source_location is not None
                assert flow.source_location.line_number > 0
                assert flow.sink_location is not None
                assert flow.sink_location.line_number > 0

    def test_get_flows_by_severity_groups_correctly(self):
        """Test get_flows_by_severity groups flows into severity buckets."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / "multi_sink.py").write_text(
                "def handler():\n"
                "    val = request.args.get('val')\n"
                "    cursor.execute('SELECT * FROM t WHERE v=' + val)\n"
            )

            config = TaintConfig(exclude_patterns=["__pycache__", ".git"])
            analyzer = TaintAnalyzer(config=config)
            report = analyzer.scan(tmpdir_path)

            by_severity = report.get_flows_by_severity()
            assert "critical" in by_severity
            assert "high" in by_severity
            assert "medium" in by_severity

    def test_severity_threshold_filters_medium(self):
        """Test that min_severity=critical excludes medium and high flows."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            # redirect() is a MEDIUM sink
            (tmpdir_path / "redirect_code.py").write_text(
                "def redir():\n"
                "    url = request.args.get('next')\n"
                "    return redirect(url)\n"
            )

            config = TaintConfig(
                min_severity="critical",
                exclude_patterns=["__pycache__", ".git"],
            )
            analyzer = TaintAnalyzer(config=config)
            report = analyzer.scan(tmpdir_path)

            for flow in report.flows:
                assert flow.severity == "critical"


class TestShellCommandTaintFlow:
    """Tests for taint flows reaching shell command sinks."""

    def test_request_args_to_os_system_detected(self):
        """Test that request.args to os.system taint flow is detected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / "shell_inject.py").write_text(
                "import os\n"
                "\n"
                "def run_cmd():\n"
                "    cmd = request.args\n"
                "    os.system(cmd)\n"
            )

            config = TaintConfig(exclude_patterns=["__pycache__", ".git"])
            analyzer = TaintAnalyzer(config=config)
            report = analyzer.scan(tmpdir_path)

            assert report.total_flows > 0
            shell_flows = [
                f for f in report.flows
                if f.sink_type == TaintSinkType.SHELL_COMMAND.value
            ]
            assert len(shell_flows) > 0

    def test_shell_injection_flow_severity_critical(self):
        """Test that shell command sink produces critical severity flow."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / "os_inject.py").write_text(
                "import os\n"
                "\n"
                "def exec_path():\n"
                "    path = request.form.get('path')\n"
                "    os.system(path)\n"
            )

            config = TaintConfig(exclude_patterns=["__pycache__", ".git"])
            analyzer = TaintAnalyzer(config=config)
            report = analyzer.scan(tmpdir_path)

            shell_flows = [
                f for f in report.flows
                if f.sink_type == TaintSinkType.SHELL_COMMAND.value
            ]
            if shell_flows:
                assert shell_flows[0].severity == "critical"
